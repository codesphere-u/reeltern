"""Entrypoint for standalone Reeltern Studio desktop executables."""
import multiprocessing
from pathlib import Path
import sys
import traceback


def _clean_argv(argv):
    # macOS LaunchServices passes -psn_0_... when opening a .app bundle from Finder.
    return [arg for arg in argv[1:] if not arg.startswith('-psn_')]


def _report_gui_error(exc):
    log_dir = Path.home() / 'ReelternWorkspace'
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / 'studio-startup.log').write_text(traceback.format_exc(), encoding='utf-8')
    except OSError:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            'Reeltern Studio Startup Error',
            f'{exc}\n\nDetails were saved to {log_dir / "studio-startup.log"}.',
        )
        root.destroy()
    except Exception:
        pass


def main():
    multiprocessing.freeze_support()
    args = _clean_argv(sys.argv)
    if not args:
        try:
            from reeltern.studio import launch
            launch()
        except Exception as exc:
            _report_gui_error(exc)
            raise SystemExit(1) from exc
        return

    sys.argv = [sys.argv[0], *args]
    from reeltern.cli import main as cli_main
    cli_main()


if __name__ == '__main__':
    main()
