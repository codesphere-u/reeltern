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
            from reeltern.client_config import configuration
            config = json.loads(configuration('generic', root / 'workspace', media))['mcpServers']['reeltern']
            params = StdioServerParameters(**config)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listing = await session.list_tools()
                    self.assertEqual(len(listing.tools), 31)
                    reference = json.loads((Path(__file__).resolve().parents[1] / 'docs' / 'mcp-tools.json').read_text(encoding='utf-8'))
                    self.assertEqual({t.name: t.inputSchema for t in listing.tools}, {t['name']: t['inputSchema'] for t in reference['tools']}, 'Regenerate the documented MCP schemas')
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
                    discovered = await call('list_transcripts', {'asset_id': asset['id'], 'limit': 1})
                    self.assertEqual(discovered['transcripts'][0]['id'], registered['id'])
                    self.assertNotIn('cues', discovered['transcripts'][0])
                    self.assertEqual((await call('list_transcripts', {'offset': 1}))['transcripts'], [])
                    bad_page = await session.call_tool('list_transcripts', {'limit': 0})
                    self.assertTrue(bad_page.isError)
                    cues = await call('get_transcript', {'transcript_id': registered['id']})
                    self.assertEqual(cues['total'], 2)
                    selected = await call('plan_from_transcript', {'transcript_id': registered['id'], 'cue_ids': ['c00002', 'c00001']})
                    self.assertEqual(selected['clips'][0]['start'], 3)
                    disabled = await session.call_tool('draft_edit', {'transcript_id': registered['id'], 'brief': 'Short edit'})
                    self.assertTrue(disabled.isError)
                    card = await call('create_title_card', {'title': 'Intro Card', 'subtitle': 'Reeltern v0.5', 'duration': 1.2})
                    self.assertIn('id', card)
                    visuals = await call('inspect_media_visuals', {'asset_id': asset['id'], 'thumbs': 3, 'samples': 20})
                    self.assertGreaterEqual(len(visuals['storyboard']), 1)
                    self.assertTrue(visuals['waveform']['has_audio'])
                    self.assertTrue(Path(visuals['contact_sheet']).exists())
                    self.assertIn('scene_cuts', visuals['telemetry'])
                    import base64, math, struct, wave
                    asset_png = await session.read_resource(f"reeltern://visual/asset/{asset['id']}")
                    self.assertTrue(base64.b64decode(asset_png.contents[0].blob).startswith(b'\x89PNG'))
                    caps = await call('capabilities', {})
                    bgm_path = Path(caps['media_root']) / 'bgm.wav'
                    with wave.open(str(bgm_path), 'wb') as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(16000)
                        frames = b''.join(struct.pack('<h', int(4000 * math.sin(2 * math.pi * 220 * i / 16000))) for i in range(16000 * 2))
                        wav.writeframes(frames)
                    audio_asset = await call('import_audio', {'path': 'bgm.wav'})
                    self.assertEqual(audio_asset['kind'], 'audio')
                    split = await call('split_clip', {'plan_id': selected['id'], 'clip_index': 0, 'offset_seconds': 0.5})
                    self.assertEqual(len(split['clips']), 3)
                    styled = await call('style_clip', {'plan_id': split['id'], 'clip_index': 0, 'grade': 'cinematic', 'fade_in': 0.2, 'title_overlay': 'Chapter One'})
                    self.assertEqual(styled['clips'][0]['grade'], 'cinematic')
                    animated = await call('animate_clip', {'plan_id': styled['id'], 'clip_index': 0, 'motion': 'zoom_in', 'flip': 'horizontal'})
                    self.assertEqual(animated['clips'][0]['motion'], 'zoom_in')
                    tl_styled = await call('apply_timeline_style', {'plan_id': animated['id'], 'fit': 'blur_fill', 'transition': 'crossfade', 'caption_mode': 'burn', 'caption_style': 'kinetic', 'normalize_audio': True})
                    self.assertEqual(tl_styled['transition'], 'crossfade')
                    self.assertEqual(tl_styled['caption_mode'], 'burn')
                    mixed = await call('configure_audio_mix', {'plan_id': tl_styled['id'], 'music_asset_id': audio_asset['id'], 'music_volume': 0.18, 'music_ducking': True, 'voice_cleanup': True, 'progress_bar': True})
                    self.assertEqual(mixed['music_asset_id'], audio_asset['id'])
                    self.assertTrue(mixed['voice_cleanup'])
                    composed = await call('compose_video', {'asset_ids': [asset['id']], 'director_style': 'viral_reel', 'intro_title': 'Director Cut', 'transcript_id': registered['id'], 'music_asset_id': audio_asset['id']})
                    self.assertEqual(composed['plan']['fit'], 'blur_fill')
                    self.assertEqual(composed['composition_summary']['director_style'], 'viral_reel')
                    receipt = await call('get_render_receipt', {'job_id': job['id']})
                    self.assertIn('source snapshot hashes', receipt['verified'])
                    audit = await call('audit_render', {'job_id': job['id']})
                    self.assertIn('lufs', audit)
                    self.assertTrue(Path(audit['contact_sheet']).exists())
                    render_png = await session.read_resource(f"reeltern://visual/render/{job['id']}")
                    self.assertTrue(base64.b64decode(render_png.contents[0].blob).startswith(b'\x89PNG'))
                    resources = await session.list_resources()
                    self.assertTrue({'reeltern://guide', 'reeltern://cookbook'}.issubset({str(r.uri) for r in resources.resources}))
                    templates = await session.list_resource_templates()
                    self.assertTrue({'reeltern://visual/asset/{asset_id}', 'reeltern://visual/render/{job_id}'}.issubset({t.uriTemplate for t in templates.resourceTemplates}))
                    prompts = await session.list_prompts()
                    self.assertEqual({p.name for p in prompts.prompts}, {'first_pass', 'editorial_draft', 'viral_short', 'polish_edit'})
                    prompt = await session.get_prompt('editorial_draft', {'transcript_id': registered['id'], 'brief': 'Keep the conclusion'})
                    self.assertIn(registered['id'], prompt.messages[0].content.text)
                    viral_prompt = await session.get_prompt('viral_short', {'asset_id': asset['id'], 'intro_title': 'Hook'})
                    self.assertIn(asset['id'], viral_prompt.messages[0].content.text)
