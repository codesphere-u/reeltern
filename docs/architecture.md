# Architecture and invariants

Desktop Studio, the command line and MCP all call `Workspace` and `Renderer`. They do not maintain separate editing logic.

```text
Local video → copied snapshot + SHA-256 ID → analysis
                                           ↓
                                  immutable edit plan
                                           ↓
                                  review / child revision
                                           ↓
                            queued preview or final render
                                           ↓
                              verified MP4 + receipt
```

## Workspace

- `assets/<hash>.media` holds copied source bytes; `assets/<hash>.json` records name and probe information.
- `analysis/<hash>.json` records parameters, quiet intervals, retained ranges and caveats.
- `transcripts/<hash>.json` stores supplied cue text and source timing; `agent_runs/<id>.json` stores bounded inference decisions and validation outcomes.
- `plans/<hash>.json` holds the complete normalized timeline. Its ID is a canonical JSON hash; modifying it outside the application invalidates it.
- `cache/<hash>.mkv` holds normalized H.264/PCM segments; a companion JSON checksum protects reuse from accidental corruption.
- `jobs/<id>.json` records status. `jobs/<id>/` contains final media, plan, receipt and process logs.

Original input files are read and copied, never modified. Asset hashes are checked before analysis/rendering and again before final success. Plan edits create a new file and may reference a parent. Hashing is integrity checking, not access control or a signature.

## Timing and audio

Source ranges are in seconds. Output durations are quantized to whole frames at 30 fps. Each clip has an explicit frame count and timeline start. FFmpeg normalizes geometry, sample aspect ratio, frame rate, audio tempo, stereo channels and 48 kHz audio. Clips without audio receive silence.

Intermediate audio is PCM, avoiding repeated AAC encoder priming across cuts. The final concatenation copies normalized video and encodes audio once. A receipt is emitted only after probing dimensions/duration, decoding both streams without errors, and rechecking source hashes. This verifies technical integrity, not aesthetic quality or perfect perceptual lip sync.

## Reuse and cancellation

The segment key includes source identity, source range, speed, output dimensions, fit, renderer version and FFmpeg version. Editorial reasons and timeline placement do not change the segment's pixels, so reordering can reuse it. Corrupted or missing cache entries are rerendered.

One executor serializes render jobs within a server. Jobs report queued/running/verifying/complete/failed/cancelled. Subprocesses use argument arrays, no shell, and disk logs to avoid unbounded output buffering. Cancellation terminates, then kills if necessary, and waits for process exit. Temporary and partial outputs are not promoted to a successful result.

An OS-held workspace lock prevents concurrent renderer instances. The next owner after a crash marks unfinished jobs interrupted, making them eligible for an explicit retry with segment reuse. Preview and full export have separate cached resolutions. Cache eviction, quotas, disk preflight, automatic worker restart and distributed workers are future work.

## Design choices

- Use an explicit cut plan before introducing a language-model planner. This makes proposed edits reviewable and independently executable.
- Keep the first-pass heuristic transparent. Louder does not mean more meaningful.
- Keep optional research models outside the tested core, so an unavailable GPU/model cannot silently change ordinary editing behavior.
- Prefer honest status and technical verification over a broad list of claimed AI features.

## Evidence-constrained editorial agent

A local Ollama request sees a bounded transcript window and brief. It returns IDs and short reasons, never code or raw timestamps. The validator checks known unique IDs, allowed fields and whole-cue duration. One repair is permitted. Selected source text is attached independently from model paraphrases; a valid selection is not proof of preserved meaning. A draft is saved before any separate render request.

Attached transcript cues are intersected with source selections, retimed by speed and timeline position, and emitted as SRT plus a selectable MP4 subtitle stream. Mid-cue trims preserve full cue text and require review because word-level alignment is unavailable.
