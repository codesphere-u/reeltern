"""Official MCP SDK, stdio only. No shell tools or arbitrary output paths."""
import asyncio
from importlib import metadata as _metadata
import json
from pathlib import Path
from typing import Annotated, Literal
from .workspace import Workspace
from .render import Renderer


def _compact_json_schema(schema):
    """Strip Pydantic UI noise, flatten nullable anyOf wrappers, and inline single-use $defs."""
    if not isinstance(schema, dict):
        return schema

    def _clean(node):
        if isinstance(node, list):
            return [_clean(x) for x in node]
        if not isinstance(node, dict):
            return node
        out = {k: _clean(v) for k, v in node.items() if k != 'title'}
        if out.get('additionalProperties') is True:
            out.pop('additionalProperties', None)
        variants = out.get('anyOf')
        if isinstance(variants, list) and len(variants) == 2 and {'type': 'null'} in variants:
            other = next((v for v in variants if v != {'type': 'null'}), None)
            if isinstance(other, dict) and isinstance(other.get('type'), str) and not any(
                c in other for c in ('anyOf', 'oneOf', 'allOf')
            ):
                out.pop('anyOf')
                t = other['type']
                for k, v in other.items():
                    if k == 'type':
                        out['type'] = [t, 'null']
                    elif k not in out:
                        out[k] = v
        if 'properties' in out and isinstance(out['properties'], dict) and 'required' not in out:
            out['required'] = []
        return out

    cleaned = _clean(schema)
    defs = cleaned.get('$defs')
    if isinstance(defs, dict) and defs:
        counts = {}

        def _count(obj):
            if isinstance(obj, dict):
                ref = obj.get('$ref')
                if isinstance(ref, str) and ref.startswith('#/$defs/'):
                    name = ref[8:]
                    counts[name] = counts.get(name, 0) + 1
                for k, v in obj.items():
                    if k != '$defs':
                        _count(v)
            elif isinstance(obj, list):
                for item in obj:
                    _count(item)

        _count(cleaned)
        single = {k: defs[k] for k, c in counts.items() if c == 1 and k in defs and '#/$defs/' not in json.dumps(defs[k])}

        def _inline(obj):
            if isinstance(obj, dict):
                ref = obj.get('$ref')
                if isinstance(ref, str) and ref.startswith('#/$defs/'):
                    key = ref[8:]
                    if key in single:
                        merged = dict(single[key])
                        merged.update({k: _inline(v) for k, v in obj.items() if k != '$ref'})
                        return merged
                return {k: _inline(v) for k, v in obj.items() if k != '$defs'}
            if isinstance(obj, list):
                return [_inline(x) for x in obj]
            return obj

        if single:
            cleaned = _inline(cleaned)
            rem = {k: v for k, v in defs.items() if k not in single and counts.get(k, 0) > 0}
            if rem:
                cleaned['$defs'] = rem
    return cleaned


def create_server(workspace, media_root, agent_model=None, ollama_url="http://127.0.0.1:11434"):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    from pydantic import BaseModel, ConfigDict, Field
    from . import transcript
    from .agent import EditorialAgent

    class ClipInput(BaseModel):
        model_config = ConfigDict(extra='forbid')
        asset_id: str = Field(pattern=r'^[a-f0-9]{64}$', description='SHA-256 asset ID')
        start: float = Field(default=0, ge=0, allow_inf_nan=False, strict=True, description='Source start s')
        end: float | None = Field(default=None, gt=0, allow_inf_nan=False, strict=True, description='Source end s')
        speed: float = Field(default=1, ge=0.25, le=4.0, allow_inf_nan=False, strict=True, description='Speed 0.25–4x')
        reason: str = Field(default='User selection', max_length=500, description='Clip reason')

    class CueInput(BaseModel):
        model_config = ConfigDict(extra='forbid')
        start: float = Field(ge=0, allow_inf_nan=False, strict=True, description='Cue start sec')
        end: float = Field(gt=0, allow_inf_nan=False, strict=True, description='Cue end sec')
        text: str = Field(min_length=1, max_length=2000, description='Caption text')

    ws = Workspace(workspace, media_root)
    agent = None if agent_model is None else EditorialAgent(ws, agent_model, ollama_url)
    expensive = asyncio.Semaphore(2)

    async def _run_bg(function, *args):
        async with expensive:
            return await asyncio.to_thread(function, *args)

    renderer = Renderer(ws)
    server = FastMCP(
        'Reeltern',
        instructions='Local immutable video editing, smart director, and QA server. Read reeltern://guide and reeltern://cookbook first.',
    )
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)

    PresetType = Literal['landscape', 'portrait', 'square', 'fhd', 'reels']
    FitType = Literal['contain', 'cover', 'blur_fill']
    GradeType = Literal['none', 'cinematic', 'warm', 'crisp', 'noir', 'vivid', 'moody', 'teal_orange', 'vintage', 'studio']
    MotionType = Literal['none', 'zoom_in', 'zoom_out', 'pan_left', 'pan_right']
    TransitionType = Literal['cut', 'crossfade', 'wipeleft', 'wiperight', 'slideleft', 'slideright', 'dissolve', 'smoothleft', 'circleopen', 'fadeblack']
    CaptionStyleType = Literal['clean', 'boxed', 'bold', 'kinetic']
    DirectorStyleType = Literal['cinematic', 'viral_reel', 'tutorial', 'documentary', 'noir_trailer']

    @server.tool(annotations=read, structured_output=False)
    def capabilities() -> dict:
        """List supported editing tools, presets, effects, director profiles, and limits."""
        try:
            ver = _metadata.version('reeltern')
        except _metadata.PackageNotFoundError:
            ver = '0.6.0'
        return {
            'version': ver,
            'editorial_agent_enabled': agent is not None,
            'transport': 'stdio',
            'media_root': str(ws.media_root),
            'presets': ['landscape', 'portrait', 'square', 'fhd', 'reels'],
            'fits': ['contain', 'cover', 'blur_fill'],
            'grades': ['none', 'cinematic', 'warm', 'crisp', 'noir', 'vivid', 'moody', 'teal_orange', 'vintage', 'studio'],
            'motions': ['none', 'zoom_in', 'zoom_out', 'pan_left', 'pan_right'],
            'transitions': ['cut', 'crossfade', 'wipeleft', 'wiperight', 'slideleft', 'slideright', 'dissolve', 'smoothleft', 'circleopen', 'fadeblack'],
            'caption_modes': ['soft', 'burn', 'both', 'none'],
            'caption_styles': ['clean', 'boxed', 'bold', 'kinetic'],
            'director_styles': ['cinematic', 'viral_reel', 'tutorial', 'documentary', 'noir_trailer'],
            'editing': [
                'blur_fill vertical framing', 'Ken Burns zoom & pan motion', 'AI director compose_video',
                'kinetic word-highlight captions', 'sidechain-ducked music bed mix', 'voice cleanup & loudnorm',
                'ebur128 & exposure render QA', 'contact sheet & scene detection',
            ],
            'max_clips': 200,
            'max_queued_jobs': 8,
        }

    @server.tool(annotations=write, structured_output=False)
    async def import_media(
        path: Annotated[str, Field(description='Media path inside media root')],
    ) -> dict:
        """Snapshot a local video inside media root and return its asset ID."""
        return await _run_bg(ws.import_media, path)

    @server.tool(annotations=write, structured_output=False)
    async def import_audio(
        path: Annotated[str, Field(description='Audio track path in media root')],
    ) -> dict:
        """Import a WAV, MP3, M4A, AAC, FLAC, or OGG soundtrack inside media root."""
        return await _run_bg(ws.import_audio, path)

    @server.tool(annotations=read, structured_output=False)
    def list_assets() -> list[dict]:
        """List imported assets with duration, resolution, and audio status."""
        return ws.assets()

    @server.tool(annotations=write, structured_output=False)
    async def create_title_card(
        title: Annotated[str, Field(min_length=1, max_length=120, description='Primary card heading')],
        subtitle: Annotated[str, Field(max_length=200, description='Optional subtitle')] = '',
        duration: Annotated[float, Field(ge=0.5, le=30.0, description='Duration in sec')] = 3.0,
        preset: Annotated[PresetType, Field(description='Frame size preset')] = 'landscape',
        background: Annotated[str, Field(pattern=r'^#[0-9a-fA-F]{6}$', description='Hex backdrop e.g. #0f172a')] = '#0f172a',
        accent: Annotated[str, Field(pattern=r'^#[0-9a-fA-F]{6}$', description='Hex bar/sub color')] = '#38bdf8',
    ) -> dict:
        """Generate and import an MP4 title/chapter slate asset in workspace."""
        return await _run_bg(ws.create_card, title, subtitle, duration, preset, background, accent)

    @server.tool(annotations=write, structured_output=False)
    async def inspect_media_visuals(
        asset_id: Annotated[str, Field(description='Target asset SHA-256 ID')],
        thumbs: Annotated[int, Field(ge=1, le=24, description='Storyboard frame count')] = 6,
        samples: Annotated[int, Field(ge=8, le=512, description='Waveform amplitude buckets')] = 60,
    ) -> dict:
        """Extract storyboard contact sheet, scene cuts, exposure metrics, and audio peaks."""
        return await _run_bg(ws.inspect_visuals, asset_id, thumbs, samples)

    @server.tool(annotations=write, structured_output=False)
    async def analyze_audio(
        asset_id: Annotated[str, Field(description='Target asset SHA-256 ID')],
        threshold_db: Annotated[float, Field(description='Silence gate in dB')] = -35,
        minimum_silence: Annotated[float, Field(description='Min silence span in sec')] = 0.6,
        margin: Annotated[float, Field(description='Padding around speech sec')] = 0.15,
    ) -> dict:
        """Detect quiet intervals and suggested kept ranges without editing source media."""
        return await _run_bg(ws.analyze, asset_id, threshold_db, minimum_silence, margin)

    @server.tool(annotations=write, structured_output=False)
    async def suggest_edit(
        asset_id: Annotated[str, Field(description='Target asset SHA-256 ID')],
        preset: Annotated[PresetType, Field(description='Output frame preset')] = 'landscape',
        threshold_db: Annotated[float, Field(description='Silence gate in dB')] = -35,
        minimum_silence: Annotated[float, Field(description='Min silence span in sec')] = 0.6,
        margin: Annotated[float, Field(description='Padding around speech sec')] = 0.15,
    ) -> dict:
        """Create a reversible silence-trimmed draft plan for review before render."""
        return await _run_bg(ws.suggest, asset_id, preset, threshold_db, minimum_silence, margin)

    @server.tool(annotations=write, structured_output=False)
    async def compose_video(
        asset_ids: Annotated[list[str], Field(description='Ordered video asset IDs')],
        director_style: Annotated[DirectorStyleType, Field(description='Preset production style')] = 'cinematic',
        preset: Annotated[PresetType | None, Field(description='Optional output preset override')] = None,
        target_seconds: Annotated[float | None, Field(ge=1.0, le=14400.0, description='Optional target duration sec')] = None,
        intro_title: Annotated[str, Field(max_length=120, description='Optional opening slate title')] = '',
        transcript_id: Annotated[str | None, Field(description='Optional transcript SHA-256 ID')] = None,
        music_asset_id: Annotated[str | None, Field(description='Optional background audio ID')] = None,
        notes: Annotated[str, Field(max_length=2000, description='Revision note')] = 'AI director composition',
    ) -> dict:
        """Auto-assemble footage with style-matched pacing, grades, motion, ducking, and captions."""
        from .director import compose_plan
        return await _run_bg(compose_plan, ws, asset_ids, director_style, preset, target_seconds, intro_title, transcript_id, music_asset_id, notes)

    @server.tool(annotations=write, structured_output=False)
    def create_plan(
        clips: Annotated[list[ClipInput], Field(description='Ordered playback clips')],
        preset: Annotated[PresetType, Field(description='Output preset')] = 'landscape',
        fit: Annotated[FitType, Field(description='Contain, cover, or blur_fill')] = 'contain',
        parent: Annotated[str | None, Field(description='Parent plan ID')] = None,
        notes: Annotated[str, Field(description='Revision note')] = 'Manual edit',
        transcript_ids: Annotated[list[str] | None, Field(description='Transcript IDs')] = None,
    ) -> dict:
        """Save an immutable timeline revision with ordered clips and framing."""
        return ws.create_plan(
            [c.model_dump(exclude_none=True) for c in clips],
            preset=preset,
            fit=fit,
            parent=parent,
            notes=notes,
            transcript_ids=transcript_ids,
        )

    @server.tool(annotations=write, structured_output=False)
    def split_clip(
        plan_id: Annotated[str, Field(description='Source plan ID')],
        clip_index: Annotated[int, Field(ge=0, description='Zero-based clip index')],
        offset_seconds: Annotated[float, Field(gt=0, description='Split point in clip output sec')],
        notes: Annotated[str | None, Field(description='Optional revision note')] = None,
    ) -> dict:
        """Split a timeline clip non-destructively at an output offset into a new revision."""
        return ws.split_clip(plan_id, clip_index, offset_seconds, notes)

    @server.tool(annotations=write, structured_output=False)
    def style_clip(
        plan_id: Annotated[str, Field(description='Source plan ID')],
        clip_index: Annotated[int, Field(ge=0, description='Zero-based clip index')],
        grade: Annotated[GradeType | None, Field(description='Color grade look')] = None,
        fade_in: Annotated[float | None, Field(ge=0.0, le=5.0, description='Fade-in sec')] = None,
        fade_out: Annotated[float | None, Field(ge=0.0, le=5.0, description='Fade-out sec')] = None,
        volume: Annotated[float | None, Field(ge=0.0, le=2.0, description='Audio gain 0–2')] = None,
        rotate: Annotated[Literal[0, 90, 180, 270] | None, Field(description='Clockwise rotation deg')] = None,
        title_overlay: Annotated[str | None, Field(max_length=100, description='Lower-third label')] = None,
    ) -> dict:
        """Apply color grade, fades, audio volume, rotation, or lower-third overlay to one clip."""
        changes = {}
        for k, v in (
            ('grade', grade), ('fade_in', fade_in), ('fade_out', fade_out),
            ('volume', volume), ('rotate', rotate), ('title_overlay', title_overlay),
        ):
            if v is not None:
                changes[k] = v
        return ws.update_clip(plan_id, clip_index, changes, notes=f'Styled clip {clip_index + 1}')

    @server.tool(annotations=write, structured_output=False)
    def animate_clip(
        plan_id: Annotated[str, Field(description='Source plan ID')],
        clip_index: Annotated[int, Field(ge=0, description='Zero-based clip index')],
        motion: Annotated[MotionType | None, Field(description='Ken Burns zoom or pan')] = None,
        flip: Annotated[Literal['none', 'horizontal', 'vertical'] | None, Field(description='Mirror axis')] = None,
        speed: Annotated[float | None, Field(ge=0.25, le=4.0, description='Playback speed 0.25–4x')] = None,
    ) -> dict:
        """Configure camera motion, mirroring, or playback speed ramp for one timeline clip."""
        changes = {}
        for k, v in (('motion', motion), ('flip', flip), ('speed', speed)):
            if v is not None:
                changes[k] = v
        return ws.update_clip(plan_id, clip_index, changes, notes=f'Updated motion on clip {clip_index + 1}')

    @server.tool(annotations=write, structured_output=False)
    def apply_timeline_style(
        plan_id: Annotated[str, Field(description='Source plan ID')],
        preset: Annotated[PresetType | None, Field(description='Frame size preset')] = None,
        fit: Annotated[FitType | None, Field(description='Contain, cover, or blur_fill')] = None,
        transition: Annotated[TransitionType | None, Field(description='Join transition')] = None,
        transition_duration: Annotated[float | None, Field(ge=0.15, le=1.5, description='Transition span sec')] = None,
        normalize_audio: Annotated[bool | None, Field(description='Enable EBU R128 loudness')] = None,
        caption_mode: Annotated[Literal['soft', 'burn', 'both', 'none'] | None, Field(description='Subtitle burn/track mode')] = None,
        caption_style: Annotated[CaptionStyleType | None, Field(description='Burned caption look')] = None,
    ) -> dict:
        """Set timeline-wide format, transitions, loudness normalization, and burned-in caption style."""
        return ws.update_plan_style(
            plan_id,
            preset=preset,
            fit=fit,
            transition=transition,
            transition_duration=transition_duration,
            normalize_audio=normalize_audio,
            caption_mode=caption_mode,
            caption_style=caption_style,
        )

    @server.tool(annotations=write, structured_output=False)
    def configure_audio_mix(
        plan_id: Annotated[str, Field(description='Source plan ID')],
        music_asset_id: Annotated[str | None, Field(description='Background music audio ID')] = None,
        clear_music: Annotated[bool, Field(description='Remove attached music track')] = False,
        music_volume: Annotated[float | None, Field(ge=0.0, le=1.0, description='Music bed level 0–1')] = None,
        music_ducking: Annotated[bool | None, Field(description='Auto-duck music under speech')] = None,
        voice_cleanup: Annotated[bool | None, Field(description='Highpass EQ + speech compressor')] = None,
        progress_bar: Annotated[bool | None, Field(description='Accent playback progress bar')] = None,
        progress_color: Annotated[str | None, Field(pattern=r'^#[0-9a-fA-F]{6}$', description='Progress bar hex color')] = None,
    ) -> dict:
        """Configure background music ducking, speech cleanup EQ, and bottom progress bar overlay."""
        return ws.update_plan_style(
            plan_id,
            music_asset_id=music_asset_id,
            clear_music=clear_music,
            music_volume=music_volume,
            music_ducking=music_ducking,
            voice_cleanup=voice_cleanup,
            progress_bar=progress_bar,
            progress_color=progress_color,
            notes='Updated audio mix & overlay polish',
        )

    @server.tool(annotations=read, structured_output=False)
    def get_plan(
        plan_id: Annotated[str, Field(description='Plan SHA-256 ID')],
    ) -> dict:
        """Inspect source ranges, speed, effects, and timeline offsets of a saved plan."""
        return ws.plan(plan_id)

    @server.tool(annotations=read, structured_output=False)
    def list_plans() -> list[dict]:
        """List saved immutable plan revisions in this workspace."""
        return ws.plans()

    @server.tool(annotations=read, structured_output=False)
    def compare_plans(
        before: Annotated[str, Field(description='Baseline plan ID')],
        after: Annotated[str, Field(description='Updated plan ID')],
    ) -> dict:
        """Compare clip order, duration, format, transitions, and captions across two plans."""
        return ws.compare(before, after)

    @server.tool(annotations=write, structured_output=False)
    def render_plan(
        plan_id: Annotated[str, Field(description='Target plan ID')],
        preview: Annotated[bool, Field(description='Half-res fast preview')] = True,
    ) -> dict:
        """Queue asynchronous local MP4 preview or full export render and return job ID."""
        return renderer.submit(plan_id, preview)

    @server.tool(annotations=read, structured_output=False)
    def job_status(
        job_id: Annotated[str, Field(description='Render job ID')],
    ) -> dict:
        """Read render progress, cache hits, output file path, or failure details."""
        return renderer.status(job_id)

    @server.tool(annotations=write, structured_output=False)
    def cancel_job(
        job_id: Annotated[str, Field(description='Render job ID')],
    ) -> dict:
        """Request cancellation of a queued or running local render job."""
        return renderer.cancel(job_id)

    @server.tool(annotations=write, structured_output=False)
    async def audit_render(
        job_id: Annotated[str, Field(description='Completed render job ID')],
    ) -> dict:
        """Inspect finished video exposure, black frames, EBU loudness, contact sheet, and fixes."""
        from .director import audit_job_render
        return await _run_bg(audit_job_render, ws, renderer, job_id)

    @server.tool(annotations=write, structured_output=False)
    def register_transcript(
        asset_id: Annotated[str, Field(description='Target asset ID')],
        cues: Annotated[list[CueInput], Field(description='Chronological cues list')],
    ) -> dict:
        """Save user-supplied timecoded cues for an imported asset (no ASR run)."""
        value = transcript.register(ws, asset_id, [c.model_dump() for c in cues])
        return {'id': value['id'], 'asset_id': asset_id, 'cue_count': len(value['cues']), 'provenance': value['provenance']}

    @server.tool(annotations=read, structured_output=False)
    def list_transcripts(
        asset_id: Annotated[str | None, Field(description='Optional asset filter')] = None,
        offset: Annotated[int, Field(ge=0, description='Pagination offset')] = 0,
        limit: Annotated[int, Field(ge=1, le=100, description='Max items 1–100')] = 20,
    ) -> dict:
        """List paged transcript metadata without returning full cue arrays."""
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Offset must be non-negative and limit 1–100')
        if asset_id is not None:
            ws.asset(asset_id)
        values = []
        for path in sorted((ws.root / 'transcripts').glob('*.json')):
            value = transcript.get(ws, path.stem)
            if asset_id is None or value['asset_id'] == asset_id:
                values.append({'id': value['id'], 'asset_id': value['asset_id'], 'cue_count': len(value['cues']), 'provenance': value['provenance']})
        return {'total': len(values), 'offset': offset, 'transcripts': values[offset:offset+limit]}

    @server.tool(annotations=read, structured_output=False)
    def get_transcript(
        transcript_id: Annotated[str, Field(description='Transcript SHA-256 ID')],
        offset: Annotated[int, Field(ge=0, description='Cue start index')] = 0,
        limit: Annotated[int, Field(ge=1, le=100, description='Max cues 1–100')] = 50,
    ) -> dict:
        """Read a bounded page of transcript cues with IDs and timestamps."""
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Offset must be non-negative and limit 1–100')
        value = transcript.get(ws, transcript_id)
        return {'id': value['id'], 'asset_id': value['asset_id'], 'total': len(value['cues']), 'cues': value['cues'][offset:offset+limit]}

    @server.tool(annotations=read, structured_output=False)
    def search_transcript(
        transcript_id: Annotated[str, Field(description='Transcript SHA-256 ID')],
        query: Annotated[str, Field(description='Search words')],
        limit: Annotated[int, Field(ge=1, le=100, description='Max results 1–100')] = 20,
    ) -> dict:
        """Search transcript cues matching all query words and return real cue IDs."""
        return transcript.search(ws, transcript_id, query, limit)

    @server.tool(annotations=write, structured_output=False)
    def plan_from_transcript(
        transcript_id: Annotated[str, Field(description='Transcript SHA-256 ID')],
        cue_ids: Annotated[list[str], Field(description='Ordered cue IDs to keep')],
        preset: Annotated[PresetType, Field(description='Frame size preset')] = 'landscape',
        parent: Annotated[str | None, Field(description='Optional parent plan ID')] = None,
    ) -> dict:
        """Create a captioned timeline revision from exact selected transcript cue IDs."""
        return transcript.select(ws, transcript_id, cue_ids, preset, parent)

    @server.tool(annotations=write, structured_output=False)
    async def draft_edit(
        transcript_id: Annotated[str, Field(description='Transcript SHA-256 ID')],
        brief: Annotated[str, Field(description='Editorial selection brief')],
        target_seconds: Annotated[float, Field(ge=1, le=600, description='Max duration sec')] = 60,
        preset: Annotated[PresetType, Field(description='Frame size preset')] = 'portrait',
        start: Annotated[float, Field(ge=0, description='Source window start sec')] = 0,
        end: Annotated[float | None, Field(description='Optional window end sec')] = None,
    ) -> dict:
        """Use the local Ollama model (--agent-model) to draft an evidence-backed plan."""
        if agent is None:
            raise ValueError('Editorial agent is disabled. Start the server with --agent-model and an installed local Ollama model.')
        return await _run_bg(agent.draft, transcript_id, brief, target_seconds, preset, start, end)

    @server.tool(annotations=read, structured_output=False)
    def list_jobs(
        limit: Annotated[int, Field(ge=1, le=100, description='Max jobs 1–100')] = 20,
    ) -> list[dict]:
        """List recent render jobs in this workspace, including interrupted jobs."""
        if not 1 <= limit <= 100:
            raise ValueError('Limit must be 1–100')
        files = sorted((ws.root / 'jobs').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        return [json.loads(p.read_text()) for p in files[:limit]]

    @server.tool(annotations=read, structured_output=False)
    def get_render_receipt(
        job_id: Annotated[str, Field(description='Completed job ID')],
    ) -> dict:
        """Read technical verification checks, SHA-256 digest, and media info for a job."""
        state = renderer.status(job_id)
        if state['status'] != 'complete':
            raise ValueError('No completed render receipt for this job')
        return json.loads((ws.root / 'jobs' / job_id / 'receipt.json').read_text())

    @server.tool(annotations=write, structured_output=False)
    def retry_job(
        job_id: Annotated[str, Field(description='Failed/cancelled job ID')],
    ) -> dict:
        """Retry a failed, cancelled, or interrupted render as a new job reusing cache."""
        old = renderer.status(job_id)
        if old['status'] not in ('failed', 'cancelled', 'interrupted'):
            raise ValueError('Only failed, cancelled or interrupted jobs can be retried')
        return renderer.submit(old['plan_id'], old['preview'])

    @server.resource('reeltern://guide')
    def guide() -> str:
        return (
            'Workflow: import_media (+ optional import_audio / create_title_card) -> inspect_media_visuals -> '
            'compose_video OR manual create_plan/plan_from_transcript -> refine via split_clip, style_clip, animate_clip, '
            'apply_timeline_style, configure_audio_mix -> render_plan(preview=true) -> job_status -> audit_render -> final render. '
            'Preserve transcript_ids across revisions. Never claim speech understanding from silence or invent cue IDs.'
        )

    @server.resource('reeltern://cookbook')
    def cookbook() -> str:
        return (
            'Recipes for high-craft videos:\n'
            '1) Vertical Shorts/Reels from horizontal source: preset="reels", fit="blur_fill", grade="vivid", '
            'caption_mode="both", caption_style="kinetic", progress_bar=true, voice_cleanup=true, normalize_audio=true.\n'
            '2) Cinematic Story: preset="fhd", fit="contain", grade="cinematic", transition="crossfade", '
            'alternating motion="zoom_in"/"zoom_out", optional music_asset_id with music_ducking=true.\n'
            '3) Quality Loop: inspect_media_visuals -> read reeltern://visual/asset/{id} contact sheet -> compose/style -> '
            'render preview -> run audit_render(job_id) -> check luma_avg/lufs -> adjust brightness/volume if needed -> final export.'
        )

    @server.resource('reeltern://visual/asset/{asset_id}', mime_type='image/png')
    def asset_contact_sheet(asset_id: str) -> bytes:
        vis = ws.inspect_visuals(asset_id, thumbs=6, samples=60)
        sheet = vis.get('contact_sheet')
        if not sheet:
            raise ValueError('Audio-only assets do not have a video contact sheet')
        return Path(sheet).read_bytes()

    @server.resource('reeltern://visual/render/{job_id}', mime_type='image/png')
    def render_contact_sheet(job_id: str) -> bytes:
        from .director import audit_job_render
        report = audit_job_render(ws, renderer, job_id)
        return Path(report['contact_sheet']).read_bytes()

    @server.prompt()
    def first_pass(asset_id: str) -> str:
        return (
            f'Prepare a conservative first-pass edit for asset {asset_id}. '
            'Inspect visuals/audio with inspect_media_visuals, propose a reversible plan, consider subtle fades or color grade only if helpful, and render a preview.'
        )

    @server.prompt()
    def editorial_draft(transcript_id: str, brief: str) -> str:
        return (
            f'Draft a reviewable edit from transcript {transcript_id}. Brief: {brief}\n'
            'Read cues and preserve qualifiers. Use existing cue IDs only via plan_from_transcript or draft_edit, '
            'enable burned-in kinetic or boxed captions via apply_timeline_style, and render+audit a preview before final export.'
        )

    @server.prompt()
    def viral_short(asset_id: str, intro_title: str = '') -> str:
        return (
            f'Create a crisp vertical 9:16 short from asset {asset_id}'
            + (f' with intro slate "{intro_title}"' if intro_title else '')
            + '. Call inspect_media_visuals first, use compose_video(director_style="viral_reel"), render a preview, and verify exposure and loudness with audit_render.'
        )

    @server.prompt()
    def polish_edit(plan_id: str, goal: str) -> str:
        return (
            f'Polish plan {plan_id}. Goal: {goal}\n'
            'Inspect the current plan, apply targeted style_clip/animate_clip/configure_audio_mix refinements, '
            'render a preview, run audit_render for exposure/loudness QC, and summarize compare_plans before final export.'
        )

    for tool_info in server._tool_manager.list_tools():
        tool_info.parameters = _compact_json_schema(tool_info.parameters)

    return server, renderer


def serve(workspace, media_root, agent_model=None, ollama_url="http://127.0.0.1:11434"):
    server, renderer = create_server(workspace, media_root, agent_model, ollama_url)
    try:
        server.run(transport='stdio')
    finally:
        renderer.close()
