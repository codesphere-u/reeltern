# Reeltern

**Your footage. In full flight.**

[![Tests](https://github.com/codesphere-u/reeltern/actions/workflows/tests.yml/badge.svg)](https://github.com/codesphere-u/reeltern/actions/workflows/tests.yml)
[![License: GPL v3 or later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)

[Quick start](#get-started) · [Editorial agent](docs/editorial-agent.md) · [MCP reference](docs/mcp.md) · [Validation](VALIDATION.md)

A local video editor for people and AI assistants. Turn footage into an inspectable cut plan, revise it without losing the original, preview the result, and export a verified video.

**Version 0.3 · early preview.** Transcript-first editing, a bounded local editorial agent, and reversible video workflows. The core is tested on synthetic media; the local agent has also been exercised with an installed Ollama model. The eleven optional upstream adapters remain experimental. This is not a full multitrack editor or a finished consumer product.

## Why this exists

An automated edit should be something you can examine and change. Reeltern keeps the source ranges, reasons, playback speeds and output timing behind every cut. An assistant and a person use the same saved plan, and every revision can be revisited.

- **Edit from text:** import an SRT transcript, search/select actual sentences, and create a captioned edit with source timestamps.
- **Local editorial agent:** give an installed Ollama model a brief. It can select only real transcript cues, has a duration budget and at most one repair attempt, and produces a draft with quoted evidence.
- **Captions that follow cuts:** source captions are retimed across trimming, reordering and speed changes, with SRT and selectable MP4 subtitle outputs.
- **Reversible editing:** original media is copied into content-addressed snapshots; plans are immutable revisions with parent links.
- **Conservative first pass:** propose cuts from quiet audio, with margins. No audio or entirely quiet audio retains the footage instead of deleting everything.
- **A real timeline:** combine sources, trim, reorder, remove clips, and change speed from 0.5× to 2× while adjusting audio tempo.
- **Review before export:** inspect exact ranges and reasons in the desktop editor; preview at half resolution; compare revisions through MCP or Python.
- **Three output shapes:** landscape, portrait and square. Preserve the image with padding or choose center cropping explicitly.
- **Verified rendering:** completed exports pass dimension/duration checks, full video/audio decoding and source-integrity checks. Each has an edit plan and verification receipt.
- **Faster revisions and recovery:** unchanged encoded segments are reused after a checksum check. Interrupted jobs can be explicitly retried; a workspace lock prevents competing renderers.
- **MCP access:** twenty typed tools expose this same workflow to an MCP-compatible assistant. No arbitrary shell tool or network server is exposed.

## Get started

Python 3.10–3.12 is the intended range; this release was tested locally on Python 3.12/macOS. A Python installation with Tkinter is needed for the desktop interface. The CLI and MCP do not require Tkinter.

```sh
git clone https://github.com/codesphere-u/reeltern.git
cd reeltern
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[mcp]'
reeltern gui
```

Windows: activate with `.venv\Scripts\activate`. Linux desktop installations may need `python3-tk`. FFmpeg is supplied by `imageio-ffmpeg` on supported platforms, with an installed system FFmpeg preferred. Set `REELTERN_FFMPEG` to select a specific build. Some platforms may need a system FFmpeg installation.

1. **Import footage.** Select one or more local videos.
2. **Keep all / assemble** creates a timeline, or **Suggest quiet cuts** proposes a first pass for one selected video.
3. Select a clip, change its source in/out points or speed, and choose **Apply revision**. Reorder/remove clips as needed.
4. Choose **Preview edit**, wait for completion, then **Play completed video** in your default player.
5. Choose **Export final MP4**. The results folder contains the video, plan, logs and receipt.

The desktop uses a fixed, readable timeline table rather than a waveform/drag-and-drop timeline. **Undo to parent** and **Earlier plans** restore previous edits. `contain` preserves the whole image; `cover` crops the center. Neither tracks faces.

You can also launch the installed desktop app with `Launch.command` on macOS or `Launch.bat` on Windows. These launchers assume the dependencies above are installed.

## Try it before importing your footage

```sh
reeltern demo --workspace demo-project
```

This creates a small synthetic source, removes its middle section, exports a captioned preview, and demonstrates segment reuse. It needs no model download or user footage. Open the result path printed by the command.

## Edit from a brief or transcript

Select one video in the desktop editor and choose **Transcript & AI**. Import an SRT, then either keep selected cues or enter a brief and an installed local Ollama model name. Every AI output remains a draft you can inspect and revise.

```sh
reeltern transcript interview.mp4 interview.srt --workspace my-project
# Use the transcript ID printed above:
reeltern agent TRANSCRIPT_ID "Keep the explanation and conclusion, preserving qualifications" \
  --workspace my-project --model YOUR_INSTALLED_MODEL --seconds 45
```

No speech-recognition engine is bundled. Bring a transcript from your preferred tool. An MCP assistant can also select transcript cues directly, without Ollama. [Full editorial workflow](docs/editorial-agent.md).

## One-command first pass

```sh
# Propose a cut plan without rendering
reeltern edit footage.mp4 --workspace my-project

# Propose and render a portrait preview
reeltern edit footage.mp4 --workspace my-project --preset portrait --preview

# Propose and render a final landscape video
reeltern edit footage.mp4 --workspace my-project --render
```

The CLI prints the saved plan and job outcome. Quietness is a signal, not a judgment about what matters: review the plan before relying on it for a final edit.

## Connect an AI assistant

Install the MCP extra above. Configure your MCP client with the full path to the environment's Python executable:

```json
{
  "mcpServers": {
    "reeltern": {
      "command": "/absolute/path/to/reeltern/.venv/bin/python",
      "args": [
        "-m", "reeltern.cli", "mcp",
        "--workspace", "/absolute/path/to/my-project",
        "--media-root", "/absolute/path/to/footage"
      ]
    }
  }
}
```

This is a generic client configuration example; each client may use a different configuration format. On Windows, use the environment's `Scripts/python.exe` and JSON-escaped paths. Only one renderer can own a workspace at a time; a second instance receives a clear error. No account credentials or API keys are required by Reeltern. Your chosen assistant may have its own pricing and data-handling policies.

Example request to the connected assistant:

> Import interview.mp4 from the footage folder. Propose conservative quiet-section cuts, explain the source ranges you would remove, and create a portrait preview. Keep the whole image rather than cropping it. Show me the result and keep the original plan so we can undo changes.

See [MCP tool reference](docs/mcp.md) for the workflow and [architecture](docs/architecture.md) for persistence and timing details.

## The eleven-tool ecosystem

The original optional integrations are retained under:

```sh
reeltern toolkit
reeltern doctor
reeltern run workflow.json --output renders
```

They cover PySceneDetect, Auto-Editor, vid.stab, color-matcher, rembg, RIFE, Real-ESRGAN, Demucs, librosa, HyperFrames and FFmpeg. See [adapter setup and limitations](docs/legacy-toolkit.md) and [upstream sources](SOURCES.md).

The new cut-plan editor uses FFmpeg directly for its tested first-pass analysis and render path. Optional adapters are not silently substituted into that path or exposed through MCP. You can explicitly import an adapter's completed output into the editor. Their GPU/model setups still need separate acceptance testing.

## Boundaries of this release

- SDR, 30 fps, H.264/AAC MP4 output. Only the first video/audio streams are used. HDR, original metadata, subtitles, chapters and multitrack audio are not preserved.
- No built-in transcription, face/motion tracking, transitions or generative video. The local agent can propose transcript-based selections, but its editorial judgment and explanations are not guaranteed. Review the returned source evidence. Captions come from supplied text; they are not speech-verified or burned in.
- Faster/slower playback uses ordinary frame-rate conversion and audio tempo adjustment. It does not invoke RIFE interpolation.
- Analysis and imports run locally and can take time on long videos. Render jobs are queued and cancellable; analysis/import cancellation is not implemented.
- After a crash, the next renderer marks unfinished jobs as interrupted. MCP can retry them as new jobs and reuse verified segments. There is no automatic background restart or mid-encoder resume.
- Snapshots and segment caches use disk space and are not automatically evicted. Start with short footage and monitor available storage. Input limit: 8 GiB per file; timeline limit: 200 clips/four hours; queue limit: eight outstanding renders per server.
- The workspace is trusted local state, not a sandbox against malicious local processes. Import footage you trust. MCP restricts imports to the configured media directory and rejects traversal/symlink escapes. Paths and edit metadata may be visible to your MCP client; video is not automatically uploaded.
- No one-click installer, package-registry release, or claim of production readiness. See [validation](VALIDATION.md) for exactly what was checked.

## A shared workflow, not a black box

```mermaid
flowchart LR
  A[Local footage + supplied transcript] --> B[Human or AI draft]
  B --> C[Immutable plan + source evidence]
  C --> D[Review and revise]
  D --> E[Captioned preview]
  E --> F[Verified final export]
```

The same engine serves desktop, CLI and MCP. An assistant's proposal does not become an irreversible edit, and a successful encoder exit is not the only export check.

## Contribute

```sh
python -m pip install -e '.[mcp]'
python -m unittest discover -s tests -v
```

Tests generate their own media and exercise the real encoder, decoder and MCP stdio transport. See [CONTRIBUTING.md](CONTRIBUTING.md) for the quality bar and near-term priorities.

## License

Reeltern is GPL-3.0-or-later. See [LICENSE](LICENSE). Third-party engines and model weights retain their own licenses. Their inclusion in this ecosystem does not grant permission to redistribute arbitrary binaries or weights. No model weights are included here.
