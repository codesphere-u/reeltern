# Validation — 15 November 2026

## Version 0.5.0 AI Director, creator-grade visual/audio polish, and closed-loop render QA

- **59 automated tests passed locally** on macOS (Python 3.13.18 venv, PyAV 16.1.0, imageio-ffmpeg 0.8.1, MCP SDK 1.30.0) across unit, CLI, MCP stdio, real-time `PreviewEngine` frame composition, and `Studio` workstation UI checks, and **93 relative documentation links + six client configurations + the 31-tool MCP reference** checked cleanly.
- **New verified coverage (`test_director_v5.py` & expanded `test_mcp.py`):**
  - `import_audio` soundtrack import (WAV metadata validation + rejection of non-audio inputs).
  - Pixel-level frame verification of `fit='blur_fill'` red border halo vs `fit='contain'` black bars in `portrait` output, plus sliding bottom blue `#3B82F6` `progress_bar` pixels.
  - Per-clip Ken Burns `zoom_in` and `pan_right` camera motion rendering with exact 60-frame timing at 30 fps.
  - `kinetic` word-highlight ASS subtitle burning alongside `voice_cleanup` EQ/compressor, `sidechaincompress` ducked background music (`music_asset_id`), and EBU R128 loudness normalization, verified via subtitle stream presence, lower-third pixel diffs, and receipt verification entries.
  - Visual inspection extraction producing tiled `contact_sheet.png`, PyAV `scene_cuts` detection across color cuts, exposure/contrast telemetry, and waveform `energy_peaks`.
  - One-call AI Director (`compose_plan`) for `viral_reel` and `cinematic` profiles plus closed-loop `audit_job_render` reporting integrated LUFS (`-16.0`), true peak (`-13.0` dBFS in preview test), luminance, contrast, rendered contact sheet, and flagging all-black renders cleanly.
  - CLI `import-audio`, `compose --style viral_reel --music ... --preview --audit`, and `audit` subcommands, plus Desktop `Studio` v0.5.0 widgets (`motion`, `blur_fill`, `voice_cleanup`, `progress_bar`, `audit_render`).
  - Full stdio MCP client/server test covering all 31 tools, `reeltern://cookbook` + `reeltern://guide`, binary PNG resource templates (`reeltern://visual/asset/{asset_id}`, `reeltern://visual/render/{job_id}`), and all 4 prompts (`first_pass`, `editorial_draft`, `viral_short`, `polish_edit`).
  - AgentFlight MCP schema audit across all 31 exported tools (`docs/mcp-tools.json`): **100/100 Grade A (`0` errors, `0` warnings, 5310 est. tokens/turn, 10/10 rules passed)**.

## Version 0.4.0 advanced video workflow toolkit & token optimization

- **44 automated tests passed locally** on macOS (Python 3.13.18 venv, PyAV 16.1.0, imageio-ffmpeg 0.8.1, MCP SDK 1.30.0) and **93 relative documentation links + 26-tool MCP reference** checked cleanly.
- **New verified coverage (`test_workflows_v4.py` & `test_mcp.py`):**
  - Synthesizing branded H.264/AAC title cards (`create_card`), non-destructive clip splitting (`split_clip`), per-clip color grades/fades/volume/lower-third ASS overlays, `crossfade` (`xfade` + `acrossfade`) joins, and EBU R128 loudness normalization verified by duration, dimension, and receipt checks.
  - Pixel-level frame check on `noir` grade + `boxed` burned-in captions in `square` resolution (`720×720`) alongside soft `mov_text` track.
  - Extended speed range (`4.0×` chained `atempo`), `90°` rotation + horizontal flip into `reels` preview (`540×960`), and real storyboard PNG / audio waveform bucket extraction.
  - CLI `card` and `inspect` end-to-end execution.
  - Desktop Tkinter `Studio` widget verification (asset selection, timeline assembly, playhead clip splitting, clip effects application, timeline transition styling, undo).
  - Compact `EditorialAgent` prompt verification (omitting duplicated JSON Schema, compact cues JSON, under 400 chars system prompt).
  - AgentFlight MCP schema audit across all 26 exported tools (`docs/mcp-tools.json`): **100/100 Grade A (`0` errors, `0` warnings)**, vs baseline 0.3.2 (`0/100 Grade F`, `50` warnings).
  - Cross-platform OS matrix tests for v0.4.0 will run via GitHub Actions on push (`tests.yml`).

## Version 0.3.2 packaging

The 38-test core suite and documentation checks passed locally. A clean macOS installation from the release ZIP created an isolated environment, installed the included wheel and dependencies, rendered and verified the synthetic demo, reused both cached segments, and completed a real MCP handshake using its generated configuration. The launcher was exercised from an installation path containing spaces.

The Release workflow gates publication on these package smoke checks and the core suite across Python 3.10, 3.11 and 3.12 on Ubuntu 22.04 x64, Windows Server 2022 x64, macOS 15 Apple Silicon and macOS 15 Intel. The Python 3.10 suite skips the TOML parser unit test because stdlib tomllib starts at Python 3.11. Check the release's workflow result for the actual remote outcome. The matrix does not certify desktop visual behavior, every consumer OS version, or optional GPU adapters. See [release compatibility](docs/releases.md).

## Version 0.3.1

**38 automated tests passed locally** on macOS / Python 3.12 in approximately eight seconds. The new checks cover JSON/TOML configuration parsing, paths containing spaces, preservation of the environment's Python executable, invalid setup inputs, transcript metadata discovery/pagination, and an executable documented MCP client that renders selected cues and reads a verification receipt. The integration test launches the server using generated configuration; it also compares published input schemas with discovered tools and checks prompt discovery.

Documentation checks validate 73 relative links, five client configuration templates, and the 21-tool reference. These checks run in CI as well. Setup formats were checked against official vendor documentation and the installed Codex/Claude Code CLI help. The installed Codex CLI also accepted generated settings through a read-only configuration override; no user settings were changed. This does not certify a full interactive session in every vendor client or every client release. Machine-specific configurations are generated for the user to merge; the generator does not change client settings.

The previous 0.3 release passed the full 34-test suite on GitHub Actions for Linux, macOS and Windows. Consult Actions for the current commit's remote results. The previous core/media limitations below still apply.

## Version 0.3

**34 automated tests passed locally** on macOS / Python 3.12, using PyAV 16.1.0, imageio-ffmpeg 0.8.1 and official MCP SDK 1.30.0. The final suite completed in approximately 6.1 seconds on this machine. This is a small synthetic-fixture test suite, not a production performance benchmark.

Coverage:

- Legacy workflow validation, output isolation, failure/cancel state and real export with audio.
- Real-media quiet-section analysis with padding; no-audio keep-all behavior; all-quiet fallback (parser response injected for this case).
- Source preservation, immutable revision links and plan comparison.
- Reordering red/blue source sections, checked by decoding output frames and examining first/last colors, with exact 60-frame output for the two-second edit.
- Mixed silent/audio sources, speed adjustment and full 720×1280 portrait export.
- Output receipt checksums and unchanged-segment reuse across identical and partially revised plans.
- Invalid ranges, non-finite values, invalid options, path traversal and symlink escape rejection.
- Changed media snapshot and edited plan detection.
- Queued cancellation, running-process cancellation, timeout and failed-process diagnostics.
- Actual MCP stdio client/server initialization, tool discovery, rejected out-of-root import, media import, cut proposal, plan readback, asynchronous preview render and guide-resource discovery.

**Desktop acceptance check passed:** the actual Tk application selected a plan, changed a source range, created a child revision, restored its parent, rendered a preview, enabled playback and kept key controls within the window. This check exercised widgets programmatically. The computer-use service could not attach to this Python window, so a screenshot review and physical click-through were not completed.

New coverage in 0.3:

- Supplied SRT parsing, chronological timing validation, transcript integrity, search and exact cue-based selections.
- Captions retimed across source cuts, reordering and speed changes; real MP4 subtitle stream plus extracted SRT readback.
- Agent grounding, duration budgets, unknown action/ID rejection, one-repair limit and authoritative source quotes. Unit tests inject model responses; they do not measure model quality.
- Competing-renderer rejection and recovery of persisted unfinished jobs. This simulates interrupted state, not an OS power-loss test.
- MCP transcript import/readback/selection, strict nested input schemas, disabled-agent behavior and render receipts.

**New desktop acceptance passed:** the transcript panel loaded saved cues, selected the first and last source sections, created a four-second plan, preserved captions through a trim and undo, and rendered a playable preview. Key controls fit within the default window. This was a programmatic widget check, not a physical click-through or comprehensive accessibility audit.

**Real local-model smoke test:** an already-installed Ollama `qwen3.5:0.8b` model selected the requested first and last cues of a six-second synthetic fixture. The resulting four-second portrait preview completed verification. Draft plus render took about 4.2 seconds in this run with cached video segments. The model's explanation misstated what the last cue said, despite choosing the correct ID. This motivated returning actual source quotes separately from unverified model explanations. One tiny fixture does not establish editorial quality, general accuracy or performance.

**Packaging:** editable installation with the MCP extra succeeded. A distributable wheel is built separately during release preparation.

A GitHub Actions workflow is included for Python 3.12 on Ubuntu, macOS and Windows. Check the repository's Actions page for actual remote results; the existence of that workflow is not proof that every platform has passed.

## What is still unverified

- The optional PySceneDetect, Auto-Editor, vid.stab, color-matcher, rembg, RIFE, Real-ESRGAN, Demucs, librosa and HyperFrames adapters have not had end-to-end acceptance tests here.
- Variable-frame-rate edge cases, rotated phone video, offset/multiple audio tracks, HDR handling, long-video resource use, repeated failure recovery and large projects need broader coverage.
- No built-in speech recognition or systematic aesthetic/editorial quality evaluation. Transcript-based selection is implemented, but broad real-footage and adversarial-model evaluation remains outstanding.
- No cross-product benchmark establishes a speed/quality advantage over existing editors.

## Reproduce

```sh
python -m pip install -e '.[mcp]'
python -m unittest discover -s tests -v
```

Tests generate their own footage. They do not require user videos or model downloads. A working FFmpeg binary is required; the core package's imageio-ffmpeg fallback provides one on supported platforms.
