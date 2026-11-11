"""Check local documentation links and configuration examples without networking."""
import json
from pathlib import Path
import re
import tomllib

root = Path(__file__).resolve().parents[1]
files = list(root.glob('*.md')) + list((root/'docs').rglob('*.md')) + list((root/'examples').rglob('*.md')) + [root/'llms.txt']
checked = 0
for source in files:
    for href in re.findall(r'\]\(([^)]+)\)', source.read_text(encoding='utf-8')):
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', href) or href.startswith('#'):
            continue
        path = href.split('#', 1)[0]
        assert (source.parent/path).exists(), f'{source.relative_to(root)}: broken link {href}'
        checked += 1
for path in (root/'examples/clients').glob('*.json'):
    value = json.loads(path.read_text(encoding='utf-8'))
    entry = value['servers' if path.stem == 'vscode' else 'mcpServers']['reeltern']
    assert entry['args'][:3] == ['-m', 'reeltern.cli', 'mcp'], path
    assert '--workspace' in entry['args'] and '--media-root' in entry['args'], path
entry = tomllib.loads((root/'examples/clients/codex.toml').read_text())['mcp_servers']['reeltern']
assert entry['tool_timeout_sec'] >= 240
reference = json.loads((root/'docs/mcp-tools.json').read_text(encoding='utf-8'))
assert len(reference['tools']) == len({t['name'] for t in reference['tools']}) == 21
print(f'Checked {checked} local links, five client configurations, and the 21-tool reference.')
