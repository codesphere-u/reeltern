# Validation — 11 November 2026

## Version 0.2

**22 automated tests passed locally** on macOS / Python 3.12, using PyAV 16.1.0, imageio-ffmpeg 0.8.1 and official MCP SDK 1.30.0. The final suite completed in approximately 5.3 seconds on this machine. This is a small synthetic-fixture test suite, not a production performance benchmark.

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

**Packaging:** editable installation with the MCP extra succeeded. A distributable wheel is built separately during release preparation.

A GitHub Actions workflow is included for Python 3.12 on Ubuntu, macOS and Windows. Check the repository's Actions page for actual remote results; the existence of that workflow is not proof that every platform has passed.

## What is still unverified

- The optional PySceneDetect, Auto-Editor, vid.stab, color-matcher, rembg, RIFE, Real-ESRGAN, Demucs, librosa and HyperFrames adapters have not had end-to-end acceptance tests here.
- Variable-frame-rate edge cases, rotated phone video, offset/multiple audio tracks, HDR handling, long-video resource use, repeated failure recovery and large projects need broader coverage.
- No semantic editing, speech recognition or aesthetic quality evaluation is implemented or claimed.
- No cross-product benchmark establishes a speed/quality advantage over existing editors.

## Reproduce

```sh
python -m pip install -e '.[mcp]'
python -m unittest discover -s tests -v
```

Tests generate their own footage. They do not require user videos or model downloads. A working FFmpeg binary is required; the core package's imageio-ffmpeg fallback provides one on supported platforms.
