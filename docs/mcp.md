# MCP tools

Reeltern uses the official Python MCP SDK's supported 1.x line (`mcp>=1.28,<2`), tested with 1.30.0. This explicit upper bound avoids implicitly migrating to the SDK's newer major API. The server uses stdio; stdout is reserved for protocol messages. SDK diagnostics go to stderr.

| Tool | Purpose |
|---|---|
| `capabilities` | Discover features and limits |
| `import_media` | Copy an allowed local video into a verified source snapshot |
| `list_assets` | Inspect imported names, durations, dimensions and audio availability |
| `analyze_audio` | Detect quiet intervals and suggested kept ranges |
| `suggest_edit` | Save a conservative first-pass plan |
| `create_plan` | Save a multi-clip timeline or child revision |
| `get_plan` | Inspect every cut, source time, reason, speed and output time |
| `list_plans` | Discover saved versions |
| `compare_plans` | Compare ordered selections, duration and output format |
| `render_plan` | Queue a preview or final export; returns a job ID |
| `job_status` | Check progress, result paths or failure |
| `cancel_job` | Request cancellation of a job owned by the current server |
| `register_transcript` | Save supplied timecoded cues for an asset |
| `get_transcript` | Read a bounded page of cue IDs and text |
| `search_transcript` | Find source cues by words |
| `plan_from_transcript` | Build a captioned plan from selected cue IDs |
| `draft_edit` | Ask an explicitly configured local model for a constrained draft |
| `list_jobs` | Discover recent jobs, including interrupted runs |
| `get_render_receipt` | Inspect technical verification evidence |
| `retry_job` | Retry a failed, cancelled or interrupted job as a new job |

Read tools have read-only annotations. Import, analysis, planning and rendering have non-destructive write annotations. Analysis creates a cache file, so it is not labeled read-only. Tool annotations describe intended behavior; client-side authorization remains the client's responsibility.

## Example plan

`create_plan` accepts:

```json
{
  "clips": [
    {"asset_id": "<ID returned by import_media>", "start": 2.5, "end": 7.0, "speed": 1, "reason": "User-selected opening"},
    {"asset_id": "<ID returned by import_media>", "start": 12.0, "end": 16.5, "speed": 1.25, "reason": "Shorten the selected demonstration"}
  ],
  "preset": "portrait",
  "fit": "contain",
  "notes": "Opening and demonstration, with source context preserved"
}
```

Start/end values always refer to the original imported source, not the previous timeline. Clip array order is playback order. Add `parent` with the previous plan ID to keep a revision relationship. Plans do not mutate one another. The output includes source and timeline coordinates.

## Recommended interaction

1. Confirm which user-selected footage to use; import it.
2. Register a supplied transcript and inspect/search its cues, or analyze audio for a silence-based first pass.
3. Inspect and explain exact cut ranges. Silence detection does not identify speech, filler words, mistakes or importance.
4. Save revisions using `create_plan`. Compare when useful.
5. Call `render_plan` with `preview: true`; poll `job_status` until a terminal state.
6. Report the local preview only when status is `complete`. On `failed`, report the error rather than claiming a usable video.
7. Once the desired plan is clear, render it with `preview: false`.

The `reeltern://guide` resource, `first_pass` prompt and `editorial_draft` prompt provide these workflows to clients. Carry `transcript_ids` forward when revising a captioned plan with `create_plan`. Servers do not upload completed files or open them automatically. A client may choose to display/open the local path using its own capabilities.

## Scope and shutdown

The media root is a startup setting, not a tool argument an assistant can widen. Only supported local video files inside that directory can be imported. All job artifacts are under the workspace. No arbitrary executable, filtergraph, network fetch or HTML execution is exposed. The legacy optional-engine launcher is a separate trusted desktop/CLI workflow.

An OS-held lock enforces one renderer per workspace. Clean shutdown cancels and reaps managed processes. After a crash, the next owner marks unfinished jobs interrupted; retry_job submits a new job with the same plan and preview setting. Cached segments can be reused; there is no automatic background restart. Do not give the server untrusted workspace contents.

Imports, audio analysis and agent requests run off the MCP event loop with a concurrency limit of two, so status calls remain responsive. Agent inference is opt-in with --agent-model; see [editorial setup](editorial-agent.md). Clip and transcript cue inputs expose detailed schemas to MCP clients and reject unknown properties.
