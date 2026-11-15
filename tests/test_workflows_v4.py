import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_studio import fixture
from reeltern.media import ff, probe
from reeltern.render import Renderer
from reeltern.workspace import Workspace
from reeltern import transcript


class AdvancedWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.media = Path(cls.shared.name)
        cls.source = fixture(cls.media)
        cls.silent = fixture(cls.media, 'silent.mp4', audio=False)

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

    def _render(self, plan, preview=True):
        job = self.renderer.submit(plan['id'], preview)
        result = self.renderer.wait(job['id'], timeout=60)
        self.assertEqual(result['status'], 'complete', result)
        return result

    def test_create_card_split_and_crossfade_transition_render(self):
        card = self.ws.create_card(
            title='Episode 1',
            subtitle='Local Edit Test',
            duration=1.2,
            preset='landscape',
            background='#0f172a',
            accent='#38bdf8',
        )
        self.assertAlmostEqual(card['duration'], 1.2, delta=0.1)
        self.assertTrue(card['audio'])

        base = self.ws.create_plan([
            {'asset_id': card['id'], 'start': 0, 'end': 1.2, 'reason': 'Title card'},
            {'asset_id': self.asset['id'], 'start': 0, 'end': 2.0, 'reason': 'Intro clip'},
        ])
        split = self.ws.split_clip(base['id'], 1, 1.0)
        self.assertEqual(len(split['clips']), 3)
        styled = self.ws.update_clip(
            split['id'],
            1,
            {'grade': 'cinematic', 'fade_in': 0.2, 'fade_out': 0.2, 'volume': 0.8, 'title_overlay': 'Lower Third: Part A'},
        )
        crossed = self.ws.update_plan_style(
            styled['id'],
            transition='crossfade',
            transition_duration=0.3,
            normalize_audio=True,
        )
        self.assertLess(crossed['duration'], styled['duration'])
        result = self._render(crossed, preview=True)
        info = probe(result['output'])
        self.assertEqual((info['width'], info['height']), (640, 360))
        self.assertAlmostEqual(info['duration'], crossed['duration'], delta=0.12)
        receipt = json.loads(Path(result['receipt']).read_text(encoding='utf-8'))
        self.assertIn('crossfade transition', receipt['verified'])
        self.assertIn('EBU R128 loudness normalization', receipt['verified'])

    def test_noir_grade_and_burned_in_captions_modify_pixels(self):
        evidence = transcript.register(self.ws, self.asset['id'], [
            {'start': 0, 'end': 1.5, 'text': 'Burned caption visibility check'},
            {'start': 2.5, 'end': 4.0, 'text': 'Second line with contrast'},
        ])
        plain = transcript.select(self.ws, evidence['id'], ['c00001'])
        noir_burned = self.ws.create_plan(
            [{'asset_id': self.asset['id'], 'start': 0, 'end': 1.5, 'grade': 'noir', 'speed': 0.5}],
            preset='square',
            transcript_ids=[evidence['id']],
            caption_mode='both',
            caption_style='boxed',
        )
        self.assertEqual(noir_burned['duration'], 3.0)
        result = self._render(noir_burned, preview=False)
        info = probe(result['output'])
        self.assertEqual((info['width'], info['height']), (720, 720))
        self.assertEqual(info['subtitle_tracks'], 1)
        receipt = json.loads(Path(result['receipt']).read_text(encoding='utf-8'))
        self.assertIn('burned-in boxed captions', receipt['verified'])
        self.assertEqual(plain['preset'], 'landscape')

        import av
        with av.open(result['output']) as c:
            frame = next(c.decode(video=0)).reformat(width=32, height=32, format='rgb24')
            data = bytes(frame.planes[0])
            # Noir grade turns RGB channels nearly monochrome (|R - G| small everywhere) before overlay pixels.
            diffs = [abs(data[i] - data[i + 1]) for i in range(0, len(data), 3)]
            self.assertLess(sum(diffs) / len(diffs), 12)

    def test_wide_speed_range_rotate_and_storyboard_waveform(self):
        visuals = self.ws.inspect_visuals(self.asset['id'], thumbs=4, samples=24)
        self.assertTrue(visuals['waveform']['has_audio'])
        self.assertEqual(len(visuals['waveform']['samples']), 24)
        self.assertGreaterEqual(len(visuals['storyboard']), 1)
        for thumb in visuals['storyboard']:
            self.assertTrue(Path(thumb['path']).is_file())

        fast_rotated = self.ws.create_plan(
            [{'asset_id': self.asset['id'], 'start': 0, 'end': 4.0, 'speed': 4.0, 'rotate': 90, 'flip': 'horizontal'}],
            preset='reels',
        )
        result = self._render(fast_rotated, preview=True)
        info = probe(result['output'])
        self.assertEqual((info['width'], info['height']), (540, 960))
        self.assertAlmostEqual(info['duration'], 1.0, delta=0.12)

    def test_cli_card_and_inspect_commands(self):
        res_card = subprocess.run(
            [sys.executable, '-m', 'reeltern.cli', 'card', 'CLI Title', '--workspace', str(self.ws.root), '--duration', '1.0'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(res_card.returncode, 0, res_card.stderr)
        card_data = json.loads(res_card.stdout)
        self.assertEqual(len(card_data['id']), 64)

        res_inspect = subprocess.run(
            [sys.executable, '-m', 'reeltern.cli', 'inspect', str(self.source), '--workspace', str(self.ws.root), '--thumbs', '3', '--samples', '16'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(res_inspect.returncode, 0, res_inspect.stderr)
        vis = json.loads(res_inspect.stdout)
        self.assertEqual(len(vis['waveform']['samples']), 16)

    def test_agent_prompt_token_reduction(self):
        from unittest.mock import patch
        from reeltern.agent import EditorialAgent
        tr = transcript.register(self.ws, self.asset['id'], [
            {'start': 0, 'end': 1, 'text': 'Opening point.'},
            {'start': 3, 'end': 4, 'text': 'Closing point.'},
        ])
        agent = EditorialAgent(self.ws, 'test-local')
        captured = {}
        payload = json.dumps({'summary': 'Compact', 'selections': [{'cue_id': 'c00001', 'reason': 'ok'}]})

        def capture_req(messages):
            captured['messages'] = messages
            return payload

        with patch.object(agent, 'request', side_effect=capture_req):
            agent.draft(tr['id'], 'Keep opening', 2)
        sys_prompt = captured['messages'][0]['content']
        user_prompt = captured['messages'][1]['content']
        # Compact system prompt omits bloated full JSON Schema (enforced via Ollama `format`) and uses compact cue keys.
        self.assertNotIn('additionalProperties', sys_prompt)
        self.assertIn('"cues":[', user_prompt)
        self.assertLess(len(sys_prompt), 400)

    def test_studio_desktop_widgets_and_actions(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f'No graphical display available for Tk test: {exc}')
        root.withdraw()
        # Release parent fixture lock before Studio claims workspace ownership.
        self.renderer.close()
        from reeltern.studio import Studio
        app = None
        try:
            app = Studio(root, self.ws.root)
            self.assertEqual(len(app.assets.get_children()), 1)
            app.assets.selection_set(self.asset['id'])
            app.assemble()
            self.assertIsNotNone(app.plan)
            app.timeline.selection_set('0')
            app.select_clip()
            app.playhead_sec = 1.5
            app.split_at_playhead()
            self.assertEqual(len(app.plan['clips']), 2)
            app.timeline.selection_set('0')
            app.select_clip()
            app.fx_fields['grade'].set('warm')
            app.fx_fields['title_overlay'].set('Opening Scene')
            app.apply_clip_effects()
            self.assertEqual(app.plan['clips'][0]['grade'], 'warm')
            app.tl_fields['transition'].set('dissolve')
            app.apply_timeline_style()
            self.assertEqual(app.plan['transition'], 'dissolve')
            app.undo()
            self.assertNotIn('transition', app.plan)
        finally:
            if app is not None:
                app.renderer.close()
            root.destroy()
