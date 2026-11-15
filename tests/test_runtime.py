import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
from reeltern.media import Cancelled, atomic_json, execute, read_json


class RuntimeTests(unittest.TestCase):
    def test_running_process_is_cancelled_and_reaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = threading.Event()
            timer = threading.Timer(.3, event.set)
            timer.start()
            try:
                with self.assertRaises(Cancelled):
                    execute([sys.executable, '-c', 'import time; time.sleep(20)'], Path(tmp), event)
            finally:
                timer.cancel()

    def test_failed_process_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, 'intentional failure'):
                execute([sys.executable, '-c', 'import sys; print("intentional failure"); sys.exit(3)'], Path(tmp))

    def test_process_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, 'exceeded'):
                execute([sys.executable, '-c', 'import time; time.sleep(20)'], Path(tmp), timeout=.1)

    def test_atomic_json_and_read_json_retry_permission_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'job.json'
            real_replace = os.replace
            replace_attempts = []

            def flaky_replace(src, dst):
                replace_attempts.append((src, dst))
                if len(replace_attempts) < 3:
                    raise PermissionError(5, 'Access is denied')
                return real_replace(src, dst)

            with mock.patch('reeltern.media.os.replace', side_effect=flaky_replace), mock.patch('reeltern.media.time.sleep'):
                atomic_json(target, {'status': 'complete', 'ok': True})

            self.assertEqual(len(replace_attempts), 3)
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

            real_read_text = Path.read_text
            read_attempts = []

            def flaky_read_text(self_path, *args, **kwargs):
                read_attempts.append(self_path)
                if len(read_attempts) < 3:
                    raise PermissionError(5, 'Access is denied')
                return real_read_text(self_path, *args, **kwargs)

            with mock.patch.object(Path, 'read_text', flaky_read_text), mock.patch('reeltern.media.time.sleep'):
                data = read_json(target)

            self.assertEqual(len(read_attempts), 3)
            self.assertEqual(data, {'status': 'complete', 'ok': True})
