"""Queued renders with verified output, reusable segments and durable receipts."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
import uuid
from .media import Cancelled, atomic_json, digest, ff, ffmpeg, key, probe, execute
from .workspace import PRESETS


class Renderer:
    def __init__(self, workspace):
        self.ws = workspace
        from .locking import WorkspaceLock
        self.ownership = WorkspaceLock(self.ws.root / '.render.lock')
        try:
            for path in (self.ws.root / 'jobs').glob('*.json'):
                previous = json.loads(path.read_text())
                if previous.get('status') in ('queued', 'running', 'verifying'):
                    previous.update(status='interrupted', error='Previous renderer ended before completion. Retry creates a new job and reuses verified cached segments.')
                    atomic_json(path, previous)
        except Exception:
            self.ownership.close()
            raise
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='reeltern-render')
        self.lock = threading.RLock()
        self.events = {}
        self.closed = False

    def submit(self, plan_id, preview=False):
        plan = self.ws.plan(plan_id)
        with self.lock:
            if self.closed:
                raise RuntimeError('Renderer is shutting down')
            if sum(not f.done() for _, f in self.events.values()) >= 8:
                raise ValueError('Render queue is full; wait for a job to finish')
            identifier = uuid.uuid4().hex
            folder = self.ws.root / 'jobs' / identifier
            folder.mkdir()
            state = {'id': identifier, 'plan_id': plan_id, 'status': 'queued', 'preview': bool(preview),
                     'completed_clips': 0, 'total_clips': len(plan['clips']), 'cache_hits': 0, 'created_at': time.time()}
            atomic_json(self.ws.path('jobs', identifier), state)
            cancel = threading.Event()
            future = self.pool.submit(self._render, deepcopy(plan), state, folder, cancel)
            self.events[identifier] = (cancel, future)
            return deepcopy(state)

    def status(self, identifier):
        return self.ws.read('jobs', identifier)

    def cancel(self, identifier):
        with self.lock:
            self.status(identifier)
            if identifier in self.events:
                self.events[identifier][0].set()
            else:
                raise ValueError('This job is not owned by this running server')
        return {'id': identifier, 'cancellation_requested': True}

    def wait(self, identifier, timeout=None):
        self.events[identifier][1].result(timeout=timeout)
        return self.status(identifier)

    def close(self):
        with self.lock:
            self.closed = True
            for event, future in self.events.values():
                if not future.done():
                    event.set()
        try:
            self.pool.shutdown(wait=True)
        finally:
            self.ownership.close()

    def _render(self, plan, state, folder, cancel):
        started = time.monotonic()
        save = lambda: atomic_json(self.ws.path('jobs', state['id']), state)
        try:
            if cancel.is_set():
                raise Cancelled('Render cancelled')
            state['status'] = 'running'
            save()
            assets = {c['asset_id']: self.ws.asset(c['asset_id'], verify=True) for c in plan['clips']}
            w, h = PRESETS[plan['preset']]
            if state['preview']:
                w, h = w // 2, h // 2
            version_file = execute([ffmpeg(), '-version'], folder, cancel)
            engine_version = version_file.read_text(errors='replace').splitlines()[0]
            segments = []
            for index, clip in enumerate(plan['clips']):
                if cancel.is_set():
                    raise Cancelled('Render cancelled')
                signature = key({'clip': {k: v for k, v in clip.items() if k not in ('reason', 'timeline_start')},
                                 'width': w, 'height': h, 'fit': plan['fit'], 'engine': engine_version, 'renderer': 2})
                cached = self.ws.path('cache', signature, '.mkv')
                receipt_path = self.ws.path('cache', signature)
                valid = False
                if cached.is_file() and receipt_path.is_file():
                    try:
                        valid = digest(cached) == json.loads(receipt_path.read_text())['sha256']
                    except (ValueError, KeyError):
                        pass
                if valid:
                    state['cache_hits'] += 1
                else:
                    temp = folder / f'clip-{index:04d}.mkv'
                    source = self.ws.path('assets', clip['asset_id'], '.media')
                    length = clip['frames'] / 30
                    size = (f'scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2'
                            if plan['fit'] == 'contain' else
                            f'scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={w}:{h}')
                    vf = f'[0:v:0]setpts=(PTS-STARTPTS)/{clip["speed"]},fps=30,{size},setsar=1,tpad=stop_mode=clone:stop_duration=1,trim=end_frame={clip["frames"]},setpts=N/(30*TB)[v]'
                    args = ['-protocol_whitelist', 'file,pipe', '-ss', str(clip['start']), '-t', str(clip['end']-clip['start']), '-i', source]
                    if assets[clip['asset_id']]['audio']:
                        af = f'[0:a:0]asetpts=PTS-STARTPTS,atempo={clip["speed"]},aresample=48000,apad,atrim=duration={length}[a]'
                    else:
                        args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
                        af = f'[1:a:0]atrim=duration={length},asetpts=PTS-STARTPTS[a]'
                    ff([*args, '-filter_complex', vf + ';' + af, '-map', '[v]', '-map', '[a]', '-t', str(length),
                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '24' if state['preview'] else '18',
                        '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', temp], folder, cancel)
                    info = probe(temp)
                    if abs(info['duration'] - length) > 0.1:
                        raise RuntimeError('Segment duration failed verification')
                    temp.replace(cached)
                    atomic_json(receipt_path, {'sha256': digest(cached), 'duration': info['duration']})
                segments.append(cached)
                state['completed_clips'] = index + 1
                save()
            # Generated numeric names avoid concat-file quoting of user paths.
            import shutil
            for index, segment in enumerate(segments):
                shutil.copyfile(segment, folder / f'segment-{index:04d}.mkv')
            listing = folder / 'concat.txt'
            listing.write_text(''.join(f"file 'segment-{i:04d}.mkv'\n" for i in range(len(segments))))
            output = folder / ('preview.mp4' if state['preview'] else 'final.mp4')
            from .transcript import timeline_captions, srt
            captions = timeline_captions(self.ws, plan)
            subtitle_args = []
            mapping = ['-map', '0:v:0', '-map', '0:a:0']
            if captions:
                subtitle = folder / 'captions.srt'
                subtitle.write_text(srt(captions), encoding='utf-8')
                subtitle_args = ['-i', subtitle]
                mapping += ['-map', '1:0', '-c:s', 'mov_text']
            ff(['-f', 'concat', '-safe', '1', '-i', listing, *subtitle_args, *mapping,
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', str(plan['duration']), '-movflags', '+faststart', output], folder, cancel)
            state['status'] = 'verifying'
            save()
            info = probe(output)
            if info['width'] != w or info['height'] != h or not info['audio'] or abs(info['duration'] - plan['duration']) > 0.1:
                raise RuntimeError('Output dimensions, audio or duration failed verification')
            if captions and info['subtitle_tracks'] != 1:
                raise RuntimeError('Caption stream missing from output')
            ff(['-v', 'error', '-xerror', '-i', output, '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'], folder, cancel)
            for asset_id in assets:
                self.ws.asset(asset_id, verify=True)
            if cancel.is_set():
                raise Cancelled('Render cancelled')
            receipt = {'plan': plan, 'media': list(assets.values()), 'output': info, 'sha256': digest(output),
                       'engine': engine_version, 'cache_hits': state['cache_hits'], 'elapsed_seconds': time.monotonic()-started,
                       'caption_count': len(captions), 'transcript_ids': plan.get('transcript_ids', []),
                       'verified': ['dimensions', 'duration', 'video and audio decode', 'source snapshot hashes'],
                       'limitations': ['SDR output, 30 fps', 'first video/audio streams only', 'no semantic quality score']}
            atomic_json(folder / 'receipt.json', receipt)
            atomic_json(folder / 'edit-plan.json', plan)
            state.update(status='complete', output=str(output), receipt=str(folder / 'receipt.json'), elapsed_seconds=receipt['elapsed_seconds'])
            if captions:
                state['captions'] = str(folder / 'captions.srt')
            # Segment cache remains; job folders need only final artifacts and logs.
            for segment in folder.glob('segment-*.mkv'):
                segment.unlink()
        except Cancelled as exc:
            state.update(status='cancelled', error=str(exc))
        except Exception as exc:
            state.update(status='failed', error=str(exc))
        finally:
            save()
