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
    navigator.clipboard
      ?.writeText(text)
      .then(() => {
        const prev = btn.textContent;
        btn.textContent = 'Copied ✓';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = prev;
          btn.classList.remove('copied');
        }, 1400);
      })
      .catch(() => {});
  }

  /* ---- Theme Toggle (Matte Obsidian vs Univer Paper) + Nav + Scroll Reveal ---- */
  function initChrome() {
    const toggle = document.querySelector('.menu-toggle');
    const nav = document.querySelector('.header-nav');
    if (toggle && nav) {
      toggle.addEventListener('click', () => {
        const open = nav.classList.toggle('open');
        toggle.setAttribute('aria-expanded', String(open));
      });
    }

    const themeBtn = document.getElementById('theme-toggle');
    const themeMeta = document.querySelector('meta[name="theme-color"]');
    function applyTheme(next) {
      document.documentElement.setAttribute('data-theme', next);
      if (themeMeta) themeMeta.setAttribute('content', next === 'light' ? '#fbfaf8' : '#09090b');
      try {
        localStorage.setItem('reeltern-theme', next);
      } catch (_) {}
      if (themeBtn) {
        themeBtn.setAttribute('title', next === 'light' ? 'Switch to dark studio' : 'Switch to light paper');
      }
    }
    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        const cur = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
        applyTheme(cur === 'light' ? 'dark' : 'light');
      });
    }

    document.querySelectorAll('[data-reveal]').forEach((el) => el.classList.add('is-visible'));
  }

  /* ---- Command Palette (⌘K) ---- */
  function initCommandPalette() {
    const modal = document.getElementById('cmdk-modal');
    const openBtn = document.getElementById('open-cmdk');
    const input = document.getElementById('cmdk-input');
    const results = document.getElementById('cmdk-results');
    if (!modal || !input || !results) return;

    const baseItems = [
      { title: 'Overview & Live Studio', kind: 'Page', href: './', keywords: 'home hero timeline canvas' },
      { title: 'blur_fill Halo Framing · Aspect Comparison', kind: 'Feature', href: './#blur-compare', keywords: 'blur_fill blur contain cover 9:16 vertical letterboxing' },
      { title: 'Interactive Director Studio Sandbox', kind: 'Page', href: './studio.html', keywords: 'studio playground viral_reel cinematic noir_trailer' },
      { title: 'MCP Setup Guide (Claude, Codex, Cursor, VS Code)', kind: 'Docs', href: './docs.html#mcp-setup', keywords: 'mcp-config toml claude codex cursor vscode' },
      { title: 'AI Director Production Profiles (5 styles)', kind: 'Docs', href: './docs.html#director-profiles', keywords: 'viral_reel cinematic tutorial documentary noir_trailer' },
      { title: 'CLI Subcommands Reference', kind: 'Docs', href: './docs.html#cli-reference', keywords: 'compose inspect audit studio demo' },
      { title: '31 MCP Tool Schemas', kind: 'Spec', href: './tools.html', keywords: 'tools schema agentflight' },
      { title: 'Releases & Client-Side SHA-256 Verifier', kind: 'Downloads', href: './releases.html', keywords: 'zip wheel tar.gz checksum sha256 macos windows linux' },
    ];

    let allItems = [...baseItems];
    let loadedTools = false;

    async function ensureToolsLoaded() {
      if (loadedTools) return;
      loadedTools = true;
      try {
        const res = await fetch('./mcp-tools.json');
        if (!res.ok) return;
        const data = await res.json();
        const tools = (data.tools || []).map((t) => ({
          title: `${t.name} — ${t.description || ''}`,
          kind: 'MCP Tool',
          href: `./tools.html?q=${encodeURIComponent(t.name)}`,
          keywords: JSON.stringify(t.inputSchema || {}).toLowerCase(),
        }));
        allItems = [...baseItems, ...tools];
        renderResults();
      } catch (_) {}
    }

    function renderResults() {
      const q = (input.value || '').trim().toLowerCase();
      const matched = allItems
        .filter((it) => !q || it.title.toLowerCase().includes(q) || it.kind.toLowerCase().includes(q) || (it.keywords || '').includes(q))
        .slice(0, 12);
      if (!matched.length) {
        results.innerHTML = `<div class="cmdk-item" style="color:var(--ink-subtle)">No matching pages or MCP tools.</div>`;
        return;
      }
      results.innerHTML = matched
        .map(
          (it) => `<a class="cmdk-item" href="${esc(it.href)}"><span>${esc(it.title)}</span><span class="cmdk-kind">${esc(it.kind)}</span></a>`
        )
        .join('');
    }

    function open() {
      modal.classList.add('open');
      ensureToolsLoaded();
      renderResults();
      setTimeout(() => input.focus(), 10);
    }

    function close() {
      modal.classList.remove('open');
    }

    openBtn?.addEventListener('click', open);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) close();
    });
    results.addEventListener('click', (e) => {
      if (e.target.closest('a')) close();
    });
    input.addEventListener('input', renderResults);
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (modal.classList.contains('open')) close();
        else open();
      } else if (e.key === 'Escape' && modal.classList.contains('open')) {
        close();
      }
    });
  }

  /* ---- Hero Agent / Client Selector (Plannotator + Stitch style) ---- */
  function initHeroTargets(latestTag) {
    const tabBtns = document.querySelectorAll('#hero-target-tabs .agent-btn');
    const cmdText = document.getElementById('hero-cmd-text');
    const copyBtn = document.getElementById('hero-copy-cmd');
    const stepsEl = document.getElementById('hero-steps-list');
    if (!tabBtns.length || !cmdText || !stepsEl) return;

    const ver = (latestTag || 'v0.5.0').replace(/^v/, '');
    const PROFILES = {
      claude: {
        cmd: `pip install -e '.[mcp]' && reeltern mcp-config claude-code --workspace ./ws --media-root ./footage`,
        steps: [
          `reeltern mcp-config claude-code --workspace ./ws --media-root ./footage > .mcp.json`,
          `Start Claude Code in the project directory (auto-detects .mcp.json)`,
          `Ask Claude: "Inspect launch.mp4 visually and compose a viral_reel"`,
        ],
      },
      codex: {
        cmd: `reeltern mcp-config codex --workspace ./ws --media-root ./footage >> ~/.codex/config.toml`,
        steps: [
          `Verify [mcp_servers.reeltern] appears in ~/.codex/config.toml`,
          `Grant scoped media access via --media-root ./footage`,
          `Prompt Codex to inspect contacts & audit loudness at -16 LUFS`,
        ],
      },
      cursor: {
        cmd: `reeltern mcp-config cursor --workspace ./ws --media-root ./footage > .cursor/mcp.json`,
        steps: [
          `Reload Cursor MCP servers to register 31 typed video tools`,
          `Open .cursor/mcp.json to verify virtualenv python executable path`,
          `Ask Composer: "compose demo.mp4 with style=tutorial & preview"`,
        ],
      },
      vscode: {
        cmd: `reeltern mcp-config vscode --workspace ./ws --media-root ./footage > .vscode/mcp.json`,
        steps: [
          `VS Code reads stdio definition under servers.reeltern`,
          `Use Copilot Agent Mode to inspect scene cuts via reeltern://visual/asset/{id}`,
          `Render preview first, verify audit_render score, then export 1080p`,
        ],
      },
      cli: {
        cmd: `pip install -e '.[mcp]' && reeltern compose launch.mp4 --style viral_reel --music bgm.wav --preview --audit`,
        steps: [
          `Run zero-setup synthetic test project: reeltern demo --workspace demo-ws`,
          `Launch native Tk desktop timeline: reeltern studio`,
          `Re-audit any job anytime: reeltern audit JOB_ID --workspace ./ws`,
        ],
      },
      macos: {
        cmd: `unzip reeltern-${ver}-macos-python.zip && cd reeltern-${ver}-macos-python && python3 install.py`,
        steps: [
          `Creates isolated .venv inside the extracted folder (never alters system Python)`,
          `Verify archive checksum locally using ./releases.html dropzone`,
          `Launch Desktop Studio or CLI with ./reeltern.sh gui`,
        ],
      },
      windows: {
        cmd: `Expand-Archive reeltern-${ver}-windows-python.zip -DestinationPath . && cd reeltern-${ver}-windows-python && py -3.12 install.py`,
        steps: [
          `Includes bundled portable runner script (.\\reeltern.cmd)`,
          `Run preview render: .\\reeltern.cmd compose clip.mp4 --style viral_reel --preview`,
          `Open Desktop Studio: .\\reeltern.cmd gui`,
        ],
      },
      linux: {
        cmd: `unzip reeltern-${ver}-linux-python.zip && cd reeltern-${ver}-linux-python && python3 install.py`,
        steps: [
          `GUI requires system python3-tk; headless CLI & MCP server work anywhere`,
          `Verify SHA-256 matches official SHA256SUMS.txt from GitHub Releases`,
          `Start MCP or demo: sh reeltern.sh demo --workspace demo-project`,
        ],
      },
    };

    let activeKey = 'claude';
    function render(key) {
      activeKey = key;
      const p = PROFILES[key] || PROFILES.claude;
      tabBtns.forEach((b) => b.classList.toggle('active', b.dataset.target === key));
      cmdText.textContent = p.cmd;
      stepsEl.innerHTML = p.steps
        .map(
          (step, idx) => `
          <div class="detail-step">
            <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
              <span class="detail-step-num">${idx + 1}.</span>${esc(step)}
            </span>
            <button class="copy-btn" type="button" data-copy-step="${esc(step)}">Copy</button>
          </div>
        `
        )
        .join('');
    }

    tabBtns.forEach((btn) => {
      btn.addEventListener('click', () => render(btn.dataset.target));
    });

    stepsEl.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-copy-step]');
      if (btn) copyWithFeedback(btn, btn.dataset.copyStep || '');
    });

    if (copyBtn) {
      copyBtn.addEventListener('click', () => copyWithFeedback(copyBtn, cmdText.textContent || ''));
    }

    render(activeKey);
  }

  /* ---- Live Univer-Inspired Hero Workstation ---- */
  function initWorkstation() {
    const canvas = document.getElementById('hero-preview-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const STYLES = {
      viral_reel: { preset: '1080×1920', fit: 'blur_fill', grade: 'vivid', motion: 'zoom_in', bar: true, captions: 'kinetic' },
      cinematic: { preset: '1920×1080', fit: 'cover', grade: 'cinematic', motion: 'zoom_in', bar: false, captions: 'clean' },
      tutorial: { preset: '1920×1080', fit: 'contain', grade: 'studio', motion: 'none', bar: true, captions: 'boxed' },
      noir_trailer: { preset: '1920×1080', fit: 'cover', grade: 'noir', motion: 'zoom_in', bar: false, captions: 'bold' },
    };

    const INITIAL_CLIPS = [
      { id: 'c1', title: '01 · Intro Hook', dur: 1.5, slate: true, accent: '#f59e0b', words: ['YOUR', 'FOOTAGE'] },
      { id: 'c2', title: '02 · Product Demo', dur: 2.7, slate: false, accent: '#34d399', words: ['SHIP', 'STUDIO', 'REELS'] },
      { id: 'c3', title: '03 · Audit QA', dur: 1.8, slate: false, accent: '#818cf8', words: ['VERIFIED', 'SHA-256'] },
    ];

    const state = {
      style: 'viral_reel',
      fit: 'blur_fill',
      grade: 'vivid',
      playing: true,
      t: 1.6,
      total: 6.0,
      clips: INITIAL_CLIPS.map((c) => ({ ...c })),
      selectedClip: 1,
    };

    const rail = document.getElementById('ws-timeline-rail');
    const playhead = document.getElementById('ws-playhead');
    const tcEl = document.getElementById('ws-timecode');
    const styleBadge = document.getElementById('ws-style-badge');
    const formulaEl = document.getElementById('ws-formula-expr');
    const cellRef = document.getElementById('ws-cell-ref');
    const selBox = document.getElementById('ws-selection-box');
    const agentTag = document.getElementById('ws-agent-tag');
    const scenePill = document.getElementById('ws-scene-pill');
    const tlSummary = document.getElementById('ws-timeline-summary');
    const mVoice = document.getElementById('meter-voice');
    const mMusic = document.getElementById('meter-music');
    const mVoiceDb = document.getElementById('meter-voice-db');
    const mMusicDb = document.getElementById('meter-music-db');

    function syncChrome() {
      const s = STYLES[state.style];
      if (styleBadge) styleBadge.textContent = `${state.style} · ${s.preset}`;
      if (formulaEl) formulaEl.textContent = `=COMPOSE("${state.style}", fit="${state.fit}", grade="${state.grade}")`;
      if (cellRef) cellRef.textContent = `V1:CLIP_0${state.selectedClip + 1}`;
      if (selBox) selBox.classList.toggle('is-wide', state.fit === 'cover' || (state.fit === 'contain' && s.preset === '1920×1080'));
      if (agentTag) agentTag.textContent = `Agent · ${state.fit}`;
      if (tlSummary) tlSummary.textContent = `${state.clips.length} clips · ${s.captions} captions · -16.0 LUFS`;
    }

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
      syncChrome();
    }

    function splitAtCurrent() {
      if (state.clips.length >= 6) return;
      let acc = 0;
      for (let i = 0; i < state.clips.length; i++) {
        const c = state.clips[i];
        if (state.t > acc + 0.3 && state.t < acc + c.dur - 0.3) {
          const left = state.t - acc;
          const right = c.dur - left;
          state.clips.splice(
            i,
            1,
            { ...c, dur: left, title: `${c.title} A` },
            { ...c, id: `${c.id}_b`, dur: right, title: `${c.title} B` }
          );
          state.selectedClip = i + 1;
          renderClipsRail();
          break;
        }
        acc += c.dur;
      }
    }

    document.querySelectorAll('#ws-style-pills .chip-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        state.style = btn.dataset.style;
        const p = STYLES[state.style];
        state.fit = p.fit;
        state.grade = p.grade;
        document.querySelectorAll('#ws-style-pills .chip-btn').forEach((b) => b.classList.toggle('active', b === btn));
        document.querySelectorAll('#ws-fit-pills .chip-btn').forEach((b) => b.classList.toggle('active', b.dataset.fit === state.fit));
        syncChrome();
        renderClipsRail();
      });
    });

    document.querySelectorAll('#ws-fit-pills .chip-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        state.fit = btn.dataset.fit;
        document.querySelectorAll('#ws-fit-pills .chip-btn').forEach((b) => b.classList.toggle('active', b === btn));
        syncChrome();
      });
    });

    const playBtn = document.getElementById('ws-play-btn');
    if (playBtn) {
      playBtn.addEventListener('click', () => {
        state.playing = !state.playing;
        playBtn.textContent = state.playing ? 'Pause' : 'Play';
      });
    }
    document.getElementById('ws-split-btn')?.addEventListener('click', splitAtCurrent);
    document.getElementById('hero-preview-word')?.addEventListener('click', () => {
      splitAtCurrent();
      document.getElementById('workstation-hero')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    document.getElementById('ws-reset-btn')?.addEventListener('click', () => {
      state.clips = INITIAL_CLIPS.map((c) => ({ ...c }));
      state.selectedClip = 1;
      state.t = 0.25;
      renderClipsRail();
    });

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
        if (cellRef) cellRef.textContent = `V1:CLIP_0${index + 1}`;
      }

      const portrait = state.fit === 'blur_fill' || (state.fit === 'contain' && STYLES[state.style].preset === '1080×1920');
      const fw = portrait ? 186 : w - 72;
      const fh = h;
      const fx = (w - fw) / 2;

      const gradeFilter =
        {
          vivid: 'saturate(1.32) contrast(1.06)',
          cinematic: 'contrast(1.1) brightness(0.95)',
          studio: 'contrast(1.05) brightness(1.04)',
          noir: 'grayscale(1) contrast(1.35)',
        }[state.grade] || 'none';

      ctx.save();
      ctx.filter = gradeFilter;

      if (state.fit === 'blur_fill') {
        const halo = ctx.createRadialGradient(w / 2, h / 2, 18, w / 2, h / 2, 330);
        halo.addColorStop(0, clip.accent);
        halo.addColorStop(0.55, '#1e1b4b');
        halo.addColorStop(1, '#09090b');
        ctx.globalAlpha = 0.48;
        ctx.fillStyle = halo;
        ctx.fillRect(0, 0, w, h);
        ctx.globalAlpha = 1;
      } else {
        ctx.fillStyle = '#050608';
        ctx.fillRect(0, 0, w, h);
      }

      ctx.save();
      ctx.beginPath();
      ctx.rect(fx, 0, fw, fh);
      ctx.clip();

      const innerGrad = ctx.createLinearGradient(fx, 0, fx + fw, fh);
      innerGrad.addColorStop(0, '#0f172a');
      innerGrad.addColorStop(1, '#1e293b');
      ctx.fillStyle = innerGrad;
      ctx.fillRect(fx, 0, fw, fh);

      const zoom = STYLES[state.style].motion === 'zoom_in' ? 1 + localRatio * 0.12 : 1.0;
      ctx.save();
      ctx.translate(fx + fw / 2, fh / 2);
      ctx.scale(zoom, zoom);

      ctx.strokeStyle = clip.accent;
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      for (let x = -72; x <= 72; x += 6) {
        const y = Math.sin(x * 0.08 + t * 4.2) * 20;
        if (x === -72) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      ctx.fillStyle = '#f4f4f5';
      ctx.font = '600 13px Inter, -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(clip.title.toUpperCase(), 0, -46);

      ctx.fillStyle = '#a1a1aa';
      ctx.font = '500 11px JetBrains Mono, monospace';
      ctx.fillText(`z=${zoom.toFixed(2)}x · f=${Math.floor(t * 30)}`, 0, 52);
      ctx.restore();

      // Kinetic Captions
      const words = clip.words || ['REELTERN'];
      const activeIdx = Math.floor(localRatio * words.length) % words.length;
      ctx.font = '700 14px Inter, -apple-system, sans-serif';
      const capY = fh - 40;
      const baseX = fx + fw / 2;
      if (STYLES[state.style].captions === 'boxed') {
        ctx.fillStyle = 'rgba(0,0,0,0.72)';
        ctx.fillRect(baseX - 78, capY - 17, 156, 24);
      }
      const fullStr = words.join('  ');
      let cursor = baseX - ctx.measureText(fullStr).width / 2;
      ctx.textAlign = 'left';
      words.forEach((word, wi) => {
        const txt = word + (wi < words.length - 1 ? '  ' : '');
        ctx.fillStyle = wi === activeIdx ? '#fbbf24' : '#f4f4f5';
        ctx.fillText(txt, cursor, capY);
        cursor += ctx.measureText(txt).width;
      });

      if (STYLES[state.style].bar) {
        ctx.fillStyle = 'rgba(255,255,255,0.14)';
        ctx.fillRect(fx, fh - 4, fw, 4);
        ctx.fillStyle = '#3b82f6';
        ctx.fillRect(fx, fh - 4, fw * (t / state.total), 4);
      }

      ctx.restore();
      ctx.restore();

      if (tcEl) tcEl.textContent = `00:0${t.toFixed(2)} / 00:0${state.total.toFixed(2)}`;
      if (playhead) playhead.style.left = `${(t / state.total) * 100}%`;

      const speechWave = 0.48 + 0.44 * Math.abs(Math.sin(t * 5.6)) * (clip.slate ? 0.25 : 1);
      const duckedMusic = Math.max(0.14, 0.72 - speechWave * 0.56);
      if (mVoice) mVoice.style.width = `${Math.round(speechWave * 100)}%`;
      if (mMusic) mMusic.style.width = `${Math.round(duckedMusic * 100)}%`;
      if (mVoiceDb) mVoiceDb.textContent = `${Math.round(-30 + speechWave * 22)} dB`;
      if (mMusicDb) mMusicDb.textContent = `${Math.round(-34 + duckedMusic * 18)} dB`;
    }

    renderClipsRail();
    let last = performance.now();
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) state.playing = false;

    function tick(now) {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      if (state.playing) state.t = (state.t + dt) % state.total;
      drawFrame(state.t);
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  /* ---- 4-Stage Pipeline Switcher ---- */
  function initPipeline() {
    const items = document.querySelectorAll('.stage-item');
    const title = document.getElementById('stage-title');
    const desc = document.getElementById('stage-desc');
    const code = document.getElementById('stage-code');
    const foot = document.getElementById('stage-foot');
    const copyBtn = document.getElementById('stage-copy-btn');
    if (!items.length || !code) return;

    const STAGES = {
      inspect: {
        title: 'inspect_media_visuals → reeltern://visual/asset/{id}',
        desc: 'Extracts a tiled contact_sheet.png, detects scene boundaries & near-black frames via PyAV, and highlights loud audio peaks before building any cut list.',
        foot: 'Cache key v2',
        code: `{\n  "contact_sheet": "visuals/asset_v2_sheet.png",\n  "telemetry": {\n    "luma_avg": 0.44,\n    "contrast_score": 0.19,\n    "scene_cuts": [1.98, 4.12],\n    "black_frames": 0\n  }\n}`,
      },
      compose: {
        title: 'compose_video(asset_ids, director_style="viral_reel")',
        desc: 'Combines silence detection, opening title cards, blur_fill framing, alternating zoom_in / pan motion, voice_cleanup, ducked music, and kinetic captions into an immutable plan.',
        foot: 'SHA-256 DAG revision',
        code: `reeltern compose footage.mp4 \\\n  --style viral_reel \\\n  --music soundtrack.wav \\\n  --intro "Launch Highlight" \\\n  --preview --audit`,
      },
      render: {
        title: 'FFmpeg filter_complex: blur_fill + zoompan + sidechaincompress + ASS',
        desc: 'Encodes each normalized segment once (keyed by source hash, trim, speed, grade, and motion), joins transitions cleanly, ducks music under speech, and normalizes to -16 LUFS.',
        foot: '~0.34s cache hit',
        code: `[0:v]split[fg][bg];\n[bg]scale=1080:1920:force_original_aspect_ratio=increase,gblur=sigma=24[halo];\n[halo][fg]overlay=(W-w)/2:(H-h)/2[canvas];\n[music][voice]sidechaincompress=threshold=0.04:ratio=6:attack=25:release=320[duck];\n[voice][duck]amix=inputs=2,loudnorm=I=-16:TP=-1.5`,
      },
      audit: {
        title: 'audit_render(job_id) → EBU R128 + Luminance Scorecard',
        desc: 'Inspects the finished MP4 using FFmpeg ebur128 plus PyAV exposure sampling and emits a post-render contact sheet alongside exact remediation suggestions if checks fail.',
        foot: 'SHA-256 verified receipt',
        code: `{\n  "passed": true,\n  "lufs": -16.0,\n  "true_peak_db": -1.8,\n  "black_frames": 0,\n  "contact_sheet": "jobs/c2925b/audit/render_contact_sheet.png",\n  "suggestions": ["Ready for final 1080p export."]\n}`,
      },
    };

    function activate(key) {
      const s = STAGES[key] || STAGES.inspect;
      items.forEach((b) => b.classList.toggle('active', b.dataset.stage === key));
      if (title) title.textContent = s.title;
      if (desc) desc.textContent = s.desc;
      if (foot) foot.textContent = s.foot;
      code.textContent = s.code;
    }

    activate('inspect');
    items.forEach((btn) => btn.addEventListener('click', () => activate(btn.dataset.stage)));
    copyBtn?.addEventListener('click', () => copyWithFeedback(copyBtn, code.textContent || ''));
  }

  /* ---- Blur Compare Slider & "How It Works" Switcher ---- */
  function initShowcaseInteractions() {
    const slider = document.getElementById('blur-slider');
    const compareBox = document.getElementById('blur-compare');
    if (slider && compareBox) {
      slider.addEventListener('input', () => {
        compareBox.style.setProperty('--split', `${slider.value}%`);
      });
    }

    const howBtns = document.querySelectorAll('[data-how-mode]');
    const howTitle = document.getElementById('how-window-title');
    const howCode = document.getElementById('how-code-view');
    const howGrid = document.getElementById('how-steps-grid');
    if (!howBtns.length || !howCode || !howGrid) return;

    const MODES = {
      agent: {
        title: 'MCP Workflow · Claude Code / Codex / Cursor / VS Code',
        code: `assistant -> call import_media(path="footage/launch.mp4")\nassistant -> call inspect_media_visuals(asset_id)   # PNG contact sheet + cuts\nassistant -> call compose_video(asset_ids, style="viral_reel", music_id=...)\nassistant -> call render_plan(plan_id, preview=true) -> audit_render(job_id)\n# PASSED (-16.0 LUFS, 0 black frames) -> export final 1080p MP4`,
        steps: [
          { t: 'Inspect real frames', d: 'Your AI reads a tiled PNG contact sheet, scene cuts, and speech peaks before editing.' },
          { t: 'Compose immutable plan', d: 'Applies styles, blur_fill framing, captions, and ducked music into a reversible DAG.' },
          { t: 'Audit & deliver locally', d: 'Closed-loop EBU R128 and black-frame checks run offline before final 1080p export.' },
        ],
      },
      human: {
        title: 'Human Workflow · CLI & Desktop Studio',
        code: `$ pip install -e '.[mcp]'\n$ reeltern compose launch.mp4 --style viral_reel --music bgm.wav --preview --audit\n$ reeltern studio   # scrub waveform + timeline visually without touching raw files`,
        steps: [
          { t: 'Run one CLI command', d: 'compose produces a complete styled edit with titles, captions, and music ducking.' },
          { t: 'Fine-tune in Desktop Studio', d: 'Adjust trims, split clips at the playhead, or swap grades with full revision history.' },
          { t: 'Export with receipt proof', d: 'Every final MP4 verifies full decode, dimensions, duration, and SHA-256 digests.' },
        ],
      },
    };

    function setHow(mode) {
      const m = MODES[mode] || MODES.agent;
      howBtns.forEach((b) => b.classList.toggle('active', b.dataset.howMode === mode));
      if (howTitle) howTitle.textContent = m.title;
      howCode.textContent = m.code;
      howGrid.innerHTML = m.steps
        .map(
          (st, i) => `
          <div class="how-step">
            <div class="how-step-head">
              <span class="step-circle">${i + 1}</span>
              <h3>${esc(st.t)}</h3>
            </div>
            <p>${esc(st.d)}</p>
          </div>
        `
        )
        .join('');
    }

    howBtns.forEach((btn) => btn.addEventListener('click', () => setHow(btn.dataset.howMode)));
    setHow('agent');
  }

  /* ---- GitHub Releases + Downloads Table & Verifier ---- */
  async function fetchReleasesData() {
    let releases = [];
    let source = 'live';
    try {
      const res = await fetch(API_URL, { headers: { Accept: 'application/vnd.github+json' } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (Array.isArray(json) && json.length) releases = json.filter((r) => !r.draft);
    } catch (_) {
      source = 'cached';
    }

    if (!releases.length) {
      try {
        const fb = await fetch('./releases.json', { cache: 'no-store' });
        if (fb.ok) {
          const json = await fb.json();
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
      return `# Extract reeltern-${cleanVer}-macos-python.zip cleanly:\ncd reeltern-${cleanVer}-macos-python\npython3 install.py\n./reeltern.sh compose your-clip.mp4 --style viral_reel --preview --audit\n./reeltern.sh gui`;
    }
    if (osTab === 'windows') {
      return `# Extract reeltern-${cleanVer}-windows-python.zip, then in PowerShell:\ncd reeltern-${cleanVer}-windows-python\npy -3.12 install.py\n.\\reeltern.cmd compose your-clip.mp4 --style viral_reel --preview --audit\n.\\reeltern.cmd gui`;
    }
    if (osTab === 'linux') {
      return `# Extract reeltern-${cleanVer}-linux-python.zip (GUI needs python3-tk):\ncd reeltern-${cleanVer}-linux-python\npython3 install.py\nsh reeltern.sh demo --workspace demo-project\nsh reeltern.sh gui`;
    }
    return `python3 -m venv .venv && source .venv/bin/activate\npython -m pip install "./reeltern-${cleanVer}-py3-none-any.whl[mcp]"\n# Or install directly from GitHub:\npython -m pip install "git+${REPO_URL}.git"`;
  }

  async function initReleasesSystem() {
    const userOS = detectPlatform();
    const { releases, source } = await fetchReleasesData();
    const latest = releases[0] || null;
    const latestTag = latest ? latest.tag_name : 'v0.5.0';

    document.querySelectorAll('[data-latest-tag]').forEach((el) => {
      el.textContent = latestTag;
    });
    document.querySelectorAll('[data-latest-badge]').forEach((el) => {
      el.textContent = latestTag;
    });
    const proofRel = document.getElementById('proof-release-val');
    if (proofRel && latest) proofRel.textContent = latest.tag_name;

    initHeroTargets(latestTag);

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
        const sha = match.digest ? ` · sha256:${match.digest.replace(/^sha256:/, '').slice(0, 12)}…` : '';
        heroMeta.textContent = `${match.name} · ${formatBytes(match.size)}${sha}`;
      } else {
        heroBtn.href = `${REPO_URL}/releases`;
        heroLabel.textContent = 'Browse GitHub Releases';
        heroMeta.textContent = 'github.com/codesphere-u/reeltern/releases';
      }
    }

    const select = document.getElementById('dl-release-select');
    const tbody = document.getElementById('dl-asset-tbody');
    const statusEl = document.getElementById('dl-release-status');
    const titleEl = document.getElementById('dl-release-title');
    const installPre = document.getElementById('os-install-code');
    const osCopyBtn = document.getElementById('os-copy-btn');
    const osTabs = document.querySelectorAll('[data-os-tab]');

    let activeOsTab = userOS;
    osTabs.forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.osTab === activeOsTab);
      tab.addEventListener('click', () => {
        activeOsTab = tab.dataset.osTab;
        osTabs.forEach((t) => t.classList.toggle('active', t === tab));
        if (installPre) {
          installPre.textContent = renderInstallSnippet(activeOsTab, select?.value || latestTag);
        }
      });
    });
    osCopyBtn?.addEventListener('click', () => copyWithFeedback(osCopyBtn, installPre?.textContent || ''));

    function renderHomeTable(rel) {
      if (!rel || !tbody) return;
      const dt = rel.published_at ? new Date(rel.published_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
      if (statusEl) statusEl.textContent = `${source === 'live' ? 'LIVE GITHUB API' : 'CACHED SNAPSHOT'} · ${rel.prerelease ? 'PREVIEW' : 'STABLE'}${dt ? ' · ' + dt : ''}`;
      if (titleEl) titleEl.textContent = rel.name || `Reeltern ${rel.tag_name}`;
      if (installPre) installPre.textContent = renderInstallSnippet(activeOsTab, rel.tag_name);

      const sorted = [...(rel.assets || [])].sort((a, b) => (classifyAsset(a.name).key === userOS ? -1 : 0) - (classifyAsset(b.name).key === userOS ? -1 : 0));
      tbody.innerHTML = sorted
        .map((a) => {
          const info = classifyAsset(a.name);
          const rec = info.key === userOS;
          const sha = (a.digest || '').replace(/^sha256:/, '');
          return `
            <tr class="${rec ? 'is-recommended' : ''}">
              <td><code>${esc(a.name)}</code></td>
              <td><span class="badge-rec ${rec ? 'accent' : ''}">${rec ? 'Recommended OS' : esc(info.badge)}</span></td>
              <td class="mono">${formatBytes(a.size)}</td>
              <td class="mono" style="color:var(--ink-muted)">${sha ? esc(sha.slice(0, 16) + '…') : '—'}</td>
              <td style="text-align:right">
                <a class="btn ${rec ? 'btn-primary' : 'btn-secondary'}" style="padding:0.35rem 0.78rem;font-size:0.78rem" href="${esc(a.browser_download_url)}">Download</a>
              </td>
            </tr>
          `;
        })
        .join('');
    }

    if (select && releases.length) {
      select.innerHTML = releases
        .map((r, i) => `<option value="${esc(r.tag_name)}">${esc(r.tag_name)}${i === 0 ? ' (Latest)' : ''}${r.prerelease ? ' · preview' : ''}</option>`)
        .join('');
      renderHomeTable(releases[0]);
      select.addEventListener('change', () => {
        const chosen = releases.find((r) => r.tag_name === select.value) || releases[0];
        renderHomeTable(chosen);
      });
    } else if (installPre) {
      installPre.textContent = renderInstallSnippet(activeOsTab, '0.5.0');
    }

    initReleasesPage(releases, source, userOS);
  }

  function formatInlineMd(text) {
    return esc(text)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong style="color:var(--ink)">$1</strong>');
  }

  function renderReleaseNotes(md) {
    return String(md || '')
      .split('\n')
      .slice(0, 26)
      .map((line) => {
        const trimmed = line.trim();
        if (!trimmed) return '';
        if (trimmed.startsWith('##')) {
          return `<h4 style="margin:0.85rem 0 0.35rem;font-size:0.94rem;color:var(--ink)">${formatInlineMd(trimmed.replace(/^#+\s*/, ''))}</h4>`;
        }
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return `<div style="padding-left:0.9rem;margin:0.2rem 0;color:var(--ink-muted);font-size:0.86rem">• ${formatInlineMd(trimmed.slice(2))}</div>`;
        }
        return `<p style="margin:0.3rem 0;color:var(--ink-muted);font-size:0.86rem">${formatInlineMd(trimmed)}</p>`;
      })
      .join('');
  }

  function initReleasesPage(releases, source, userOS) {
    const container = document.getElementById('all-releases-container');
    const syncMeta = document.getElementById('rel-sync-meta');
    if (syncMeta) syncMeta.textContent = `${releases.length} release(s) · ${source === 'live' ? 'Live GitHub Releases API' : 'Cached JSON snapshot'}`;

    let filter = 'all';
    function drawList() {
      if (!container) return;
      const list = releases.filter((r) => (filter === 'stable' ? !r.prerelease : filter === 'pre' ? r.prerelease : true));
      if (!list.length) {
        container.innerHTML = `<div class="vault-card" style="padding:1.25rem;color:var(--ink-muted)">No matching releases published under this filter yet.</div>`;
        return;
      }
      container.innerHTML = list
        .map((rel) => {
          const dt = rel.published_at ? new Date(rel.published_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
          const rows = (rel.assets || [])
            .map((a) => {
              const info = classifyAsset(a.name);
              const rec = info.key === userOS;
              const sha = (a.digest || '').replace(/^sha256:/, '');
              return `
                <tr class="${rec ? 'is-recommended' : ''}">
                  <td><code>${esc(a.name)}</code></td>
                  <td><span class="badge-rec ${rec ? 'accent' : ''}">${rec ? 'Your OS' : esc(info.badge)}</span></td>
                  <td class="mono">${formatBytes(a.size)}</td>
                  <td class="mono">${sha ? `<button class="copy-btn" type="button" data-copy-sha="${esc(sha)}">${esc(sha.slice(0, 14))}… (copy)</button>` : '—'}</td>
                  <td style="text-align:right"><a class="btn ${rec ? 'btn-primary' : 'btn-secondary'}" style="padding:0.35rem 0.78rem;font-size:0.78rem" href="${esc(a.browser_download_url)}">Download</a></td>
                </tr>
              `;
            })
            .join('');
          return `
            <article class="vault-card">
              <div class="vault-toolbar">
                <div>
                  <span class="badge-rec accent">${esc(rel.tag_name)} · ${rel.prerelease ? 'Preview Release' : 'Stable Release'}</span>
                  <h2 style="margin:0.45rem 0 0;font-size:1.28rem">${esc(rel.name || rel.tag_name)}</h2>
                  <div class="mono" style="font-size:0.74rem;color:var(--ink-subtle);margin-top:0.2rem">Published ${esc(dt)}</div>
                </div>
                <a class="btn btn-ghost" style="padding:0.42rem 0.85rem;font-size:0.82rem" href="${esc(rel.html_url)}" target="_blank" rel="noopener noreferrer">GitHub Release →</a>
              </div>
              <div style="padding:1.1rem 1.35rem;border-bottom:1px solid var(--border)">${renderReleaseNotes(rel.body)}</div>
              <div class="table-wrap">
                <table class="asset-table">
                  <thead><tr><th>Asset</th><th>Platform</th><th>Size</th><th>SHA-256 Digest</th><th style="text-align:right">Download</th></tr></thead>
                  <tbody>${rows}</tbody>
                </table>
              </div>
            </article>
          `;
        })
        .join('');
    }

    if (container) {
      drawList();
      container.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-copy-sha]');
        if (btn) copyWithFeedback(btn, btn.dataset.copySha || '');
      });
      document.querySelectorAll('[data-rel-filter]').forEach((btn) => {
        btn.addEventListener('click', () => {
          filter = btn.dataset.relFilter;
          document.querySelectorAll('[data-rel-filter]').forEach((b) => b.classList.toggle('active', b === btn));
          drawList();
        });
      });
    }

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
        const hex = Array.from(new Uint8Array(digestBuf))
          .map((b) => b.toString(16).padStart(2, '0'))
          .join('');
        let hit = null;
        for (const r of releases) {
          for (const a of r.assets || []) {
            const official = (a.digest || '').replace(/^sha256:/, '').toLowerCase();
            if (official && official === hex) {
              hit = { tag: r.tag_name, name: a.name };
              break;
            }
          }
          if (hit) break;
        }
        resultEl.innerHTML = hit
          ? `<span style="color:var(--verified)">MATCH CONFIRMED ✓</span> — ${esc(file.name)} matches <strong>${esc(hit.name)}</strong> (${esc(hit.tag)})<br><span style="opacity:0.8">sha256: ${esc(hex)}</span>`
          : `Local SHA-256 (no matching asset in fetched releases):<br><span style="color:var(--warn)">${esc(hex)}</span>`;
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

  /* ---- MCP Client Config Generator (docs.html#mcp-setup) ---- */
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
    copyBtn?.addEventListener('click', () => copyWithFeedback(copyBtn, out.textContent || ''));
    update();
  }

  /* ---- AG-UI Docs Scrollspy ---- */
  function initDocsScrollspy() {
    const tocLinks = document.querySelectorAll('.docs-toc .toc-link');
    const sideLinks = document.querySelectorAll('.docs-sidebar .docs-nav-item[href^="#"]');
    if (!tocLinks.length && !sideLinks.length) return;

    const sections = Array.from(document.querySelectorAll('.docs-prose [id]'));
    if (!sections.length) return;

    function updateActive() {
      let current = sections[0].id;
      for (const sec of sections) {
        if (sec.getBoundingClientRect().top <= 140) current = sec.id;
      }
      tocLinks.forEach((a) => a.classList.toggle('active', a.getAttribute('href') === `#${current}`));
      sideLinks.forEach((a) => a.classList.toggle('active', a.getAttribute('href') === `#${current}`));
    }
    window.addEventListener('scroll', updateActive, { passive: true });
    updateActive();
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
      const parts = [`reeltern compose footage.mp4`, `--style ${activeStyle}`, `--preset ${els.preset.value}`];
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
        const checks = [els.fit.value, voice ? 'voice EQ' : null, duck ? 'music ducking' : null, bar ? 'progress bar' : null].filter(Boolean);
        els.qa.innerHTML = `<span><strong>PREDICTED AUDIT:</strong> PASSED · ${esc(lufs)} · 0 black frames</span><span style="opacity:0.85">${esc(checks.join(' · '))}</span>`;
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
    const initialQ = new URLSearchParams(window.location.search).get('q');
    if (searchInput && initialQ) searchInput.value = initialQ;

    let tools = [];
    try {
      const res = await fetch('./mcp-tools.json');
      const data = await res.json();
      tools = data.tools || [];
    } catch (_) {
      grid.innerHTML = `<div class="tool-row">Could not load <code>mcp-tools.json</code>.</div>`;
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
            <article class="tool-row">
              <div class="tool-head">
                <span class="tool-name">${esc(t.name)}</span>
                <span class="badge-rec ${ro ? '' : 'accent'}">${ro ? 'read-only' : 'mutating'}</span>
              </div>
              <p style="margin:0;color:var(--ink-muted);font-size:0.9rem">${esc(t.description)}</p>
              <div class="param-list">${chips}</div>
              <details style="margin-top:0.65rem">
                <summary class="mono" style="font-size:0.74rem;color:var(--ink-subtle);cursor:pointer">JSON Schema</summary>
                <pre class="code-window" style="margin-top:0.5rem;border-radius:8px;border:1px solid var(--border);font-size:0.74rem;max-height:220px">${esc(JSON.stringify(t.inputSchema, null, 2))}</pre>
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
    initCommandPalette();
    initWorkstation();
    initPipeline();
    initShowcaseInteractions();
    initMcpConfig();
    initDocsScrollspy();
    initPlayground();
    initToolsExplorer();
    initReleasesSystem();
  });
})();
