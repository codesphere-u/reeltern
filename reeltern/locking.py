"""OS-released workspace ownership; prevents concurrent cache/job writers."""
import os


class WorkspaceLock:
    def __init__(self, path):
        self.file = open(path, 'a+b')
        self.held = False
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0, 2)
                if self.file.tell() == 0:
                    self.file.write(b'0')
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.held = True
        except OSError as exc:
            self.file.close()
            raise RuntimeError('Another Reeltern renderer owns this workspace. Close it or choose a separate workspace.') from exc

    def close(self):
        if not self.held:
            return
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.held = False
            self.file.close()
