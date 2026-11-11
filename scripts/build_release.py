"""Assemble OS-specific Python installation bundles and checksums (no dependency binaries)."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    version = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
    assert (ROOT/'release/version.txt').read_text().strip() == version
    output = Path(output).resolve()
    wheel = output/f'reeltern-{version}-py3-none-any.whl'
    source = output/f'reeltern-{version}.tar.gz'
    if not wheel.is_file() or not source.is_file():
        raise ValueError('Build the wheel and source distribution first with python -m build')
    for platform in ('windows', 'macos', 'linux'):
        name = f'reeltern-{version}-{platform}-python'
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/name; folder.mkdir()
            shutil.copy2(wheel, folder/wheel.name)
            shutil.copy2(ROOT/'packaging/install.py', folder/'install.py')
            shutil.copy2(ROOT/'LICENSE', folder/'LICENSE')
            shutil.copy2(ROOT/'SOURCES.md', folder/'SOURCES.md')
            for document in ('README.md', 'AGENTS.md', 'CLAUDE.md', 'CONTRIBUTING.md', 'SECURITY.md', 'VALIDATION.md', 'CHANGELOG.md', 'llms.txt'):
                shutil.copy2(ROOT/document, folder/document)
            shutil.copytree(ROOT/'examples', folder/'examples', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT/'.github/ISSUE_TEMPLATE', folder/'.github/ISSUE_TEMPLATE')
            shutil.copytree(ROOT/'docs', folder/'docs')
            launcher = 'reeltern.cmd' if platform == 'windows' else './reeltern.sh'
            text = f'''# Reeltern {version} — {platform} Python installation bundle

Extract this entire archive into a writable folder. Install Python 3.12 (recommended); the release tests Python 3.10–3.12. Internet access is needed for dependency installation. No Python runtime, third-party binaries or model weights are bundled. This is not a standalone native app or an offline installer.

1. Run `python install.py` (Windows: `py -3.12 install.py`; macOS/Linux: `python3 install.py`). This creates `.venv` here, installs the included wheel and its dependencies, and checks them. It does not change your global Python packages.
2. Run `{launcher} demo --workspace demo-project` to generate and verify a captioned edit.
3. Run `{launcher} gui` for the desktop. Tkinter is required; Linux may need its distribution's `python3-tk` and `python3-venv` packages. CLI/MCP do not need a display.
4. Run `{launcher} mcp-config codex --workspace editing-project --media-root demo-project/demo-input` to print client settings. Substitute `claude-code`, `cursor`, `vscode` or `generic` as needed.

If a Unix launcher is not executable after extraction, run `chmod +x reeltern.sh`. Keep the folder in place after installation: environments and generated MCP configurations contain absolute paths. To move it, extract a fresh bundle and install again. To uninstall, close its running processes and remove its environment/bundle after saving any footage or projects you want to keep.

This is an unsigned early preview. macOS and Windows may ask you to review downloaded scripts. You can inspect `install.py` and invoke it from your terminal; no system security setting needs to be disabled. No administrator rights are needed for the local installation.

See docs/releases.md for the tested OS/architecture matrix; docs/clients.md for AI setup; docs/troubleshooting.md for errors. Optional enhancement adapters and local models require separate setup. Some optional external tools may not be available on every platform.
'''
            (folder/'START-HERE.md').write_text(text, encoding='utf-8')
            if platform == 'windows':
                (folder/'reeltern.cmd').write_text('@echo off\r\n"%~dp0.venv\\Scripts\\python.exe" -m reeltern.cli %*\r\n', encoding='utf-8')
                (folder/'Launch.cmd').write_text('@echo off\r\ncall "%~dp0reeltern.cmd" gui --workspace "%~dp0reeltern-workspace"\r\npause\r\n', encoding='utf-8')
            else:
                (folder/'reeltern.sh').write_text('#!/bin/sh\nBUNDLE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1\nexec "$BUNDLE_DIR/.venv/bin/python" -m reeltern.cli "$@"\n', encoding='utf-8')
                (folder/'reeltern.sh').chmod(0o755)
                if platform == 'macos':
                    (folder/'Launch.command').write_text('#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec ./reeltern.sh gui\n', encoding='utf-8')
                    (folder/'Launch.command').chmod(0o755)
            with zipfile.ZipFile(output/(name+'.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(folder.rglob('*')):
                    if path.is_file():
                        archive.write(path, path.relative_to(Path(temp)))
    assets = sorted([wheel, source, *output.glob(f'reeltern-{version}-*-python.zip')])
    (output/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in assets), encoding='utf-8')
    print(json.dumps({'version': version, 'assets': [p.name for p in assets]+['SHA256SUMS.txt']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='dist')
    build(parser.parse_args().output)
