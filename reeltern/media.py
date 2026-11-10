"""Local media primitives shared by desktop, CLI and MCP."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid


class Cancelled(RuntimeError):
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def ffmpeg():
    from .engine import binary
    program = binary('ffmpeg')
    if program:
        return program
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise RuntimeError('Install Reeltern dependencies or set REELTERN_FFMPEG') from exc


def probe(path):
    import av
    with av.open(str(path), options={'protocol_whitelist': 'file,pipe'}) as container:
        video = next(iter(container.streams.video), None)
        if video is None:
            raise ValueError('The file must contain a video stream')
        duration = float(video.duration * video.time_base) if video.duration is not None else float(container.duration or 0) / av.time_base
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('Cannot determine a positive video duration')
        return {'duration': duration, 'width': video.width, 'height': video.height,
                'fps': float(video.average_rate or 0), 'audio': bool(container.streams.audio),
                'video_codec': video.codec_context.name, 'format': container.format.name}


def execute(args, folder, cancel=None, timeout=3600):
    """Capture to disk, not an unbounded pipe; terminate and reap on cancellation."""
    cancel = cancel or threading.Event()
    if cancel.is_set():
        raise Cancelled('Render cancelled')
    folder = Path(folder)
    log = folder / ('process-' + uuid.uuid4().hex + '.log')
    started = time.monotonic()
    with log.open('wb') as stream:
        proc = subprocess.Popen([str(x) for x in args], cwd=folder, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream)
        try:
            while proc.poll() is None:
                if cancel.wait(0.1):
                    raise Cancelled('Render cancelled')
                if time.monotonic() - started > timeout:
                    raise RuntimeError(f'Media operation exceeded {timeout}s')
            if cancel.is_set():
                raise Cancelled('Render cancelled')
            if proc.returncode:
                with log.open('rb') as f:
                    f.seek(max(0, log.stat().st_size - 3000))
                    detail = f.read().decode('utf-8', errors='replace')
                raise RuntimeError(f'Media operation failed: {detail}')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
    return log


def ff(args, folder, cancel=None):
    return execute([ffmpeg(), '-hide_banner', '-nostdin', '-n', *args], folder, cancel)


def number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be a finite number between {minimum} and {maximum}')
    return float(value)


def silence_ranges(log, duration):
    """Parse paired FFmpeg events, including a trailing silence without an end."""
    ranges, start = [], None
    for kind, value in re.findall(r'silence_(start|end):\s*([\d.eE+-]+)', log):
        t = max(0.0, min(duration, float(value)))
        if kind == 'start':
            start = t
        elif start is not None:
            if t > start:
                ranges.append([start, t])
            start = None
    if start is not None and start < duration:
        ranges.append([start, duration])
    return ranges


def kept_ranges(silences, duration, margin):
    cuts = []
    for start, end in silences:
        a, b = (0 if start <= 0.01 else start + margin), (duration if end >= duration - 0.01 else end - margin)
        if b > a:
            if cuts and a <= cuts[-1][1]:
                cuts[-1][1] = max(cuts[-1][1], b)
            else:
                cuts.append([a, b])
    kept, cursor = [], 0.0
    for start, end in cuts:
        if start - cursor >= 1 / 30:
            kept.append([cursor, start])
        cursor = end
    if duration - cursor >= 1 / 30:
        kept.append([cursor, duration])
    return kept
