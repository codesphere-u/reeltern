"""Print client configuration without editing the user's settings."""
import json
from pathlib import Path
import sys

CLIENTS = ('claude-code', 'codex', 'cursor', 'vscode', 'generic')


def configuration(client, workspace, media_root, agent_model=None):
    if client not in CLIENTS:
        raise ValueError('Unsupported MCP client')
    media = Path(media_root).expanduser().resolve()
    if not media.is_dir():
        raise ValueError('Media root must be an existing directory')
    project = Path(workspace).expanduser().resolve()
    if project.exists() and not project.is_dir():
        raise ValueError('Workspace must be a directory')
    # Preserve the virtual environment executable; resolving its symlink can
    # select the system interpreter and lose installed dependencies.
    command = str(Path(sys.executable).absolute())
    args = ['-m', 'reeltern.cli', 'mcp', '--workspace', str(project), '--media-root', str(media)]
    if agent_model is not None:
        if not isinstance(agent_model, str) or not agent_model.strip() or len(agent_model) > 200 or 'cloud' in agent_model.casefold():
            raise ValueError('Choose an installed local model, not a cloud model')
        args += ['--agent-model', agent_model]
    entry = {'command': command, 'args': args}
    if client == 'codex':
        # JSON basic strings/arrays are valid TOML for these values; ensure_ascii
        # False avoids JSON surrogate escapes for non-BMP path characters.
        encode = lambda value: json.dumps(value, ensure_ascii=False)
        return ('[mcp_servers.reeltern]\ncommand = ' + encode(command) + '\nargs = ' + encode(args)
                + '\nstartup_timeout_sec = 30\ntool_timeout_sec = 300\n')
    if client == 'vscode':
        value = {'servers': {'reeltern': {'type': 'stdio', **entry}}}
    else:
        if client == 'claude-code':
            entry['type'] = 'stdio'
            entry['timeout'] = 300000
        value = {'mcpServers': {'reeltern': entry}}
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'
