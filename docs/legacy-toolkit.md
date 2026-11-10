> This is the original 0.1 adapter workflow. Use the main README for the new cut-plan editor. Optional engines remain experimental.

# Legacy optional-engine toolkit

**Your footage. In full flight.**

A local desktop starter that connects eleven open-source video tools through one reusable workflow. No account, subscription or language-model API is required. This is a developer preview, not a finished timeline editor or a one-click installer.

## Start here

Requires Python 3.10+ with Tkinter and an FFmpeg build with H.264 encoding. Python 3.11 is a practical starting point for the optional AI packages; their compatibility requirements differ.

Get the source from [codesphere-u/reeltern](https://github.com/codesphere-u/reeltern):

```sh
git clone https://github.com/codesphere-u/reeltern.git
cd reeltern
```

From this project folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
reeltern doctor
reeltern toolkit
```

Windows: activate with `.venv\Scripts\activate`. Linux may require your distribution's `python3-tk` package. Install FFmpeg from https://ffmpeg.org/download.html and put it on PATH. If using Homebrew on macOS, `brew install ffmpeg` provides basic export; check for the vidstab filters separately.

In the window, choose a video and results folder, leave **Export MP4** selected, then click **Run workflow**. Each run creates a new `job-*` folder. Open the video path reported in `manifest.json`. Originals are never edited. **Check tools** reports discovery only, not a full model/hardware readiness test.

## What each integration does

| Step | Behavior in this starter | Setup |
|---|---|---|
| PySceneDetect | Writes scene boundaries and separate clips; keeps current video | `pip install -e '.[analysis]'` |
| Auto-Editor | Removes quiet regions with 0.2-second margins | Install upstream CLI; put `auto-editor` on PATH |
| vid.stab | Two-pass motion stabilization | FFmpeg with `vidstabdetect` and `vidstabtransform` |
| color-matcher | Matches every frame to a reference image | `pip install -e '.[frames]'` |
| rembg | Extracts foreground and composites over charcoal | Same frames extra; u2net weights download on first use |
| RIFE | Normalizes to 30 fps, interpolates 2× at 30 fps for silent slow motion | Separate RIFE checkout, environment and weights |
| Real-ESRGAN | Upscales frames 4× and restores source audio | Upstream `realesrgan-ncnn-vulkan` binary and model files |
| Demucs | Exports vocals, drums, bass and other stems; leaves video audio unchanged | Separate Demucs environment/CLI |
| librosa | Writes beat times and splits source every fourth detected beat | Analysis extra; source must have audio |
| HyperFrames | Renders your complete HTML project as the new current video | Install upstream HyperFrames CLI; provide project containing `index.html` |
| FFmpeg | H.264/AAC MP4 export with even dimensions | FFmpeg on PATH |

Scenes, beats and stems are side outputs: later steps continue from the current video, not from the individual clips. Beat splitting is not an automatic montage of multiple shots. HyperFrames renders an authored composition; include your footage in that composition if needed. It does not automatically create or overlay titles. Select only the steps relevant to your edit.

All adapters are implemented, but optional-engine renders have not yet been validated in this environment. See `VALIDATION.md` for exact test coverage. The dependency ranges are starting constraints, not a certified compatibility matrix.

## Configure separate engines

Avoid putting every AI package in one Python environment. RIFE and Demucs in particular may need their own dependency versions. Follow the official repositories linked in `SOURCES.md`.

Environment settings:

- `REELTERN_FFMPEG`: full path to FFmpeg, if absent from PATH.
- `REELTERN_AUTO_EDITOR`: full path to Auto-Editor.
- `REELTERN_DEMUCS`: full path to the Demucs executable in its environment.
- `REELTERN_REALESRGAN_NCNN_VULKAN`: full path to its executable. Keep its upstream model layout intact.
- `REELTERN_HYPERFRAMES`: full path to an already installed HyperFrames executable. No implicit `npx` download is performed by this app.
- `REELTERN_RIFE_DIR`: checkout containing `inference_video.py` and populated `train_log/`.
- `REELTERN_RIFE_PYTHON`: full path to Python in the RIFE environment.

Model weights and third-party binaries are not included. Initial model downloads need internet and consume disk space; after setup, the selected local models process your media locally. HTML compositions can include remote assets or scripts, so use trusted projects and local assets for offline rendering.

## Reusable workflows

Save a workflow from the desktop window, then run it from the command line:

```sh
reeltern validate my-edit.json
reeltern run my-edit.json --output renders
```

Example (relative media paths resolve beside the JSON file):

```json
{
  "version": 1,
  "input": "footage.mp4",
  "steps": [
    {"op": "trim"},
    {"op": "stabilize"},
    {"op": "color", "reference": "reference.jpg"},
    {"op": "export"}
  ]
}
```

CLI workflows preserve your specified order. The desktop window uses a fixed sensible order. Each completed step records its output in `manifest.json`; external tool details go into `process.log`. Failures stop the workflow. Cancel interrupts managed external commands; in-process model loading, scene detection and beat analysis can take time to return. There is no resume or rollback of partial results yet.

## Current limits

- SDR prototype: frame effects normalize to 30 fps and re-encode to H.264. HDR, color-management metadata, multiple audio tracks and subtitles are not preserved.
- Frame effects materialize PNGs, which can take substantial disk space. Start with a short 720p clip. Results retain intermediate files for inspection.
- Background removal and color transfer run independently per frame; temporal flicker is possible. Transparent video export is not implemented.
- Slow motion deliberately drops audio. Run audio analysis before slow motion if you need stems or beats.
- RIFE, upscaling and Demucs can be slow on CPU; NCNN upscaling requires a compatible Vulkan device/runtime. This project's hardware paths are not yet benchmarked.
- This UI is a workflow launcher, not a timeline, preview player, multitrack mixer, or natural-language editing agent.
- GUI loading of saved workflows, custom background choice, arbitrary export formats, rendered title templates, scene-aware interpolation, smart montage assembly and dependency installers are future work.

## Development

```sh
python -m unittest discover -s tests -v
```

FFmpeg integration tests skip when FFmpeg is unavailable. New adapters should validate dependencies, use argument lists rather than shell commands, preserve source media, fail on missing output, and document timing/audio behavior. Add real-media tests for each supported engine before a public release.

## License

Reeltern's original code is GPL-3.0-or-later; see the root `LICENSE`. No warranty. The GPL choice accommodates the intended color-matcher integration. Third-party engines, binaries and model weights retain their respective terms; this license does not relicense them. Before distributing bundled engines or weights, record the precise versions and include their required license notices and source provisions. See the root `SOURCES.md`.

After setup, macOS users can double-click `Launch.command`; Windows users can run `Launch.bat`. Alternatively run `sh Launch.command` from Terminal on macOS.
