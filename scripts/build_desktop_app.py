"""Build and smoke-test native Reeltern Studio desktop apps for macOS, Windows, and Linux."""
import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import platform
import plistlib
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]


def _png_chunk(tag, data):
    body = tag + data
    return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)


def _render_icon_png(path, size=256):
    """Render a crisp anti-aliased Reeltern aperture/play emblem without external imaging deps."""
    rows = []
    half = (size - 1) / 2.0
    radius = size * 0.44
    tri_a = (-size * 0.14, -size * 0.21)
    tri_b = (-size * 0.14, size * 0.21)
    tri_c = (size * 0.24, 0.0)

    def sign(px, py, ax, ay, bx, by):
        return (px - bx) * (ay - by) - (ax - bx) * (py - by)

    def in_triangle(px, py):
        d1 = sign(px, py, *tri_a, *tri_b)
        d2 = sign(px, py, *tri_b, *tri_c)
        d3 = sign(px, py, *tri_c, *tri_a)
        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        return not (has_neg and has_pos)

    for y in range(size):
        row = bytearray([0])
        cy = y - half
        for x in range(size):
            cx = x - half
            sq = max(abs(cx), abs(cy))
            corner = math.hypot(max(0.0, abs(cx) - size * 0.26), max(0.0, abs(cy) - size * 0.26))
            dist = corner - size * 0.18 if abs(cx) > size * 0.26 and abs(cy) > size * 0.26 else sq - radius
            if dist > 1.5:
                row.extend((0, 0, 0, 0))
                continue
            alpha = max(0, min(255, int(255 * (1.0 - max(0.0, dist) / 1.5))))
            t = max(0.0, min(1.0, (x + y) / (2.0 * size)))
            r = int(11 + t * 8)
            g = int(17 + t * 18)
            b = int(32 + t * 28)
            d_ring = abs(math.hypot(cx, cy) - size * 0.34)
            if d_ring < size * 0.032:
                blend = 1.0 - max(0.0, d_ring - size * 0.022) / max(1.0, size * 0.01)
                r = int(r * (1 - blend) + 56 * blend)
                g = int(g * (1 - blend) + 189 * blend)
                b = int(b * (1 - blend) + 248 * blend)
            if in_triangle(cx, cy):
                r, g, b = 241, 245, 249
            elif math.hypot(cx, cy) < size * 0.31 and abs(d_ring - size * 0.032) < 1.2:
                r, g, b = 129, 140, 248
            row.extend((r, g, b, alpha))
        rows.append(bytes(row))

    raw = zlib.compress(b''.join(rows), level=9)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    png = b'\x89PNG\r\n\x1a\n' + _png_chunk(b'IHDR', ihdr) + _png_chunk(b'IDAT', raw) + _png_chunk(b'IEND', b'')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return path


def _build_icons(build_dir):
    png_256 = _render_icon_png(build_dir / 'icon-256.png', 256)
    if sys.platform == 'win32':
        ico_path = build_dir / 'icon.ico'
        png_bytes = png_256.read_bytes()
        header = struct.pack('<HHH', 0, 1, 1)
        entry = struct.pack('<BBBBHHII', 0, 0, 0, 0, 1, 32, len(png_bytes), 22)
        ico_path.write_bytes(header + entry + png_bytes)
        return ico_path
    if sys.platform == 'darwin' and shutil.which('iconutil'):
        iconset = build_dir / 'reeltern.iconset'
        iconset.mkdir(parents=True, exist_ok=True)
        for dim in (16, 32, 64, 128, 256):
            _render_icon_png(iconset / f'icon_{dim}x{dim}.png', dim)
            _render_icon_png(iconset / f'icon_{dim}x{dim}@2x.png', min(512, dim * 2))
        icns_path = build_dir / 'icon.icns'
        res = subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(icns_path)], check=False)
        if res.returncode == 0 and icns_path.is_file():
            return icns_path
    return png_256


def _platform_tag():
    machine = platform.machine().lower()
    if sys.platform == 'darwin':
        return 'macos-arm64' if machine in ('arm64', 'aarch64') else 'macos-x64'
    if sys.platform == 'win32':
        return 'windows-x64'
    return 'linux-x64' if machine in ('x86_64', 'amd64') else f'linux-{machine}'


def _smoke_test(exe, include_gui=False):
    print(f'Smoke testing binary: {exe}')
    with tempfile.TemporaryDirectory(prefix='reeltern-app-smoke-') as temp:
        tmp = Path(temp)
        media = tmp / 'media'
        media.mkdir()

        cfg_res = subprocess.run(
            [str(exe), 'mcp-config', 'antigravity', '--workspace', str(tmp / 'ws'), '--media-root', str(media)],
            check=True,
            capture_output=True,
            text=True,
        )
        cfg = json.loads(cfg_res.stdout)
        entry = cfg['mcpServers']['reeltern']
        assert entry['args'][0] == 'mcp', entry
        assert '-m' not in entry['args'], entry

        demo_res = subprocess.run(
            [str(exe), 'demo', '--workspace', str(tmp / 'demo-ws')],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(demo_res.stdout)
        assert Path(report['video']).is_file(), report
        assert report['edit_seconds'] == 4.0, report

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            async def _probe_mcp():
                params = StdioServerParameters(
                    command=str(exe),
                    args=['mcp', '--workspace', str(tmp / 'mcp-ws'), '--media-root', str(media)],
                )
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        assert len(tools.tools) == 31, f'Expected 31 MCP tools, got {len(tools.tools)}'
                        resources = await session.list_resources()
                        prompts = await session.list_prompts()
                        assert len(prompts.prompts) == 4, prompts
                        cap = await session.call_tool('capabilities', {})
                        assert not cap.isError, cap

            asyncio.run(_probe_mcp())
            print('Verified bundled MCP stdio server: 31 tools + 4 prompts.')
        except ImportError:
            print('mcp SDK not installed in build Python; skipped stdio MCP handshake.')

        if include_gui:
            env = {**os.environ, 'REELTERN_STUDIO_SMOKE_MS': '750', 'HOME': str(tmp / 'home')}
            (tmp / 'home').mkdir(exist_ok=True)
            subprocess.run([str(exe)], env=env, check=True, timeout=25)
            print('Verified GUI startup and clean exit in zero-arg desktop mode.')


def _package_artifact(dist_dir, app_name, version, plat_tag, icon_path):
    if sys.platform == 'darwin':
        app_bundle = dist_dir / f'{app_name}.app'
        plist_file = app_bundle / 'Contents' / 'Info.plist'
        with plist_file.open('rb') as handle:
            plist = plistlib.load(handle)
        plist['CFBundleDisplayName'] = 'Reeltern Studio'
        plist['CFBundleShortVersionString'] = version
        plist['CFBundleVersion'] = version
        plist['NSHighResolutionCapable'] = True
        with plist_file.open('wb') as handle:
            plistlib.dump(plist, handle)
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app_bundle)], check=True)

        dmg_path = dist_dir / f'Reeltern-Studio-{version}-{plat_tag}.dmg'
        dmg_path.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory(prefix='reeltern-dmg-') as stage:
            stage_dir = Path(stage)
            shutil.copytree(app_bundle, stage_dir / f'{app_name}.app', symlinks=True)
            os.symlink('/Applications', stage_dir / 'Applications')
            subprocess.run(
                ['hdiutil', 'create', '-volname', 'Reeltern Studio', '-srcfolder', str(stage_dir), '-ov', '-format', 'UDZO', str(dmg_path)],
                check=True,
            )
        return dmg_path

    folder = dist_dir / app_name
    if sys.platform == 'win32':
        zip_path = dist_dir / f'Reeltern-Studio-{version}-{plat_tag}.zip'
        zip_path.unlink(missing_ok=True)
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(folder.rglob('*')):
                if item.is_file():
                    archive.write(item, Path('Reeltern-Studio') / item.relative_to(folder))
        return zip_path

    # Linux portable folder + icon + .desktop installer helper
    shutil.copy2(icon_path, folder / 'reeltern.png')
    desktop = folder / 'reeltern-studio.desktop'
    desktop.write_text(
        '[Desktop Entry]\n'
        'Type=Application\n'
        'Name=Reeltern Studio\n'
        'Comment=Local AI Director & Reversible Video Studio\n'
        'Exec=reeltern-studio\n'
        'Icon=reeltern\n'
        'Categories=AudioVideo;Video;AudioVideoEditing;\n'
        'Terminal=false\n',
        encoding='utf-8',
    )
    tar_path = dist_dir / f'Reeltern-Studio-{version}-{plat_tag}.tar.gz'
    tar_path.unlink(missing_ok=True)
    with tarfile.open(tar_path, 'w:gz') as archive:
        archive.add(folder, arcname='reeltern-studio')
    return tar_path


def main():
    parser = argparse.ArgumentParser(description='Build native Reeltern Studio desktop application')
    parser.add_argument('--smoke', action='store_true', help='Run CLI + MCP smoke verification on the built binary')
    parser.add_argument('--smoke-gui', action='store_true', help='Also launch and auto-close the desktop GUI window')
    parser.add_argument('--dist-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()

    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    plat_tag = _platform_tag()
    app_name = 'reeltern-studio' if sys.platform.startswith('linux') else 'Reeltern Studio'

    dist_dir = args.dist_dir.resolve()
    work_dir = ROOT / 'build' / 'desktop'
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    for leftover in (dist_dir / app_name, dist_dir / f'{app_name}.app'):
        if leftover.exists():
            shutil.rmtree(leftover)

    icon_path = _build_icons(work_dir)

    pyinstaller_cmd = [
        sys.executable,
        '-m',
        'PyInstaller',
        '--noconfirm',
        '--clean',
        '--onedir',
        '--name',
        app_name,
        '--distpath',
        str(dist_dir),
        '--workpath',
        str(work_dir / 'work'),
        '--specpath',
        str(work_dir),
        '--icon',
        str(icon_path),
        '--collect-all',
        'av',
        '--collect-all',
        'imageio_ffmpeg',
        '--hidden-import',
        'mcp',
        '--collect-submodules',
        'mcp.server',
        '--collect-submodules',
        'mcp.shared',
        '--collect-submodules',
        'mcp.types',
        '--collect-data',
        'mcp',
        '--exclude-module',
        'mcp.cli',
        '--collect-all',
        'pydantic',
        '--collect-all',
        'pydantic_core',
        '--collect-all',
        'anyio',
        '--collect-all',
        'httpx',
        '--collect-all',
        'reeltern',
        '--copy-metadata',
        'reeltern',
        '--hidden-import',
        'tkinter',
        '--hidden-import',
        'tkinter.ttk',
        '--hidden-import',
        'tkinter.filedialog',
        '--hidden-import',
        'tkinter.messagebox',
    ]
    if sys.platform in ('darwin', 'win32'):
        pyinstaller_cmd.append('--windowed')
    if sys.platform == 'darwin':
        pyinstaller_cmd += ['--osx-bundle-identifier', 'ai.reeltern.studio']
    pyinstaller_cmd.append(str(ROOT / 'packaging' / 'desktop_entry.py'))

    subprocess.run(pyinstaller_cmd, cwd=ROOT, check=True)

    if sys.platform == 'darwin':
        exe = dist_dir / f'{app_name}.app' / 'Contents' / 'MacOS' / app_name
    elif sys.platform == 'win32':
        exe = dist_dir / app_name / f'{app_name}.exe'
    else:
        exe = dist_dir / app_name / app_name

    assert exe.is_file(), f'Expected executable missing: {exe}'

    if args.smoke or args.smoke_gui:
        _smoke_test(exe, include_gui=args.smoke_gui)

    artifact = _package_artifact(dist_dir, app_name, version, plat_tag, icon_path)
    print(f'Built desktop package: {artifact}')


if __name__ == '__main__':
    main()
