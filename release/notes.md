## Reeltern 0.6.0 — Native Desktop Studio Apps & First-Class Antigravity MCP

Edit directly in the **Reeltern Studio** standalone desktop app (macOS Apple Silicon & Intel, Windows x64, Linux x64), the CLI, or **31 AgentFlight Grade-A MCP tools** across **Antigravity, Claude Code, Codex, Cursor, VS Code**, and other local clients.

### Standalone Desktop Studio Apps (Zero Python Setup)

- **macOS Apple Silicon (.dmg):** `Reeltern-Studio-0.6.0-macos-arm64.dmg`
- **macOS Intel (.dmg):** `Reeltern-Studio-0.6.0-macos-x64.dmg`
- **Windows x64 (.zip):** `Reeltern-Studio-0.6.0-windows-x64.zip` (`Reeltern Studio.exe`)
- **Linux x64 (.tar.gz):** `Reeltern-Studio-0.6.0-linux-x64.tar.gz` (`reeltern-studio` + desktop entry)

### Python CLI & MCP Installation Bundles

- **Windows CLI Bundle:** `reeltern-0.6.0-windows-python.zip`
- **macOS CLI Bundle:** `reeltern-0.6.0-macos-python.zip`
- **Linux CLI Bundle:** `reeltern-0.6.0-linux-python.zip`
- **Existing Python environment:** `reeltern-0.6.0-py3-none-any.whl`
- **Source:** `reeltern-0.6.0.tar.gz`
- **Download verification:** `SHA256SUMS.txt`

### What is new in 0.6.0

- **Native Cross-OS Desktop Studio Executables:** Built with bundled FFmpeg (`imageio-ffmpeg`), PyAV, Tkinter dark workstation UI, and headless CLI/MCP stdio support inside `packaging/desktop_entry.py` and `scripts/build_desktop_app.py`. Double-click to open Studio cleanly (`~/ReelternWorkspace` default writable directory), or pass `mcp --workspace ... --media-root ...` for headless MCP stdio.
- **First-Class Antigravity MCP Support:** Added `antigravity` to `mcp-config` (`~/.gemini/config/mcp_config.json`), `examples/clients/antigravity.json`, documentation, and the website hero/docs configurators.
- **One-Click Studio Onboarding:** Added **Load Demo** (loads synthetic footage, storyboard, waveform, and timeline immediately), **Workspace…** folder switcher, and **Connect AI** live configuration copy modal inside **Reeltern Studio**, plus `reeltern studio` CLI alias.

### Release checks & limits

Publication is gated on core unit tests across Ubuntu, Windows, and macOS (Python 3.10–3.12), documentation validation, OS bundle smoke tests, plus standalone Desktop Studio binary builds and MCP stdio handshake smoke tests across all four runners (`macos-15`, `macos-15-intel`, `windows-2022`, `ubuntu-22.04`). Bundles and `.dmg`/`.exe` builds remain unsigned (ad-hoc signed on macOS).

[Showcase & Downloads](https://codesphere-u.github.io/reeltern/) · [Install guide](https://github.com/codesphere-u/reeltern/blob/v0.6.0/docs/releases.md) · [AI setup](https://github.com/codesphere-u/reeltern/blob/v0.6.0/docs/clients.md) · [Validation](https://github.com/codesphere-u/reeltern/blob/v0.6.0/VALIDATION.md)
