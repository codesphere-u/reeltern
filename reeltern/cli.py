import argparse
import json
from pathlib import Path
from .director import DIRECTOR_STYLES, audit_job_render, compose_plan
from .effects import CAPTION_STYLES, COLOR_GRADES, FIT_MODES, MOTIONS, TRANSITIONS
from .engine import Job, doctor, validate
from .workspace import PRESETS


def main():
    parser = argparse.ArgumentParser(description="Reeltern — local video & AI director workflows")
    sub = parser.add_subparsers(dest="command", required=True)
    gui = sub.add_parser("gui", help="Open the reversible timeline editor")
    gui.add_argument("--workspace", default="reeltern-workspace")
    sub.add_parser("toolkit", help="Open the legacy optional-engine launcher")
    mcp = sub.add_parser("mcp", help="Serve local editing tools over MCP stdio")
    mcp.add_argument("--workspace", required=True)
    mcp.add_argument("--media-root", required=True)
    mcp.add_argument("--agent-model", help="Opt in to an installed local Ollama model")
    mcp.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    from .client_config import CLIENTS
    config = sub.add_parser("mcp-config", help="Print client setup with absolute paths; does not modify settings")
    config.add_argument("client", choices=CLIENTS)
    config.add_argument("--workspace", required=True)
    config.add_argument("--media-root", required=True)
    config.add_argument("--agent-model")
    transcript = sub.add_parser("transcript", help="Import an SRT transcript for a video")
    transcript.add_argument("input", type=Path)
    transcript.add_argument("srt", type=Path)
    transcript.add_argument("--workspace", default="reeltern-workspace")
    agent = sub.add_parser("agent", help="Draft an edit from a brief and supplied transcript")
    agent.add_argument("transcript_id")
    agent.add_argument("brief")
    agent.add_argument("--model", required=True)
    agent.add_argument("--workspace", default="reeltern-workspace")
    agent.add_argument("--seconds", type=float, default=60)
    agent.add_argument("--preset", choices=list(PRESETS), default="portrait")
    agent.add_argument("--style", choices=["none", *DIRECTOR_STYLES], default="none")
    demo = sub.add_parser("demo", help="Generate a small reproducible captioned edit")
    demo.add_argument("--workspace", default="reeltern-demo")
    import_aud = sub.add_parser("import-audio", help="Import a local WAV/MP3/M4A/FLAC/OGG soundtrack")
    import_aud.add_argument("input", type=Path)
    import_aud.add_argument("--workspace", default="reeltern-workspace")
    card = sub.add_parser("card", help="Generate a verified title/chapter card asset")
    card.add_argument("title")
    card.add_argument("--subtitle", default="")
    card.add_argument("--duration", type=float, default=3.0)
    card.add_argument("--preset", choices=list(PRESETS), default="landscape")
    card.add_argument("--background", default="#0f172a")
    card.add_argument("--accent", default="#38bdf8")
    card.add_argument("--workspace", default="reeltern-workspace")
    inspect_cmd = sub.add_parser("inspect", help="Extract storyboard contact sheet, scene cuts, and audio peaks")
    inspect_cmd.add_argument("input", type=Path)
    inspect_cmd.add_argument("--workspace", default="reeltern-workspace")
    inspect_cmd.add_argument("--thumbs", type=int, default=6)
    inspect_cmd.add_argument("--samples", type=int, default=60)
    compose_cmd = sub.add_parser("compose", help="Auto-compose polished edit using an AI Director profile")
    compose_cmd.add_argument("inputs", nargs="+", type=Path)
    compose_cmd.add_argument("--workspace", default="reeltern-workspace")
    compose_cmd.add_argument("--style", choices=list(DIRECTOR_STYLES), default="cinematic")
    compose_cmd.add_argument("--preset", choices=list(PRESETS))
    compose_cmd.add_argument("--seconds", type=float)
    compose_cmd.add_argument("--intro", default="")
    compose_cmd.add_argument("--srt", type=Path)
    compose_cmd.add_argument("--music", type=Path)
    compose_cmd.add_argument("--render", action="store_true")
    compose_cmd.add_argument("--preview", action="store_true")
    compose_cmd.add_argument("--audit", action="store_true")
    audit_cmd = sub.add_parser("audit", help="Run exposure, black-frame, and EBU R128 loudness QA on a finished job")
    audit_cmd.add_argument("job_id")
    audit_cmd.add_argument("--workspace", default="reeltern-workspace")
    edit = sub.add_parser("edit", help="Create a silence-assisted plan with optional polish, optionally preview/render")
    edit.add_argument("input", type=Path)
    edit.add_argument("--workspace", default="reeltern-workspace")
    edit.add_argument("--preset", choices=list(PRESETS), default="landscape")
    edit.add_argument("--fit", choices=list(FIT_MODES), default="contain")
    edit.add_argument("--grade", choices=list(COLOR_GRADES), default="none")
    edit.add_argument("--motion", choices=list(MOTIONS), default="none")
    edit.add_argument("--transition", choices=list(TRANSITIONS), default="cut")
    edit.add_argument("--fade-in", type=float, default=0.0)
    edit.add_argument("--fade-out", type=float, default=0.0)
    edit.add_argument("--volume", type=float, default=1.0)
    edit.add_argument("--title-overlay", default="")
    edit.add_argument("--voice-cleanup", action="store_true")
    edit.add_argument("--progress-bar", action="store_true")
    edit.add_argument("--normalize-audio", action="store_true")
    edit.add_argument("--music", type=Path)
    edit.add_argument("--srt", type=Path)
    edit.add_argument("--burn-captions", action="store_true")
    edit.add_argument("--caption-style", choices=list(CAPTION_STYLES), default="clean")
    edit.add_argument("--render", action="store_true")
    edit.add_argument("--preview", action="store_true")
    sub.add_parser("doctor", help="Check optional tools")
    for name in ("run", "validate"):
        p = sub.add_parser(name)
        p.add_argument("recipe", type=Path)
        if name == "run":
            p.add_argument("--output", default="renders")
    args = parser.parse_args()
    try:
        if args.command == "gui":
            from .studio import launch
            launch(args.workspace)
        elif args.command == "toolkit":
            from .gui import launch
            launch()
        elif args.command == "mcp-config":
            from .client_config import configuration
            print(configuration(args.client, args.workspace, args.media_root, args.agent_model), end='')
        elif args.command == "mcp":
            from .mcp_server import serve
            serve(args.workspace, args.media_root, args.agent_model, args.ollama_url)
        elif args.command == "transcript":
            from .workspace import Workspace
            from .transcript import parse_srt, register
            ws = Workspace(args.workspace)
            asset = ws.import_media(args.input)
            result = register(ws, asset['id'], parse_srt(args.srt.read_text(encoding='utf-8-sig')))
            print(json.dumps({'transcript_id': result['id'], 'cue_count': len(result['cues']), 'asset_id': asset['id']}, indent=2))
        elif args.command == "agent":
            from .workspace import Workspace
            from .agent import EditorialAgent
            result = EditorialAgent(Workspace(args.workspace), args.model).draft(
                args.transcript_id, args.brief, args.seconds, args.preset, director_style=args.style,
            )
            print(json.dumps(result, indent=2))
        elif args.command == "demo":
            from .demo import run_demo
            print(json.dumps(run_demo(args.workspace), indent=2))
        elif args.command == "import-audio":
            from .workspace import Workspace
            ws = Workspace(args.workspace)
            print(json.dumps(ws.import_audio(args.input), indent=2))
        elif args.command == "card":
            from .workspace import Workspace
            ws = Workspace(args.workspace)
            asset = ws.create_card(args.title, args.subtitle, args.duration, args.preset, args.background, args.accent)
            print(json.dumps(asset, indent=2))
        elif args.command == "inspect":
            from .workspace import Workspace
            ws = Workspace(args.workspace)
            asset = ws.import_media(args.input)
            print(json.dumps(ws.inspect_visuals(asset['id'], args.thumbs, args.samples), indent=2))
        elif args.command == "compose":
            from .workspace import Workspace
            from .render import Renderer
            ws = Workspace(args.workspace)
            asset_ids = [ws.import_media(p)['id'] for p in args.inputs]
            transcript_id = None
            if args.srt:
                from .transcript import parse_srt, register
                transcript_id = register(ws, asset_ids[0], parse_srt(args.srt.read_text(encoding='utf-8-sig')))['id']
            music_id = ws.import_audio(args.music)['id'] if args.music else None
            composed = compose_plan(
                ws,
                asset_ids,
                director_style=args.style,
                preset=args.preset,
                target_seconds=args.seconds,
                intro_title=args.intro,
                transcript_id=transcript_id,
                music_asset_id=music_id,
            )
            output_payload = {'plan': composed['plan'], 'composition_summary': composed['composition_summary']}
            if args.render or args.preview or args.audit:
                renderer = Renderer(ws)
                try:
                    job = renderer.submit(composed['plan']['id'], bool(args.preview))
                    result = renderer.wait(job['id'])
                    output_payload['job'] = result
                    if result['status'] != 'complete':
                        raise RuntimeError(result.get('error', 'Render failed'))
                    if args.audit:
                        output_payload['audit'] = audit_job_render(ws, renderer, job['id'])
                finally:
                    renderer.close()
            print(json.dumps(output_payload, indent=2))
        elif args.command == "audit":
            from .workspace import Workspace
            from .render import Renderer
            ws = Workspace(args.workspace)
            renderer = Renderer(ws)
            try:
                print(json.dumps(audit_job_render(ws, renderer, args.job_id), indent=2))
            finally:
                renderer.close()
        elif args.command == "edit":
            from .workspace import Workspace
            from .render import Renderer
            ws = Workspace(args.workspace)
            asset = ws.import_media(args.input)
            transcript_ids = []
            if args.srt:
                from .transcript import parse_srt, register
                t = register(ws, asset['id'], parse_srt(args.srt.read_text(encoding='utf-8-sig')))
                transcript_ids = [t['id']]
            music_id = ws.import_audio(args.music)['id'] if args.music else None
            plan = ws.suggest(asset["id"], args.preset)
            clips = ws._raw_clips(plan)
            for clip in clips:
                if args.grade != 'none':
                    clip['grade'] = args.grade
                if args.motion != 'none':
                    clip['motion'] = args.motion
                if args.fade_in > 0:
                    clip['fade_in'] = args.fade_in
                if args.fade_out > 0:
                    clip['fade_out'] = args.fade_out
                if abs(args.volume - 1.0) > 1e-6:
                    clip['volume'] = args.volume
            if args.title_overlay and clips:
                clips[0]['title_overlay'] = args.title_overlay
            has_style = (
                args.fit != 'contain' or args.grade != 'none' or args.motion != 'none'
                or args.transition != 'cut' or args.fade_in > 0 or args.fade_out > 0
                or abs(args.volume - 1.0) > 1e-6 or args.title_overlay or args.normalize_audio
                or args.voice_cleanup or args.progress_bar or music_id or transcript_ids or args.burn_captions
            )
            if has_style:
                plan = ws.create_plan(
                    clips,
                    preset=args.preset,
                    fit=args.fit,
                    parent=plan['id'],
                    notes='CLI workflow edit',
                    transcript_ids=transcript_ids,
                    transition=args.transition,
                    normalize_audio=args.normalize_audio,
                    voice_cleanup=args.voice_cleanup,
                    progress_bar=args.progress_bar,
                    music_asset_id=music_id,
                    caption_mode='both' if (args.burn_captions and transcript_ids) else ('burn' if args.burn_captions else 'soft'),
                    caption_style=args.caption_style,
                )
            print(json.dumps(plan, indent=2))
            if args.render or args.preview:
                renderer = Renderer(ws)
                try:
                    job = renderer.submit(plan["id"], args.preview)
                    result = renderer.wait(job["id"])
                    print(json.dumps(result, indent=2))
                    if result["status"] != "complete":
                        raise RuntimeError(result.get("error", "Render failed"))
                finally:
                    renderer.close()
        elif args.command == "doctor":
            for key, available in doctor().items():
                print(f"{'FOUND  ' if available else 'MISSING'} {key}")
        else:
            recipe = json.loads(args.recipe.read_text())
            # Relative media references are relative to the workflow file.
            base = args.recipe.resolve().parent
            if recipe.get("input"):
                recipe["input"] = str(base / recipe["input"])
            for step in recipe.get("steps", []):
                for key in ("reference", "project"):
                    if key in step:
                        step[key] = str(base / step[key])
            if args.command == "validate":
                validate(recipe)
                print("Workflow structure and input paths are valid. Use doctor to check tools.")
            else:
                Job(recipe, args.output).run()
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        parser.exit(1, f"Reeltern: {exc}\n")


if __name__ == "__main__":
    main()
