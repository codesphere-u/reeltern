## Reeltern 0.5.0 — AI Director, creator-grade polish, and closed-loop QA

Edit through Reeltern Studio (desktop), the command line, or **31 AgentFlight Grade-A MCP tools** for Claude Code, Codex, Cursor, VS Code, and other local clients.

### Downloads

- **Windows:** `reeltern-0.5.0-windows-python.zip`
- **macOS (Apple Silicon or Intel):** `reeltern-0.5.0-macos-python.zip`
- **Linux:** `reeltern-0.5.0-linux-python.zip`
- **Existing Python environment:** `reeltern-0.5.0-py3-none-any.whl`
- **Source:** `reeltern-0.5.0.tar.gz`
- **Download verification:** `SHA256SUMS.txt`

**These are Python installation bundles, not standalone native apps.** Install Python first (3.12 recommended), extract the ZIP, and run `python3 install.py` on macOS/Linux or `py -3.12 install.py` on Windows. The installer creates a private `.venv` and installs dependencies locally without changing global packages. See the included `START-HERE.md`.

### What is new in 0.5.0

- **AI Director (`compose_video` / `reeltern compose --style ...`):** One-call production presets (`cinematic`, `viral_reel`, `tutorial`, `documentary`, `noir_trailer`) pairing silence trimming, intro slates, aspect framing, motion, color grading, voice cleanup, music ducking, loudness normalization, and captions.
- **Closed-loop render QA (`audit_render` / `reeltern audit JOB_ID`):** Measures EBU R128 integrated loudness (`-16 LUFS`), true peak, luminance, contrast, near-black frames, rendered contact sheet PNGs, and actionable repair fixes.
- **Creator-grade video & audio:** `blur_fill` vertical halo framing, Ken Burns camera motion (`zoom_in`, `zoom_out`, `pan_left`, `pan_right`), **10 color grades**, **10 `xfade` transitions**, `kinetic` word-highlight burned ASS captions, sliding bottom `progress_bar`, `voice_cleanup` EQ/compressor, and `import_audio` + `sidechaincompress` music ducking.
- **MCP visual inspection & ergonomics:** Expanded to **31 tools (`100/100 Grade A`, `0` errors, `0` warnings)**, binary PNG resource templates (`reeltern://visual/asset/{asset_id}`, `reeltern://visual/render/{job_id}`), `reeltern://cookbook`, and `viral_short` / `polish_edit` prompts.

### Release checks & limits

Publication is gated on core unit tests (`53` checks locally, including pixel, audio, CLI, Studio Tk, and live stdio MCP checks) plus clean bundle installation, real demo render, cache-reuse checks, and 31-tool MCP handshake across Python 3.10–3.12 on Ubuntu, Windows, and macOS. Python and internet access are required for bundle dependency setup; GUI requires Tkinter. Bundles remain unsigned; there is still no built-in speech recognition or face tracking.

[Showcase & Downloads](https://codesphere-u.github.io/reeltern/) · [Install guide](https://github.com/codesphere-u/reeltern/blob/v0.5.0/docs/releases.md) · [AI setup](https://github.com/codesphere-u/reeltern/blob/v0.5.0/docs/clients.md) · [Validation](https://github.com/codesphere-u/reeltern/blob/v0.5.0/VALIDATION.md)
