import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from reeltern.engine import Job, validate, binary


class Workflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input video.mp4"
        self.source.write_bytes(b"not real video")
        self.recipe = {"version": 1, "input": str(self.source), "steps": [{"op": "export"}]}

    def test_invalid_step_and_options_fail_before_output(self):
        for step in ({"op": "invented"}, {"op": "export", "shell": "anything"}):
            self.recipe["steps"] = [step]
            with self.assertRaises(ValueError):
                Job(self.recipe, self.root)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_failed_job_records_failure_and_preserves_source(self):
        job = Job(self.recipe, self.root, lambda _: None)
        with patch.object(job, "preflight"), patch.object(job, "step", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                job.run()
        self.assertEqual(json.loads((job.root / "manifest.json").read_text())["status"], "failed")
        self.assertEqual(self.source.read_bytes(), b"not real video")

    def test_cancel_records_cancelled(self):
        job = Job(self.recipe, self.root, lambda _: None)
        job.cancelled.set()
        with patch.object(job, "preflight"):
            with self.assertRaises(RuntimeError):
                job.run()
        self.assertEqual(json.loads((job.root / "manifest.json").read_text())["status"], "cancelled")

    def test_unique_output_directories(self):
        self.assertNotEqual(Job(self.recipe, self.root).root, Job(self.recipe, self.root).root)

    @unittest.skipUnless(binary("ffmpeg"), "FFmpeg is not installed")
    def test_real_export_with_audio_and_spaces(self):
        self.source.unlink()
        subprocess.run([binary("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24:duration=1", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libx264", "-c:a", "aac", str(self.source)], check=True)
        original = self.source.read_bytes()
        job = Job(self.recipe, self.root, lambda _: None)
        job.run()
        manifest = json.loads((job.root / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "complete")
        result = subprocess.run([binary("ffmpeg"), "-v", "error", "-i", manifest["video"], "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(original, self.source.read_bytes())


if __name__ == "__main__":
    unittest.main()
