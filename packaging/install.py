"""Install the included Reeltern wheel into this bundle's private environment."""
import json
from pathlib import Path
import subprocess
import sys
import venv


def main():
    if sys.version_info < (3, 10):
        raise SystemExit('Reeltern requires Python 3.10 or newer. Python 3.12 is recommended.')
    root = Path(__file__).resolve().parent
    wheels = list(root.glob('reeltern-*.whl'))
    if len(wheels) != 1:
        raise SystemExit('Expected exactly one Reeltern wheel beside install.py. Extract the complete bundle first.')
    environment = root / '.venv'
    marker = root / '.reeltern-install.json'
    if environment.exists() and not marker.is_file():
        raise SystemExit('An unrelated .venv already exists here. Extract the bundle into a fresh folder.')
    if not environment.exists():
        print('Creating the local Reeltern environment...', flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
        marker.write_text(json.dumps({'package': wheels[0].name}), encoding='utf-8')
    python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    print('Installing Reeltern and MCP dependencies from your configured package index...', flush=True)
    subprocess.run([str(python), '-m', 'pip', 'install', str(wheels[0]) + '[mcp]'], check=True)
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
    print('Installed. See START-HERE.md for the demo, desktop and AI setup commands.')


if __name__ == '__main__':
    main()
