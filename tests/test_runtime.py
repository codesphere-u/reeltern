import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from reeltern.media import Cancelled, execute


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
