"""Deterministic AI Director composition & post-render visual/audio quality auditing."""
from pathlib import Path
from .effects import analyze_video_frames, extract_storyboard, measure_loudness, waveform_peaks
from .media import atomic_json, number

DIRECTOR_STYLES = {
    'cinematic': {
        'preset': 'fhd',
        'grade': 'cinematic',
        'transition': 'crossfade',
        'transition_duration': 0.45,
        'normalize_audio': True,
        'voice_cleanup': True,
        'caption_style': 'clean',
        'progress_bar': False,
        'progress_color': '#38bdf8',
        'motion_cycle': ('zoom_in', 'zoom_out'),
        'fade_in': 0.35,
        'fade_out': 0.45,
        'music_volume': 0.16,
    },
    'viral_reel': {
        'preset': 'reels',
        'grade': 'vivid',
        'transition': 'slideleft',
        'transition_duration': 0.25,
        'normalize_audio': True,
        'voice_cleanup': True,
        'caption_style': 'kinetic',
        'progress_bar': True,
        'progress_color': '#38bdf8',
        'motion_cycle': ('zoom_in', 'none', 'zoom_out'),
        'fade_in': 0.15,
        'fade_out': 0.25,
        'music_volume': 0.20,
    },
    'tutorial': {
        'preset': 'landscape',
        'grade': 'studio',
        'transition': 'cut',
        'transition_duration': 0.25,
        'normalize_audio': True,
        'voice_cleanup': True,
        'caption_style': 'boxed',
        'progress_bar': True,
        'progress_color': '#22c55e',
        'motion_cycle': ('none',),
        'fade_in': 0.2,
        'fade_out': 0.3,
        'music_volume': 0.12,
    },
    'documentary': {
        'preset': 'fhd',
        'grade': 'warm',
        'transition': 'crossfade',
        'transition_duration': 0.5,
        'normalize_audio': True,
        'voice_cleanup': True,
        'caption_style': 'clean',
        'progress_bar': False,
        'progress_color': '#f59e0b',
        'motion_cycle': ('zoom_in', 'pan_right', 'zoom_out'),
        'fade_in': 0.4,
        'fade_out': 0.5,
        'music_volume': 0.18,
    },
    'noir_trailer': {
        'preset': 'fhd',
        'grade': 'noir',
        'transition': 'dissolve',
        'transition_duration': 0.45,
        'normalize_audio': True,
        'voice_cleanup': True,
        'caption_style': 'bold',
        'progress_bar': False,
        'progress_color': '#e2e8f0',
        'motion_cycle': ('zoom_in', 'zoom_out'),
        'fade_in': 0.4,
        'fade_out': 0.6,
        'music_volume': 0.24,
    },
}


def _select_budgeted_ranges(candidates, budget):
    """Select chronological highest-scoring intervals within budget (never reorders or invents timestamps)."""
    if budget is None:
        return candidates
    total = sum(c['end'] - c['start'] for c in candidates)
    if total <= budget:
        return candidates
    scored = []
    n = len(candidates)
    for idx, item in enumerate(candidates):
        dur = item['end'] - item['start']
        # Boost opening/closing anchors and higher-energy segments while fitting target budget.
        anchor_bonus = 0.25 if idx in (0, n - 1) else 0.0
        scored.append((item.get('score', 0.5) + anchor_bonus, idx, dur, item))
    chosen = []
    remaining = budget
    for _, idx, dur, item in sorted(scored, key=lambda x: x[0], reverse=True):
        if dur <= remaining + 0.05:
            chosen.append((idx, item))
            remaining -= dur
    if not chosen and candidates:
        # Trim the strongest candidate cleanly down to budget.
        best = max(candidates, key=lambda x: x.get('score', 0.5))
        trimmed = dict(best)
        trimmed['end'] = round(min(best['end'], best['start'] + max(0.3, budget)), 3)
        trimmed['reason'] = f"{best['reason']} (tightened to budget)"
        return [trimmed]
    return [item for _, item in sorted(chosen, key=lambda x: x[0])]


def _asset_candidates(ws, asset_id, transcript_doc):
    asset = ws.asset(asset_id, verify=True)
    if transcript_doc and transcript_doc['asset_id'] == asset_id:
        out = []
        for cue in transcript_doc['cues']:
            out.append({
                'asset_id': asset_id,
                'start': cue['start'],
                'end': cue['end'],
                'reason': f"Transcript {cue['id']}: {cue['text'][:240]}",
                'score': min(1.0, len(cue['text']) / 80.0),
            })
        return out

    analysis = ws.analyze(asset_id)
    source = ws.path('assets', asset_id, '.media')
    wf = waveform_peaks(source, samples=48)
    peaks = wf.get('samples') or []
    dur = max(0.25, asset['duration'])
    out = []
    for a, b in analysis['kept_ranges']:
        if b - a < 0.2:
            continue
        if peaks:
            lo = max(0, min(len(peaks) - 1, int(a / dur * len(peaks))))
            hi = max(lo + 1, min(len(peaks), int(b / dur * len(peaks)) + 1))
            energy = sum(peaks[lo:hi]) / max(1, hi - lo)
        else:
            energy = 0.5
        out.append({
            'asset_id': asset_id,
            'start': a,
            'end': b,
            'reason': 'Active speech/motion highlight',
            'score': round(0.4 + energy, 3),
        })
    return out or [{'asset_id': asset_id, 'start': 0.0, 'end': asset['duration'], 'reason': 'Full source clip', 'score': 0.5}]


def compose_plan(
    ws,
    asset_ids,
    director_style='cinematic',
    preset=None,
    target_seconds=None,
    intro_title='',
    transcript_id=None,
    music_asset_id=None,
    notes='AI director composition',
):
    """Assemble a polished, style-consistent, reversible timeline plan from local assets."""
    if director_style not in DIRECTOR_STYLES:
        raise ValueError(f'Director style must be one of {", ".join(DIRECTOR_STYLES)}')
    if not isinstance(asset_ids, list) or not 1 <= len(asset_ids) <= 20:
        raise ValueError('Provide between 1 and 20 video asset IDs')
    profile = DIRECTOR_STYLES[director_style]
    from .workspace import PRESETS
    target_preset = preset or profile['preset']
    if target_preset not in PRESETS:
        raise ValueError('Unsupported preset')
    if target_seconds is not None:
        target_seconds = number(target_seconds, 'target_seconds', 1.0, 14400.0)
    if not isinstance(intro_title, str) or len(intro_title) > 120:
        raise ValueError('Intro title must be text of at most 120 characters')

    transcript_doc = None
    transcript_ids = []
    if transcript_id is not None:
        from .transcript import get as get_transcript
        transcript_doc = get_transcript(ws, transcript_id)
        transcript_ids = [transcript_id]

    assets = [ws.asset(aid, verify=True) for aid in asset_ids]
    for a in assets:
        if a.get('kind') == 'audio' or a.get('width', 0) <= 0:
            raise ValueError('Director asset_ids must point to video assets; attach audio with music_asset_id')

    target_w, target_h = PRESETS[target_preset]
    target_ratio = target_w / target_h
    aspect_mismatch = any(abs((a['width'] / max(1, a['height'])) - target_ratio) > 0.45 for a in assets)
    fit = 'blur_fill' if aspect_mismatch else 'contain'

    intro_card = None
    intro_dur = 0.0
    if intro_title.strip():
        intro_dur = 1.6 if target_seconds is None or target_seconds >= 4.0 else 1.0
        intro_card = ws.create_card(
            intro_title.strip(),
            subtitle=director_style.replace('_', ' ').title(),
            duration=intro_dur,
            preset=target_preset,
            accent=profile['progress_color'],
        )

    candidates = []
    for a in assets:
        candidates.extend(_asset_candidates(ws, a['id'], transcript_doc))
    remaining_budget = None if target_seconds is None else max(0.5, target_seconds - intro_dur)
    chosen = _select_budgeted_ranges(candidates, remaining_budget)

    motion_cycle = profile['motion_cycle']
    clips = []
    if intro_card is not None:
        clips.append({
            'asset_id': intro_card['id'],
            'start': 0.0,
            'end': round(intro_card['duration'], 3),
            'speed': 1.0,
            'grade': 'none',
            'motion': 'zoom_in',
            'fade_in': min(0.25, intro_card['duration'] * 0.35),
            'reason': f'Title slate: {intro_title.strip()}',
        })

    for idx, item in enumerate(chosen):
        entry = {
            'asset_id': item['asset_id'],
            'start': item['start'],
            'end': item['end'],
            'speed': 1.0,
            'reason': item['reason'],
        }
        if profile['grade'] != 'none':
            entry['grade'] = profile['grade']
        motion = motion_cycle[idx % len(motion_cycle)]
        clip_dur = item['end'] - item['start']
        if motion != 'none' and clip_dur >= 0.8:
            entry['motion'] = motion
        if idx == 0 and intro_card is None:
            entry['fade_in'] = min(profile['fade_in'], clip_dur * 0.35)
        if idx == len(chosen) - 1:
            entry['fade_out'] = min(profile['fade_out'], clip_dur * 0.35)
        clips.append(entry)

    caption_mode = 'both' if transcript_ids else 'soft'
    plan = ws.create_plan(
        clips,
        preset=target_preset,
        fit=fit,
        notes=notes,
        transcript_ids=transcript_ids,
        transition=profile['transition'],
        transition_duration=profile['transition_duration'],
        normalize_audio=profile['normalize_audio'],
        caption_mode=caption_mode,
        caption_style=profile['caption_style'],
        voice_cleanup=profile['voice_cleanup'],
        progress_bar=profile['progress_bar'],
        progress_color=profile['progress_color'],
        music_asset_id=music_asset_id,
        music_volume=profile['music_volume'],
        music_ducking=True,
    )
    return {
        'plan': plan,
        'composition_summary': {
            'director_style': director_style,
            'preset': target_preset,
            'auto_fit': fit,
            'transition': profile['transition'],
            'grade': profile['grade'],
            'caption_style': profile['caption_style'] if transcript_ids else 'none',
            'intro_card_created': intro_card is not None,
            'music_attached': music_asset_id is not None,
            'clip_count': len(plan['clips']),
            'duration': plan['duration'],
        },
    }


def audit_job_render(ws, renderer, job_id):
    """Run pixel exposure, black-frame, contact sheet, and EBU R128 loudness QA on a finished job."""
    state = renderer.status(job_id)
    if state['status'] != 'complete':
        raise ValueError('Audit requires a completed render job')
    output = Path(state['output'])
    if not output.is_file():
        raise ValueError('Rendered output file is missing')

    audit_dir = ws.root / 'jobs' / job_id / 'audit'
    audit_dir.mkdir(parents=True, exist_ok=True)
    thumbs, sheet_path = extract_storyboard(output, audit_dir, count=6, sheet_name='render_contact_sheet.png')
    visual = analyze_video_frames(output)
    loudness = measure_loudness(output, audit_dir)

    issues = []
    suggestions = []
    if visual['luma_avg'] < 0.14:
        issues.append(f"Low average brightness ({visual['luma_avg']:.2f})")
        suggestions.append('Use style_clip with brightness=0.06 or grade="studio".')
    elif visual['luma_avg'] > 0.88:
        issues.append(f"Overexposed highlights (luma_avg={visual['luma_avg']:.2f})")
        suggestions.append('Lower brightness or switch from "vivid" to "cinematic".')
    if visual['black_frames'] > 0:
        issues.append(f"{visual['black_frames']} near-black frame(s) detected in samples")
        suggestions.append('Trim silent black leader/tail or shorten fade durations.')
    if loudness['has_audio'] and loudness['lufs'] is not None:
        if loudness['lufs'] < -23.0:
            issues.append(f"Quiet integrated audio ({loudness['lufs']:.1f} LUFS)")
            suggestions.append('Enable normalize_audio=true via apply_timeline_style.')
        if loudness['true_peak_db'] is not None and loudness['true_peak_db'] > -0.3:
            issues.append(f"Audio true peak near clipping ({loudness['true_peak_db']:.1f} dBFS)")
            suggestions.append('Lower clip volume or enable normalize_audio=true (-1.5 dBTP ceiling).')

    report = {
        'job_id': job_id,
        'plan_id': state['plan_id'],
        'passed': len(issues) == 0,
        'luma_avg': visual['luma_avg'],
        'contrast_score': visual['contrast_score'],
        'black_frames': visual['black_frames'],
        'motion_level': visual['motion_level'],
        'lufs': loudness['lufs'],
        'true_peak_db': loudness['true_peak_db'],
        'contact_sheet': sheet_path,
        'thumb_count': len(thumbs),
        'issues': issues,
        'suggestions': suggestions,
    }
    atomic_json(ws.root / 'jobs' / job_id / 'audit.json', report)
    return report
