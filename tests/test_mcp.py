import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from test_studio import fixture


class MCPIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_edit_preview_and_readback(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media = root / 'media'
            media.mkdir()
            fixture(media)
            params = StdioServerParameters(command=sys.executable, args=['-m', 'reeltern.cli', 'mcp', '--workspace', str(root / 'workspace'), '--media-root', str(media)])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listing = await session.list_tools()
                    self.assertEqual(len(listing.tools), 20)
                    async def call(name, args):
                        result = await session.call_tool(name, args)
                        self.assertFalse(result.isError, result)
                        return json.loads(result.content[0].text)
                    caps = await call('capabilities', {})
                    self.assertEqual(caps['transport'], 'stdio')
                    result = await session.call_tool('import_media', {'path': '../outside.mp4'})
                    self.assertTrue(result.isError)
                    asset = await call('import_media', {'path': 'speech.mp4'})
                    plan = await call('suggest_edit', {'asset_id': asset['id']})
                    self.assertEqual(len(plan['clips']), 2)
                    self.assertEqual((await call('get_plan', {'plan_id': plan['id']}))['id'], plan['id'])
                    job = await call('render_plan', {'plan_id': plan['id']})
                    for _ in range(200):
                        state = await call('job_status', {'job_id': job['id']})
                        if state['status'] in ('complete', 'failed', 'cancelled'):
                            break
                        await asyncio.sleep(.1)
                    self.assertEqual(state['status'], 'complete', state)
                    self.assertTrue(Path(state['output']).is_file())
                    invalid = await session.call_tool('create_plan', {'clips': [{'asset_id': asset['id'], 'shell': 'not allowed'}]})
                    self.assertTrue(invalid.isError)
                    registered = await call('register_transcript', {'asset_id': asset['id'], 'cues': [{'start': 0, 'end': 1, 'text': 'Introduction'}, {'start': 3, 'end': 4, 'text': 'Conclusion'}]})
                    cues = await call('get_transcript', {'transcript_id': registered['id']})
                    self.assertEqual(cues['total'], 2)
                    selected = await call('plan_from_transcript', {'transcript_id': registered['id'], 'cue_ids': ['c00002', 'c00001']})
                    self.assertEqual(selected['clips'][0]['start'], 3)
                    disabled = await session.call_tool('draft_edit', {'transcript_id': registered['id'], 'brief': 'Short edit'})
                    self.assertTrue(disabled.isError)
                    receipt = await call('get_render_receipt', {'job_id': job['id']})
                    self.assertIn('source snapshot hashes', receipt['verified'])
                    resources = await session.list_resources()
                    self.assertIn('reeltern://guide', [str(r.uri) for r in resources.resources])
