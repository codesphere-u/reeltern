"""Content-addressed media snapshots and immutable, inspectable edit decisions."""
import json
from pathlib import Path
import re
import shutil
import uuid
from .media import atomic_json, digest, key, probe, number, ff, silence_ranges, kept_ranges

from .effects import (
    CAPTION_MODES, CAPTION_STYLES, COLOR_GRADES, FIT_MODES, FLIPS, MOTIONS,
    ROTATIONS, TRANSITIONS, analyze_video_frames, extract_storyboard,
    hex_color, render_title_card, waveform_peaks,
)

PRESETS = {
    'landscape': (1280, 720),
    'portrait': (720, 1280),
    'square': (720, 720),
    'fhd': (1920, 1080),
    'reels': (1080, 1920),
}
AUDIO_EXTS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.opus'}
VIDEO_EXTS = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'}


class Workspace:
    def __init__(self, root, media_root=None):
        self.root = Path(root).expanduser().resolve()
        self.media_root = Path(media_root).expanduser().resolve() if media_root else None
        for name in ('assets', 'plans', 'jobs', 'cache', 'analysis', 'transcripts', 'agent_runs'):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def path(self, kind, identifier, suffix='.json'):
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{32}|[a-f0-9]{64}', identifier):
            raise ValueError('Invalid identifier')
        candidate = self.root / kind / (identifier + suffix)
        if not candidate.resolve().is_relative_to(self.root):
            raise ValueError('Workspace path escapes its root')
        return candidate

    def read(self, kind, identifier):
        return json.loads(self.path(kind, identifier).read_text(encoding='utf-8'))

    def _resolve_import_path(self, filename):
        path = Path(filename).expanduser()
        if self.media_root:
            path = (self.media_root / path).resolve()
            if not path.is_relative_to(self.media_root):
                raise ValueError('Media must be inside the configured media root')
        else:
            path = path.resolve()
        return path

    def _snapshot_asset(self, path, metadata):
        staging = self.root / 'assets' / (uuid.uuid4().hex + '.tmp')
        try:
            shutil.copyfile(path, staging)
            meta = metadata(staging)
            identifier = digest(staging)
            dest = self.path('assets', identifier, '.media')
            if dest.exists() and digest(dest) != identifier:
                raise ValueError('Existing asset snapshot has been modified')
            staging.replace(dest)
            asset = {'id': identifier, 'name': path.name, 'bytes': dest.stat().st_size, **meta}
            atomic_json(self.path('assets', identifier), asset)
            return asset
        finally:
            staging.unlink(missing_ok=True)

    def import_media(self, filename):
        path = self._resolve_import_path(filename)
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
            raise ValueError('Choose a local MP4, MOV, MKV, WebM, AVI or M4V video')
        if path.stat().st_size > 8 * 1024**3:
            raise ValueError('Import limit is 8 GiB per file')
        return self._snapshot_asset(path, probe)

    def import_audio(self, filename):
        path = self._resolve_import_path(filename)
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
            raise ValueError('Choose a local WAV, MP3, M4A, AAC, FLAC, OGG or OPUS audio file')
        if path.stat().st_size > 1024**3:
            raise ValueError('Audio import limit is 1 GiB per file')
        return self._snapshot_asset(path, lambda p: probe(p, allow_audio_only=True))

    def assets(self):
        return [json.loads(p.read_text()) for p in sorted((self.root / 'assets').glob('*.json'))]

    def asset(self, identifier, verify=False):
        asset = self.read('assets', identifier)
        if asset.get('id') != identifier:
            raise ValueError('Asset metadata identity mismatch')
        if verify and digest(self.path('assets', identifier, '.media')) != identifier:
            raise ValueError('Asset snapshot changed; re-import the original footage')
        return asset

    def analyze(self, identifier, threshold_db=-35, minimum_silence=0.6, margin=0.15):
        asset = self.asset(identifier, verify=True)
        threshold_db = number(threshold_db, 'threshold_db', -80, -5)
        minimum_silence = number(minimum_silence, 'minimum_silence', 0.1, 10)
        margin = number(margin, 'margin', 0, 2)
        analysis_id = key({'asset': identifier, 'threshold': threshold_db, 'minimum': minimum_silence, 'margin': margin, 'version': 1})
        saved = self.path('analysis', analysis_id)
        if saved.exists():
            return self.read('analysis', analysis_id)
        folder = self.root / 'analysis' / uuid.uuid4().hex
        folder.mkdir()
        silences = []
        if asset['audio']:
            log = ff(['-protocol_whitelist', 'file,pipe', '-i', self.path('assets', identifier, '.media'), '-map', '0:a:0', '-af', f'silencedetect=noise={threshold_db}dB:d={minimum_silence}', '-vn', '-f', 'null', '-'], folder)
            silences = silence_ranges(log.read_text(errors='replace'), asset['duration'])
        kept = kept_ranges(silences, asset['duration'], margin)
        warnings = ['Quiet sections are not necessarily mistakes. Review the cuts before exporting.']
        if not asset['audio']:
            warnings.append('No audio track: all footage retained.')
        if not kept:
            kept = [[0.0, asset['duration']]]
            warnings.append('All audio was below the threshold: kept everything to avoid an empty edit.')
        result = {'id': analysis_id, 'asset_id': identifier, 'duration': asset['duration'], 'silences': silences,
                  'kept_ranges': kept, 'threshold_db': threshold_db, 'minimum_silence': minimum_silence, 'margin': margin,
                  'warnings': warnings, 'method': 'FFmpeg audio loudness; no speech understanding'}
        atomic_json(saved, result)
        return result

    def create_plan(
        self,
        clips,
        preset='landscape',
        fit='contain',
        parent=None,
        notes='Manual edit',
        transcript_ids=None,
        transition='cut',
        transition_duration=0.4,
        normalize_audio=False,
        caption_mode='soft',
        caption_style='clean',
        voice_cleanup=False,
        progress_bar=False,
        progress_color='#38bdf8',
        music_asset_id=None,
        music_volume=0.18,
        music_ducking=True,
    ):
        if preset not in PRESETS or fit not in FIT_MODES:
            raise ValueError('Choose a supported preset and contain/cover/blur_fill fit')
        if transition not in TRANSITIONS:
            raise ValueError(f'Transition must be one of {", ".join(TRANSITIONS)}')
        transition_duration = number(transition_duration, 'transition duration', 0.15, 1.5)
        for flag_name, flag_val in (
            ('normalize_audio', normalize_audio),
            ('voice_cleanup', voice_cleanup),
            ('progress_bar', progress_bar),
            ('music_ducking', music_ducking),
        ):
            if not isinstance(flag_val, bool):
                raise ValueError(f'{flag_name} must be a boolean')
        progress_color = hex_color(progress_color, 'progress_color')
        music_volume = number(music_volume, 'music_volume', 0.0, 1.0)
        if music_asset_id is not None:
            music_asset = self.asset(music_asset_id)
            if not music_asset.get('audio'):
                raise ValueError('Music asset must contain an audio stream')
        if caption_mode not in CAPTION_MODES:
            raise ValueError(f'Caption mode must be one of {", ".join(CAPTION_MODES)}')
        if caption_style not in CAPTION_STYLES:
            raise ValueError(f'Caption style must be one of {", ".join(CAPTION_STYLES)}')
        if not isinstance(clips, list) or not 1 <= len(clips) <= 200:
            raise ValueError('A plan needs between 1 and 200 clips')
        if parent:
            self.plan(parent)
        if not isinstance(notes, str) or len(notes) > 2000:
            raise ValueError('Notes must be text of at most 2000 characters')
        from .transcript import get as get_transcript
        transcript_ids = [] if transcript_ids is None else transcript_ids
        if not isinstance(transcript_ids, list) or len(transcript_ids) > 200:
            raise ValueError('Provide a list of at most 200 transcript IDs')
        transcript_assets = [get_transcript(self, t)['asset_id'] for t in transcript_ids]
        if len(set(transcript_assets)) != len(transcript_assets):
            raise ValueError('Attach only one transcript per asset')

        allowed_clip_keys = {
            'asset_id', 'start', 'end', 'speed', 'reason',
            'grade', 'motion', 'fade_in', 'fade_out', 'volume', 'flip', 'rotate',
            'title_overlay', 'brightness', 'contrast', 'saturation',
        }
        extra_plan_fields = {}
        if transition != 'cut':
            extra_plan_fields['transition'] = transition
            if abs(transition_duration - 0.4) > 1e-6:
                extra_plan_fields['transition_duration'] = transition_duration
        if normalize_audio:
            extra_plan_fields['normalize_audio'] = True
        if caption_mode != 'soft':
            extra_plan_fields['caption_mode'] = caption_mode
        if caption_style != 'clean':
            extra_plan_fields['caption_style'] = caption_style
        if voice_cleanup:
            extra_plan_fields['voice_cleanup'] = True
        if progress_bar:
            extra_plan_fields['progress_bar'] = True
            if progress_color != '#38bdf8':
                extra_plan_fields['progress_color'] = progress_color
        if music_asset_id is not None:
            extra_plan_fields['music_asset_id'] = music_asset_id
            if abs(music_volume - 0.18) > 1e-6:
                extra_plan_fields['music_volume'] = music_volume
            if not music_ducking:
                extra_plan_fields['music_ducking'] = False

        normalized, cursor = [], 0
        for index, clip in enumerate(clips):
            if not isinstance(clip, dict) or set(clip) - allowed_clip_keys:
                raise ValueError('Clip contains unsupported fields')
            asset = self.asset(clip.get('asset_id'))
            if asset.get('kind') == 'audio' or asset.get('width', 0) <= 0:
                raise ValueError('Video clips must reference a video asset; attach audio tracks via music_asset_id')
            start = number(clip.get('start', 0), 'start', 0, asset['duration'])
            end = number(clip.get('end', asset['duration']), 'end', 0, asset['duration'])
            speed = number(clip.get('speed', 1), 'speed', 0.25, 4.0)
            frames = round((end - start) / speed * 30)
            if end <= start or frames < 1:
                raise ValueError('Every clip must have at least one output frame')
            reason = clip.get('reason', 'User selection')
            if not isinstance(reason, str) or len(reason) > 500:
                raise ValueError('Clip reason must be text of at most 500 characters')

            overlap_frames = 0
            if index > 0 and transition != 'cut':
                prev_dur = normalized[-1]['frames'] / 30
                cur_dur = frames / 30
                eff = min(transition_duration, prev_dur * 0.45, cur_dur * 0.45)
                overlap_frames = min(normalized[-1]['frames'] - 1, frames - 1, round(eff * 30))
                overlap_frames = max(0, overlap_frames)
            timeline_cursor = cursor - overlap_frames

            entry = {
                'asset_id': asset['id'],
                'start': start,
                'end': end,
                'speed': speed,
                'reason': reason,
                'timeline_start': timeline_cursor / 30,
                'frames': frames,
            }
            # Preserve identical v2 hash for plain cuts while supporting optional per-clip visual/audio polish.
            grade = clip.get('grade', 'none')
            if grade not in COLOR_GRADES:
                raise ValueError(f'Unknown color grade: {grade}')
            if grade != 'none':
                entry['grade'] = grade

            motion = clip.get('motion', 'none')
            if motion not in MOTIONS:
                raise ValueError(f'Unknown motion: {motion}')
            if motion != 'none':
                entry['motion'] = motion

            flip = clip.get('flip', 'none')
            if flip not in FLIPS:
                raise ValueError(f'Flip must be one of {", ".join(FLIPS)}')
            if flip != 'none':
                entry['flip'] = flip

            rotate = clip.get('rotate', 0)
            if isinstance(rotate, bool) or rotate not in ROTATIONS:
                raise ValueError('Rotate must be 0, 90, 180 or 270')
            if rotate:
                entry['rotate'] = int(rotate)

            for field, default_val, lo, hi in (
                ('fade_in', 0.0, 0.0, 5.0),
                ('fade_out', 0.0, 0.0, 5.0),
                ('volume', 1.0, 0.0, 2.0),
                ('brightness', 0.0, -0.5, 0.5),
                ('contrast', 1.0, 0.5, 2.0),
                ('saturation', 1.0, 0.0, 2.5),
            ):
                val = number(clip.get(field, default_val), field, lo, hi)
                if abs(val - default_val) > 1e-6:
                    entry[field] = val

            title_overlay = clip.get('title_overlay', '')
            if not isinstance(title_overlay, str) or len(title_overlay) > 100:
                raise ValueError('Title overlay must be text of at most 100 characters')
            if title_overlay.strip():
                entry['title_overlay'] = title_overlay.strip()

            normalized.append(entry)
            cursor = timeline_cursor + frames
        if cursor > 30 * 60 * 60 * 4:
            raise ValueError('Timeline limit is four hours')
        plan = {'version': 2, 'fps': 30, 'preset': preset, 'fit': fit, 'clips': normalized,
                'duration': cursor / 30, 'frames': cursor, 'parent': parent, 'notes': notes}
        if transcript_ids:
            plan['transcript_ids'] = transcript_ids
        if extra_plan_fields:
            plan.update(extra_plan_fields)
        identifier = key(plan)
        plan['id'] = identifier
        atomic_json(self.path('plans', identifier), plan)
        return plan

    def plan(self, identifier):
        plan = self.read('plans', identifier)
        if plan.get('id') != identifier or key({k: v for k, v in plan.items() if k != 'id'}) != identifier:
            raise ValueError('Plan was modified outside Reeltern; create a new revision')
        return plan

    def plans(self):
        return [self.plan(p.stem) for p in sorted((self.root / 'plans').glob('*.json'))]

    def suggest(self, identifier, preset='landscape', threshold_db=-35, minimum_silence=0.6, margin=0.15):
        analysis = self.analyze(identifier, threshold_db, minimum_silence, margin)
        return self.create_plan([{'asset_id': identifier, 'start': a, 'end': b, 'reason': 'Retained around audible activity; review for meaning'} for a, b in analysis['kept_ranges']], preset=preset, notes='Silence-assisted first pass. ' + ' '.join(analysis['warnings']))

    def compare(self, before, after):
        left, right = self.plan(before), self.plan(after)
        def signatures(plan):
            return [(c['asset_id'], c['start'], c['end'], c['speed']) for c in plan['clips']]
        a, b = signatures(left), signatures(right)
        return {'before': before, 'after': after, 'duration_before': left['duration'], 'duration_after': right['duration'],
                'duration_change': right['duration'] - left['duration'], 'before_order': a, 'after_order': b,
                'preset_change': [left['preset'], right['preset']], 'fit_change': [left['fit'], right['fit']],
                'transition_change': [left.get('transition', 'cut'), right.get('transition', 'cut')],
                'caption_mode_change': [left.get('caption_mode', 'soft'), right.get('caption_mode', 'soft')],
                'note': 'Each tuple is asset ID, source start, source end, playback speed. Original plans remain available.'}

    def create_card(self, title, subtitle='', duration=3.0, preset='landscape', background='#0f172a', accent='#38bdf8'):
        if preset not in PRESETS:
            raise ValueError('Unsupported preset')
        width, height = PRESETS[preset]
        card_dir = self.root / 'analysis' / 'cards'
        card_dir.mkdir(parents=True, exist_ok=True)
        card_key = key({'title': title, 'subtitle': subtitle, 'duration': duration, 'preset': preset, 'background': background, 'accent': accent})
        out_path = card_dir / f'card-{card_key[:16]}.mp4'
        if not out_path.exists():
            render_title_card(out_path, width, height, duration, title, subtitle, background=background, accent=accent, work_dir=card_dir)
        previous_root = self.media_root
        try:
            self.media_root = None
            return self.import_media(out_path)
        finally:
            self.media_root = previous_root

    def visuals_cache_id(self, identifier, thumbs=6, samples=80):
        return key({'asset': identifier, 'visuals': 2, 'thumbs': int(thumbs), 'samples': int(samples)})

    def inspect_visuals(self, identifier, thumbs=6, samples=80):
        asset = self.asset(identifier, verify=True)
        source = self.path('assets', identifier, '.media')
        cache_path = self.path('analysis', self.visuals_cache_id(identifier, thumbs, samples))
        thumb_dir = self.root / 'analysis' / 'thumbs' / identifier[:16]
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding='utf-8'))
            sheet_ok = cached.get('contact_sheet') is None or Path(cached['contact_sheet']).is_file()
            if sheet_ok and all(Path(item['path']).is_file() for item in cached.get('storyboard', [])):
                return cached
        waveform = waveform_peaks(source, samples=samples)
        if asset.get('kind') == 'audio' or asset.get('width', 0) <= 0:
            result = {
                'asset_id': identifier,
                'kind': 'audio',
                'duration': asset['duration'],
                'contact_sheet': None,
                'storyboard': [],
                'waveform': waveform,
                'telemetry': {'motion_level': 'audio_only', 'scene_cuts': [], 'recommendations': ['Audio track ready to attach via music_asset_id.']},
            }
        else:
            storyboard, contact_sheet = extract_storyboard(source, thumb_dir, count=thumbs, duration=asset['duration'])
            telemetry = analyze_video_frames(source, duration=asset['duration'])
            result = {
                'asset_id': identifier,
                'kind': 'video',
                'duration': asset['duration'],
                'contact_sheet': contact_sheet,
                'storyboard': storyboard,
                'waveform': waveform,
                'telemetry': telemetry,
            }
        atomic_json(cache_path, result)
        return result

    @staticmethod
    def _raw_clips(plan):
        keys = {
            'asset_id', 'start', 'end', 'speed', 'reason', 'grade', 'motion',
            'fade_in', 'fade_out', 'volume', 'flip', 'rotate', 'title_overlay',
            'brightness', 'contrast', 'saturation',
        }
        return [{k: v for k, v in c.items() if k in keys} for c in plan['clips']]

    def plan_options(self, plan):
        opts = {}
        for k in (
            'transition', 'transition_duration', 'normalize_audio',
            'caption_mode', 'caption_style', 'voice_cleanup',
            'progress_bar', 'progress_color', 'music_asset_id',
            'music_volume', 'music_ducking',
        ):
            if k in plan:
                opts[k] = plan[k]
        return opts

    def split_clip(self, plan_id, clip_index, offset_seconds, notes=None):
        plan = self.plan(plan_id)
        if type(clip_index) is not int or not 0 <= clip_index < len(plan['clips']):
            raise ValueError('Clip index out of range')
        clips = self._raw_clips(plan)
        target = clips[clip_index]
        clip_output_dur = (target['end'] - target['start']) / target['speed']
        offset = number(offset_seconds, 'split offset', 0.05, clip_output_dur - 0.05)
        split_source = round(target['start'] + offset * target['speed'], 4)
        if split_source <= target['start'] + 0.01 or split_source >= target['end'] - 0.01:
            raise ValueError('Split offset is too close to clip boundary')
        left = dict(target)
        left['end'] = split_source
        left['reason'] = f"{target['reason']} (Part 1)".strip()
        right = dict(target)
        right['start'] = split_source
        right['reason'] = f"{target['reason']} (Part 2)".strip()
        new_clips = clips[:clip_index] + [left, right] + clips[clip_index + 1:]
        return self.create_plan(
            new_clips,
            preset=plan['preset'],
            fit=plan['fit'],
            parent=plan['id'],
            notes=notes or f'Split clip {clip_index + 1} at {offset:.2f}s',
            transcript_ids=plan.get('transcript_ids'),
            **self.plan_options(plan),
        )

    def update_clip(self, plan_id, clip_index, changes, notes='Updated clip'):
        plan = self.plan(plan_id)
        if type(clip_index) is not int or not 0 <= clip_index < len(plan['clips']):
            raise ValueError('Clip index out of range')
        if not isinstance(changes, dict) or not changes:
            raise ValueError('Provide clip changes')
        clips = self._raw_clips(plan)
        clips[clip_index].update(changes)
        return self.create_plan(
            clips,
            preset=plan['preset'],
            fit=plan['fit'],
            parent=plan['id'],
            notes=notes,
            transcript_ids=plan.get('transcript_ids'),
            **self.plan_options(plan),
        )

    def update_plan_style(
        self,
        plan_id,
        *,
        preset=None,
        fit=None,
        transition=None,
        transition_duration=None,
        normalize_audio=None,
        caption_mode=None,
        caption_style=None,
        voice_cleanup=None,
        progress_bar=None,
        progress_color=None,
        music_asset_id=None,
        clear_music=False,
        music_volume=None,
        music_ducking=None,
        notes='Updated timeline style',
    ):
        plan = self.plan(plan_id)
        opts = self.plan_options(plan)
        for key_name, val in (
            ('transition', transition),
            ('transition_duration', transition_duration),
            ('normalize_audio', normalize_audio),
            ('caption_mode', caption_mode),
            ('caption_style', caption_style),
            ('voice_cleanup', voice_cleanup),
            ('progress_bar', progress_bar),
            ('progress_color', progress_color),
            ('music_asset_id', music_asset_id),
            ('music_volume', music_volume),
            ('music_ducking', music_ducking),
        ):
            if val is not None:
                opts[key_name] = val
        if clear_music:
            opts.pop('music_asset_id', None)
        return self.create_plan(
            self._raw_clips(plan),
            preset=preset or plan['preset'],
            fit=fit or plan['fit'],
            parent=plan['id'],
            notes=notes,
            transcript_ids=plan.get('transcript_ids'),
            **opts,
        )
