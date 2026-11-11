"""Content-addressed media snapshots and immutable, inspectable edit decisions."""
import json
from pathlib import Path
import re
import shutil
import uuid
from .media import atomic_json, digest, key, probe, number, ff, silence_ranges, kept_ranges

PRESETS = {'landscape': (1280, 720), 'portrait': (720, 1280), 'square': (720, 720)}


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

    def import_media(self, filename):
        path = Path(filename).expanduser()
        if self.media_root:
            path = (self.media_root / path).resolve()
            if not path.is_relative_to(self.media_root):
                raise ValueError('Media must be inside the configured media root')
        else:
            path = path.resolve()
        if not path.is_file() or path.suffix.lower() not in {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'}:
            raise ValueError('Choose a local MP4, MOV, MKV, WebM, AVI or M4V video')
        if path.stat().st_size > 8 * 1024**3:
            raise ValueError('Import limit is 8 GiB per file')
        staging = self.root / 'assets' / (uuid.uuid4().hex + '.tmp')
        try:
            shutil.copyfile(path, staging)
            metadata = probe(staging)
            identifier = digest(staging)
            dest = self.path('assets', identifier, '.media')
            if dest.exists() and digest(dest) != identifier:
                raise ValueError('Existing asset snapshot has been modified')
            staging.replace(dest)
            asset = {'id': identifier, 'name': path.name, 'bytes': dest.stat().st_size, **metadata}
            atomic_json(self.path('assets', identifier), asset)
            return asset
        finally:
            staging.unlink(missing_ok=True)

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

    def create_plan(self, clips, preset='landscape', fit='contain', parent=None, notes='Manual edit', transcript_ids=None):
        if preset not in PRESETS or fit not in ('contain', 'cover'):
            raise ValueError('Choose landscape/portrait/square and contain/cover')
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
        normalized, cursor = [], 0
        for clip in clips:
            if not isinstance(clip, dict) or set(clip) - {'asset_id', 'start', 'end', 'speed', 'reason'}:
                raise ValueError('Clip accepts only asset_id, start, end, speed and reason')
            asset = self.asset(clip.get('asset_id'))
            start = number(clip.get('start', 0), 'start', 0, asset['duration'])
            end = number(clip.get('end', asset['duration']), 'end', 0, asset['duration'])
            speed = number(clip.get('speed', 1), 'speed', 0.5, 2)
            frames = round((end - start) / speed * 30)
            if end <= start or frames < 1:
                raise ValueError('Every clip must have at least one output frame')
            reason = clip.get('reason', 'User selection')
            if not isinstance(reason, str) or len(reason) > 500:
                raise ValueError('Clip reason must be text of at most 500 characters')
            normalized.append({'asset_id': asset['id'], 'start': start, 'end': end, 'speed': speed,
                               'reason': reason, 'timeline_start': cursor / 30, 'frames': frames})
            cursor += frames
        if cursor > 30 * 60 * 60 * 4:
            raise ValueError('Timeline limit is four hours')
        plan = {'version': 2, 'fps': 30, 'preset': preset, 'fit': fit, 'clips': normalized,
                'duration': cursor / 30, 'frames': cursor, 'parent': parent, 'notes': notes}
        if transcript_ids:
            plan['transcript_ids'] = transcript_ids
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
                'note': 'Each tuple is asset ID, source start, source end, playback speed. Original plans remain available.'}
