(() => {
  'use strict';

  const OWNER = 'codesphere-u';
  const REPO = 'reeltern';
  const REPO_URL = `https://github.com/${OWNER}/${REPO}`;
  const API_URL = `https://api.github.com/repos/${OWNER}/${REPO}/releases?per_page=20`;

  function esc(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatBytes(bytes) {
    const n = Number(bytes) || 0;
    if (n <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
    return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  function detectPlatform() {
    const hint = (
      (navigator.userAgentData && navigator.userAgentData.platform) ||
      navigator.platform ||
      navigator.userAgent ||
      ''
    ).toLowerCase();
    if (hint.includes('mac')) return 'macos';
    if (hint.includes('win')) return 'windows';
    if (hint.includes('linux') || hint.includes('x11') || hint.includes('ubuntu')) return 'linux';
    return 'macos';
  }

  function platformLabel(key) {
    return { macos: 'macOS', windows: 'Windows', linux: 'Linux', wheel: 'Python Wheel' }[key] || 'Release';
  }

  function classifyAsset(name) {
    const lower = (name || '').toLowerCase();
    if (lower.includes('macos')) return { key: 'macos', label: 'macOS Bundle (.zip)', badge: 'macOS' };
    if (lower.includes('windows')) return { key: 'windows', label: 'Windows Bundle (.zip)', badge: 'Windows' };
    if (lower.includes('linux')) return { key: 'linux', label: 'Linux Bundle (.zip)', badge: 'Linux' };
    if (lower.endsWith('.whl')) return { key: 'wheel', label: 'Python Wheel (.whl)', badge: 'pip / venv' };
    if (lower.endsWith('.tar.gz')) return { key: 'source', label: 'Source Archive (.tar.gz)', badge: 'Source' };
    if (lower.includes('sha256')) return { key: 'checksum', label: 'SHA-256 Checksums', badge: 'Verify' };
    return { key: 'other', label: name, badge: 'Asset' };
  }

  function copyWithFeedback(btn, text) {
    if (!btn) return;
    navigator.clipboard?.writeText(text).then(() => {
      const prev = btn.textContent;
      btn.textContent = 'Copied ✓';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = prev;
        btn.classList.remove('copied');
      }, 1500);
    }).catch(() => {});
  }

  /* ---- Navigation & Scroll Reveals ---- */
  function initChrome() {
    const toggle = document.querySelector('.menu-toggle');
    const nav = document.querySelector('.header-nav');
    if (toggle && nav) {
      toggle.addEventListener('click', () => {
        const open = nav.classList.toggle('open');
        toggle.setAttribute('aria-expanded', String(open));
      });
    }

    const targets = document.querySelectorAll('[data-reveal]');
    if (!targets.length) return;
    if (!('IntersectionObserver' in window)) {
      targets.forEach((el) => el.classList.add('is-visible'));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.01, rootMargin: '120px 0px' }
    );
    targets.forEach((el) => io.observe(el));
  }

  /* ---- Live GitHub Releases + Fallback Engine ---- */
  async function fetchReleasesData() {
    let releases = [];
    let source = 'live';
    try {
      const res = await fetch(API_URL, { headers: { Accept: 'application/vnd.github+json' } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (Array.isArray(json) && json.length) {
        releases = json.filter((r) => !r.draft);
      }
    } catch (_) {
      source = 'cached';
    }

    if (!releases.length) {
      try {
        const fallback = await fetch('./releases.json', { cache: 'no-store' });
        if (fallback.ok) {
          const json = await fallback.json();
          if (Array.isArray(json)) releases = json.filter((r) => !r.draft);
          source = 'cached';
        }
      } catch (_) {}
    }

    return { releases, source };
  }

  function renderInstallSnippet(osTab, ver) {
    const cleanVer = (ver || '0.5.0').replace(/^v/, '');
    if (osTab === 'macos') {
      return [
        `# Extract reeltern-${cleanVer}-macos-python.zip cleanly, then run:`,
        `cd reeltern-${cleanVer}-macos-python`,
        `python3 install.py`,
        `./reeltern.sh compose your-clip.mp4 --style viral_reel --preview --audit`,
        `./reeltern.sh gui`,
      ].join('\n');
    }
    if (osTab === 'windows') {
      return [
        `# Extract reeltern-${cleanVer}-windows-python.zip, then open PowerShell:`,
        `cd reeltern-${cleanVer}-windows-python`,
        `py -3.12 install.py`,
        `.\\reeltern.cmd compose your-clip.mp4 --style viral_reel --preview --audit`,
        `.\\reeltern.cmd gui`,
      ].join('\n');
    }
    if (osTab === 'linux') {
      return [
        `# Extract reeltern-${cleanVer}-linux-python.zip (GUI needs python3-tk):`,
        `cd reeltern-${cleanVer}-linux-python`,
        `python3 install.py`,
        `sh reeltern.sh demo --workspace demo-project`,
        `sh reeltern.sh gui`,
      ].join('\n');
    }
    return [
      `python3 -m venv .venv && source .venv/bin/activate`,
      `python -m pip install "./reeltern-${cleanVer}-py3-none-any.whl[mcp]"`,
      `# Or install directly from source repository:`,
      `python -m pip install "git+${REPO_URL}.git"`,
    ].join('\n');
  }

  async function initReleasesSystem() {
    const userOS = detectPlatform();
    const { releases, source } = await fetchReleasesData();

    const tagEls = document.querySelectorAll('[data-latest-tag]');
    const latest = releases[0] || null;
    if (latest) {
      tagEls.forEach((el) => {
        el.textContent = `${latest.tag_name}${latest.prerelease ? ' preview' : ''}`;
      });
    } else {
      tagEls.forEach((el) => {
        el.textContent = 'Releases';
      });
    }

    // Update Hero Smart Download Button
    const heroBtn = document.getElementById('hero-primary-dl');
    const heroLabel = document.getElementById('hero-dl-label');
    const heroMeta = document.getElementById('hero-dl-meta');
    if (heroBtn && heroLabel && heroMeta) {
      if (latest && Array.isArray(latest.assets) && latest.assets.length) {
        const match =
          latest.assets.find((a) => classifyAsset(a.name).key === userOS) ||
          latest.assets.find((a) => classifyAsset(a.name).key === 'wheel') ||
          latest.assets[0];
        heroBtn.href = match.browser_download_url;
        heroLabel.textContent = `Download for ${platformLabel(userOS)} (${latest.tag_name})`;
        const digestShort = match.digest ? ` · sha256:${match.digest.replace(/^sha256:/, '').slice(0, 12)}…` : '';
        heroMeta.innerHTML = `<strong>${esc(match.name)}</strong> · ${formatBytes(match.size)}${esc(digestShort)} · <span>${source === 'live' ? 'Live GitHub Release' : 'Synced Snapshot'}</span>`;
      } else {
        heroBtn.href = `${REPO_URL}/releases`;
        heroLabel.textContent = 'Download from GitHub Releases';
        heroMeta.innerHTML = `<a href="${REPO_URL}/releases" style="color:var(--mint-hi)">Browse releases on GitHub</a>`;
      }
    }

    // Index Downloads Vault (#downloads)
    const select = document.getElementById('dl-release-select');
    const assetGrid = document.getElementById('dl-asset-grid');
    const statusEl = document.getElementById('dl-release-status');
    const titleEl = document.getElementById('dl-release-title');
    const installPre = document.getElementById('os-install-code');
    const osTabs = document.querySelectorAll('[data-os-tab]');

    let activeOsTab = userOS;
    osTabs.forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.osTab === activeOsTab);
      tab.addEventListener('click', () => {
        activeOsTab = tab.dataset.osTab;
        osTabs.forEach((t) => t.classList.toggle('active', t === tab));
        if (installPre) {
          const selectedTag = select?.value || latest?.tag_name || 'v0.5.0';
          installPre.textContent = renderInstallSnippet(activeOsTab, selectedTag);
        }
      });
    });

    function renderHomeRelease(rel) {
      if (!rel || !assetGrid) return;
      const dt = rel.published_at ? new Date(rel.published_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
      if (statusEl) {
        statusEl.textContent = `${source === 'live' ? 'LIVE GITHUB RELEASE FEED' : 'CACHED RELEASE SNAPSHOT'} · ${rel.prerelease ? 'PREVIEW RELEASE' : 'STABLE RELEASE'}${dt ? ' · ' + dt : ''}`;
      }
      if (titleEl) {
        titleEl.textContent = rel.name || `Reeltern ${rel.tag_name}`;
      }
      if (installPre) {
        installPre.textContent = renderInstallSnippet(activeOsTab, rel.tag_name);
      }

      const sorted = [...(rel.assets || [])].sort((a, b) => {
        const ak = classifyAsset(a.name).key === userOS ? -1 : 0;
        const bk = classifyAsset(b.name).key === userOS ? -1 : 0;
        return ak - bk;
      });

      assetGrid.innerHTML = sorted
        .map((asset) => {
          const info = classifyAsset(asset.name);
          const rec = info.key === userOS;
          const sha = (asset.digest || '').replace(/^sha256:/, '');
          return `
            <div class="asset-card ${rec ? 'is-recommended' : ''}">
              <div>
                <div class="asset-platform">
                  <span>${esc(info.label)}</span>
                  <span class="badge-rec">${rec ? 'Recommended OS' : esc(info.badge)}</span>
                </div>
                <div class="asset-meta" style="margin-top: 0.45rem;">${esc(asset.name)}</div>
                <div class="asset-meta">${formatBytes(asset.size)} · ${asset.download_count ?? 0} downloads</div>
                ${sha ? `<div class="asset-meta" title="${esc(sha)}">sha256: ${esc(sha.slice(0, 16))}…</div>` : ''}
              </div>
              <a class="btn ${rec ? 'btn-primary' : 'btn-secondary'}" style="padding: 0.55rem 0.9rem; font-size: 0.84rem;" href="${esc(asset.browser_download_url)}">
                Download
              </a>
            </div>
          `;
        })
        .join('');
    }

    if (select && releases.length) {
      select.innerHTML = releases
        .map((r, i) => `<option value="${esc(r.tag_name)}">${esc(r.tag_name)}${i === 0 ? ' (Newest)' : ''}${r.prerelease ? ' · preview' : ''}</option>`)
        .join('');
      renderHomeRelease(releases[0]);
      select.addEventListener('change', () => {
        const chosen = releases.find((r) => r.tag_name === select.value) || releases[0];
        renderHomeRelease(chosen);
      });
    } else if (installPre) {
      installPre.textContent = renderInstallSnippet(activeOsTab, '0.5.0');
    }

    // releases.html full feed + browser SHA-256 verifier
    initReleasesPage(releases, source, userOS);
  }

  function renderReleaseNotes(md) {
    const lines = String(md || '').split('\n').slice(0, 18);
    return lines
      .map((line) => {
        const trimmed = line.trim();
        if (!trimmed) return '';
        if (trimmed.startsWith('##')) {
          return `<h4 style="margin: 0.75rem 0 0.25rem; color: var(--mint-hi);">${esc(trimmed.replace(/^#+\s*/, ''))}</h4>`;
        }
        if (trimmed.startsWith('- ')) {
          return `<div style="padding-left: 0.9rem; color: var(--ink-65); font-size: 0.9rem;">• ${esc(trimmed.slice(2))}</div>`;
        }
        return `<p style="margin: 0.25rem 0; color: var(--ink-65); font-size: 0.9rem;">${esc(trimmed)}</p>`;
      })
      .join('');
  }

  function initReleasesPage(releases, source, userOS) {
    const container = document.getElementById('all-releases-container');
    const syncMeta = document.getElementById('rel-sync-meta');
    if (syncMeta) {
      syncMeta.textContent = `${releases.length} release(s) · source: ${source === 'live' ? 'Live GitHub Releases API' : 'Cached JSON snapshot'}`;
    }

    let filter = 'all';
    function drawList() {
      if (!container) return;
      const list = releases.filter((r) => {
        if (filter === 'stable') return !r.prerelease;
        if (filter === 'pre') return r.prerelease;
        return true;
      });
      if (!list.length) {
        container.innerHTML = `<div class="release-hub-card"><p style="margin:0;color:var(--ink-65)">No matching releases published in this filter yet. Check back or switch to All Releases.</p></div>`;
        return;
      }
      container.innerHTML = list
        .map((rel) => {
          const dt = rel.published_at ? new Date(rel.published_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
          const assetsHtml = (rel.assets || [])
            .map((a) => {
              const info = classifyAsset(a.name);
              const rec = info.key === userOS;
              const sha = (a.digest || '').replace(/^sha256:/, '');
              return `
                <div class="asset-card ${rec ? 'is-recommended' : ''}">
                  <div>
                    <div class="asset-platform">
                      <span>${esc(info.label)}</span>
                      <span class="badge-rec">${rec ? 'Your OS' : esc(info.badge)}</span>
                    </div>
                    <div class="asset-meta" style="margin-top:0.35rem;">${esc(a.name)}</div>
                    <div class="asset-meta">${formatBytes(a.size)} · ${a.download_count ?? 0} downloads</div>
                    ${sha ? `<div class="asset-meta">sha256:${esc(sha.slice(0, 18))}…</div>` : ''}
                  </div>
                  <a class="btn ${rec ? 'btn-primary' : 'btn-secondary'}" style="padding:0.5rem 0.85rem;font-size:0.83rem;" href="${esc(a.browser_download_url)}">Download</a>
                </div>
              `;
            })
            .join('');
          return `
            <article class="release-hub-card">
              <div class="release-toolbar">
                <div>
                  <span class="bento-tag">${esc(rel.tag_name)} · ${rel.prerelease ? 'Preview Release' : 'Stable Release'}</span>
                  <h2 style="margin: 0.5rem 0 0; font-size: 1.45rem;">${esc(rel.name || rel.tag_name)}</h2>
                  <div class="mono" style="font-size: 0.78rem; color: var(--ink-45); margin-top: 0.2rem;">Published ${esc(dt)}</div>
                </div>
                <a class="btn btn-ghost" href="${esc(rel.html_url)}" target="_blank" rel="noopener noreferrer">View on GitHub →</a>
              </div>
              <div style="margin-top: 0.9rem;">${renderReleaseNotes(rel.body)}</div>
              <div class="asset-grid">${assetsHtml}</div>
            </article>
          `;
        })
        .join('');
    }

    if (container) {
      drawList();
      document.querySelectorAll('[data-rel-filter]').forEach((btn) => {
        btn.addEventListener('click', () => {
          filter = btn.dataset.relFilter;
          document.querySelectorAll('[data-rel-filter]').forEach((b) => b.classList.toggle('active', b === btn));
          drawList();
        });
      });
    }

    // Browser Web Crypto SHA-256 Verifier
    const dropzone = document.getElementById('sha-dropzone');
    const fileInput = document.getElementById('sha-file-input');
    const resultEl = document.getElementById('sha-result');
    if (dropzone && fileInput && resultEl) {
      async function hashFile(file) {
        if (!file) return;
        if (!window.crypto?.subtle) {
          resultEl.textContent = 'Web Crypto API requires HTTPS or localhost.';
          return;
        }
        resultEl.textContent = `Computing SHA-256 for ${file.name} (${formatBytes(file.size)})…`;
        const buf = await file.arrayBuffer();
        const digestBuf = await crypto.subtle.digest('SHA-256', buf);
        const hex = Array.from(new Uint8Array(digestBuf)).map((b) => b.toString(16).padStart(2, '0')).join('');

        let matchedRel = null;
        let matchedAsset = null;
        for (const r of releases) {
          for (const a of r.assets || []) {
            const official = (a.digest || '').replace(/^sha256:/, '').toLowerCase();
            if (official && official === hex) {
              matchedRel = r.tag_name;
              matchedAsset = a.name;
              break;
            }
          }
          if (matchedAsset) break;
        }

        if (matchedAsset) {
          resultEl.innerHTML = `<span style="color: var(--pass);">MATCH CONFIRMED ✓</span> — ${esc(file.name)} matches <strong>${esc(matchedAsset)}</strong> (${esc(matchedRel)})<br><span style="opacity:0.8">sha256: ${esc(hex)}</span>`;
        } else {
          resultEl.innerHTML = `Local SHA-256 computed (no official checksum match in fetched releases):<br><span style="color:var(--amber)">${esc(hex)}</span>`;
        }
      }

      dropzone.addEventListener('click', () => fileInput.click());
      dropzone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          fileInput.click();
        }
      });
      fileInput.addEventListener('change', () => hashFile(fileInput.files?.[0]));
      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
      dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        hashFile(e.dataTransfer?.files?.[0]);
      });
    }
  }

  /* ---- Interactive Hero Command Tabs ---- */
  function initCmdDeck() {
    const pre = document.getElementById('hero-cmd-text');
    const copyBtn = document.getElementById('hero-copy-cmd');
    const tabs = document.querySelectorAll('.cmd-tab');
    if (!pre || !tabs.length) return;

    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        tabs.forEach((t) => {
          t.classList.toggle('active', t === tab);
          t.setAttribute('aria-selected', String(t === tab));
        });
        pre.textContent = tab.dataset.cmd || '';
      });
    });

    if (copyBtn) {
      copyBtn.addEventListener('click', () => copyWithFeedback(copyBtn, pre.textContent || ''));
    }
  }

  /* ---- Live Interactive Hero Workstation (Canvas + Timeline + Ducking) ---- */
  function initWorkstation() {
    const canvas = document.getElementById('hero-preview-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const STYLES = {
      viral_reel: { preset: '1080×1920', fit: 'blur_fill', grade: 'vivid', motion: 'zoom_in', bar: true, captions: 'kinetic' },
      cinematic: { preset: '1920×1080', fit: 'cover', grade: 'cinematic', motion: 'zoom_in', bar: false, captions: 'clean' },
      tutorial: { preset: '1920×1080', fit: 'contain', grade: 'studio', motion: 'none', bar: true, captions: 'boxed' },
      documentary: { preset: '1920×1080', fit: 'contain', grade: 'warm', motion: 'pan_right', bar: false, captions: 'clean' },
      noir_trailer: { preset: '1920×1080', fit: 'cover', grade: 'noir', motion: 'zoom_in', bar: false, captions: 'bold' },
    };

    const INITIAL_CLIPS = [
      { id: 'c1', title: '01 · Intro Hook', dur: 1.5, slate: true, accent: '#ffd166', words: ['YOUR', 'FOOTAGE'] },
      { id: 'c2', title: '02 · Product Demo', dur: 2.7, slate: false, accent: '#66ddbe', words: ['SHIP', 'STUDIO', 'REELS', 'LOCALLY'] },
      { id: 'c3', title: '03 · Audit Proof', dur: 1.8, slate: false, accent: '#3b82f6', words: ['VERIFIED', 'SHA-256'] },
    ];

    const state = {
      style: 'viral_reel',
      fit: 'blur_fill',
      grade: 'vivid',
      playing: true,
      t: 1.4,
      total: 6.0,
      clips: INITIAL_CLIPS.map((c) => ({ ...c })),
      selectedClip: 1,
    };

    const rail = document.getElementById('ws-timeline-rail');
    const playhead = document.getElementById('ws-playhead');
    const tcEl = document.getElementById('ws-timecode');
    const styleBadge = document.getElementById('ws-style-badge');
    const fitBadge = document.getElementById('hud-fit-badge');
    const fxBadge = document.getElementById('hud-fx-badge');
    const scenePill = document.getElementById('ws-scene-pill');
    const tlSummary = document.getElementById('ws-timeline-summary');
    const mVoice = document.getElementById('meter-voice');
    const mMusic = document.getElementById('meter-music');
    const mVoiceDb = document.getElementById('meter-voice-db');
    const mMusicDb = document.getElementById('meter-music-db');

    function renderClipsRail() {
      if (!rail || !playhead) return;
      rail.querySelectorAll('.clip-block').forEach((el) => el.remove());
      state.clips.forEach((clip, idx) => {
        const div = document.createElement('div');
        div.className = `clip-block ${clip.slate ? 'is-slate' : ''} ${idx === state.selectedClip ? 'is-selected' : ''}`;
        div.style.flex = String(clip.dur);
        div.innerHTML = `<span class="clip-title">${esc(clip.title)}</span><span class="clip-meta">${clip.dur.toFixed(1)}s</span>`;
        rail.insertBefore(div, playhead);
      });
      if (tlSummary) {
        const s = STYLES[state.style];
        tlSummary.textContent = `${state.clips.length} clips · ${s.captions} captions · progress_bar: ${s.bar ? 'ON' : 'OFF'}`;
      }
    }

    function syncBadges() {
      const s = STYLES[state.style];
      if (styleBadge) styleBadge.textContent = `${state.style} · ${s.preset}`;
      if (fitBadge) fitBadge.textContent = `fit: ${state.fit}`;
      if (fxBadge) fxBadge.textContent = `grade: ${state.grade} · ${s.motion}`;
    }

    document.querySelectorAll('#ws-style-pills .chip-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        state.style = btn.dataset.style;
        const p = STYLES[state.style];
        state.fit = p.fit;
        state.grade = p.grade;
        document.querySelectorAll('#ws-style-pills .chip-btn').forEach((b) => b.classList.toggle('active', b === btn));
        document.querySelectorAll('#ws-fit-pills .chip-btn').forEach((b) => b.classList.toggle('active', b.dataset.fit === state.fit));
        document.querySelectorAll('#ws-grade-pills .chip-btn').forEach((b) => b.classList.toggle('active', b.dataset.grade === state.grade));
        syncBadges();
        renderClipsRail();
      });
    });

    document.querySelectorAll('#ws-fit-pills .chip-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        state.fit = btn.dataset.fit;
        document.querySelectorAll('#ws-fit-pills .chip-btn').forEach((b) => b.classList.toggle('active', b === btn));
        syncBadges();
      });
    });

    document.querySelectorAll('#ws-grade-pills .chip-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        state.grade = btn.dataset.grade;
        document.querySelectorAll('#ws-grade-pills .chip-btn').forEach((b) => b.classList.toggle('active', b === btn));
        syncBadges();
      });
    });

    const playBtn = document.getElementById('ws-play-btn');
    if (playBtn) {
      playBtn.addEventListener('click', () => {
        state.playing = !state.playing;
        playBtn.textContent = state.playing ? 'Pause' : 'Play';
      });
    }

    const splitBtn = document.getElementById('ws-split-btn');
    if (splitBtn) {
      splitBtn.addEventListener('click', () => {
        if (state.clips.length >= 6) return;
        let acc = 0;
        for (let i = 0; i < state.clips.length; i++) {
          const c = state.clips[i];
          if (state.t > acc + 0.35 && state.t < acc + c.dur - 0.35) {
            const left = state.t - acc;
            const right = c.dur - left;
            const first = { ...c, dur: left, title: `${c.title} (A)` };
            const second = { ...c, id: `${c.id}_b`, dur: right, title: `${c.title} (B)` };
            state.clips.splice(i, 1, first, second);
            state.selectedClip = i + 1;
            renderClipsRail();
            break;
          }
          acc += c.dur;
        }
      });
    }

    const resetBtn = document.getElementById('ws-reset-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        state.clips = INITIAL_CLIPS.map((c) => ({ ...c }));
        state.selectedClip = 1;
        state.t = 0.2;
        renderClipsRail();
      });
    }

    if (rail) {
      rail.addEventListener('click', (e) => {
        const rect = rail.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        state.t = ratio * state.total;
      });
    }

    function currentClipAt(t) {
      let acc = 0;
      for (let i = 0; i < state.clips.length; i++) {
        const c = state.clips[i];
        if (t <= acc + c.dur || i === state.clips.length - 1) {
          return { clip: c, index: i, localRatio: Math.max(0, Math.min(1, (t - acc) / c.dur)) };
        }
        acc += c.dur;
      }
      return { clip: state.clips[0], index: 0, localRatio: 0 };
    }

    function drawFrame(t) {
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const { clip, index, localRatio } = currentClipAt(t);
      if (state.selectedClip !== index) {
        state.selectedClip = index;
        if (scenePill) scenePill.textContent = clip.title;
      }

      const portraitFrame = state.fit === 'blur_fill' || state.fit === 'contain' || STYLES[state.style].preset === '1080×1920';
      const fw = portraitFrame ? 174 : w;
      const fh = h;
      const fx = portraitFrame ? (w - fw) / 2 : 0;

      // Grade tint
      const gradeFilter = {
        vivid: 'saturate(1.38) contrast(1.08)',
        teal_orange: 'contrast(1.14) saturate(1.16)',
        cinematic: 'contrast(1.12) brightness(0.96)',
        studio: 'contrast(1.08) brightness(1.05)',
        noir: 'grayscale(1) contrast(1.34)',
      }[state.grade] || 'none';

      ctx.save();
      ctx.filter = gradeFilter;

      // Outer Frame Canvas (blur_fill halo vs contain dark backdrop)
      if (portraitFrame) {
        if (state.fit === 'blur_fill') {
          const halo = ctx.createRadialGradient(w / 2, h / 2, 20, w / 2, h / 2, 340);
          halo.addColorStop(0, clip.accent);
          halo.addColorStop(0.55, '#132b45');
          halo.addColorStop(1, '#050912');
          ctx.globalAlpha = 0.42;
          ctx.fillStyle = halo;
          ctx.fillRect(0, 0, w, h);
          ctx.globalAlpha = 1;
        } else {
          ctx.fillStyle = '#020408';
          ctx.fillRect(0, 0, w, h);
        }
      }

      // Subject Box inside Frame
      ctx.save();
      ctx.beginPath();
      ctx.rect(fx, 0, fw, fh);
      ctx.clip();

      const innerGrad = ctx.createLinearGradient(fx, 0, fx + fw, fh);
      innerGrad.addColorStop(0, '#0b182c');
      innerGrad.addColorStop(1, '#123142');
      ctx.fillStyle = innerGrad;
      ctx.fillRect(fx, 0, fw, fh);

      // Motion simulation: zoom_in / pan_right
      const zoom = STYLES[state.style].motion === 'zoom_in' ? 1 + localRatio * 0.12 : 1.0;
      const panX = STYLES[state.style].motion === 'pan_right' ? (localRatio - 0.5) * 28 : 0;
      ctx.save();
      ctx.translate(fx + fw / 2 + panX, fh / 2);
      ctx.scale(zoom, zoom);

      // Motion Vector Curves inside shot
      ctx.strokeStyle = clip.accent;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      for (let x = -70; x <= 70; x += 6) {
        const y = Math.sin(x * 0.08 + t * 4.2) * 22;
        if (x === -70) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      ctx.fillStyle = '#f4f7fc';
      ctx.font = '700 13px -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(clip.title.toUpperCase(), 0, -44);

      ctx.fillStyle = 'rgba(203,213,225,0.75)';
      ctx.font = '600 11px ui-monospace, monospace';
      ctx.fillText(`z=${zoom.toFixed(2)}x · f=${Math.floor(t * 30)}`, 0, 52);
      ctx.restore();

      // Kinetic Captions
      const words = clip.words || ['REELTERN'];
      const activeIdx = Math.floor(localRatio * words.length) % words.length;
      ctx.font = '800 15px -apple-system, sans-serif';
      ctx.textAlign = 'center';
      const captionStr = words.join('  ');
      const baseX = fx + fw / 2;
      const capY = fh - 38;
      if (STYLES[state.style].captions === 'boxed') {
        ctx.fillStyle = 'rgba(0,0,0,0.68)';
        ctx.fillRect(baseX - 72, capY - 18, 144, 24);
      }
      const totalWidth = ctx.measureText(captionStr).width;
      let cursor = baseX - totalWidth / 2;
      ctx.textAlign = 'left';
      words.forEach((word, wi) => {
        const txt = word + (wi < words.length - 1 ? '  ' : '');
        ctx.fillStyle = wi === activeIdx ? '#ffd166' : '#f4f7fc';
        ctx.fillText(txt, cursor, capY);
        cursor += ctx.measureText(txt).width;
      });

      // Electric Blue bottom progress bar
      if (STYLES[state.style].bar) {
        ctx.fillStyle = 'rgba(255,255,255,0.16)';
        ctx.fillRect(fx, fh - 5, fw, 5);
        ctx.fillStyle = '#3b82f6';
        ctx.fillRect(fx, fh - 5, fw * (t / state.total), 5);
      }

      ctx.restore();
      ctx.restore();

      // Timecode & Ducking Meters
      if (tcEl) {
        tcEl.textContent = `00:0${t.toFixed(2)} / 00:0${state.total.toFixed(2)}`;
      }
      if (playhead) {
        playhead.style.left = `${(t / state.total) * 100}%`;
      }

      const speechWave = 0.52 + 0.42 * Math.abs(Math.sin(t * 5.6)) * (clip.slate ? 0.25 : 1);
      const duckedMusic = Math.max(0.14, 0.72 - speechWave * 0.56);
      if (mVoice) mVoice.style.width = `${Math.round(speechWave * 100)}%`;
      if (mMusic) mMusic.style.width = `${Math.round(duckedMusic * 100)}%`;
      if (mVoiceDb) mVoiceDb.textContent = `${Math.round(-30 + speechWave * 22)} dB`;
      if (mMusicDb) mMusicDb.textContent = `${Math.round(-34 + duckedMusic * 18)} dB`;
    }

    syncBadges();
    renderClipsRail();

    let last = performance.now();
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduced) state.playing = false;

    function tick(now) {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      if (state.playing) {
        state.t = (state.t + dt) % state.total;
      }
      drawFrame(state.t);
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  /* ---- 4-Stage Pipeline Switcher ---- */
  function initPipeline() {
    const items = document.querySelectorAll('.stage-item');
    const tag = document.getElementById('stage-tag');
    const title = document.getElementById('stage-title');
    const desc = document.getElementById('stage-desc');
    const code = document.getElementById('stage-code');
    const foot = document.getElementById('stage-foot');
    if (!items.length || !code) return;

    const STAGES = {
      inspect: {
        tag: 'Step 01 · inspect_media_visuals',
        title: 'inspect_media_visuals → reeltern://visual/asset/{id}',
        desc: 'Extracts a tiled contact_sheet.png, detects scene boundaries & near-black frames via PyAV, and highlights loud audio peaks before building any cut list.',
        foot: 'Cache key v2 · zero repeated frame decodes',
        code: `{\n  "contact_sheet": "visuals/asset_v2_sheet.png",\n  "telemetry": {\n    "luma_avg": 0.44,\n    "contrast_score": 0.19,\n    "scene_cuts": [1.98, 4.12],\n    "black_frames": 0\n  }\n}`,
      },
      compose: {
        tag: 'Step 02 · compose_video (AI Director)',
        title: 'compose_video(asset_ids, director_style="viral_reel")',
        desc: 'Combines silence detection, opening title cards, blur_fill framing, alternating zoom_in / pan motion, voice_cleanup, ducked music, and kinetic captions into an immutable plan.',
        foot: 'Reversible SHA-256 DAG revision created cleanly',
        code: `reeltern compose footage.mp4 \\\n  --style viral_reel \\\n  --music soundtrack.wav \\\n  --intro "Launch Highlight" \\\n  --preview --audit`,
      },
      render: {
        tag: 'Step 03 · render_plan (Segment Cache)',
        title: 'FFmpeg filter_complex: blur_fill + zoompan + sidechaincompress + ASS',
        desc: 'Encodes each normalized segment once (keyed by source hash, trim, speed, grade, and motion), joins transitions with xfade/acrossfade, ducks music under speech, and masters to -16 LUFS.',
        foot: 'Unchanged clips hit cache in ~0.34s',
        code: `[0:v]split[fg][bg];\n[bg]scale=1080:1920:force_original_aspect_ratio=increase,gblur=sigma=24[halo];\n[halo][fg]overlay=(W-w)/2:(H-h)/2[canvas];\n[music][voice]sidechaincompress=threshold=0.04:ratio=6:attack=25:release=320[duck];\n[voice][duck]amix=inputs=2,loudnorm=I=-16:TP=-1.5`,
      },
      audit: {
        tag: 'Step 04 · audit_render (Closed-Loop QA)',
        title: 'audit_render(job_id) → EBU R128 + Luminance Scorecard',
        desc: 'Inspects the finished MP4 using FFmpeg ebur128 plus PyAV exposure sampling and emits a post-render contact sheet alongside exact remediation suggestions if checks fail.',
        foot: 'Full decode + SHA-256 verification receipt attached',
        code: `{\n  "passed": true,\n  "lufs": -16.0,\n  "true_peak_db": -1.8,\n  "black_frames": 0,\n  "contact_sheet": "jobs/c2925b/audit/render_contact_sheet.png",\n  "suggestions": ["Ready for final 1080p export."]\n}`,
      },
    };

    function activate(key) {
      const s = STAGES[key] || STAGES.inspect;
      items.forEach((b) => b.classList.toggle('active', b.dataset.stage === key));
      if (tag) tag.textContent = s.tag;
      if (title) title.textContent = s.title;
      if (desc) desc.textContent = s.desc;
      if (foot) foot.textContent = s.foot;
      code.textContent = s.code;
    }

    activate('inspect');
    items.forEach((btn) => btn.addEventListener('click', () => activate(btn.dataset.stage)));
  }

  /* ---- Compare Slider & Kinetic Ticker ---- */
  function initBentoInteractions() {
    const slider = document.getElementById('blur-slider');
    const mask = document.getElementById('blur-mask');
    const div = document.getElementById('blur-divider');
    if (slider && mask && div) {
      slider.addEventListener('input', () => {
        const val = `${slider.value}%`;
        mask.style.width = val;
        div.style.left = val;
      });
    }

    const line = document.getElementById('bento-kinetic-line');
    if (line && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      const words = ['BUILD', 'STUDIO', 'REELS', 'LOCALLY'];
      let idx = 0;
      setInterval(() => {
        idx = (idx + 1) % words.length;
        line.innerHTML = words
          .map((w, i) => `<span style="color:${i === idx ? 'var(--amber)' : 'var(--ink-65)'};margin:0 4px;">${w}</span>`)
          .join('');
      }, 650);
    }
  }

  /* ---- MCP Client Config Generator ---- */
  function initMcpConfig() {
    const tabs = document.querySelectorAll('#mcp-client-tabs .chip-btn');
    const pyIn = document.getElementById('cfg-python');
    const wsIn = document.getElementById('cfg-workspace');
    const mediaIn = document.getElementById('cfg-media');
    const out = document.getElementById('cfg-output');
    const fileTag = document.getElementById('cfg-filename');
    const copyBtn = document.getElementById('cfg-copy-btn');
    if (!out || !tabs.length) return;

    let client = 'claude-code';
    const FILES = {
      'claude-code': '.mcp.json',
      codex: '~/.codex/config.toml',
      cursor: '.cursor/mcp.json',
      vscode: '.vscode/mcp.json',
      generic: 'mcp-servers.json',
    };

    function update() {
      const py = pyIn?.value.trim() || 'python3';
      const ws = wsIn?.value.trim() || './workspace';
      const media = mediaIn?.value.trim() || './footage';
      const args = ['-m', 'reeltern.cli', 'mcp', '--workspace', ws, '--media-root', media];
      if (fileTag) fileTag.textContent = FILES[client] || 'config.json';

      if (client === 'codex') {
        out.textContent = `[mcp_servers.reeltern]\ncommand = ${JSON.stringify(py)}\nargs = ${JSON.stringify(args)}\ntool_timeout_sec = 300`;
      } else if (client === 'vscode') {
        out.textContent = JSON.stringify({ servers: { reeltern: { type: 'stdio', command: py, args } } }, null, 2);
      } else {
        out.textContent = JSON.stringify({ mcpServers: { reeltern: { command: py, args } } }, null, 2);
      }
    }

    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        client = tab.dataset.client;
        tabs.forEach((b) => b.classList.toggle('active', b === tab));
        update();
      });
    });

    [pyIn, wsIn, mediaIn].forEach((el) => el?.addEventListener('input', update));
    if (copyBtn) copyBtn.addEventListener('click', () => copyWithFeedback(copyBtn, out.textContent || ''));
    update();
  }

  /* ---- Studio Playground (studio.html) ---- */
  function initPlayground() {
    const cliOut = document.getElementById('pg-cli-out');
    const jsonOut = document.getElementById('pg-json-out');
    if (!cliOut || !jsonOut) return;

    const DEFAULTS = {
      viral_reel: { preset: 'reels', fit: 'blur_fill', transition: 'slideleft', grade: 'vivid', motion: 'zoom_in', captions: 'kinetic', voice: true, duck: true, bar: true, loud: true },
      cinematic: { preset: 'fhd', fit: 'cover', transition: 'crossfade', grade: 'cinematic', motion: 'zoom_in', captions: 'clean', voice: true, duck: true, bar: false, loud: true },
      tutorial: { preset: 'fhd', fit: 'contain', transition: 'wipeleft', grade: 'studio', motion: 'none', captions: 'boxed', voice: true, duck: false, bar: true, loud: true },
      documentary: { preset: 'fhd', fit: 'contain', transition: 'dissolve', grade: 'vintage', motion: 'pan_right', captions: 'clean', voice: true, duck: true, bar: false, loud: true },
      noir_trailer: { preset: 'fhd', fit: 'cover', transition: 'fadeblack', grade: 'noir', motion: 'zoom_in', captions: 'bold', voice: true, duck: true, bar: false, loud: true },
    };

    let activeStyle = 'viral_reel';
    const els = {
      preset: document.getElementById('pg-preset'),
      fit: document.getElementById('pg-fit'),
      transition: document.getElementById('pg-transition'),
      grade: document.getElementById('pg-grade'),
      motion: document.getElementById('pg-motion'),
      captions: document.getElementById('pg-captions'),
      intro: document.getElementById('pg-intro'),
      voice: document.getElementById('pg-toggle-voice'),
      duck: document.getElementById('pg-toggle-duck'),
      bar: document.getElementById('pg-toggle-bar'),
      loud: document.getElementById('pg-toggle-loud'),
      badge: document.getElementById('pg-summary-badge'),
      qa: document.getElementById('pg-qa-preview'),
    };

    const boolOf = (btn, label) => {
      const on = btn?.dataset.bool === 'true';
      if (btn) {
        btn.classList.toggle('active', on);
        btn.textContent = `${label}: ${on ? 'ON' : 'OFF'}`;
      }
      return on;
    };

    function refresh() {
      const voice = boolOf(els.voice, 'voice_cleanup EQ');
      const duck = boolOf(els.duck, 'music_ducking');
      const bar = boolOf(els.bar, 'progress_bar');
      const loud = boolOf(els.loud, 'loudnorm (-16 LUFS)');
      const intro = els.intro?.value.trim() || '';

      if (els.badge) els.badge.textContent = `${activeStyle} · ${els.preset.value}`;

      const parts = [
        `reeltern compose footage.mp4`,
        `--style ${activeStyle}`,
        `--preset ${els.preset.value}`,
      ];
      if (intro) parts.push(`--intro ${JSON.stringify(intro)}`);
      if (duck) parts.push(`--music bgm.wav`);
      parts.push('--preview --audit');
      cliOut.textContent = parts.join(' ');

      const payload = {
        version: 2,
        preset: els.preset.value,
        fit: els.fit.value,
        transition: els.transition.value,
        caption_style: els.captions.value,
        voice_cleanup: voice,
        progress_bar: bar,
        normalize_audio: loud,
        music_ducking: duck,
        clips: [
          ...(intro ? [{ asset_id: 'title_card_sha256', start: 0, end: 2.0, grade: els.grade.value, title_overlay: intro }] : []),
          { asset_id: 'source_sha256', start: 0.0, end: 6.5, speed: 1.0, grade: els.grade.value, motion: els.motion.value },
        ],
      };
      jsonOut.textContent = JSON.stringify(payload, null, 2);

      if (els.qa) {
        const lufs = loud ? '-16.0 LUFS' : 'Unnormalized';
        const checks = [
          els.fit.value === 'blur_fill' ? 'blur_fill framing' : `${els.fit.value} fit`,
          voice ? 'voice EQ/comp' : null,
          duck ? 'sidechain ducking' : null,
          bar ? 'accent bar' : null,
        ].filter(Boolean);
        els.qa.innerHTML = `<span><strong>PREDICTED AUDIT:</strong> PASSED · ${esc(lufs)} · 0 black frames</span><span style="opacity:0.85">Verified tags: ${esc(checks.join(' · '))}</span>`;
      }
    }

    document.querySelectorAll('[data-pg-style]').forEach((btn) => {
      btn.addEventListener('click', () => {
        activeStyle = btn.dataset.pgStyle;
        document.querySelectorAll('[data-pg-style]').forEach((b) => b.classList.toggle('active', b === btn));
        const d = DEFAULTS[activeStyle];
        if (d) {
          els.preset.value = d.preset;
          els.fit.value = d.fit;
          els.transition.value = d.transition;
          els.grade.value = d.grade;
          els.motion.value = d.motion;
          els.captions.value = d.captions;
          els.voice.dataset.bool = String(d.voice);
          els.duck.dataset.bool = String(d.duck);
          els.bar.dataset.bool = String(d.bar);
          els.loud.dataset.bool = String(d.loud);
        }
        refresh();
      });
    });

    [els.voice, els.duck, els.bar, els.loud].forEach((btn) => {
      btn?.addEventListener('click', () => {
        btn.dataset.bool = btn.dataset.bool === 'true' ? 'false' : 'true';
        refresh();
      });
    });

    [els.preset, els.fit, els.transition, els.grade, els.motion, els.captions, els.intro].forEach((el) => {
      el?.addEventListener('input', refresh);
      el?.addEventListener('change', refresh);
    });

    document.getElementById('pg-copy-cli')?.addEventListener('click', (e) => copyWithFeedback(e.currentTarget, cliOut.textContent || ''));
    document.getElementById('pg-copy-json')?.addEventListener('click', (e) => copyWithFeedback(e.currentTarget, jsonOut.textContent || ''));
    refresh();
  }

  /* ---- 31-Tool MCP Schema Explorer (tools.html) ---- */
  async function initToolsExplorer() {
    const grid = document.getElementById('tools-explorer-grid');
    if (!grid) return;

    const searchInput = document.getElementById('tool-search');
    const catBtns = document.querySelectorAll('[data-cat]');

    let tools = [];
    try {
      const res = await fetch('./mcp-tools.json');
      const data = await res.json();
      tools = data.tools || [];
    } catch (_) {
      grid.innerHTML = `<div class="tool-card">Could not load <code>mcp-tools.json</code>.</div>`;
      return;
    }

    function categorize(name) {
      if (['compose_video', 'style_clip', 'animate_clip', 'apply_timeline_style', 'configure_audio_mix'].includes(name)) return 'director';
      if (['capabilities', 'import_media', 'import_audio', 'list_assets', 'create_title_card', 'inspect_media_visuals', 'analyze_audio'].includes(name)) return 'media';
      if (['suggest_edit', 'create_plan', 'split_clip', 'get_plan', 'list_plans', 'compare_plans'].includes(name)) return 'plan';
      if (['render_plan', 'job_status', 'cancel_job', 'audit_render', 'list_jobs', 'get_render_receipt', 'retry_job'].includes(name)) return 'render';
      return 'transcript';
    }

    let activeCat = 'all';
    function draw() {
      const q = (searchInput?.value || '').trim().toLowerCase();
      const filtered = tools.filter((t) => {
        if (activeCat !== 'all' && categorize(t.name) !== activeCat) return false;
        if (!q) return true;
        return t.name.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q);
      });

      grid.innerHTML = filtered
        .map((t) => {
          const props = Object.keys(t.inputSchema?.properties || {});
          const req = new Set(t.inputSchema?.required || []);
          const ro = t.annotations?.readOnlyHint;
          const chips = props.length
            ? props.map((p) => `<span class="param-chip ${req.has(p) ? 'req' : ''}">${esc(p)}${req.has(p) ? '*' : ''}</span>`).join('')
            : `<span class="param-chip">no arguments</span>`;
          return `
            <article class="tool-card">
              <div class="tool-head">
                <span class="tool-name">${esc(t.name)}</span>
                <span class="badge-rec">${ro ? 'read-only' : 'mutating'}</span>
              </div>
              <p style="margin:0;color:var(--ink-65);font-size:0.9rem;">${esc(t.description)}</p>
              <div class="param-list">${chips}</div>
              <details>
                <summary class="mono" style="font-size:0.75rem;color:var(--ink-45);cursor:pointer;">Inspect JSON Schema</summary>
                <pre class="code-window" style="margin-top:0.5rem;font-size:0.72rem;max-height:200px;">${esc(JSON.stringify(t.inputSchema, null, 2))}</pre>
              </details>
            </article>
          `;
        })
        .join('');
    }

    catBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        activeCat = btn.dataset.cat;
        catBtns.forEach((b) => b.classList.toggle('active', b === btn));
        draw();
      });
    });
    searchInput?.addEventListener('input', draw);
    draw();
  }

  document.addEventListener('DOMContentLoaded', () => {
    initChrome();
    initCmdDeck();
    initWorkstation();
    initPipeline();
    initBentoInteractions();
    initMcpConfig();
    initPlayground();
    initToolsExplorer();
    initReleasesSystem();
  });
})();
