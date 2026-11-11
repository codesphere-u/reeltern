## Reeltern 0.3.2 — local editing for people and AI

First packaged GitHub preview release. Edit through the desktop, command line, or 21 MCP tools for Claude Code, Codex, Cursor, VS Code and other local clients.

### Downloads

- **Windows:** `reeltern-0.3.2-windows-python.zip`
- **macOS (Apple Silicon or Intel):** `reeltern-0.3.2-macos-python.zip`
- **Linux:** `reeltern-0.3.2-linux-python.zip`
- **Existing Python environment:** `reeltern-0.3.2-py3-none-any.whl`
- **Source:** `reeltern-0.3.2.tar.gz`
- **Download verification:** `SHA256SUMS.txt`

**These are Python installation bundles, not standalone native apps.** Install Python first (3.12 recommended), extract the ZIP, and run `python3 install.py` on macOS/Linux or `py -3.12 install.py` on Windows. The installer creates a private environment and downloads dependencies from your configured package index. It does not install model weights or change global Python packages. See the included `START-HERE.md`.

### What works

- Reversible source-based cut plans, trim/reorder/speed, and silence-assisted first passes.
- Supplied SRT transcripts, cue selection and retimed selectable captions.
- Optional local Ollama editorial drafts with source evidence and bounded validation.
- Verified previews/exports, cached segments and explicit interrupted-job retry.
- Client configuration generation, 21 MCP tools, implementation docs and an executable example.

### Release checks

Publication is gated on core tests and a clean bundle installation, real demo render, cache-reuse check and MCP handshake for Python 3.10, 3.11 and 3.12 on Ubuntu 22.04 x64, Windows Server 2022 x64, macOS 15 Apple Silicon and macOS 15 Intel. These checks do not certify every desktop OS version or GUI interaction.

### Limits

Early preview. Python and an internet connection are required for installation. GUI use needs Tkinter and a desktop session. Bundles are unsigned. No built-in transcription, burned-in captions, face tracking or full multitrack editor. The original optional enhancement adapters remain experimental. AI suggestions require review. No PyPI, container image or GitHub Packages registry publication is included.

[Install guide](https://github.com/codesphere-u/reeltern/blob/v0.3.2/docs/releases.md) · [AI setup](https://github.com/codesphere-u/reeltern/blob/v0.3.2/docs/clients.md) · [Validation](https://github.com/codesphere-u/reeltern/blob/v0.3.2/VALIDATION.md) · [Roadmap](https://github.com/codesphere-u/reeltern/blob/v0.3.2/docs/roadmap.md)
