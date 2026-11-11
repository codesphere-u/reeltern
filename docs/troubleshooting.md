# Troubleshooting

| Symptom | Check and resolution |
|---|---|
| `No module named reeltern` / `mcp` | Run the exact Python path in the client configuration with `-m pip show reeltern mcp`. Install `'.[mcp]'` from the repository with that interpreter. Regenerate config after moving an environment. |
| Server starts in a terminal but not the client | Use generated absolute executable/argument paths. Check client logs. Stdio is launched by the client; do not run it as an HTTP service. A terminal apparently waiting after `reeltern mcp` is normal. |
| No tools appear | Restart the configured server/session, check its enabled/trusted state and call `capabilities`. The current release exposes 21 tools. Check whether the client expects `mcpServers`, `servers`, or TOML. |
| `Another Reeltern renderer owns this workspace` | Close the other Studio/MCP process or choose a different workspace. Do not delete the lock file to bypass a live owner. OS locks are released when their process exits. |
| Import rejected | The file must exist under the configured media root, including after resolving symlinks. A relative import is relative to that root. Use paths on the server's machine. |
| `draft_edit` is disabled | Select cues with the assistant and `plan_from_transcript`, or restart with `--agent-model` and an already installed local Ollama model. |
| Local model request fails | Check that Ollama is running at the configured loopback address and that the installed model supports structured JSON. No automatic model installation occurs. See `agent_runs/` for the decision error. |
| Tool times out | Large imports/analysis and optional inference may exceed the client's timeout. Generated Codex/Claude configs allow five minutes. Inspect saved artifacts before repeating; a timeout is not proof of cancellation. Rendering uses job polling. |
| Job failed or interrupted | Read `job_status`; fix the cause. Use `retry_job` for a new attempt. Keep the client running until completion. A completed partial file without a successful job/receipt is not a verified export. |
| Captions are invisible | The MP4 has selectable subtitles, not burned-in text. Enable subtitles in your player or use `captions.srt`. Social platforms may ignore embedded subtitles. |
| Captions show words trimmed out | Mid-cue trims keep the full original cue text. Supply finer-grained cues or edit boundaries to complete cues; word-level alignment is planned. |
| Source looks cropped | `cover` center-crops; revise the plan with `fit: contain` to preserve the whole image with padding. No face tracking is implemented. |
| `doctor` reports missing tools | `doctor` checks optional legacy tools too. Missing RIFE/Demucs/etc. does not mean core editing is unavailable. Run the core demo to check the installed render path. |
| GUI fails to import Tkinter | Install a Python build with Tk support (often `python3-tk` on Linux), or use CLI/MCP. |

## Useful diagnostics

```sh
python --version
python -m pip show reeltern mcp av imageio-ffmpeg
python -m reeltern.cli --help
python -m reeltern.cli demo --workspace diagnostic-demo
```

`jobs/<id>.json` has persisted status. `jobs/<id>/` contains logs and, on success, output, plan and verification receipt. `agent_runs/<id>.json` contains local model decision reports. Files can contain local paths, transcript text and prompts; sanitize them before sharing in a public issue.

Include your OS, Python/Reeltern versions, client name/version, exact failing step, sanitized error and a minimal sample you have permission to share. A screenshot alone may not show a subprocess error. See [validation limits](../VALIDATION.md) before assuming a media format is supported.
