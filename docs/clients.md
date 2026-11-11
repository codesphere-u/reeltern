# Use Reeltern with an AI assistant

Reeltern is a local **stdio MCP server**. Claude Code, Codex, Cursor, and VS Code can launch it as a child process. Your assistant supplies the reasoning; Reeltern supplies the editing tools. **Ollama is optional**: you do not need a second model to let your existing assistant select transcript cues.

## Install and generate your configuration

From a clone of this repository, create a Python environment and install the MCP extra:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[mcp]'
python -m reeltern.cli demo --workspace demo-project
```

Windows PowerShell: use `py -3.12 -m venv .venv`, then run `.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"`. You can use that executable for every `python` command below without activating the environment.

Choose an existing footage folder and a separate folder for working files. Run one of:

```sh
python -m reeltern.cli mcp-config claude-code --workspace ./editing-project --media-root ./demo-project/demo-input
python -m reeltern.cli mcp-config codex --workspace ./editing-project --media-root ./demo-project/demo-input
python -m reeltern.cli mcp-config cursor --workspace ./editing-project --media-root ./demo-project/demo-input
python -m reeltern.cli mcp-config vscode --workspace ./editing-project --media-root ./demo-project/demo-input
```

The command prints a configuration with your environment's Python executable and absolute paths. It does not modify settings, start a model, or create a workspace. Merge the printed server entry into your existing configuration; do not replace unrelated servers. Run this with the Python environment in which you installed Reeltern. Regenerate it if you move that environment or your footage.

| Client | Where to merge the result | Format |
|---|---|---|
| Claude Code | Project `.mcp.json` | `mcpServers.reeltern` |
| Codex | `~/.codex/config.toml` | `[mcp_servers.reeltern]` |
| Cursor | Project `.cursor/mcp.json` | `mcpServers.reeltern` |
| VS Code | Project `.vscode/mcp.json` | `servers.reeltern`, type `stdio` |
| Another local MCP client | Run `mcp-config generic`; follow its settings format | Command + argument array |

Example files with placeholder paths are in [examples/clients](../examples/clients/). Prefer generated configuration for actual use. Absolute paths are machine-specific: keep your personal configuration out of shared commits. Use different workspace folders if two clients will run at the same time. One renderer owns a workspace at a time; close Studio before connecting MCP to that same workspace.

### Claude Code

Alternatively, register the server from your project directory with the CLI. Replace the three absolute paths:

```sh
claude mcp add --transport stdio --scope local reeltern -- /absolute/reeltern/.venv/bin/python -m reeltern.cli mcp --workspace /absolute/editing-project --media-root /absolute/footage
```

Inspect with `claude mcp get reeltern` or `/mcp`. Project configuration may require client trust/approval. Generated JSON includes a five-minute tool timeout. [Official Claude Code MCP documentation](https://code.claude.com/docs/en/mcp).

### Codex

Alternatively register the same launcher:

```sh
codex mcp add reeltern -- /absolute/reeltern/.venv/bin/python -m reeltern.cli mcp --workspace /absolute/editing-project --media-root /absolute/footage
codex mcp get reeltern
```

Generated TOML sets a 30-second startup timeout and a 300-second tool timeout; CLI registration alone does not add those settings. Add them when using slower analysis or the optional local agent. [Official Codex MCP documentation](https://developers.openai.com/codex/mcp).

### Cursor and VS Code

Merge the generated entry into the file in the table, then use the client's MCP controls to enable/restart it and inspect startup errors. VS Code uses a different top-level JSON key from Cursor. [Cursor documentation](https://cursor.com/docs/mcp) · [VS Code configuration reference](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).

The configuration formats were checked against these official references on 11 November 2026. The generated launcher is exercised through the official Python MCP client in tests. Client UI sessions and every vendor release are not certified by that test.

## Verify the connection

Ask your assistant:

> Use Reeltern's capabilities tool and list_assets. Tell me which media root it can access and whether the local editorial agent is enabled. Do not import or render anything yet.

You should see 21 tools, stdio transport, the configured media root, and the current version. Tool names may gain a client-specific prefix. This checks the real connection rather than relying on a config file's existence.

Then try the generated demo footage:

> Import synthetic-source.mp4 with Reeltern. Make a landscape plan keeping source seconds 0–2 and 4–6, in that order. Render a preview, wait until it completes, read the verification receipt, and show me the output path. The synthetic source has a tone, not speech.

For your own footage, use the [agent workflow](agent-workflow.md). An assistant must receive a supplied transcript to select by spoken content. File import alone does not expose video frames or speech to the model.

## Optional local editorial model

Add `--agent-model YOUR_INSTALLED_MODEL` to `mcp-config` if you want the server's `draft_edit` tool to call your existing local Ollama service. No model download happens automatically. Direct selection with `plan_from_transcript` works without it. See [editorial agent limits](editorial-agent.md).

Rendering returns a job ID promptly. Keep the client session open and poll `job_status`; stopping the MCP process can interrupt work. An inference or analysis call may take longer than a client's default timeout. A client timeout does not prove the underlying operation was cancelled; inspect saved plans/jobs before repeating it.

## Privacy and remote environments

Reeltern processes media on the machine running its server. Your assistant provider may receive tool results, transcript text, names, paths and prompts according to its own settings. Local rendering does not make a cloud assistant private. Use the separate local agent only when that meets your needs and your Ollama service is configured locally.

This release has no hosted HTTP endpoint, authentication layer or remote media transfer. A cloud-only client cannot reach your laptop through a stdio configuration. In WSL, containers, SSH or remote workspaces, install Reeltern there and use paths visible there. Windows host paths and Linux guest paths are not interchangeable.

See [troubleshooting](troubleshooting.md) for setup, locks, captions and job failures.
