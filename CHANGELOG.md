# Changelog

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
