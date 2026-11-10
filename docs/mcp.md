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
2. Analyze or create a manual plan.
3. Inspect and explain exact cut ranges. Silence detection does not identify speech, filler words, mistakes or importance.
4. Save revisions using `create_plan`. Compare when useful.
5. Call `render_plan` with `preview: true`; poll `job_status` until a terminal state.
6. Report the local preview only when status is `complete`. On `failed`, report the error rather than claiming a usable video.
7. Once the desired plan is clear, render it with `preview: false`.

The `reeltern://guide` resource and `first_pass` prompt provide this workflow to clients. Servers do not upload completed files or open them automatically. A client may choose to display/open the local path using its own capabilities.

## Scope and shutdown

The media root is a startup setting, not a tool argument an assistant can widen. Only supported local video files inside that directory can be imported. All job artifacts are under the workspace. No arbitrary executable, filtergraph, network fetch or HTML execution is exposed. The legacy optional-engine launcher is a separate trusted desktop/CLI workflow.

The server supports one active renderer with a bounded queue. Clean shutdown requests cancellation and reaps managed render processes. Hard crashes can leave an incomplete job status; there is no durable worker service or automatic recovery yet. Use one server instance per workspace, and do not give it untrusted workspace contents.
