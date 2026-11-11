"""A reproducible first-run demo; no footage, account or model download needed."""
from pathlib import Path
import time
from .media import ff, atomic_json
from .workspace import Workspace
from .transcript import register, select
from .render import Renderer


def run_demo(workspace):
    ws = Workspace(workspace)
    folder = ws.root / 'demo-input'
    folder.mkdir(exist_ok=True)
    source = folder / 'synthetic-source.mp4'
    if not source.exists():
        ff(['-f', 'lavfi', '-i', 'testsrc2=s=640x360:r=30:d=6', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=6', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', source], folder)
    asset = ws.import_media(source)
    evidence = register(ws, asset['id'], [
        {'start': 0, 'end': 2, 'text': 'This is synthetic demonstration footage.'},
        {'start': 2, 'end': 4, 'text': 'This middle section will be left out.'},
        {'start': 4, 'end': 6, 'text': 'Captions follow the selected source ranges.'}])
    plan = select(ws, evidence['id'], ['c00001', 'c00003'], notes='Synthetic demo: two real source ranges, middle omitted, captions retimed.')
    renderer = Renderer(ws)
    try:
        first = renderer.wait(renderer.submit(plan['id'], True)['id'])
        if first['status'] != 'complete':
            raise RuntimeError(first.get('error', 'Demo render failed'))
        second = renderer.wait(renderer.submit(plan['id'], True)['id'])
        if second['status'] != 'complete':
            raise RuntimeError(second.get('error', 'Demo cached render failed'))
        report = {'synthetic': True, 'source_seconds': asset['duration'], 'edit_seconds': plan['duration'],
                  'transcript_id': evidence['id'], 'plan_id': plan['id'], 'first_render_seconds': first['elapsed_seconds'],
                  'cached_render_seconds': second['elapsed_seconds'], 'cache_hits': second['cache_hits'],
                  'video': first['output'], 'captions': first['captions'], 'receipt': first['receipt'],
                  'note': 'This demonstrates mechanics on a tiny fixture, not speech recognition or a general performance benchmark.'}
        atomic_json(ws.root / 'demo-report.json', report)
        return report
    finally:
        renderer.close()
