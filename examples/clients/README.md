# Client templates

These files contain placeholder paths. Prefer `python -m reeltern.cli mcp-config CLIENT --workspace PROJECT --media-root FOOTAGE` to generate paths from your installed environment. It prints configuration only.

| Template | Destination |
|---|---|
| `claude-code.json` | Project `.mcp.json` |
| `codex.toml` | Merge into `~/.codex/config.toml` |
| `cursor.json` | Project `.cursor/mcp.json` |
| `vscode.json` | Project `.vscode/mcp.json` |
| `generic.json` | Adapt command/args to another local stdio client |

Merge just the Reeltern entry, preserving other settings. On Windows the executable is normally `.venv\Scripts\python.exe`; the generator handles path quoting. Give simultaneous clients different workspaces. See [client setup](../../docs/clients.md) for connection verification and official references.
