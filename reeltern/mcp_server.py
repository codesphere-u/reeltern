"""Official MCP SDK, stdio only. No shell tools or arbitrary output paths."""
from pathlib import Path
from .workspace import Workspace
from .render import Renderer


def create_server(workspace, media_root):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    ws = Workspace(workspace, media_root)
    renderer = Renderer(ws)
    server = FastMCP('Reeltern', instructions='Local video editing with inspectable, immutable plans. Import only user-selected footage. Inspect proposed cuts with get_plan and compare_plans; quiet audio does not imply unwanted content. Preview before a final render when useful. Render returns a job ID; poll job_status. Do not claim completion until status is complete. Original files and earlier plans are preserved.')
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)

    @server.tool(annotations=read)
    def capabilities() -> dict:
        """Describe supported editing operations and explicit limitations."""
        return {'version': '0.2.0', 'transport': 'stdio', 'media_root': str(ws.media_root),
                'editing': ['silence-assisted cut proposals', 'multi-source timeline', 'trim and reorder', '0.5–2x speed with audio', 'portrait/square/landscape', 'contain or center crop', 'immutable revisions', 'preview', 'verified asynchronous render', 'segment cache'],
                'limits': ['No speech transcription or semantic highlight detection', 'No face tracking; cover is center crop', 'SDR 30 fps output', 'Legacy optional AI adapters are not exposed to MCP'],
                'max_clips': 200, 'max_queued_jobs': 8}

    @server.tool(annotations=write)
    def import_media(path: str) -> dict:
        """Snapshot a video inside the configured media root. Returns an asset ID."""
        return ws.import_media(path)

    @server.tool(annotations=read)
    def list_assets() -> list[dict]:
        """List imported media, duration, dimensions and audio availability."""
        return ws.assets()

    @server.tool(annotations=write)
    def analyze_audio(asset_id: str, threshold_db: float = -35, minimum_silence: float = 0.6, margin: float = 0.15) -> dict:
        """Detect quiet intervals and proposed kept ranges. Analysis writes a cached report; does not edit media."""
        return ws.analyze(asset_id, threshold_db, minimum_silence, margin)

    @server.tool(annotations=write)
    def suggest_edit(asset_id: str, preset: str = 'landscape', threshold_db: float = -35, minimum_silence: float = 0.6, margin: float = 0.15) -> dict:
        """Create a reversible first-pass cut plan based on audio activity. Review before rendering."""
        return ws.suggest(asset_id, preset, threshold_db, minimum_silence, margin)

    @server.tool(annotations=write)
    def create_plan(clips: list[dict], preset: str = 'landscape', fit: str = 'contain', parent: str | None = None, notes: str = 'Manual edit') -> dict:
        """Create an immutable timeline/revision. Each clip: asset_id, start/end in source seconds, optional speed 0.5–2 and reason. Array order is playback order. Parent identifies an earlier plan. fit=cover center-crops; contain preserves the whole image."""
        return ws.create_plan(clips, preset, fit, parent, notes)

    @server.tool(annotations=read)
    def get_plan(plan_id: str) -> dict:
        """Inspect every source range, reason, playback speed and output time in a plan."""
        return ws.plan(plan_id)

    @server.tool(annotations=read)
    def list_plans() -> list[dict]:
        """List saved plans and their parent revisions, including earlier edits."""
        return ws.plans()

    @server.tool(annotations=read)
    def compare_plans(before: str, after: str) -> dict:
        """Compare source ranges, order, duration and format between two saved plans."""
        return ws.compare(before, after)

    @server.tool(annotations=write)
    def render_plan(plan_id: str, preview: bool = True) -> dict:
        """Queue a render of this exact plan. Preview uses half-resolution. Poll job_status; output is local MP4, not automatically shared."""
        return renderer.submit(plan_id, preview)

    @server.tool(annotations=read)
    def job_status(job_id: str) -> dict:
        """Read persistent progress, cache hits, output and verification receipt or error."""
        return renderer.status(job_id)

    @server.tool(annotations=write)
    def cancel_job(job_id: str) -> dict:
        """Request cancellation of a queued or running render owned by this server."""
        return renderer.cancel(job_id)

    @server.resource('reeltern://guide')
    def guide() -> str:
        return 'Import → analyze/suggest → inspect → create revision if needed → preview → job_status → final render. Never infer meaning from silence. All clips reference source seconds. Retain a useful reason for each edit. Report output paths only after verification succeeds.'

    @server.prompt()
    def first_pass(asset_id: str) -> str:
        return f'Prepare a conservative first-pass edit for asset {asset_id}. Inspect its audio analysis, propose a plan preserving context, explain the removed ranges and limitations, and produce a preview for review. Do not claim transcription or semantic understanding.'

    return server, renderer


def serve(workspace, media_root):
    server, renderer = create_server(workspace, media_root)
    try:
        server.run(transport='stdio')
    finally:
        renderer.close()
