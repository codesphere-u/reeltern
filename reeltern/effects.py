"""Pure local validation, deterministic FFmpeg builders, visual telemetry, and audio metering."""
import math
from pathlib import Path
import re
from .media import ff, number, probe

COLOR_GRADES = {
    'none': '',
    'cinematic': 'eq=contrast=1.10:saturation=1.08:brightness=-0.02,colorbalance=rs=0.03:gs=0.00:bs=0.04:rh=0.03:bh=-0.03,vignette=angle=PI/5',
    'warm': 'eq=saturation=1.15:brightness=0.01,colorbalance=rs=0.07:gs=0.02:bs=-0.06',
    'crisp': 'eq=contrast=1.12:saturation=1.08,unsharp=5:5:0.65:5:5:0.0',
    'noir': 'eq=saturation=0.0:contrast=1.28:brightness=-0.03,vignette=angle=PI/4',
    'vivid': 'eq=saturation=1.35:contrast=1.08:gamma=1.04',
    'moody': 'eq=contrast=1.16:brightness=-0.05:saturation=0.82,vignette=angle=PI/4',
    'teal_orange': 'eq=contrast=1.12:saturation=1.14,colorbalance=rs=-0.04:gs=0.01:bs=0.06:rh=0.06:gh=0.02:bh=-0.05',
    'vintage': 'eq=contrast=0.95:saturation=0.82:brightness=0.02,colorbalance=rs=0.05:gs=0.02:bs=-0.05,vignette=angle=PI/4',
    'studio': 'eq=contrast=1.08:saturation=1.10:brightness=0.02,unsharp=5:5:0.75:5:5:0.0',
}

TRANSITIONS = {
    'cut': None,
    'crossfade': 'fade',
    'wipeleft': 'wipeleft',
    'wiperight': 'wiperight',
    'slideleft': 'slideleft',
    'slideright': 'slideright',
    'dissolve': 'dissolve',
    'smoothleft': 'smoothleft',
    'circleopen': 'circleopen',
    'fadeblack': 'fadeblack',
}

FIT_MODES = ('contain', 'cover', 'blur_fill')
MOTIONS = ('none', 'zoom_in', 'zoom_out', 'pan_left', 'pan_right')
FLIPS = ('none', 'horizontal', 'vertical')
ROTATIONS = (0, 90, 180, 270)
CAPTION_MODES = ('soft', 'burn', 'both', 'none')
CAPTION_STYLES = ('clean', 'boxed', 'bold', 'kinetic')

_HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def hex_color(value, name='color'):
    if not isinstance(value, str) or not _HEX_RE.fullmatch(value.strip()):
        raise ValueError(f'{name} must be a 6-digit hex color like #0f172a')
    return value.strip().lower()


def _ass_bgr(hex_rgb, alpha='00'):
    clean = hex_color(hex_rgb).lstrip('#')
    r, g, b = clean[0:2], clean[2:4], clean[4:6]
    return f'&H{alpha.upper()}{b.upper()}{g.upper()}{r.upper()}'


def sanitize_ass_text(text):
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(text))
    cleaned = cleaned.replace('{', '(').replace('}', ')')
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n').replace('\n', r'\N')
    return cleaned.strip()


def _ass_time(seconds):
    cs = max(0, round(seconds * 100))
    hours, cs = divmod(cs, 360000)
    minutes, cs = divmod(cs, 6000)
    secs, cs = divmod(cs, 100)
    return f'{hours}:{minutes:02d}:{secs:02d}.{cs:02d}'


def atempo_filters(speed):
    speed = number(speed, 'playback speed', 0.25, 4.0)
    if abs(speed - 1.0) < 1e-6:
        return []
    filters = []
    remaining = speed
    while remaining < 0.5 - 1e-9:
        filters.append('atempo=0.5')
        remaining /= 0.5
    while remaining > 2.0 + 1e-9:
        filters.append('atempo=2.0')
        remaining /= 2.0
    filters.append(f'atempo={remaining:.6g}')
    return filters


def motion_filters(motion, width, height, frames):
    """Build deterministic camera motion filters over a WxH normalized clip."""
    if motion not in MOTIONS:
        raise ValueError(f'Unknown motion: {motion}')
    if motion == 'none':
        return []
    denom = max(int(frames) - 1, 1)
    dur = max(int(frames) / 30.0, 0.1)
    if motion == 'zoom_in':
        return [
            f'scale={width * 2}:{height * 2}:flags=bilinear',
            f"zoompan=z='1+0.12*min(in/{denom}\\,1)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps=30:s={width}x{height}",
        ]
    if motion == 'zoom_out':
        return [
            f'scale={width * 2}:{height * 2}:flags=bilinear',
            f"zoompan=z='1.12-0.12*min(in/{denom}\\,1)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps=30:s={width}x{height}",
        ]
    w_os = (round(width * 1.14) // 2) * 2
    h_os = (round(height * 1.14) // 2) * 2
    if motion == 'pan_left':
        x_expr = f"(iw-ow)*(1-min(t/{dur:.4f}\\,1))"
    else:
        x_expr = f"(iw-ow)*min(t/{dur:.4f}\\,1)"
    return [
        f'scale={w_os}:{h_os}:flags=bicubic',
        f"crop=w={width}:h={height}:x='{x_expr}':y=(ih-oh)/2",
    ]


def clip_video_filters(clip, width, height):
    """Build safe deterministic FFmpeg video filters for a normalized clip (single-stream helper)."""
    filters = []
    rotate = int(clip.get('rotate', 0))
    if rotate == 90:
        filters.append('transpose=1')
    elif rotate == 180:
        filters.append('transpose=1,transpose=1')
    elif rotate == 270:
        filters.append('transpose=2')

    flip = clip.get('flip', 'none')
    if flip == 'horizontal':
        filters.append('hflip')
    elif flip == 'vertical':
        filters.append('vflip')

    fit = clip.get('_fit', 'contain')
    if fit == 'cover':
        filters.append(f'scale={width}:{height}:force_original_aspect_ratio=increase')
        filters.append(f'crop={width}:{height}')
    else:
        filters.append(f'scale={width}:{height}:force_original_aspect_ratio=decrease')
        filters.append(f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#0b1120')
    filters.append('setsar=1')

    grade = clip.get('grade', 'none')
    if grade in COLOR_GRADES and COLOR_GRADES[grade]:
        filters.append(COLOR_GRADES[grade])

    brightness = float(clip.get('brightness', 0.0))
    contrast = float(clip.get('contrast', 1.0))
    saturation = float(clip.get('saturation', 1.0))
    if any(abs(v - d) > 1e-4 for v, d in ((brightness, 0.0), (contrast, 1.0), (saturation, 1.0))):
        filters.append(f'eq=brightness={brightness:.3f}:contrast={contrast:.3f}:saturation={saturation:.3f}')

    speed = float(clip.get('speed', 1.0))
    if abs(speed - 1.0) > 1e-6:
        filters.append(f'setpts=PTS/{speed:.6g}')

    filters.append('fps=30')
    filters.append('format=yuv420p')
    return filters


def _kinetic_events(cue):
    words = [sanitize_ass_text(w) for w in str(cue['text']).split() if sanitize_ass_text(w)]
    if not words:
        return []
    start, end = float(cue['start']), float(cue['end'])
    if end <= start:
        return []
    groups = [words[i:i + 4] for i in range(0, len(words), 4)]
    group_dur = (end - start) / len(groups)
    events = []
    for g_idx, group in enumerate(groups):
        g_start = start + g_idx * group_dur
        word_dur = group_dur / len(group)
        for w_idx in range(len(group)):
            w_start = g_start + w_idx * word_dur
            w_end = g_start + (w_idx + 1) * word_dur
            if w_end - w_start < 0.02:
                continue
            rendered = []
            for idx, word in enumerate(group):
                if idx == w_idx:
                    rendered.append(r'{\fscx110\fscy110\t(0,85,\fscx100\fscy100)\c&H0038D9FF&}' + word + r'{\c&H00FFFFFF&}')
                else:
                    rendered.append(word)
            events.append(f"Dialogue: 0,{_ass_time(w_start)},{_ass_time(w_end)},Default,,0,0,0,,{' '.join(rendered)}")
    return events


def build_captions_ass(width, height, cues, style='clean'):
    if style not in CAPTION_STYLES:
        raise ValueError(f'Unknown caption style: {style}')
    if style == 'kinetic':
        base_size = max(16, round(min(width, height) * 0.058))
        margin_v = max(24, round(height * 0.11))
        margin_h = max(18, round(width * 0.07))
        style_line = f'Style: Default,Sans,{base_size},&H00FFFFFF,&H00FFFFFF,&H000B1120,&H990B1120,-1,0,0,0,100,100,0,0,1,4,2,2,{margin_h},{margin_h},{margin_v},1'
    elif style == 'boxed':
        base_size = max(14, round(min(width, height) * 0.044))
        margin_v = max(14, round(height * 0.085))
        margin_h = max(16, round(width * 0.06))
        style_line = f'Style: Default,Sans,{base_size},&H00FFFFFF,&H00FFFFFF,&H000B1120,&H990B1120,-1,0,0,0,100,100,0,0,3,8,0,2,{margin_h},{margin_h},{margin_v},1'
    elif style == 'bold':
        base_size = max(14, round(min(width, height) * 0.052))
        margin_v = max(14, round(height * 0.085))
        margin_h = max(16, round(width * 0.06))
        style_line = f'Style: Default,Sans,{base_size},&H0058E2FF,&H00FFFFFF,&H000B1120,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,{margin_h},{margin_h},{margin_v},1'
    else:
        base_size = max(14, round(min(width, height) * 0.044))
        margin_v = max(14, round(height * 0.085))
        margin_h = max(16, round(width * 0.06))
        style_line = f'Style: Default,Sans,{base_size},&H00FFFFFF,&H00FFFFFF,&H000B1120,&H70000000,0,0,0,0,100,100,0,0,1,2,1,2,{margin_h},{margin_h},{margin_v},1'

    lines = [
        '[Script Info]',
        'ScriptType: v4.00+',
        f'PlayResX: {width}',
        f'PlayResY: {height}',
        'WrapStyle: 0',
        'ScaledBorderAndShadow: yes',
        '',
        '[V4+ Styles]',
        'Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding',
        style_line,
        '',
        '[Events]',
        'Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text',
    ]
    for cue in cues:
        if style == 'kinetic':
            lines.extend(_kinetic_events(cue))
        else:
            text = sanitize_ass_text(cue['text'])
            if text:
                lines.append(f"Dialogue: 0,{_ass_time(cue['start'])},{_ass_time(cue['end'])},Default,,0,0,0,,{text}")
    return '\n'.join(lines) + '\n'


def build_overlay_ass(width, height, duration, title, subtitle='', accent='#38bdf8', mode='lower_third'):
    title_text = sanitize_ass_text(title)
    sub_text = sanitize_ass_text(subtitle)
    accent_bgr = _ass_bgr(accent)
    title_size = max(14, round(min(width, height) * (0.072 if mode == 'card' else 0.044)))
    sub_size = max(11, round(title_size * 0.56))
    margin_x = max(16, round(width * 0.06))
    if mode == 'card':
        title_align, sub_align = 5, 5
        title_mv = 0
        sub_mv = 0
        title_line = f'Style: Title,Sans,{title_size},&H00FFFFFF,&H00FFFFFF,&H000B1120,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,{title_align},{margin_x},{margin_x},{title_mv},1'
        sub_line = f'Style: Subtitle,Sans,{sub_size},{accent_bgr},&H00FFFFFF,&H000B1120,&H80000000,0,0,0,0,100,100,0,0,1,1,0,{sub_align},{margin_x},{margin_x},{sub_mv},1'
        body = f'{title_text}'
        events = [f'Dialogue: 1,{_ass_time(0)},{_ass_time(duration)},Title,,0,0,0,,{body}']
        if sub_text:
            y_pos = round(height * 0.62)
            events.append(f'Dialogue: 1,{_ass_time(0)},{_ass_time(duration)},Subtitle,,0,0,0,,{{\\pos({width // 2},{y_pos})}}{sub_text}')
    else:
        margin_v = max(16, round(height * 0.08))
        title_line = f'Style: Title,Sans,{title_size},&H00FFFFFF,&H00FFFFFF,{accent_bgr},&HB00B1120,-1,0,0,0,100,100,0,0,3,8,0,1,{margin_x},{margin_x},{margin_v},1'
        sub_line = f'Style: Subtitle,Sans,{sub_size},{accent_bgr},&H00FFFFFF,&H000B1120,&H80000000,0,0,0,0,100,100,0,0,1,1,0,1,{margin_x},{margin_x},{margin_v},1'
        text = title_text + (f'\\N{sub_text}' if sub_text else '')
        events = [f'Dialogue: 1,{_ass_time(0)},{_ass_time(duration)},Title,,0,0,0,,{text}']

    header = [
        '[Script Info]',
        'ScriptType: v4.00+',
        f'PlayResX: {width}',
        f'PlayResY: {height}',
        'WrapStyle: 1',
        'ScaledBorderAndShadow: yes',
        '',
        '[V4+ Styles]',
        'Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding',
        title_line,
        sub_line,
        '',
        '[Events]',
        'Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text',
    ]
    return '\n'.join(header + events) + '\n'


def render_title_card(output_path, width, height, duration, title, subtitle='', background='#0f172a', accent='#38bdf8', work_dir=None):
    background = hex_color(background, 'background')
    accent = hex_color(accent, 'accent')
    duration = number(duration, 'card duration', 0.5, 30.0)
    if not isinstance(title, str) or not title.strip() or len(title) > 120:
        raise ValueError('Title must be 1–120 characters')
    if not isinstance(subtitle, str) or len(subtitle) > 200:
        raise ValueError('Subtitle must be text of at most 200 characters')
    output_path = Path(output_path)
    folder = Path(work_dir) if work_dir else output_path.parent
    folder.mkdir(parents=True, exist_ok=True)
    ass_path = folder / f'{output_path.stem}.ass'
    ass_path.write_text(build_overlay_ass(width, height, duration, title, subtitle, accent=accent, mode='card'), encoding='utf-8')
    bar_h = max(4, round(height * 0.01))
    bar_y = round(height * 0.56)
    bar_w = round(width * 0.24)
    bar_x = (width - bar_w) // 2
    vf = f'drawbox=x={bar_x}:y={bar_y}:w={bar_w}:h={bar_h}:color={accent}:t=fill,ass={ass_path.name}'
    try:
        ff([
            '-f', 'lavfi', '-i', f'color=c={background}:s={width}x{height}:r=30:d={duration:.3f}',
            '-f', 'lavfi', '-i', f'anullsrc=r=48000:cl=stereo:d={duration:.3f}',
            '-vf', vf,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest',
            output_path.name if work_dir is None else str(output_path),
        ], folder)
    finally:
        ass_path.unlink(missing_ok=True)
    return output_path


def waveform_peaks(path, samples=80):
    import av
    samples = int(number(samples, 'samples', 8, 512))
    raw = bytearray()
    with av.open(str(path), options={'protocol_whitelist': 'file,pipe'}) as container:
        audio = next(iter(container.streams.audio), None)
        if audio is None:
            return {'has_audio': False, 'samples': [], 'peak_db': None, 'energy_peaks': []}
        resampler = av.AudioResampler(format='s16', layout='mono', rate=8000)
        for frame in container.decode(audio):
            for out in resampler.resample(frame):
                raw.extend(bytes(out.planes[0]))
    if len(raw) < 2:
        return {'has_audio': True, 'samples': [0.0] * samples, 'peak_db': -96.0, 'energy_peaks': []}
    total_i16 = len(raw) // 2
    duration = total_i16 / 8000.0
    view = memoryview(raw[:total_i16 * 2]).cast('h')
    step = max(1, total_i16 // samples)
    peaks = []
    global_max = 0
    for i in range(samples):
        lo = min(total_i16 - 1, i * step)
        hi = total_i16 if i == samples - 1 else min(total_i16, lo + step)
        if hi <= lo:
            peaks.append(0.0)
            continue
        stride = max(1, (hi - lo) // 64)
        chunk_max = max(abs(view[idx]) for idx in range(lo, hi, stride))
        global_max = max(global_max, chunk_max)
        peaks.append(round(chunk_max / 32768.0, 4))
    peak_db = round(20.0 * math.log10(max(global_max / 32768.0, 1e-5)), 2)
    threshold = max(peaks) * 0.65 if peaks else 0.0
    energy_peaks = [
        {'t': round((i + 0.5) * duration / max(len(peaks), 1), 2), 'peak': val}
        for i, val in enumerate(peaks) if val > 0.05 and val >= threshold
    ][:8]
    return {'has_audio': True, 'samples': peaks, 'peak_db': peak_db, 'energy_peaks': energy_peaks}


def extract_storyboard(path, out_dir, count=6, width=160, height=90, duration=None, sheet_name='contact_sheet.png'):
    count = int(number(count, 'storyboard count', 1, 24))
    width = int(number(width, 'thumb width', 32, 320))
    height = int(number(height, 'thumb height', 32, 320))
    if duration is None:
        duration = probe(path)['duration']
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob('thumb_*.png'):
        old.unlink()
    sheet_path = out_dir / sheet_name
    sheet_path.unlink(missing_ok=True)
    fps = count / max(duration, 0.25)
    vf = (
        f'fps={fps:.4f},scale={width}:{height}:force_original_aspect_ratio=decrease,'
        f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#0b1120'
    )
    ff(['-i', str(path), '-vf', vf, '-frames:v', str(count), 'thumb_%02d.png'], out_dir)
    files = sorted(out_dir.glob('thumb_*.png'))
    if not files:
        ff(['-i', str(path), '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#0b1120', '-frames:v', '1', 'thumb_01.png'], out_dir)
        files = sorted(out_dir.glob('thumb_*.png'))
    actual = len(files)
    cols = min(3, max(1, actual))
    rows = max(1, math.ceil(actual / cols))
    tile_vf = (
        f'fps={fps:.4f},scale={width}:{height}:force_original_aspect_ratio=decrease,'
        f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#0b1120,'
        f'tile={cols}x{rows}:padding=6:color=#0b1120'
    )
    try:
        ff(['-i', str(path), '-vf', tile_vf, '-frames:v', '1', sheet_name], out_dir)
    except RuntimeError:
        ff(['-i', str(files[0]), sheet_name], out_dir)
    if not sheet_path.is_file() and files:
        sheet_path.write_bytes(files[0].read_bytes())
    thumbs = [
        {
            'index': idx,
            'time': round((idx + 0.5) * duration / max(actual, 1), 3),
            'path': str(item),
        }
        for idx, item in enumerate(files)
    ]
    return thumbs, str(sheet_path)


def analyze_video_frames(path, duration=None, max_samples=20):
    """Measure luminance, contrast, black frames, motion, and visual scene cuts using PyAV."""
    import av
    info = probe(path)
    duration = float(duration if duration is not None else info['duration'])
    fps = max(1.0, info.get('fps') or 30.0)
    est_frames = max(1, round(duration * fps))
    stride = max(1, est_frames // max(1, int(max_samples)))

    samples = []
    with av.open(str(path), options={'protocol_whitelist': 'file,pipe'}) as container:
        stream = next(iter(container.streams.video), None)
        if stream is None:
            raise ValueError('Missing video stream')
        for idx, frame in enumerate(container.decode(stream)):
            if idx % stride != 0:
                continue
            small = frame.reformat(width=48, height=27, format='gray')
            buf = bytes(small.planes[0])
            stride_line = small.planes[0].line_size
            pixels = []
            for y in range(27):
                row_start = y * stride_line
                pixels.extend(buf[row_start:row_start + 48])
            n_px = len(pixels)
            mean = sum(pixels) / (255.0 * n_px)
            var = sum((p / 255.0 - mean) ** 2 for p in pixels) / n_px
            t = round(float(frame.pts * stream.time_base) if frame.pts is not None else (idx / fps), 2)
            samples.append({'t': t, 'luma': mean, 'std': math.sqrt(var), 'pixels': pixels})
            if len(samples) >= max_samples:
                break

    if not samples:
        return {'luma_avg': 0.0, 'contrast_score': 0.0, 'black_frames': 0, 'motion_level': 'static', 'scene_cuts': [], 'recommendations': []}

    luma_avg = round(sum(s['luma'] for s in samples) / len(samples), 3)
    contrast_score = round(sum(s['std'] for s in samples) / len(samples), 3)
    black_frames = sum(1 for s in samples if s['luma'] < 0.03 and s['std'] < 0.02)

    deltas = []
    scene_cuts = []
    last_cut_t = -1.0
    for prev, cur in zip(samples, samples[1:]):
        diff = sum(abs(a - b) for a, b in zip(prev['pixels'], cur['pixels'])) / (255.0 * len(cur['pixels']))
        deltas.append(diff)
        if diff > 0.16 and cur['t'] - last_cut_t >= 0.75:
            scene_cuts.append(cur['t'])
            last_cut_t = cur['t']

    avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
    motion_level = 'static' if avg_delta < 0.025 else ('moderate' if avg_delta < 0.09 else 'dynamic')

    hints = []
    if luma_avg < 0.18:
        hints.append('Footage looks dark overall; apply studio grade or +0.05 brightness.')
    elif contrast_score < 0.08:
        hints.append('Low contrast detected; crisp or cinematic grade will add punch.')
    if motion_level == 'static':
        hints.append('Static camera motion; add motion="zoom_in" or "zoom_out" to keep energy up.')
    if info['width'] > info['height']:
        hints.append('Landscape framing; use fit="blur_fill" for vertical 9:16 Reels without cropping.')
    elif info['height'] > info['width']:
        hints.append('Portrait framing; fits reels/portrait presets natively.')
    if black_frames > 0:
        hints.append(f'{black_frames} dark/black frame sample(s) found; trim ends or fade smoothly.')

    return {
        'luma_avg': luma_avg,
        'contrast_score': contrast_score,
        'black_frames': black_frames,
        'motion_level': motion_level,
        'scene_cuts': scene_cuts,
        'recommendations': hints,
    }


def measure_loudness(path, folder):
    """Run FFmpeg ebur128 scanner and extract integrated LUFS, LRA, and true peak dBTP."""
    info = probe(path)
    if not info['audio']:
        return {'has_audio': False, 'lufs': None, 'lra': None, 'true_peak_db': None}
    log = ff(['-protocol_whitelist', 'file,pipe', '-i', path, '-af', 'ebur128=peak=true:framelog=quiet', '-vn', '-f', 'null', '-'], folder)
    text = log.read_text(errors='replace')
    lufs_matches = re.findall(r'I:\s*([-+]?\d+(?:\.\d+)?)\s*LUFS', text)
    lra_matches = re.findall(r'LRA:\s*([-+]?\d+(?:\.\d+)?)\s*LU', text)
    peak_matches = re.findall(r'Peak:\s*([-+]?\d+(?:\.\d+)?)\s*dBFS', text)
    return {
        'has_audio': True,
        'lufs': float(lufs_matches[-1]) if lufs_matches else None,
        'lra': float(lra_matches[-1]) if lra_matches else None,
        'true_peak_db': float(peak_matches[-1]) if peak_matches else None,
    }
