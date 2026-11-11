import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_studio import fixture


class DocumentedExamples(unittest.TestCase):
    def test_documented_mcp_client_renders_selected_cues(self):
        with tempfile.TemporaryDirectory(prefix='reeltern example ') as temp:
            root = Path(temp)
            media = root/'media'; media.mkdir()
            fixture(media)
            captions = root/'source.srt'
            captions.write_text('1\n00:00:00,000 --> 00:00:01,000\nOpening\n\n2\n00:00:03,000 --> 00:00:04,000\nConclusion\n', encoding='utf-8')
            script = Path(__file__).resolve().parents[1]/'examples'/'mcp_edit.py'
            result = subprocess.run([sys.executable, str(script), '--workspace', str(root/'project'), '--media-root', str(media), '--input', 'speech.mp4', '--srt', str(captions), '--cue-ids', 'c00002', 'c00001', '--render'], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value['job']['status'], 'complete')
            self.assertEqual(value['plan']['duration'], 2)
            self.assertEqual([c['start'] for c in value['plan']['clips']], [3, 0])
            self.assertTrue(Path(value['job']['captions']).is_file())
            self.assertIn('source snapshot hashes', value['receipt']['verified'])
