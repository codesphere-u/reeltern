"""Install an extracted release bundle, render its demo, and exercise its real MCP launcher."""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check_server(config):
    async with stdio_client(StdioServerParameters(**config)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 21
            result = await session.call_tool('capabilities', {})
            assert not result.isError, result
            assert json.loads(result.content[0].text)['version'] == '0.3.2'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='reeltern release ') as temp:
        root = Path(temp)
        with zipfile.ZipFile(args.archive) as archive:
            archive.extractall(root)
        folder = next(root.iterdir())
        subprocess.run([sys.executable, str(folder/'install.py')], check=True)
        python = folder/'.venv'/('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        # Test launcher with spaces in its installation path, not just Python imports.
        launcher = [str(folder/'reeltern.cmd')] if sys.platform == 'win32' else ['sh', str(folder/'reeltern.sh')]
        demo = root/'demo'
        subprocess.run([*launcher, 'demo', '--workspace', str(demo)], check=True, cwd=root)
        report = json.loads((demo/'demo-report.json').read_text())
        assert report['edit_seconds'] == 4 and report['cache_hits'] == 2
        config = subprocess.check_output([str(python), '-m', 'reeltern.cli', 'mcp-config', 'generic', '--workspace', str(root/'mcp-project'), '--media-root', str(demo/'demo-input')], text=True)
        entry = json.loads(config)['mcpServers']['reeltern']
        assert Path(entry['command']) == python
        asyncio.run(check_server(entry))
        print('PASS: clean bundle installation, launcher, verified render, cache reuse and MCP handshake')


if __name__ == '__main__':
    main()
