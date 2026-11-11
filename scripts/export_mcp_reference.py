"""Generate the machine-readable tool reference from the running Python definitions."""
import asyncio
import json
from pathlib import Path
import tempfile
from reeltern.mcp_server import create_server


async def export():
    with tempfile.TemporaryDirectory() as temp:
        server, renderer = create_server(Path(temp)/'workspace', temp)
        try:
            return {'transport': 'stdio', 'tools': [t.model_dump(mode='json', exclude_none=True) for t in await server.list_tools()]}
        finally:
            renderer.close()


if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1]/'docs'/'mcp-tools.json'
    target.write_text(json.dumps(asyncio.run(export()), indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(target)
