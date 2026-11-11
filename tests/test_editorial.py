import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from reeltern.workspace import Workspace
from reeltern.render import Renderer
from reeltern.agent import EditorialAgent
from reeltern.media import atomic_json, ff, probe
from reeltern import transcript
from test_studio import fixture


class EditorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.source = fixture(Path(cls.shared.name))

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Workspace(Path(self.temp.name))
        self.asset = self.ws.import_media(self.source)
        self.evidence = transcript.register(self.ws, self.asset['id'], [
            {'start': 0, 'end': 1, 'text': 'Keep this important qualification.'},
            {'start': 1, 'end': 3, 'text': 'This middle section has extra details.'},
            {'start': 3, 'end': 4, 'text': 'A useful conclusion.'}])
        self.agent = EditorialAgent(self.ws, 'test-local')

    def decision(self, *ids):
        return json.dumps({'summary': 'A concise edit.', 'selections': [{'cue_id': i, 'reason': 'Relevant to the brief'} for i in ids]})

    def test_srt_roundtrip_and_invalid_timing(self):
        raw = '\ufeff1\r\n00:00:00,000 --> 00:00:01,000\r\nHello there\r\n'
        self.assertEqual(transcript.parse_srt(raw), [{'start': 0, 'end': 1, 'text': 'Hello there'}])
        self.assertEqual(transcript.parse_srt(transcript.srt(self.evidence['cues']))[2]['text'], 'A useful conclusion.')
        with self.assertRaises(ValueError):
            transcript.parse_srt('1\n00:99:00,000 --> 00:99:01,000\ntext')

    def test_transcript_validation(self):
        for cues in [[], [{'start': 0, 'end': 9, 'text': 'outside'}], [{'start': 2, 'end': 3, 'text': 'first'}, {'start': 1, 'end': 2, 'text': 'second'}], [{'start': 0, 'end': 1, 'text': ''}]]:
            with self.assertRaises(ValueError):
                transcript.register(self.ws, self.asset['id'], cues)
        with self.assertRaises(ValueError):
            transcript.select(self.ws, self.evidence['id'], ['missing'])
        with self.assertRaises(ValueError):
            transcript.select(self.ws, self.evidence['id'], ['c00001', 'c00001'])

    def test_search_and_grounded_selection(self):
        found = transcript.search(self.ws, self.evidence['id'], 'important qualification')
        self.assertEqual(found['cues'][0]['id'], 'c00001')
        plan = transcript.select(self.ws, self.evidence['id'], ['c00003', 'c00001'])
        self.assertEqual([c['start'] for c in plan['clips']], [3, 0])
        self.assertEqual(plan['transcript_ids'], [self.evidence['id']])

    def test_caption_mapping_handles_cuts_reordering_and_speed(self):
        plan = self.ws.create_plan([{'asset_id': self.asset['id'], 'start': 3, 'end': 4, 'speed': 2}, {'asset_id': self.asset['id'], 'start': .5, 'end': 1}], transcript_ids=[self.evidence['id']])
        cues = transcript.timeline_captions(self.ws, plan)
        self.assertEqual([(c['start'], c['end']) for c in cues], [(0, .5), (.5, 1)])
        self.assertEqual(cues[0]['text'], 'A useful conclusion.')

    def test_captioned_render_is_playable_and_has_subtitle_stream(self):
        plan = transcript.select(self.ws, self.evidence['id'], ['c00001', 'c00003'])
        renderer = Renderer(self.ws)
        try:
            result = renderer.wait(renderer.submit(plan['id'], True)['id'], 30)
            self.assertEqual(result['status'], 'complete', result)
            self.assertEqual(probe(result['output'])['subtitle_tracks'], 1)
            captions = transcript.parse_srt(Path(result['captions']).read_text())
            self.assertEqual([(c['start'], c['end']) for c in captions], [(0, 1), (1, 2)])
            extracted = self.ws.root / 'extracted.srt'
            ff(['-i', result['output'], '-map', '0:s:0', extracted], self.ws.root)
            self.assertIn('A useful conclusion.', extracted.read_text())
        finally:
            renderer.close()

    def test_agent_creates_only_a_draft_using_real_ranges(self):
        with patch.object(self.agent, 'request', return_value=self.decision('c00001', 'c00003')) as model:
            result = self.agent.draft(self.evidence['id'], 'Keep qualification and conclusion.', 2)
        self.assertEqual(model.call_count, 1)
        self.assertEqual([c['start'] for c in result['plan']['clips']], [0, 3])
        self.assertEqual(result['selected_evidence'], [self.evidence['cues'][0], self.evidence['cues'][2]])
        self.assertIn('Keep this important qualification.', result['plan']['clips'][0]['reason'])
        self.assertNotIn('Relevant to the brief', result['plan']['clips'][0]['reason'])
        self.assertEqual(list((self.ws.root / 'jobs').glob('*.json')), [])
        self.assertEqual(self.ws.read('agent_runs', result['run_id'])['status'], 'draft')

    def test_agent_repairs_invalid_ids_once(self):
        with patch.object(self.agent, 'request', side_effect=[self.decision('invented'), self.decision('c00003')]) as model:
            result = self.agent.draft(self.evidence['id'], 'Conclusion only', 1)
        self.assertEqual(model.call_count, 2)
        self.assertEqual(len(self.ws.read('agent_runs', result['run_id'])['attempts']), 2)

    def test_agent_rejects_budget_and_stops_after_two_attempts(self):
        with patch.object(self.agent, 'request', return_value=self.decision('c00001', 'c00002')) as model:
            with self.assertRaisesRegex(ValueError, 'after one repair'):
                self.agent.draft(self.evidence['id'], 'Short edit', 1)
        self.assertEqual(model.call_count, 2)
        self.assertEqual(list((self.ws.root / 'plans').glob('*.json')), [])
        report = json.loads(next((self.ws.root / 'agent_runs').glob('*.json')).read_text())
        self.assertEqual(report['status'], 'failed')

    def test_agent_rejects_external_endpoints_and_cloud_names(self):
        for url in ['https://example.com', 'http://127.0.0.1.evil.test', 'http://user:pass@127.0.0.1', 'http://127.0.0.1/api', 'file:///tmp/model', 'http://127.0.0.1?x=y']:
            with self.assertRaises(ValueError):
                EditorialAgent(self.ws, 'test-local', url)
        with self.assertRaises(ValueError):
            EditorialAgent(self.ws, 'model-cloud')

    def test_agent_does_not_follow_injected_actions(self):
        malicious = json.dumps({'summary': 'Do something', 'selections': [{'cue_id': 'c00001', 'reason': 'x'}], 'command': 'delete files'})
        with patch.object(self.agent, 'request', return_value=malicious):
            with self.assertRaises(ValueError):
                self.agent.draft(self.evidence['id'], 'Short edit', 2)
        self.assertEqual(list((self.ws.root / 'plans').glob('*.json')), [])

    def test_workspace_rejects_second_renderer_and_recovers_interrupted_jobs(self):
        first = Renderer(self.ws)
        try:
            with self.assertRaisesRegex(RuntimeError, 'owns this workspace'):
                Renderer(self.ws)
        finally:
            first.close()
        identifier = 'a'*32
        atomic_json(self.ws.path('jobs', identifier), {'id': identifier, 'status': 'running'})
        recovered = Renderer(self.ws)
        try:
            self.assertEqual(recovered.status(identifier)['status'], 'interrupted')
        finally:
            recovered.close()

    def test_transcript_tampering_and_duplicate_attachments_rejected(self):
        with self.assertRaises(ValueError):
            self.ws.create_plan([{'asset_id': self.asset['id']}], transcript_ids=[self.evidence['id'], self.evidence['id']])
        path = self.ws.path('transcripts', self.evidence['id'])
        changed = json.loads(path.read_text()); changed['cues'][0]['text'] = 'changed'
        atomic_json(path, changed)
        with self.assertRaises(ValueError):
            transcript.get(self.ws, self.evidence['id'])
