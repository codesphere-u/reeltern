import argparse
import json
from pathlib import Path
from .engine import Job, doctor, validate


def main():
    parser = argparse.ArgumentParser(description="Reeltern — local video workflows")
    sub = parser.add_subparsers(dest="command", required=True)
    gui = sub.add_parser("gui", help="Open the reversible timeline editor")
    gui.add_argument("--workspace", default="reeltern-workspace")
    sub.add_parser("toolkit", help="Open the legacy optional-engine launcher")
    mcp = sub.add_parser("mcp", help="Serve local editing tools over MCP stdio")
    mcp.add_argument("--workspace", required=True)
    mcp.add_argument("--media-root", required=True)
    edit = sub.add_parser("edit", help="Create a silence-assisted plan, optionally preview/render")
    edit.add_argument("input", type=Path)
    edit.add_argument("--workspace", default="reeltern-workspace")
    edit.add_argument("--preset", choices=["landscape", "portrait", "square"], default="landscape")
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
        elif args.command == "mcp":
            from .mcp_server import serve
            serve(args.workspace, args.media_root)
        elif args.command == "edit":
            from .workspace import Workspace
            from .render import Renderer
            ws = Workspace(args.workspace)
            asset = ws.import_media(args.input)
            plan = ws.suggest(asset["id"], args.preset)
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
