"""Pure local validation and deterministic FFmpeg filter/graphics builders."""
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
}

TRANSITIONS = {
    'cut': None,
    'crossfade': 'fade',
    'wipeleft': 'wipeleft',
    'slideleft': 'slideleft',
    'dissolve': 'dissolve',
}

FLIPS = ('none', 'horizontal', 'vertical')
ROTATIONS = (0, 90, 180, 270)
CAPTION_MODES = ('soft', 'burn', 'both', 'none')
CAPTION_STYLES = ('clean', 'boxed', 'bold')

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


def clip_video_filters(clip, width, height):
    """Build safe deterministic FFmpeg video filters for a normalized clip."""
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


def build_captions_ass(width, height, cues, style='clean'):
    if style not in CAPTION_STYLES:
        raise ValueError(f'Unknown caption style: {style}')
    base_size = max(14, round(min(width, height) * (0.052 if style == 'bold' else 0.044)))
    margin_v = max(14, round(height * 0.085))
    margin_h = max(16, round(width * 0.06))
    if style == 'boxed':
        style_line = f'Style: Default,Sans,{base_size},&H00FFFFFF,&H00FFFFFF,&H000B1120,&H990B1120,-1,0,0,0,100,100,0,0,3,8,0,2,{margin_h},{margin_h},{margin_v},1'
    elif style == 'bold':
        style_line = f'Style: Default,Sans,{base_size},&H0058E2FF,&H00FFFFFF,&H000B1120,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,{margin_h},{margin_h},{margin_v},1'
    else:
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
            return {'has_audio': False, 'samples': [], 'peak_db': None}
        resampler = av.AudioResampler(format='s16', layout='mono', rate=8000)
        for frame in container.decode(audio):
            for out in resampler.resample(frame):
                raw.extend(bytes(out.planes[0]))
    if len(raw) < 2:
        return {'has_audio': True, 'samples': [0.0] * samples, 'peak_db': -96.0}
    total_i16 = len(raw) // 2
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
        # Subsample large strides quickly in pure Python without numpy.
        stride = max(1, (hi - lo) // 64)
        chunk_max = max(abs(view[idx]) for idx in range(lo, hi, stride))
        global_max = max(global_max, chunk_max)
        peaks.append(round(chunk_max / 32768.0, 4))
    peak_db = round(20.0 * math.log10(max(global_max / 32768.0, 1e-5)), 2)
    return {'has_audio': True, 'samples': peaks, 'peak_db': peak_db}


def extract_storyboard(path, out_dir, count=6, width=128, height=72, duration=None):
    count = int(number(count, 'storyboard count', 1, 24))
    width = int(number(width, 'thumb width', 32, 320))
    height = int(number(height, 'thumb height', 32, 320))
    if duration is None:
        duration = probe(path)['duration']
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob('thumb_*.png'):
        old.unlink()
    fps = count / max(duration, 0.25)
    vf = (
        f'fps={fps:.4f},scale={width}:{height}:force_original_aspect_ratio=decrease,'
        f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#0b1120'
    )
    ff(['-i', str(path), '-vf', vf, '-frames:v', str(count), 'thumb_%02d.png'], out_dir)
    files = sorted(out_dir.glob('thumb_*.png'))
    if not files:
        # Ultra-short fixture fallback: grab first frame.
        ff(['-i', str(path), '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#0b1120', '-frames:v', '1', 'thumb_01.png'], out_dir)
        files = sorted(out_dir.glob('thumb_*.png'))
    actual = len(files)
    return [
        {
            'index': idx,
            'time': round((idx + 0.5) * duration / max(actual, 1), 3),
            'path': str(item),
        }
        for idx, item in enumerate(files)
    ]
