# Changelog

## 0.6.0 — 15 November 2026

- **Standalone Cross-OS Desktop Studio Apps (`packaging/desktop_entry.py`, `scripts/build_desktop_app.py`):**
  - Added PyInstaller `--onedir` desktop packaging pipeline for **macOS Apple Silicon (`.dmg`)**, **macOS Intel (`.dmg`)**, **Windows x64 (`.zip`)**, and **Linux x64 (`.tar.gz` + `.desktop`)** bundling FFmpeg, PyAV, Tkinter, and the 31-tool MCP server with generated app icons.
  - Added safe default writable workspace selection (`~/ReelternWorkspace`) when double-clicked from Finder/Explorer or read-only working directories, `-psn_*` LaunchServices argument filtering, and frozen-executable `mcp-config` detection in `reeltern/client_config.py`.
- **First-Class Antigravity Support & Studio Onboarding (`client_config.py`, `studio.py`, `cli.py`):**
  - Added `antigravity` to `reeltern mcp-config` (`~/.gemini/config/mcp_config.json`), `examples/clients/antigravity.json`, client tests, docs, and website selectors.
  - Added **Load Demo**, **Workspace…**, and **Connect AI** configuration generator modal directly inside **Reeltern Studio**, plus the `reeltern studio` CLI alias.

## 0.5.0 — 15 November 2026

- **AI Director & Self-Critique Closed Loop (`reeltern/director.py`):**
  - Added `compose_video` (`compose_plan` / `reeltern compose --style ...`) with 5 production profiles (`cinematic`, `viral_reel`, `tutorial`, `documentary`, `noir_trailer`) that combine silence detection, intro slates, aspect-matched `blur_fill` / framing, animated camera motion, transitions, voice cleanup, background music ducking, loudness normalization, and kinetic/styled captions in a single deterministic plan.
  - Added `audit_render` (`audit_job_render` / `reeltern audit JOB_ID`) measuring rendered video EBU R128 integrated loudness & true peak (`ebur128`), average luminance, contrast spread, near-black frames, a `render_contact_sheet.png`, and actionable repair suggestions.
  - Extended `inspect_media_visuals` with tiled PNG `contact_sheet` generation, PyAV `scene_cuts`, exposure/contrast telemetry, and waveform `energy_peaks`.
- **Creator-Grade Audio & Video Pipeline (`effects.py`, `workspace.py`, `render.py`, `media.py`):**
  - Added `blur_fill` halo background canvas mode (`gblur=sigma=24,eq=brightness=-0.10`) for landscape/square clips inside vertical `portrait` or `reels` timelines.
  - Added per-clip Ken Burns camera motion (`zoom_in`, `zoom_out`, `pan_left`, `pan_right` via `zoompan`/dynamic crop at exact timeline frame counts).
  - Expanded color grades to 10 (`teal_orange`, `vintage`, `studio`, plus existing looks) and transitions to 10 (`wiperight`, `slideright`, `smoothleft`, `circleopen`, `fadeblack`, plus existing joins).
  - Added `kinetic` word-highlight ASS subtitle burning over existing supplied cues, animated bottom accent `progress_bar`, `voice_cleanup` (`highpass=f=85,acompressor`), and `import_audio` + `music_asset_id` background soundtrack mixing with FFmpeg `sidechaincompress` ducking.
- **MCP, CLI & Studio Upgrades:**
  - Expanded MCP to **31 tools** (added `import_audio`, `compose_video`, `animate_clip`, `configure_audio_mix`, `audit_render`), **`100/100 Grade A`** on AgentFlight (`0` errors, `0` warnings), binary PNG resource templates (`reeltern://visual/asset/{asset_id}`, `reeltern://visual/render/{job_id}`), `reeltern://cookbook`, and `viral_short` / `polish_edit` prompts.
  - Updated CLI (`import-audio`, `compose`, `audit`, plus `edit` flags) and Desktop `Studio` (`+ Audio`, `AI Director`, `Audit QA`, motion combobox, `blur_fill`, `Voice EQ`, `Progress Bar`, and storyboard telemetry).

## 0.4.0 — 15 November 2026

- Added `reeltern/effects.py` creative and audio core: synthesized chapter/title cards (`create_card`), non-destructive timeline clip splitting (`split_clip`), color grading presets (`cinematic`, `warm`, `crisp`, `noir`, `vivid`, `moody`), brightness/contrast/saturation controls, fade-in/out ramps, `0.25×–4×` chained `atempo` speed, horizontal/vertical flips and `90°/180°/270°` rotation, safe ASS lower-third text overlays, `crossfade`/`wipeleft`/`slideleft`/`dissolve` joins (`xfade` + `acrossfade`), EBU R128 loudness normalization (`loudnorm`), stylized burned-in captions (`clean`, `boxed`, `bold`), Full HD presets (`fhd` 1920×1080, `reels` 1080×1920), storyboard filmstrip generation, and audio waveform peak inspection.
- Redesigned `Reeltern Studio` desktop UI with an obsidian dark workstation theme, interactive proportional timeline canvas with clickable playhead & clip hitboxes, live cached PNG storyboard filmstrip & waveform canvases, multi-tab inspector (`Trim & Split`, `Color, Audio & Lower Third`, `Transitions & Burned Captions`), Title Card creation modal, revision diff comparator, and receipt inspector.
- Applied `AgentFlight` schema hardening and token compaction across all 26 MCP tools (`ergonomics_score: 100/100 Grade A`, `0` warnings, `0` errors) and compacted `EditorialAgent` prompts & cue serialization (omitting duplicated JSON Schema when Ollama structured `format` enforces schema, using compact cue keys).
- Extended CLI with `card`, `inspect`, and style/transition/caption flags on `edit`.

## 0.3.2 — 11 November 2026

- Added a gated GitHub release workflow with wheel, source archive, OS-specific Python installation bundles and SHA-256 checksums.
- Added local-environment installation and desktop/CLI launchers for Windows, macOS and Linux.
- Added clean bundle installation, real-media demo and MCP smoke checks across Python 3.10–3.12 and four OS/architecture runner targets.
- Added release installation/support documentation and explicit source-distribution contents.

## 0.3.1 — 11 November 2026

- Added configuration generation for Claude Code, Codex, Cursor, VS Code and generic MCP clients without changing user settings.
- Added paged transcript discovery for reconnected assistants; now 21 MCP tools.
- Added an executable MCP editing example and generated machine-readable tool schemas.
- Added client setup, agent workflows, troubleshooting, implementation contracts and a prioritized roadmap.
- Added shared contributor instructions for coding assistants and a compact documentation index.

## 0.3.0 — 11 November 2026

- Added SRT/timecoded transcript import, cue search and text-based cut plans.
- Added a bounded local Ollama editorial agent with grounded IDs, duration validation, one repair attempt and draft receipts.
- Added source-quoted evidence separate from unverified model explanations.
- Added caption retiming with SRT sidecars and selectable MP4 subtitles.
- Expanded MCP to 20 tools with detailed clip/cue schemas and responsive background operations.
- Added desktop Transcript & AI workflow and a reproducible no-model demo.
- Added workspace ownership locks, interrupted-job detection and explicit retries.
- Added contributor issue templates and security guidance.

## 0.2.0 — 11 November 2026

- Added immutable multi-source cut plans, parent revisions and plan comparisons.
- Added conservative audio-activity proposals with padding and keep-all handling for silent inputs.
- Added a desktop cut-plan editor with trimming, reordering, speed changes, undo, history, previews and final exports.
- Added twelve MCP tools using the official SDK and a directory-scoped import interface.
- Added queued/cancellable rendering, segment reuse and verified export receipts.
- Added landscape, portrait and square output, contain/center-crop geometry and silent-track normalization.
- Added portable FFmpeg fallback and real-media/MCP integration tests.
- Retained the 0.1 optional adapters under `reeltern toolkit`, explicitly marked experimental.

## 0.1.0 — 10 November 2026

Initial desktop/CLI workflow launcher and adapters for eleven open-source media projects.
