"""Executable MCP recipe. Run with the interpreter that has Reeltern's MCP extra."""
import argparse
import asyncio
import json
from pathlib import Path
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from reeltern.client_config import configuration
from reeltern.transcript import parse_srt


async def edit(args):
    config = json.loads(configuration('generic', args.workspace, args.media_root))['mcpServers']['reeltern']
    async with stdio_client(StdioServerParameters(**config)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            async def call(name, arguments):
                result = await session.call_tool(name, arguments)
                if result.isError:
                    raise RuntimeError(f'{name}: {result.content}')
                return json.loads(result.content[0].text)
            await call('capabilities', {})
            asset = await call('import_media', {'path': args.input})
            if args.srt:
                value = await call('register_transcript', {'asset_id': asset['id'], 'cues': parse_srt(args.srt.read_text(encoding='utf-8-sig'))})
                page = await call('get_transcript', {'transcript_id': value['id']})
                if not args.cue_ids:
                    return {'transcript': page, 'next': 'Review cues, then rerun with --cue-ids c00001 c00002. No plan or render created.'}
                plan = await call('plan_from_transcript', {'transcript_id': value['id'], 'cue_ids': args.cue_ids, 'preset': args.preset})
            else:
                plan = await call('suggest_edit', {'asset_id': asset['id'], 'preset': args.preset})
            result = {'plan': await call('get_plan', {'plan_id': plan['id']})}
            if not args.render:
                return result
            job = await call('render_plan', {'plan_id': plan['id'], 'preview': not args.final})
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                state = await call('job_status', {'job_id': job['id']})
                if state['status'] == 'complete':
                    result.update(job=state, receipt=await call('get_render_receipt', {'job_id': job['id']}))
                    return result
                if state['status'] in ('failed', 'cancelled', 'interrupted'):
                    raise RuntimeError(json.dumps(state))
                await asyncio.sleep(.5)
            await call('cancel_job', {'job_id': job['id']})
            raise TimeoutError('Render exceeded the example timeout; cancellation requested')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--media-root', required=True)
    parser.add_argument('--input', required=True, help='Absolute path or path relative to media root')
    parser.add_argument('--srt', type=Path)
    parser.add_argument('--cue-ids', nargs='+')
    parser.add_argument('--preset', choices=['landscape', 'portrait', 'square'], default='landscape')
    parser.add_argument('--render', action='store_true', help='Render after creating a plan')
    parser.add_argument('--final', action='store_true', help='Use full resolution; requires --render')
    parser.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    if args.final and not args.render:
        parser.error('--final requires --render')
    if args.cue_ids and not args.srt:
        parser.error('--cue-ids requires --srt')
    if not 0 < args.timeout <= 3600:
        parser.error('--timeout must be greater than zero and at most 3600')
    print(json.dumps(asyncio.run(edit(args)), indent=2))


if __name__ == '__main__':
    main()
