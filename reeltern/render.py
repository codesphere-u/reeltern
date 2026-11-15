"""Queued renders with verified output, reusable segments and durable receipts."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
import uuid
from .effects import COLOR_GRADES, TRANSITIONS, atempo_filters, build_captions_ass, build_overlay_ass
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
                                 'width': w, 'height': h, 'fit': plan['fit'], 'engine': engine_version, 'renderer': 3})
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
                    v_chain = []
                    rotate = int(clip.get('rotate', 0))
                    if rotate == 90:
                        v_chain.append('transpose=1')
                    elif rotate == 180:
                        v_chain.append('transpose=1,transpose=1')
                    elif rotate == 270:
                        v_chain.append('transpose=2')
                    if clip.get('flip') == 'horizontal':
                        v_chain.append('hflip')
                    elif clip.get('flip') == 'vertical':
                        v_chain.append('vflip')
                    v_chain += [f'setpts=(PTS-STARTPTS)/{clip["speed"]}', 'fps=30', size, 'setsar=1']
                    grade = clip.get('grade', 'none')
                    if grade in COLOR_GRADES and COLOR_GRADES[grade]:
                        v_chain.append(COLOR_GRADES[grade])
                    b, ct, sat = float(clip.get('brightness', 0.0)), float(clip.get('contrast', 1.0)), float(clip.get('saturation', 1.0))
                    if any(abs(v - d) > 1e-4 for v, d in ((b, 0.0), (ct, 1.0), (sat, 1.0))):
                        v_chain.append(f'eq=brightness={b:.3f}:contrast={ct:.3f}:saturation={sat:.3f}')
                    v_chain += ['tpad=stop_mode=clone:stop_duration=1', f'trim=end_frame={clip["frames"]}', 'setpts=N/(30*TB)']
                    overlay_ass = None
                    if clip.get('title_overlay'):
                        overlay_ass = folder / f'overlay-{index:04d}.ass'
                        overlay_ass.write_text(build_overlay_ass(w, h, length, clip['title_overlay'], mode='lower_third'), encoding='utf-8')
                        v_chain.append(f'ass={overlay_ass.name}')
                    fade_in = float(clip.get('fade_in', 0.0))
                    fade_out = float(clip.get('fade_out', 0.0))
                    if fade_in > 0:
                        d_in = min(fade_in, length / 2)
                        if d_in > 0.01:
                            v_chain.append(f'fade=t=in:st=0:d={d_in:.3f}')
                    if fade_out > 0:
                        d_out = min(fade_out, length / 2)
                        if d_out > 0.01:
                            v_chain.append(f'fade=t=out:st={max(0.0, length - d_out):.3f}:d={d_out:.3f}')
                    vf = '[0:v:0]' + ','.join(v_chain) + '[v]'

                    args = ['-protocol_whitelist', 'file,pipe', '-ss', str(clip['start']), '-t', str(clip['end']-clip['start']), '-i', source]
                    if assets[clip['asset_id']]['audio']:
                        a_chain = ['asetpts=PTS-STARTPTS', *atempo_filters(clip['speed']), 'aresample=48000', 'apad', f'atrim=duration={length}']
                        vol = float(clip.get('volume', 1.0))
                        if abs(vol - 1.0) > 1e-4:
                            a_chain.append(f'volume={vol:.4f}')
                        if fade_in > 0:
                            d_in = min(fade_in, length / 2)
                            if d_in > 0.01:
                                a_chain.append(f'afade=t=in:st=0:d={d_in:.3f}')
                        if fade_out > 0:
                            d_out = min(fade_out, length / 2)
                            if d_out > 0.01:
                                a_chain.append(f'afade=t=out:st={max(0.0, length - d_out):.3f}:d={d_out:.3f}')
                        af = '[0:a:0]' + ','.join(a_chain) + '[a]'
                    else:
                        args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
                        af = f'[1:a:0]atrim=duration={length},asetpts=PTS-STARTPTS[a]'
                    try:
                        ff([*args, '-filter_complex', vf + ';' + af, '-map', '[v]', '-map', '[a]', '-t', str(length),
                            '-c:v', 'libx264', '-preset', 'fast', '-crf', '24' if state['preview'] else '18',
                            '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', temp], folder, cancel)
                    finally:
                        if overlay_ass is not None:
                            overlay_ass.unlink(missing_ok=True)
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
            caption_mode = plan.get('caption_mode', 'soft')
            caption_style = plan.get('caption_style', 'clean')
            transition = plan.get('transition', 'cut')
            transition_duration = float(plan.get('transition_duration', 0.4))
            normalize_audio = bool(plan.get('normalize_audio', False))
            captions = [] if caption_mode == 'none' else timeline_captions(self.ws, plan)
            burn_captions = bool(captions and caption_mode in ('burn', 'both'))
            soft_captions = bool(captions and caption_mode in ('soft', 'both'))
            if captions:
                subtitle = folder / 'captions.srt'
                subtitle.write_text(srt(captions), encoding='utf-8')
            if burn_captions:
                (folder / 'captions.ass').write_text(build_captions_ass(w, h, captions, style=caption_style), encoding='utf-8')

            use_xfade = transition != 'cut' and len(segments) > 1
            needs_reencode = use_xfade or burn_captions or normalize_audio
            if not needs_reencode:
                subtitle_args = ['-i', folder / 'captions.srt'] if soft_captions else []
                mapping = ['-map', '0:v:0', '-map', '0:a:0'] + (['-map', '1:0', '-c:s', 'mov_text'] if soft_captions else [])
                ff(['-f', 'concat', '-safe', '1', '-i', listing, *subtitle_args, *mapping,
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', str(plan['duration']), '-movflags', '+faststart', output], folder, cancel)
            else:
                inputs = []
                filter_steps = []
                if use_xfade:
                    for i in range(len(segments)):
                        inputs += ['-i', f'segment-{i:04d}.mkv']
                    xfade_name = TRANSITIONS[transition]
                    running_dur = plan['clips'][0]['frames'] / 30
                    v_cur, a_cur = '0:v:0', '0:a:0'
                    for i in range(1, len(segments)):
                        prev_dur = plan['clips'][i - 1]['frames'] / 30
                        cur_dur = plan['clips'][i]['frames'] / 30
                        eff = min(transition_duration, prev_dur * 0.45, cur_dur * 0.45)
                        overlap = min(plan['clips'][i - 1]['frames'] - 1, plan['clips'][i]['frames'] - 1, round(eff * 30)) / 30
                        offset = max(0.0, running_dur - overlap)
                        v_next, a_next = f'vx{i}', f'ax{i}'
                        filter_steps.append(f'[{v_cur}][{i}:v:0]xfade=transition={xfade_name}:duration={overlap:.4f}:offset={offset:.4f}[{v_next}]')
                        filter_steps.append(f'[{a_cur}][{i}:a:0]acrossfade=d={overlap:.4f}[{a_next}]')
                        running_dur = offset + cur_dur
                        v_cur, a_cur = v_next, a_next
                    sub_idx = len(segments)
                else:
                    inputs += ['-f', 'concat', '-safe', '1', '-i', listing]
                    v_cur, a_cur = '0:v:0', '0:a:0'
                    sub_idx = 1

                if burn_captions:
                    filter_steps.append(f'[{v_cur}]ass=captions.ass[vout]')
                    v_cur = 'vout'
                if normalize_audio:
                    filter_steps.append(f'[{a_cur}]loudnorm=I=-16:TP=-1.5:LRA=11[aout]')
                    a_cur = 'aout'

                if soft_captions:
                    inputs += ['-i', folder / 'captions.srt']
                v_map = f'[{v_cur}]' if v_cur in ('vout',) or use_xfade else v_cur
                a_map = f'[{a_cur}]' if a_cur in ('aout',) or use_xfade else a_cur
                cmd = [*inputs, '-filter_complex', ';'.join(filter_steps), '-map', v_map, '-map', a_map]
                if soft_captions:
                    cmd += ['-map', f'{sub_idx}:0', '-c:s', 'mov_text']
                cmd += ['-c:v', 'libx264', '-preset', 'fast', '-crf', '24' if state['preview'] else '18',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-t', str(plan['duration']), '-movflags', '+faststart', output]
                ff(cmd, folder, cancel)

            state['status'] = 'verifying'
            save()
            info = probe(output)
            if info['width'] != w or info['height'] != h or not info['audio'] or abs(info['duration'] - plan['duration']) > 0.12:
                raise RuntimeError('Output dimensions, audio or duration failed verification')
            if soft_captions and info['subtitle_tracks'] != 1:
                raise RuntimeError('Caption stream missing from output')
            ff(['-v', 'error', '-xerror', '-i', output, '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'], folder, cancel)
            for asset_id in assets:
                self.ws.asset(asset_id, verify=True)
            if cancel.is_set():
                raise Cancelled('Render cancelled')
            verified = ['dimensions', 'duration', 'video and audio decode', 'source snapshot hashes']
            if use_xfade:
                verified.append(f'{transition} transition')
            if burn_captions:
                verified.append(f'burned-in {caption_style} captions')
            if normalize_audio:
                verified.append('EBU R128 loudness normalization')
            receipt = {'plan': plan, 'media': list(assets.values()), 'output': info, 'sha256': digest(output),
                       'engine': engine_version, 'cache_hits': state['cache_hits'], 'elapsed_seconds': time.monotonic()-started,
                       'caption_count': len(captions), 'caption_mode': caption_mode, 'transcript_ids': plan.get('transcript_ids', []),
                       'verified': verified,
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
