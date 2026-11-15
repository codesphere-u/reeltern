import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import tkinter as tk
import unittest
import wave

import av

from test_studio import fixture

from reeltern.director import audit_job_render, compose_plan
from reeltern.effects import CAPTION_STYLES, COLOR_GRADES, FIT_MODES, MOTIONS, TRANSITIONS
from reeltern.media import ff
from reeltern.render import Renderer
from reeltern.studio import Studio
from reeltern.transcript import register
from reeltern.workspace import Workspace


def write_wav(path: Path, seconds: float = 2.0, freq: float = 220.0, rate: int = 16000) -> Path:
    total = int(rate * seconds)
    samples = bytearray()
    for i in range(total):
        val = int(5000 * math.sin(2.0 * math.pi * freq * (i / rate)))
        samples.extend(struct.pack('<h', val))
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(bytes(samples))
    return path


def rgb_pixel(frame, x: int, y: int):
    rgb = frame.reformat(format='rgb24')
    stride = rgb.planes[0].line_size
    buf = bytes(rgb.planes[0])
    row = y if y >= 0 else rgb.height + y
    idx = row * stride + x * 3
    return buf[idx], buf[idx + 1], buf[idx + 2]


def rgb_lower_bytes(frame) -> bytes:
    rgb = frame.reformat(format='rgb24')
    stride = rgb.planes[0].line_size
    buf = bytes(rgb.planes[0])
    start = int(rgb.height * 0.65)
    return b''.join(buf[r * stride : r * stride + rgb.width * 3] for r in range(start, rgb.height))


class DirectorV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.media = Path(cls.shared.name)
        cls.video = fixture(cls.media, 'speech.mp4', audio=True)
        cls.silent = fixture(cls.media, 'silent.mp4', audio=False)
        cls.bgm = write_wav(cls.media / 'bgm.wav', seconds=2.5, freq=260.0)
        cls.dark = ff(
            ['-f', 'lavfi', '-i', 'color=black:s=160x90:r=24:d=1', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo:d=1', '-c:v', 'libx264', '-c:a', 'aac', cls.media / 'dark.mp4'],
            cls.media,
        ) or (cls.media / 'dark.mp4')

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Workspace(Path(self.temp.name) / 'workspace', self.media)
        self.asset = self.ws.import_media('speech.mp4')
        self.renderer = Renderer(self.ws)
        self.addCleanup(self.renderer.close)

    def render(self, plan, preview=True):
        job = self.renderer.submit(plan['id'], preview)
        result = self.renderer.wait(job['id'], timeout=45)
        self.assertEqual(result['status'], 'complete', result)
        return result

    def test_import_audio_and_reject_invalid(self):
        audio = self.ws.import_audio('bgm.wav')
        self.assertEqual(audio['kind'], 'audio')
        self.assertEqual(audio['width'], 0)
        self.assertTrue(audio['audio'])
        self.assertAlmostEqual(audio['duration'], 2.5, delta=0.1)

        with self.assertRaises(ValueError):
            self.ws.import_audio('speech.mp4')
        bad_txt = self.media / 'notes.txt'
        bad_txt.write_text('not audio', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.ws.import_audio('notes.txt')

    def test_blur_fill_vs_contain_and_progress_bar_pixels(self):
        contain_plan = self.ws.create_plan(
            [{'asset_id': self.asset['id'], 'start': 0.0, 'end': 1.0}],
            preset='portrait',
            fit='contain',
        )
        blur_plan = self.ws.create_plan(
            [{'asset_id': self.asset['id'], 'start': 0.0, 'end': 1.0}],
            preset='portrait',
            fit='blur_fill',
            progress_bar=True,
        )
        contain_res = self.render(contain_plan, preview=True)
        blur_res = self.render(blur_plan, preview=True)

        with av.open(contain_res['output']) as c:
            top_contain = next(c.decode(video=0))
            contain_pixel = rgb_pixel(top_contain, 180, 12)
        with av.open(blur_res['output']) as c:
            frames = list(c.decode(video=0))
            blur_pixel = rgb_pixel(frames[10], 180, 12)
            bar_px = rgb_pixel(frames[-2], 100, -3)

        # Top margin in portrait contain is near black; blur_fill has rich red halo.
        self.assertLess(contain_pixel[0], 20)
        self.assertGreater(blur_pixel[0], 80)

        # Late frame at bottom progress bar x=100 must show blue accent (#3B82F6 -> high blue channel).
        self.assertGreater(bar_px[2], bar_px[0] + 80, f'Expected blue progress bar pixel, got {bar_px}')

        receipt = json.loads(Path(blur_res['receipt']).read_text(encoding='utf-8'))
        self.assertIn('blur-fill framing', receipt['verified'])
        self.assertIn('accent progress bar', receipt['verified'])

    def test_motion_zoom_in_and_pan_right_duration_and_frames(self):
        plan = self.ws.create_plan(
            [
                {'asset_id': self.asset['id'], 'start': 0.0, 'end': 1.0, 'motion': 'zoom_in'},
                {'asset_id': self.asset['id'], 'start': 2.0, 'end': 3.0, 'motion': 'pan_right'},
            ],
            preset='landscape',
            fit='contain',
        )
        res = self.render(plan, preview=True)
        with av.open(res['output']) as c:
            frames = list(c.decode(video=0))
        self.assertEqual(len(frames), 60)
        receipt = json.loads(Path(res['receipt']).read_text(encoding='utf-8'))
        self.assertAlmostEqual(receipt['output']['duration'], 2.0, delta=0.06)
        self.assertIn('camera motion', receipt['verified'])

    def test_kinetic_captions_and_voice_cleanup_ducked_music_mix(self):
        bgm = self.ws.import_audio('bgm.wav')
        tr = register(self.ws, self.asset['id'], [{'start': 0.0, 'end': 1.8, 'text': 'Launch Day Ship Faster'}])
        plain = self.ws.create_plan(
            [{'asset_id': self.asset['id'], 'start': 0.0, 'end': 1.6}],
            preset='landscape',
        )
        polished = self.ws.create_plan(
            [{'asset_id': self.asset['id'], 'start': 0.0, 'end': 1.6}],
            preset='landscape',
            transcript_ids=[tr['id']],
            caption_mode='both',
            caption_style='kinetic',
            voice_cleanup=True,
            music_asset_id=bgm['id'],
            music_volume=0.22,
            music_ducking=True,
            normalize_audio=True,
        )
        plain_res = self.render(plain, preview=True)
        pol_res = self.render(polished, preview=True)

        with av.open(plain_res['output']) as c1, av.open(pol_res['output']) as c2:
            self.assertGreaterEqual(len(c2.streams.subtitles), 1)
            b1 = rgb_lower_bytes(list(c1.decode(video=0))[20])
            b2 = rgb_lower_bytes(list(c2.decode(video=0))[20])
        diff = sum(1 for a, b in zip(b1, b2) if abs(a - b) > 12)
        self.assertGreater(diff, 200)

        receipt = json.loads(Path(pol_res['receipt']).read_text(encoding='utf-8'))
        for expected in (
            'burned-in kinetic captions',
            'voice cleanup EQ/compressor',
            'music bed (sidechain ducked)',
            'EBU R128 loudness normalization',
        ):
            self.assertIn(expected, receipt['verified'])

    def test_inspect_visuals_contact_sheet_scene_cuts_and_energy_peaks(self):
        visuals = self.ws.inspect_visuals(self.asset['id'], thumbs=4, samples=24)
        sheet = Path(visuals['contact_sheet'])
        self.assertTrue(sheet.exists())
        self.assertTrue(sheet.read_bytes().startswith(b'\x89PNG'))
        telemetry = visuals['telemetry']
        self.assertIn('luma_avg', telemetry)
        self.assertIn('contrast_score', telemetry)
        self.assertIn('black_frames', telemetry)
        self.assertGreaterEqual(len(telemetry['scene_cuts']), 1)
        self.assertTrue(any(abs(cut - 2.0) < 0.8 for cut in telemetry['scene_cuts']), telemetry['scene_cuts'])
        self.assertIn('energy_peaks', visuals['waveform'])

    def test_compose_video_viral_reel_and_cinematic_and_audit_render(self):
        bgm = self.ws.import_audio('bgm.wav')
        tr = register(self.ws, self.asset['id'], [{'start': 0.0, 'end': 1.2, 'text': 'Ship Fast Every Week'}])
        viral = compose_plan(
            self.ws,
            [self.asset['id']],
            director_style='viral_reel',
            intro_title='Hook Card',
            transcript_id=tr['id'],
            music_asset_id=bgm['id'],
        )
        plan = viral['plan']
        self.assertEqual(plan['fit'], 'blur_fill')
        self.assertEqual(plan['preset'], 'reels')
        self.assertEqual(plan['caption_style'], 'kinetic')
        self.assertTrue(plan['progress_bar'])
        self.assertTrue(plan['voice_cleanup'])
        self.assertEqual(plan['music_asset_id'], bgm['id'])
        self.assertGreaterEqual(len(plan['clips']), 2)  # intro slate + footage

        res = self.render(plan, preview=True)
        qa = audit_job_render(self.ws, self.renderer, res['id'])
        self.assertIn('luma_avg', qa)
        self.assertIn('contrast_score', qa)
        self.assertIn('lufs', qa)
        self.assertIn('true_peak_db', qa)
        self.assertTrue(Path(qa['contact_sheet']).exists())

        cine = compose_plan(self.ws, [self.asset['id']], director_style='cinematic')
        self.assertEqual(cine['plan']['preset'], 'fhd')
        self.assertEqual(cine['plan']['transition'], 'crossfade')
        self.assertEqual(cine['plan']['clips'][0]['grade'], 'cinematic')

        # Dark footage should be flagged by audit_job_render.
        dark_asset = self.ws.import_media('dark.mp4')
        dark_plan = self.ws.create_plan([{'asset_id': dark_asset['id']}], preset='landscape')
        dark_job = self.render(dark_plan, preview=True)
        dark_qa = audit_job_render(self.ws, self.renderer, dark_job['id'])
        self.assertFalse(dark_qa['passed'])
        self.assertGreater(dark_qa['black_frames'], 0)
        self.assertTrue(dark_qa['issues'])

    def test_cli_import_audio_compose_and_audit(self):
        ws_dir = Path(self.temp.name) / 'cli-ws'
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        run = lambda *args: subprocess.run(
            [sys.executable, '-m', 'reeltern.cli', *args],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        aud = json.loads(run('import-audio', str(self.bgm), '--workspace', str(ws_dir)).stdout)
        self.assertEqual(aud['kind'], 'audio')
        comp = json.loads(
            run(
                'compose',
                str(self.video),
                '--workspace',
                str(ws_dir),
                '--style',
                'viral_reel',
                '--music',
                str(self.bgm),
                '--preview',
                '--audit',
            ).stdout
        )
        self.assertIn('composition_summary', comp)
        self.assertEqual(comp['composition_summary']['director_style'], 'viral_reel')
        self.assertIn('job', comp)
        self.assertIn('audit', comp)
        job_id = comp['job']['id']
        qa_only = json.loads(run('audit', job_id, '--workspace', str(ws_dir)).stdout)
        self.assertEqual(qa_only['job_id'], job_id)
        self.assertTrue(Path(qa_only['contact_sheet']).exists())

    def test_studio_v5_widgets_and_actions(self):
        try:
            root = tk.Tk()
        except (tk.TclError, RuntimeError) as exc:
            self.skipTest(f'Tk unavailable: {exc}')
        root.withdraw()
        app = Studio(root, Path(self.temp.name) / 'studio-ws')
        try:
            self.assertIn('teal_orange', COLOR_GRADES)
            self.assertIn('blur_fill', FIT_MODES)
            self.assertIn('kinetic', CAPTION_STYLES)
            self.assertIn('fadeblack', TRANSITIONS)
            self.assertIn('zoom_in', MOTIONS)
            self.assertIn('motion', app.fx_fields)
            self.assertIn('voice_cleanup', app.tl_fields)
            self.assertIn('progress_bar', app.tl_fields)

            with self.assertRaises(ValueError):
                app.audit_render()

            vid = app.ws.import_media(self.video)
            aud = app.ws.import_audio(self.bgm)
            app.refresh_assets()
            plan = app.ws.create_plan([{'asset_id': vid['id'], 'start': 0.0, 'end': 1.2}])
            app.show_plan(plan)
            app.timeline.selection_set('0')
            app.select_clip()
            app.fx_fields['grade'].set('teal_orange')
            app.fx_fields['motion'].set('zoom_in')
            app.apply_clip_effects()
            self.assertEqual(app.plan['clips'][0]['grade'], 'teal_orange')
            self.assertEqual(app.plan['clips'][0]['motion'], 'zoom_in')

            app.fit.set('blur_fill')
            app.tl_fields['voice_cleanup'].set(True)
            app.tl_fields['progress_bar'].set(True)
            app.tl_fields['caption_style'].set('kinetic')
            app.tl_fields['transition'].set('fadeblack')
            app.apply_timeline_style()
            self.assertEqual(app.plan['fit'], 'blur_fill')
            self.assertTrue(app.plan['voice_cleanup'])
            self.assertTrue(app.plan['progress_bar'])
            self.assertEqual(app.plan['caption_style'], 'kinetic')
            self.assertEqual(app.plan['transition'], 'fadeblack')

            composed = compose_plan(app.ws, [vid['id']], director_style='documentary', music_asset_id=aud['id'])
            app.show_plan(composed['plan'])
            self.assertEqual(app.plan['music_asset_id'], aud['id'])

            self.assertTrue(callable(app.load_demo))
            self.assertTrue(callable(app.switch_workspace))
            self.assertTrue(callable(app.connect_ai_dialog))
        finally:
            app.renderer.close()
            root.destroy()

    def test_studio_default_workspace_and_cli_alias(self):
        from unittest.mock import patch
        from reeltern.studio import resolve_default_workspace
        with patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(resolve_default_workspace(None), Path.home() / 'ReelternWorkspace')
            self.assertEqual(resolve_default_workspace('/tmp/custom-ws'), Path('/tmp/custom-ws'))
        res = subprocess.run([sys.executable, '-m', 'reeltern.cli', 'studio', '--help'], capture_output=True, text=True, check=True)
        self.assertIn('--workspace', res.stdout)

    def test_mcp_reference_sync_and_v5_schema_bounds(self):
        ref = json.loads((Path(__file__).resolve().parents[1] / 'docs' / 'mcp-tools.json').read_text(encoding='utf-8'))
        tools = {t['name']: t for t in ref['tools']}
        self.assertEqual(len(tools), 31)
        for name in ('import_audio', 'compose_video', 'animate_clip', 'configure_audio_mix', 'audit_render'):
            self.assertIn(name, tools)
        for name, tool in tools.items():
            props = tool['inputSchema'].get('properties', {})
            self.assertLessEqual(len(props), 8, f'{name} exceeds 8 top-level params')
            self.assertTrue(tool['description'].strip())


if __name__ == '__main__':
    unittest.main()
