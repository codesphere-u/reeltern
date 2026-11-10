import argparse
import json
from pathlib import Path
from .engine import Job, doctor, validate


def main():
    parser = argparse.ArgumentParser(description="Reeltern — local video workflows")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("gui", help="Open desktop window")
    sub.add_parser("doctor", help="Check optional tools")
    for name in ("run", "validate"):
        p = sub.add_parser(name)
        p.add_argument("recipe", type=Path)
        if name == "run":
            p.add_argument("--output", default="renders")
    args = parser.parse_args()
    try:
        if args.command == "gui":
            from .gui import launch
            launch()
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
