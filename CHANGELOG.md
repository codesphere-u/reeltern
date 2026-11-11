# Changelog

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
