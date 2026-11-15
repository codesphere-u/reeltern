## Reeltern 0.7.0 — Live Preview Workstation & Desktop Studio Upgrade

Edit directly in the redesigned **Reeltern Studio** standalone desktop app (macOS Apple Silicon & Intel, Windows x64, Linux x64), the CLI, or **31 AgentFlight Grade-A MCP tools** across **Antigravity, Claude Code, Codex, Cursor, VS Code**, and other local clients.

### Standalone Desktop Studio Apps (Zero Python Setup)

- **macOS Apple Silicon (.dmg):** `Reeltern-Studio-0.7.0-macos-arm64.dmg`
- **macOS Intel (.dmg):** `Reeltern-Studio-0.7.0-macos-x64.dmg`
- **Windows x64 (.zip):** `Reeltern-Studio-0.7.0-windows-x64.zip` (`Reeltern Studio.exe`)
- **Linux x64 (.tar.gz):** `Reeltern-Studio-0.7.0-linux-x64.tar.gz` (`reeltern-studio` + desktop entry)

### Python CLI & MCP Installation Bundles

- **Windows CLI Bundle:** `reeltern-0.7.0-windows-python.zip`
- **macOS CLI Bundle:** `reeltern-0.7.0-macos-python.zip`
- **Linux CLI Bundle:** `reeltern-0.7.0-linux-python.zip`
- **Existing Python environment:** `reeltern-0.7.0-py3-none-any.whl`
- **Source:** `reeltern-0.7.0.tar.gz`
- **Download verification:** `SHA256SUMS.txt`

### What is new in 0.7.0

- **Real-Time In-Window Program Monitor (`reeltern/preview.py`):** Live PyAV frame decoder and LGPL filter compositor inside **Reeltern Studio** rendering all 10 color grades (`teal_orange`, `cinematic`, true monochrome `noir`, `vintage`, `vivid`, `studio`, etc.), `blur_fill` vertical halo framing, Ken Burns preview, fades, brightness/contrast/saturation, lower-third title overlays, animated progress bar preview, toggleable safe-zone/rule-of-thirds guides, and a `Live` vs `Rendered` switch.
- **Flagship Obsidian NLE Workstation UI (`reeltern/studio.py`, `reeltern/studio_widgets.py`):** Custom flat `PillButton`, `ToggleSwitch`, smooth `ParamSlider`, `ScrollablePane`, and `MetricTile` KPI widgets across a 4-tab Inspector (`✦ Director` visual cards, `Look & FX` 2×5 grade swatch grid & live sliders, `Trim & Clip` `[ Mark In` / `Mark Out ]` & speed presets, `Mix & QA` toggles + inline LUFS/Peak/Luma/Black audit scorecard & `render_contact_sheet.png`), plus a multi-track `V1/T1/A1` visual timeline with clip thumbnails and keyboard shortcuts (`Space`, `←/→`, `I`, `O`, `S`, `⌘Z`).
- **One-Click Working Demo & Trim Fixes (`reeltern/demo.py`, `reeltern/studio.py`):** Shared active renderer cleanly during **Load Demo** so **Load Demo** immediately populates demo footage, timeline thumbnails, rendered MP4 switcher, storyboard, waveform, and Audit QA inside **Reeltern Studio**; fixed playhead-relative `[ Mark In` / `Mark Out ]` source offset calculation.

### Release checks & limits

Publication is gated on core unit tests across Ubuntu, Windows, and macOS (Python 3.10–3.12), documentation validation, OS bundle smoke tests, plus standalone Desktop Studio binary builds and MCP stdio handshake smoke tests across all four runners (`macos-15`, `macos-15-intel`, `windows-2022`, `ubuntu-22.04`). Bundles and `.dmg`/`.exe` builds remain unsigned (ad-hoc signed on macOS).

[Showcase & Downloads](https://codesphere-u.github.io/reeltern/) · [Install guide](https://github.com/codesphere-u/reeltern/blob/v0.7.0/docs/releases.md) · [AI setup](https://github.com/codesphere-u/reeltern/blob/v0.7.0/docs/clients.md) · [Validation](https://github.com/codesphere-u/reeltern/blob/v0.7.0/VALIDATION.md)
