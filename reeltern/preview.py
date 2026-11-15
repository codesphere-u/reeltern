"""Fast in-memory video frame decoding and live effect preview compositing over PyAV."""
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path
import threading
import av
from av.filter import Graph
from .workspace import PRESETS

GRADE_META = OrderedDict([
    ('none', ('Original', ('#334155', '#64748b', '#94a3b8'), {})),
    ('cinematic', ('Cinematic', ('#1e293b', '#f59e0b', '#38bdf8'), {
        'sat': 1.08, 'contrast': 1.10, 'bright': -0.02,
        'cb': 'rs=0.03:gs=0.00:bs=0.04:rh=0.03:bh=-0.03', 'vignette': 0.62,
    })),
    ('warm', ('Warm', ('#7c2d12', '#f59e0b', '#fde68a'), {
        'sat': 1.15, 'bright': 0.01, 'cb': 'rs=0.07:gs=0.02:bs=-0.06',
    })),
    ('crisp', ('Crisp', ('#0f172a', '#38bdf8', '#f8fafc'), {
        'sat': 1.08, 'contrast': 1.12, 'bright': 0.01,
    })),
    ('noir', ('Noir B&W', ('#09090b', '#52525b', '#e4e4e7'), {
        'sat': 0.0, 'contrast': 1.28, 'bright': -0.03, 'vignette': 0.78,
    })),
    ('vivid', ('Vivid Pop', ('#2563eb', '#ec4899', '#facc15'), {
        'sat': 1.35, 'contrast': 1.08, 'bright': 0.02,
    })),
    ('moody', ('Moody Dark', ('#0f172a', '#312e81', '#64748b'), {
        'sat': 0.82, 'contrast': 1.16, 'bright': -0.05, 'vignette': 0.78,
    })),
    ('teal_orange', ('Teal & Orange', ('#0d9488', '#38bdf8', '#fb923c'), {
        'sat': 1.14, 'contrast': 1.12,
        'cb': 'rs=-0.04:gs=0.01:bs=0.06:rh=0.06:gh=0.02:bh=-0.05',
    })),
    ('vintage', ('Vintage Film', ('#44403c', '#d97706', '#fef3c7'), {
        'sat': 0.82, 'contrast': 0.95, 'bright': 0.02,
        'cb': 'rs=0.05:gs=0.02:bs=-0.05', 'vignette': 0.78,
    })),
    ('studio', ('Studio Clean', ('#1e293b', '#818cf8', '#e2e8f0'), {
        'sat': 1.10, 'contrast': 1.08, 'bright': 0.02,
    })),
])


def fit_monitor_box(preset_name, max_w, max_h):
    """Compute even canvas pixel dimensions preserving the selected output preset aspect ratio."""
    pw, ph = PRESETS.get(preset_name, (1280, 720))
    scale = min(max(120, int(max_w)) / pw, max(120, int(max_h)) / ph)
    w = max(64, (int(round(pw * scale)) // 2) * 2)
    h = max(64, (int(round(ph * scale)) // 2) * 2)
    return w, h


def clip_at_time(plan, t):
    """Resolve (clip_index, clip_dict, source_seconds, clip_progress) for timeline timestamp t."""
    clips = (plan or {}).get('clips') or []
    if not clips:
        return None
    target_t = max(0.0, float(t))
    chosen_idx = len(clips) - 1
    chosen = clips[-1]
    for i, clip in enumerate(clips):
        start_tl = float(clip['timeline_start'])
        dur_tl = float(clip['frames']) / 30.0
        if target_t < start_tl + dur_tl - 1e-6:
            chosen_idx, chosen = i, clip
            break
    dur_tl = max(1e-3, float(chosen['frames']) / 30.0)
    local_tl = max(0.0, min(dur_tl, target_t - float(chosen['timeline_start'])))
    progress = max(0.0, min(1.0, local_tl / dur_tl))
    source_sec = float(chosen['start']) + local_tl * float(chosen.get('speed', 1.0))
    source_sec = max(float(chosen['start']), min(float(chosen['end']), source_sec))
    return chosen_idx, chosen, source_sec, progress, local_tl, dur_tl


def ppm_from_rgb_frame(frame):
    """Serialize an rgb24 av.VideoFrame safely (handling line_size padding) into PPM bytes."""
    rgb = frame if frame.format.name == 'rgb24' else frame.reformat(format='rgb24')
    w, h = rgb.width, rgb.height
    plane = rgb.planes[0]
    raw = memoryview(plane)
    row_bytes = w * 3
    stride = plane.line_size
    if stride == row_bytes and len(raw) == h * row_bytes:
        body = raw.tobytes()
    else:
        body = b''.join(bytes(raw[r * stride:r * stride + row_bytes]) for r in range(h))
    header = f'P6\n{w} {h}\n255\n'.encode('ascii')
    return w, h, header + body


class PreviewEngine:
    """Thread-safe read-only PyAV decoder + in-memory filter preview cache."""

    def __init__(self, max_frames=48, max_containers=3):
        self.lock = threading.Lock()
        self.frames = OrderedDict()
        self.containers = OrderedDict()
        self.max_frames = max_frames
        self.max_containers = max_containers

    def _get_container(self, path_str):
        container = self.containers.get(path_str)
        if container is not None:
            self.containers.move_to_end(path_str)
            return container
        container = av.open(path_str)
        self.containers[path_str] = container
        while len(self.containers) > self.max_containers:
            _, oldest = self.containers.popitem(last=False)
            try:
                oldest.close()
            except Exception:
                pass
        return container

    def close(self):
        """Release all open PyAV input containers and cached frames."""
        with self.lock:
            while self.containers:
                _, container = self.containers.popitem(last=False)
                try:
                    container.close()
                except Exception:
                    pass
            self.frames.clear()

    def decode_frame(self, path, timestamp_sec=0.0):
        """Decode and cache the closest rgb24 frame at timestamp_sec for path."""
        key_path = str(Path(path).resolve())
        q_ms = max(0, int(round(max(0.0, float(timestamp_sec)) * 25.0) * 40))
        cache_key = (key_path, q_ms)

        with self.lock:
            cached = self.frames.get(cache_key)
            if cached is not None:
                self.frames.move_to_end(cache_key)
                return cached

            container = self._get_container(key_path)
            if not container.streams.video:
                return None
            stream = container.streams.video[0]
            time_base = float(stream.time_base) if stream.time_base else (1.0 / 30.0)
            target_sec = max(0.0, float(timestamp_sec))
            try:
                if target_sec > 0.05:
                    container.seek(int(target_sec * av.time_base), backward=True, any_frame=False)
                else:
                    container.seek(0, backward=True, any_frame=False)
            except Exception:
                pass

            best = None
            for idx, frame in enumerate(container.decode(video=0)):
                pts_sec = float(frame.pts * time_base) if frame.pts is not None else 0.0
                best = frame
                if pts_sec >= target_sec - 0.02 or idx >= 90:
                    break

            if best is None:
                try:
                    container.seek(0, backward=True, any_frame=False)
                    for frame in container.decode(video=0):
                        best = frame
                        break
                except Exception:
                    return None
            if best is None:
                return None

            rgb = best.reformat(format='rgb24')
            rgb.time_base = Fraction(1, 30)
            rgb.pts = 0
            self.frames[cache_key] = rgb
            while len(self.frames) > self.max_frames:
                self.frames.popitem(last=False)
            return rgb

    def _filter_frame(self, frame, target_w, target_h, fit, clip, progress, local_time, clip_duration):
        clip = clip or {}
        g = Graph()
        src = g.add_buffer(template=frame)
        cur = src

        rot = int(clip.get('rotate', 0) or 0)
        if rot == 90:
            cur = self._link(g, cur, 'transpose', '1')
        elif rot == 180:
            cur = self._link(g, cur, 'transpose', '1')
            cur = self._link(g, cur, 'transpose', '1')
        elif rot == 270:
            cur = self._link(g, cur, 'transpose', '2')

        flip = clip.get('flip', 'none')
        if flip == 'horizontal':
            cur = self._link(g, cur, 'hflip', None)
        elif flip == 'vertical':
            cur = self._link(g, cur, 'vflip', None)

        motion = clip.get('motion', 'none')
        if motion in ('zoom_in', 'zoom_out', 'pan_left', 'pan_right'):
            if motion == 'zoom_in':
                z = 1.0 + 0.12 * progress
                x_expr = '(iw-ow)/2'
            elif motion == 'zoom_out':
                z = 1.12 - 0.12 * progress
                x_expr = '(iw-ow)/2'
            elif motion == 'pan_left':
                z = 1.14
                x_expr = f'(iw-ow)*{1.0 - progress:.4f}'
            else:
                z = 1.14
                x_expr = f'(iw-ow)*{progress:.4f}'
            if z > 1.001:
                cur = self._link(g, cur, 'crop', f"w='iw/{z:.4f}':h='ih/{z:.4f}':x='{x_expr}':y='(ih-oh)/2'")

        if fit == 'blur_fill':
            split = g.add('split', '2')
            cur.link_to(split)
            bg = self._link_slot(g, split, 0, 'scale', f'{target_w}:{target_h}:force_original_aspect_ratio=increase')
            bg = self._link(g, bg, 'crop', f'{target_w}:{target_h}')
            bg = self._link(g, bg, 'gblur', 'sigma=14')
            fg = self._link_slot(g, split, 1, 'scale', f'{target_w}:{target_h}:force_original_aspect_ratio=decrease')
            ov = g.add('overlay', '(W-w)/2:(H-h)/2')
            bg.link_to(ov, 0, 0)
            fg.link_to(ov, 0, 1)
            cur = ov
        elif fit == 'cover':
            cur = self._link(g, cur, 'scale', f'{target_w}:{target_h}:force_original_aspect_ratio=increase')
            cur = self._link(g, cur, 'crop', f'{target_w}:{target_h}')
        else:
            cur = self._link(g, cur, 'scale', f'{target_w}:{target_h}:force_original_aspect_ratio=decrease')
            cur = self._link(g, cur, 'pad', f'{target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=#0b1120')

        meta = GRADE_META.get(clip.get('grade', 'none'), GRADE_META['none'])[2]
        sat = max(0.0, float(meta.get('sat', 1.0)) * float(clip.get('saturation', 1.0)))
        contrast = max(0.2, float(meta.get('contrast', 1.0)) * float(clip.get('contrast', 1.0)))
        bright = float(meta.get('bright', 0.0)) + float(clip.get('brightness', 0.0))

        fade_in = max(0.0, float(clip.get('fade_in', 0.0) or 0.0))
        fade_out = max(0.0, float(clip.get('fade_out', 0.0) or 0.0))
        fade_gain = 1.0
        if fade_in > 0 and local_time < fade_in:
            fade_gain = min(fade_gain, max(0.0, local_time / fade_in))
        if fade_out > 0 and (clip_duration - local_time) < fade_out:
            fade_gain = min(fade_gain, max(0.0, (clip_duration - local_time) / fade_out))

        if sat <= 0.01:
            cur = self._link(g, cur, 'format', 'gray')
        elif abs(sat - 1.0) > 1e-3:
            cur = self._link(g, cur, 'hue', f's={sat:.4f}:b=0')

        if abs(contrast - 1.0) > 1e-3 or abs(bright) > 1e-3 or fade_gain < 0.999:
            b_off = bright * 255.0
            expr = f"clip(((val-128)*{contrast:.4f}+128+({b_off:.2f}))*{fade_gain:.4f},0,255)"
            cur = self._link(g, cur, 'lutrgb', f'r={expr}:g={expr}:b={expr}')

        if meta.get('cb'):
            cur = self._link(g, cur, 'colorbalance', meta['cb'])

        if meta.get('vignette'):
            cur = self._link(g, cur, 'vignette', f"angle={meta['vignette']:.4f}")

        cur = self._link(g, cur, 'format', 'rgb24')
        sink = g.add('buffersink')
        cur.link_to(sink)
        g.configure()
        g.push(frame)
        return g.pull()

    @staticmethod
    def _link(graph, prev, name, args):
        flt = graph.add(name, args) if args else graph.add(name)
        prev.link_to(flt)
        return flt

    @staticmethod
    def _link_slot(graph, prev, out_idx, name, args):
        flt = graph.add(name, args) if args else graph.add(name)
        prev.link_to(flt, out_idx, 0)
        return flt

    def render_clip_frame(
        self,
        path,
        timestamp_sec,
        box_w,
        box_h,
        *,
        preset='landscape',
        fit='contain',
        clip=None,
        progress=0.0,
        local_time=0.0,
        clip_duration=1.0,
    ):
        """Decode and composite a single live preview frame as (width, height, ppm_bytes)."""
        raw = self.decode_frame(path, timestamp_sec)
        if raw is None:
            return None
        tw, th = fit_monitor_box(preset, box_w, box_h)
        composed = self._filter_frame(raw, tw, th, fit, clip, progress, local_time, clip_duration)
        return ppm_from_rgb_frame(composed)

    def render_thumbnail(self, path, timestamp_sec=0.0, thumb_w=84, thumb_h=48):
        """Decode a compact landscape thumbnail as (width, height, ppm_bytes) for timeline cards."""
        raw = self.decode_frame(path, timestamp_sec)
        if raw is None:
            return None
        tw = max(32, (int(thumb_w) // 2) * 2)
        th = max(24, (int(thumb_h) // 2) * 2)
        g = Graph()
        src = g.add_buffer(template=raw)
        cur = self._link(g, src, 'scale', f'{tw}:{th}:force_original_aspect_ratio=increase')
        cur = self._link(g, cur, 'crop', f'{tw}:{th}')
        cur = self._link(g, cur, 'format', 'rgb24')
        sink = g.add('buffersink')
        cur.link_to(sink)
        g.configure()
        g.push(raw)
        return ppm_from_rgb_frame(g.pull())
