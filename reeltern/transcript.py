"""Timecoded evidence for text-based edits; transcripts are supplied, not inferred."""
import re
from .media import atomic_json, key, number


def register(ws, asset_id, cues):
    asset = ws.asset(asset_id, verify=True)
    if not isinstance(cues, list) or not 1 <= len(cues) <= 10000:
        raise ValueError('Transcript requires 1–10000 cues')
    normalized = []
    previous_end = 0.0
    for index, cue in enumerate(cues):
        if not isinstance(cue, dict) or set(cue) != {'start', 'end', 'text'}:
            raise ValueError('Each cue requires exactly start, end and text')
        start = number(cue['start'], 'cue start', 0, asset['duration'])
        end = number(cue['end'], 'cue end', 0, asset['duration'])
        text = cue['text']
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError('Cue text must contain 1–2000 characters')
        if end <= start or start < previous_end - .000001:
            raise ValueError('Cues must be chronological, non-overlapping and have positive duration')
        text = ' '.join(text.split())
        normalized.append({'id': f'c{index+1:05d}', 'start': start, 'end': end, 'text': text})
        previous_end = end
    if sum(len(c['text']) for c in normalized) > 1_000_000:
        raise ValueError('Transcript text limit is one million characters')
    value = {'asset_id': asset_id, 'cues': normalized, 'provenance': 'User-supplied transcript; not verified against speech'}
    value['id'] = key(value)
    atomic_json(ws.path('transcripts', value['id']), value)
    return value


def get(ws, transcript_id):
    value = ws.read('transcripts', transcript_id)
    if value.get('id') != transcript_id or key({k: v for k, v in value.items() if k != 'id'}) != transcript_id:
        raise ValueError('Transcript was modified; register a new version')
    return value


def search(ws, transcript_id, query, limit=20):
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise ValueError('Search requires 1–200 characters')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Limit must be 1–100')
    transcript = get(ws, transcript_id)
    words = query.casefold().split()
    matches = [c for c in transcript['cues'] if all(word in c['text'].casefold() for word in words)]
    return {'transcript_id': transcript_id, 'total_matches': len(matches), 'cues': matches[:limit]}


def select(ws, transcript_id, cue_ids, preset='landscape', parent=None, notes='Transcript selection'):
    transcript = get(ws, transcript_id)
    if not isinstance(cue_ids, list) or not 1 <= len(cue_ids) <= 200 or any(not isinstance(i, str) for i in cue_ids):
        raise ValueError('Choose 1–200 cue IDs')
    if len(set(cue_ids)) != len(cue_ids):
        raise ValueError('Duplicate cue IDs are not allowed')
    lookup = {c['id']: c for c in transcript['cues']}
    if any(i not in lookup for i in cue_ids):
        raise ValueError('Selected cue does not exist in this transcript')
    # Caller-specified order is intentional. Preserve evidence in the clip reason.
    clips = [{'asset_id': transcript['asset_id'], 'start': lookup[i]['start'], 'end': lookup[i]['end'],
              'reason': f'Transcript {i}: {lookup[i]["text"][:350]}'} for i in cue_ids]
    return ws.create_plan(clips, preset=preset, parent=parent, notes=notes, transcript_ids=[transcript_id])


def parse_srt(text):
    if not isinstance(text, str) or len(text) > 2_000_000:
        raise ValueError('SRT must be text smaller than two million characters')
    result = []
    stamp = r'(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})'
    def seconds(groups):
        h, m, s, ms = map(int, groups)
        if m >= 60 or s >= 60:
            raise ValueError('Invalid subtitle timestamp')
        return h * 3600 + m * 60 + s + ms / 1000
    for block in re.split(r'\n\s*\n', text.lstrip('\ufeff').replace('\r\n', '\n').strip()):
        lines = block.splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        if len(lines) < 2:
            raise ValueError('Malformed SRT block')
        match = re.fullmatch(stamp + r'\s+-->\s+' + stamp, lines[0].strip())
        if not match:
            raise ValueError('Malformed SRT timestamps')
        result.append({'start': seconds(match.groups()[:4]), 'end': seconds(match.groups()[4:]), 'text': ' '.join(lines[1:])})
    return result


def timeline_captions(ws, plan):
    transcripts = [get(ws, identifier) for identifier in plan.get('transcript_ids', [])]
    cues = []
    for clip in plan['clips']:
        for transcript in transcripts:
            if transcript['asset_id'] != clip['asset_id']:
                continue
            for cue in transcript['cues']:
                start, end = max(cue['start'], clip['start']), min(cue['end'], clip['end'])
                if end <= start:
                    continue
                out_start = clip['timeline_start'] + (start-clip['start']) / clip['speed']
                out_end = min(clip['timeline_start'] + clip['frames']/30, clip['timeline_start'] + (end-clip['start']) / clip['speed'])
                if out_end - out_start >= .001:
                    cues.append({'start': out_start, 'end': out_end, 'text': cue['text']})
    return sorted(cues, key=lambda c: c['start'])


def srt(cues):
    def stamp(value):
        ms = round(value * 1000)
        hours, ms = divmod(ms, 3600000)
        minutes, ms = divmod(ms, 60000)
        seconds, ms = divmod(ms, 1000)
        return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'
    return ''.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}\n\n' for i, c in enumerate(cues))
