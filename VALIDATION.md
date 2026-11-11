# Validation — 11 November 2026

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
