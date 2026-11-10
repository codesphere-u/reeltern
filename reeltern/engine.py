"""Local, sequential media jobs. External programs never run through a shell."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import uuid

OPERATIONS = {
    "scenes": "Detect and split scenes — PySceneDetect",
    "trim": "Remove silence — Auto-Editor",
    "stabilize": "Stabilize footage — vid.stab",
    "color": "Match reference colors — color-matcher",
    "background": "Replace background — rembg",
    "slowmo": "2× slow motion, silent — RIFE",
    "upscale": "4× upscale — Real-ESRGAN",
    "stems": "Separate music stems — Demucs",
    "beats": "Detect beats and split clips — librosa",
    "graphics": "Render HTML composition — HyperFrames",
    "export": "Export MP4 — FFmpeg",
}
MODULES = {"scenes": "scenedetect", "color": "color_matcher", "background": "rembg", "beats": "librosa"}
COMMANDS = {"trim": "auto-editor", "stems": "demucs", "upscale": "realesrgan-ncnn-vulkan", "graphics": "hyperframes"}


def binary(name):
    return os.environ.get("REELTERN_" + name.upper().replace("-", "_")) or shutil.which(name)


def doctor():
    result = {name: bool(binary(name)) for name in ["ffmpeg", *COMMANDS.values()]}
    for module in MODULES.values():
        result[module] = importlib.util.find_spec(module) is not None
    root = Path(os.environ.get("REELTERN_RIFE_DIR", "__not_configured__")).expanduser()
    result["RIFE checkout + weights"] = (root / "inference_video.py").is_file() and (root / "train_log").is_dir()
    return result


def validate(recipe):
    if not isinstance(recipe, dict) or recipe.get("version") != 1:
        raise ValueError("Workflow must be an object with version: 1")
    if not isinstance(recipe.get("input"), str) or not recipe["input"].strip():
        raise ValueError("Choose an existing input video")
    source = Path(recipe["input"]).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Choose an existing input video")
    steps = recipe.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Choose at least one editing step")
    for step in steps:
        if not isinstance(step, dict) or step.get("op") not in OPERATIONS:
            raise ValueError("Unknown editing step")
        allowed = {"op"} | ({"reference"} if step["op"] == "color" else {"project"} if step["op"] == "graphics" else set())
        if set(step) - allowed:
            raise ValueError(f"Unsupported options for {step['op']}: {set(step) - allowed}")
        if step["op"] in ("color", "graphics"):
            key = "reference" if step["op"] == "color" else "project"
            if not isinstance(step.get(key), str) or not step[key].strip():
                raise ValueError(f"{step['op']} needs a {key} path")
            path = Path(step[key]).expanduser().resolve()
            if (key == "reference" and not path.is_file()) or (key == "project" and not (path / "index.html").is_file()):
                raise ValueError(f"{step['op']} needs a valid {key} path")
    return source


class Job:
    def __init__(self, recipe, output, log=print):
        self.source = validate(recipe)
        self.recipe, self.log = recipe, log
        self.root = Path(output).expanduser().resolve() / ("job-" + uuid.uuid4().hex[:12])
        self.cancelled = threading.Event()
        self.manifest = {"status": "pending", "recipe": recipe, "steps": []}

    def save(self):
        temporary = self.root / "manifest.tmp"
        temporary.write_text(json.dumps(self.manifest, indent=2), encoding="utf-8")
        temporary.replace(self.root / "manifest.json")

    def check(self):
        if self.cancelled.is_set():
            raise RuntimeError("Cancelled; partial files kept in job folder")

    def run_command(self, args, cwd=None):
        self.check()
        args = [str(a) for a in args]
        self.log("Running " + Path(args[0]).name)
        with (self.root / "process.log").open("a", encoding="utf-8") as log:
            log.write(json.dumps(args) + "\n")
            log.flush()
            process = subprocess.Popen(args, cwd=cwd, stdout=log, stderr=log, stdin=subprocess.DEVNULL)
            try:
                while True:
                    try:
                        code = process.wait(timeout=0.2)
                        break
                    except subprocess.TimeoutExpired:
                        self.check()
                if code:
                    raise RuntimeError(f"{Path(args[0]).name} failed ({code}); see {self.root / 'process.log'}")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        self.check()

    def ff(self, *args, cwd=None):
        self.run_command([binary("ffmpeg"), "-hide_banner", "-nostdin", "-n", *args], cwd)

    def preflight(self):
        if not binary("ffmpeg"):
            raise RuntimeError("Install FFmpeg first; see README.md")
        for step in self.recipe["steps"]:
            op = step["op"]
            if op in MODULES and importlib.util.find_spec(MODULES[op]) is None:
                raise RuntimeError(f"{op} needs {MODULES[op]}; see README.md")
            if op in COMMANDS and not binary(COMMANDS[op]):
                raise RuntimeError(f"Install {COMMANDS[op]} first; see README.md")
            if op == "slowmo" and not doctor()["RIFE checkout + weights"]:
                raise RuntimeError("Set REELTERN_RIFE_DIR to a RIFE checkout with train_log weights")
            if op == "stabilize":
                filters = subprocess.run([binary("ffmpeg"), "-filters"], capture_output=True, text=True, check=True).stdout
                if "vidstabtransform" not in filters:
                    raise RuntimeError("This FFmpeg build lacks vid.stab; install a build with libvidstab")

    def encode(self, source, dest, vf=None):
        args = ["-i", source, "-map", "0:v:0", "-map", "0:a:0?"]
        if vf:
            args += ["-vf", vf]
        self.ff(*args, "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", dest)

    def audio(self, source, folder):
        wav = folder / "audio.wav"
        self.ff("-i", source, "-vn", "-ac", "2", "-ar", "44100", wav)
        return wav

    def frame_effect(self, op, source, folder, step):
        # Normalize to 30 fps; PNG files preserve exact frame order. SDR only.
        frames, rendered = folder / "frames", folder / "processed"
        frames.mkdir(); rendered.mkdir()
        self.ff("-i", source, "-vf", "fps=30", frames / "%08d.png")
        if op == "upscale":
            self.run_command([binary(COMMANDS[op]), "-i", frames, "-o", rendered, "-s", "4", "-n", "realesrgan-x4plus", "-f", "png"])
        else:
            from PIL import Image
            if op == "color":
                from color_matcher import ColorMatcher
                from color_matcher.normalizer import Normalizer
                import numpy as np
                matcher = ColorMatcher()
                reference = np.asarray(Image.open(Path(step["reference"]).expanduser()).convert("RGB"))
            else:
                from rembg import remove, new_session
                session = new_session("u2net")
            for file in sorted(frames.glob("*.png")):
                self.check()
                with Image.open(file) as original:
                    if op == "color":
                        result = Image.fromarray(Normalizer(matcher.transfer(src=np.asarray(original.convert("RGB")), ref=reference, method="mkl")).uint8_norm())
                    else:
                        foreground = remove(original, session=session).convert("RGBA")
                        result = Image.new("RGBA", foreground.size, (24, 28, 36, 255))
                        result.alpha_composite(foreground)
                        result = result.convert("RGB")
                    result.save(rendered / file.name)
        if len(list(rendered.glob("*.png"))) != len(list(frames.glob("*.png"))):
            raise RuntimeError("Frame processor returned an incomplete sequence")
        out = folder / "video.mp4"
        self.ff("-framerate", "30", "-i", rendered / "%08d.png", "-i", source,
                "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "libx264", "-crf", "18",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out)
        return out

    def step(self, step, source, folder):
        op = step["op"]
        out = folder / "video.mp4"
        if op == "export":
            self.encode(source, out, "pad=ceil(iw/2)*2:ceil(ih/2)*2")
        elif op == "trim":
            self.run_command([binary("auto-editor"), source, "--margin", "0.2sec", "--no-open", "--output", out])
        elif op == "stabilize":
            self.ff("-i", source, "-vf", "vidstabdetect=result=transforms.trf", "-an", "-f", "null", "-", cwd=folder)
            self.ff("-i", source, "-vf", "vidstabtransform=input=transforms.trf:smoothing=15", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", out, cwd=folder)
        elif op in ("color", "background", "upscale"):
            out = self.frame_effect(op, source, folder, step)
        elif op == "scenes":
            from scenedetect import detect, ContentDetector
            scenes = detect(str(source), ContentDetector())
            ranges = [(s.get_seconds(), e.get_seconds()) for s, e in scenes]
            (folder / "scenes.json").write_text(json.dumps(ranges))
            for i, (start, end) in enumerate(ranges):
                self.ff("-ss", str(start), "-i", source, "-t", str(end-start), "-c:v", "libx264", "-c:a", "aac", folder / f"scene-{i+1:04d}.mp4")
            return source
        elif op == "stems":
            wav = self.audio(source, folder)
            self.run_command([binary("demucs"), "-n", "htdemucs", "-o", folder / "stems", wav])
            if not list((folder / "stems").rglob("*.wav")):
                raise RuntimeError("Demucs returned no stems")
            return source
        elif op == "beats":
            import librosa
            wav = self.audio(source, folder)
            y, sr = librosa.load(wav)
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
            times = [float(b) for b in beats]
            duration = float(librosa.get_duration(y=y, sr=sr))
            (folder / "beats.json").write_text(json.dumps({"bpm": float(tempo.item() if hasattr(tempo, "item") else tempo), "seconds": times}))
            # Cut every fourth detected beat; these clips retain the source order.
            boundaries = sorted(set([0.0, *[b for b in times[::4] if 0 < b < duration], duration]))
            for i, (a, b) in enumerate(zip(boundaries, boundaries[1:])):
                self.ff("-ss", str(a), "-i", source, "-t", str(b-a), "-c:v", "libx264", "-c:a", "aac", folder / f"beat-{i+1:04d}.mp4")
            return source
        elif op == "slowmo":
            root = Path(os.environ["REELTERN_RIFE_DIR"]).expanduser().resolve()
            # Pass explicit FPS to bypass upstream shell-based audio remuxing.
            normalized = folder / "input.mp4"
            self.ff("-i", source, "-vf", "fps=30", "-an", "-c:v", "libx264", normalized)
            self.run_command([os.environ.get("REELTERN_RIFE_PYTHON", sys.executable), root / "inference_video.py",
                              "--video", normalized, "--output", out, "--model", root / "train_log", "--exp", "1", "--fps", "30"], cwd=root)
        elif op == "graphics":
            # A complete user-authored composition; does not implicitly overlay the source.
            self.run_command([binary("hyperframes"), "render", "--output", out], cwd=Path(step["project"]).expanduser().resolve())
        if not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError(f"{op} returned no video")
        return out

    def run(self):
        self.preflight()
        self.root.mkdir(parents=True, exist_ok=False)
        self.manifest["status"] = "running"
        self.save()
        current = self.source
        try:
            for i, step in enumerate(self.recipe["steps"]):
                self.check()
                folder = self.root / f"{i+1:02d}-{step['op']}"
                folder.mkdir()
                self.log(f"Step {i+1}/{len(self.recipe['steps'])}: {OPERATIONS[step['op']]}")
                current = self.step(step, current, folder)
                self.manifest["steps"].append({"op": step["op"], "video": str(current), "artifacts": str(folder)})
                self.save()
            self.check()
            self.manifest.update(status="complete", video=str(current))
            self.log(f"Finished. Results: {self.root}")
            return self.root
        except BaseException as exc:
            self.manifest.update(status="cancelled" if self.cancelled.is_set() else "failed", error=str(exc))
            raise
        finally:
            self.save()
