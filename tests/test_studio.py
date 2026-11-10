import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from reeltern.media import digest, ff, kept_ranges, silence_ranges
from reeltern.workspace import Workspace
from reeltern.render import Renderer


def fixture(folder, name='speech.mp4', audio=True):
    file = folder / name
    if audio:
        ff(['-f', 'lavfi', '-i', 'color=red:s=160x90:r=30:d=2', '-f', 'lavfi', '-i', 'color=blue:s=160x90:r=30:d=2',
            '-f', 'lavfi', '-i', r'aevalsrc=if(between(t\,1\,3)\,0\,0.3*sin(2*PI*440*t)):s=48000:d=4',
            '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-map', '2:a', '-c:v', 'libx264', '-c:a', 'aac', file], folder)
    else:
        ff(['-f', 'lavfi', '-i', 'color=green:s=96x128:r=24:d=1', '-c:v', 'libx264', file], folder)
    return file


class StudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.media = Path(cls.shared.name)
        cls.video = fixture(cls.media)
        cls.silent = fixture(cls.media, 'silent.mp4', False)

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
        result = self.renderer.wait(job['id'], timeout=40)
        self.assertEqual(result['status'], 'complete', result)
        return result

    def test_audio_analysis_removes_only_middle_silence(self):
        analysis = self.ws.analyze(self.asset['id'])
        self.assertEqual(len(analysis['kept_ranges']), 2, analysis)
        a, b = analysis['kept_ranges']
        self.assertEqual(a[0], 0)
        self.assertAlmostEqual(a[1], 1.15, delta=.08)
        self.assertAlmostEqual(b[0], 2.85, delta=.08)
        self.assertAlmostEqual(b[1], 4, delta=.03)
        self.assertEqual(analysis, self.ws.analyze(self.asset['id']))

    def test_snapshot_does_not_change_original(self):
        before = digest(self.video)
        self.ws.suggest(self.asset['id'])
        self.assertEqual(digest(self.video), before)
        self.assertEqual(digest(self.ws.path('assets', self.asset['id'], '.media')), self.asset['id'])

    def test_plan_revisions_and_order_are_preserved(self):
        original = self.ws.create_plan([{'asset_id': self.asset['id']}])
        revision = self.ws.create_plan([{'asset_id': self.asset['id'], 'start': 3, 'end': 4}, {'asset_id': self.asset['id'], 'start': 0, 'end': 1}], parent=original['id'])
        self.assertEqual(self.ws.compare(original['id'], revision['id'])['duration_change'], -2)
        self.assertEqual(self.ws.plan(original['id']), original)
        result = self.render(revision)
        import av
        with av.open(result['output']) as c:
            frames = list(c.decode(video=0))
        self.assertEqual(len(frames), 60)
        def rgb(frame):
            return bytes(frame.reformat(width=1, height=1, format='rgb24').planes[0])[:3]
        first, last = rgb(frames[0]), rgb(frames[-1])
        self.assertGreater(first[2], first[0] + 100)
        self.assertGreater(last[0], last[2] + 100)

    def test_verified_render_and_segment_reuse(self):
        plan = self.ws.suggest(self.asset['id'])
        first = self.render(plan)
        receipt = json.loads(Path(first['receipt']).read_text())
        self.assertEqual(receipt['sha256'], digest(first['output']))
        second = self.render(plan)
        self.assertEqual(second['cache_hits'], len(plan['clips']))
        clips = [{'asset_id': self.asset['id'], 'start': c['start'], 'end': c['end']} for c in plan['clips']]
        clips[1]['start'] += .2
        third = self.render(self.ws.create_plan(clips, parent=plan['id']))
        self.assertEqual(third['cache_hits'], 1)

    def test_mixed_audio_speed_and_portrait_export(self):
        silent = self.ws.import_media('silent.mp4')
        plan = self.ws.create_plan([{'asset_id': silent['id'], 'speed': 2}, {'asset_id': self.asset['id'], 'start': 0, 'end': 1, 'speed': .5}], preset='portrait')
        receipt = json.loads(Path(self.render(plan, preview=False)['receipt']).read_text())
        self.assertEqual((receipt['output']['width'], receipt['output']['height']), (720, 1280))
        self.assertAlmostEqual(receipt['output']['duration'], 2.5, delta=.05)
        self.assertTrue(receipt['output']['audio'])

    def test_silent_video_keeps_all(self):
        silent = self.ws.import_media('silent.mp4')
        plan = self.ws.suggest(silent['id'])
        self.assertEqual(len(plan['clips']), 1)
        self.assertIn('No audio', plan['notes'])

    def test_all_quiet_audio_keeps_all(self):
        with patch('reeltern.workspace.silence_ranges', return_value=[[0, 4]]):
            plan = self.ws.suggest(self.asset['id'], threshold_db=-6)
        self.assertEqual(plan['duration'], 4)
        self.assertIn('kept everything', plan['notes'])

    def test_input_and_plan_validation(self):
        for changes in [{'start': float('nan')}, {'end': 99}, {'start': 3, 'end': 1}, {'speed': True}, {'shell': 'echo test'}]:
            with self.assertRaises(ValueError):
                self.ws.create_plan([{'asset_id': self.asset['id'], **changes}])
        for action in [lambda: self.ws.create_plan([]), lambda: self.ws.plan('../outside'), lambda: self.ws.import_media('../outside.mp4')]:
            with self.assertRaises(ValueError):
                action()

    def test_symlink_import_cannot_escape_media_root(self):
        with tempfile.TemporaryDirectory() as other:
            target = Path(other) / 'outside.mp4'
            target.write_bytes(self.video.read_bytes())
            link = self.media / 'escape.mp4'
            link.symlink_to(target)
            try:
                with self.assertRaises(ValueError):
                    self.ws.import_media('escape.mp4')
            finally:
                link.unlink()

    def test_tampered_snapshot_fails_render(self):
        plan = self.ws.create_plan([{'asset_id': self.asset['id']}])
        self.ws.path('assets', self.asset['id'], '.media').write_bytes(b'changed')
        state = self.renderer.submit(plan['id'])
        result = self.renderer.wait(state['id'], 20)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('snapshot changed', result['error'])

    def test_tampered_plan_rejected(self):
        plan = self.ws.create_plan([{'asset_id': self.asset['id']}])
        plan['duration'] = 100
        self.ws.path('plans', plan['id']).write_text(json.dumps(plan))
        with self.assertRaises(ValueError):
            self.renderer.submit(plan['id'])

    def test_cancel_queued_job(self):
        gate = threading.Event()
        self.renderer.pool.submit(gate.wait)
        try:
            plan = self.ws.create_plan([{'asset_id': self.asset['id']}])
            job = self.renderer.submit(plan['id'])
            self.renderer.cancel(job['id'])
        finally:
            gate.set()
        self.assertEqual(self.renderer.wait(job['id'], 10)['status'], 'cancelled')

    def test_silence_parser_handles_boundaries(self):
        self.assertEqual(silence_ranges('silence_start: 0\nsilence_end: 1\nsilence_start: 3', 4), [[0, 1], [3, 4]])
        self.assertEqual(kept_ranges([[0, 1], [3, 4]], 4, .2), [[.8, 3.2]])
