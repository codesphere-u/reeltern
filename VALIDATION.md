# Validation — 10 November 2026

Passed on this machine (macOS, Python 3.12):

- Five automated tests: reject unknown operations/options before writing outputs; persist failure status and preserve source; persist cancellation status; isolate each run; real FFmpeg export.
- Real-media test generates a one-second 160×90 video with a sine-wave audio track, exports H.264/AAC MP4 through the job runner, decodes both output streams successfully, and checks the original bytes remain unchanged. Paths include spaces.
- Native Tk desktop window created, ran its event loop and closed successfully. This is a launch smoke test, not a visual or full interactive acceptance test.
- Python modules compiled successfully.

FFmpeg was obtained through imageio-ffmpeg 0.8.1 in a workspace-only test environment. That environment and its binaries are not part of the source archive. The test sets REELTERN_FFMPEG explicitly; the user still needs FFmpeg setup for their installation.

Not yet validated end-to-end: PySceneDetect, Auto-Editor, vid.stab, color-matcher, rembg, RIFE, Real-ESRGAN, Demucs, librosa or HyperFrames. Their adapters follow reviewed upstream interfaces, but binary/library version differences, model compatibility, memory limits, long-video timing and GPU support require real-media acceptance tests. No production readiness or all-tools-combined render is claimed.

Before a public release: test each adapter on short fixtures; test chains including audio and variable frame rates; test cancellation during real model inference; pin validated dependency versions; verify model redistribution terms; add Windows/Linux acceptance coverage and a packaged installer.
