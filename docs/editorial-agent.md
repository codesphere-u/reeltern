# Transcript-first editing and the local editorial agent

The editorial workflow is **brief → source evidence → constrained draft → review → render**. The agent selects real cue IDs; Reeltern derives all source times and captions from the supplied transcript. A model cannot invent a time range or execute a new tool through this interface.

## Bring a transcript

Export an SRT file from your preferred transcription service/editor, or supply timecoded cues through MCP. Reeltern does not perform speech recognition in this release.

```sh
reeltern transcript interview.mp4 interview.srt --workspace my-project
```

This prints a transcript ID. Cues must be chronological, non-overlapping and within the video. Overlapping multi-speaker captions need to be flattened before import. Text is normalized to one line per cue. Supplied text is not automatically checked against the audio.

Desktop: select one video, open **Transcript & AI**, import an SRT, select cues and choose **Keep selected cues**. This creates a new plan with captions. You can trim/reorder it in the normal editor.

MCP: `register_transcript` → `get_transcript` / `search_transcript` → `plan_from_transcript`. An external MCP assistant can select cues directly without a second model or Ollama installation.

## Optional local agent

If you already run Ollama with a local model, pass its exact installed name:

```sh
reeltern agent TRANSCRIPT_ID "Keep the explanation and conclusion, retaining any qualifications" \
  --workspace my-project --model YOUR_INSTALLED_MODEL --seconds 45 --preset portrait
```

Or enable the same tool for an MCP server:

```sh
reeltern mcp --workspace my-project --media-root footage --agent-model YOUR_INSTALLED_MODEL
```

The desktop's **Transcript & AI** panel also accepts a brief, installed model name and duration budget. No model is downloaded automatically. Without `--agent-model`, MCP's `draft_edit` returns a setup explanation; the rest of the tools still work.

The local API follows [Ollama's chat interface](https://docs.ollama.com/api/chat) and [structured output format](https://docs.ollama.com/capabilities/structured-outputs). A local model must support schema-constrained JSON. Cloud-labeled models and non-loopback endpoints are rejected. Ollama configuration remains the user's responsibility; loopback transport alone does not prove that a custom server never forwards requests.

## What the agent does

1. Loads one supplied transcript and checks source integrity.
2. Accepts a window of up to 200 complete cues / 40,000 text characters. Longer transcripts require a smaller `start`/`end` window through MCP/Python.
3. Sends the brief, cue text and timing to the configured local service; no video frames or source file path are sent.
4. Requests cue IDs with short editorial explanations, within the requested duration.
5. Rejects unknown/duplicate IDs, unsupported output fields and over-budget selections. Makes at most one correction request.
6. Creates an immutable captioned plan and a decision receipt under `agent_runs/`.

Each response includes **selected_evidence**: the actual stored text and timestamps. Treat this as the source record. The model's `decision.summary` and reasons are unverified opinions; they can be imprecise even when selected IDs are valid. Clip labels use source text, not model-generated paraphrases.

The agent does not automatically render, publish, call arbitrary tools, or claim that a draft is editorially correct. The budget is an upper bound; it does not pad a short selection to the requested duration.

## Captions follow the edit

Attached transcripts are intersected with every clip's source range, adjusted for speed, and moved to the corresponding output time. Reordered and repeated clips retain matching text. Outputs contain a `captions.srt` sidecar and a selectable MP4 subtitle track (`mov_text`). Captions are **not burned into pixels**. Enable subtitles in your player; some social platforms require burned-in captions, which this release does not produce.

Partial-cue trims retain the original full cue text because there is no word-level alignment. If you trim within a sentence, review or supply finer-grained cues. Captions reflect the supplied transcript and can be wrong if its timing/text is wrong.

## Reproducible demonstration

```sh
reeltern demo --workspace demo-project
```

The demo generates six seconds of synthetic video with a tone, selects the first and final two-second sections, retimes captions, renders a four-second preview, and renders again to demonstrate cache reuse. It needs no user footage, account, model or model download. The result paths and timings are written to `demo-report.json`.

The demo transcript describes synthetic imagery; it is not recognized speech. Its timing report is not a benchmark against other editors.
