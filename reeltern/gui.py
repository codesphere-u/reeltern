"""Native desktop launcher. Worker events are marshalled onto Tk's main thread."""
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .engine import Job, OPERATIONS, doctor


def launch():
    root = tk.Tk()
    root.title("Reeltern · Local video workflows")
    root.geometry("900x780")
    root.minsize(760, 650)
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Reeltern", font=("Helvetica", 26, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Your footage. Your computer. Eleven open-source tools.").pack(anchor="w", pady=(4, 18))
    paths = {}
    for key, label, directory in [("input", "Input video", False), ("output", "Results folder", True), ("reference", "Color reference image", False), ("project", "HyperFrames project folder", True)]:
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=26).pack(side="left")
        var = tk.StringVar(value=str(Path.cwd() / "renders") if key == "output" else "")
        paths[key] = var
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        def browse(v=var, d=directory):
            chosen = filedialog.askdirectory() if d else filedialog.askopenfilename()
            if chosen:
                v.set(chosen)
        ttk.Button(row, text="Browse", command=browse).pack(side="right", padx=(8, 0))
    ttk.Label(frame, text="Select steps · run in the order shown", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(18, 6))
    selected = {}
    # Trim first avoids spending AI compute on footage that will be discarded.
    order = ["trim", "stabilize", "color", "upscale", "background", "slowmo", "scenes", "stems", "beats", "graphics", "export"]
    grid = ttk.Frame(frame)
    grid.pack(fill="x")
    for i, op in enumerate(order):
        selected[op] = tk.BooleanVar(value=op == "export")
        ttk.Checkbutton(grid, text=OPERATIONS[op], variable=selected[op]).grid(row=i//2, column=i%2, sticky="w", padx=(0, 20), pady=4)
    ttk.Label(frame, text="Scenes, stems and beats create extra files. Graphics replaces the video with your HTML composition.\nBackground replacement uses charcoal; slow motion removes audio. AI tools need separate setup.", wraplength=820).pack(anchor="w", pady=12)
    controls = ttk.Frame(frame)
    controls.pack(fill="x", pady=4)
    messages = tk.Text(frame, height=10, wrap="word", state="disabled")
    messages.pack(fill="both", expand=True, pady=10)
    events = queue.Queue()
    active = {"job": None, "thread": None}

    def append(text):
        messages.configure(state="normal")
        messages.insert("end", text + "\n")
        messages.see("end")
        messages.configure(state="disabled")

    def recipe():
        steps = []
        for op in order:
            if selected[op].get():
                step = {"op": op}
                if op in ("color", "graphics"):
                    key = "reference" if op == "color" else "project"
                    step[key] = paths[key].get()
                steps.append(step)
        return {"version": 1, "input": paths["input"].get(), "steps": steps}

    def save():
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Workflow", "*.json")])
        if filename:
            Path(filename).write_text(json.dumps(recipe(), indent=2))
            append("Saved workflow: " + filename)

    def start():
        try:
            if not paths["output"].get():
                raise ValueError("Choose a results folder")
            job = Job(recipe(), paths["output"].get(), events.put)
        except Exception as exc:
            messagebox.showerror("Check your workflow", str(exc))
            return
        active["job"] = job
        run_button.configure(state="disabled")
        cancel_button.configure(state="normal")
        def worker():
            try:
                job.run()
            except Exception as exc:
                events.put("Stopped: " + str(exc))
            finally:
                events.put(None)
        thread = threading.Thread(target=worker, daemon=False)
        active["thread"] = thread
        thread.start()

    def cancel():
        if active["job"]:
            active["job"].cancelled.set()
            append("Cancellation requested. Waiting for the current frame or model call to return…")

    run_button = ttk.Button(controls, text="Run workflow", command=start)
    run_button.pack(side="left")
    cancel_button = ttk.Button(controls, text="Cancel", command=cancel, state="disabled")
    cancel_button.pack(side="left", padx=8)
    ttk.Button(controls, text="Save workflow", command=save).pack(side="left")
    ttk.Button(controls, text="Check tools", command=lambda: append("\n".join(f"{'Found' if v else 'Missing'}: {k}" for k, v in doctor().items()))).pack(side="right")

    def poll():
        while not events.empty():
            message = events.get_nowait()
            if message is None:
                active["job"] = None
                run_button.configure(state="normal")
                cancel_button.configure(state="disabled")
            else:
                append(message)
        root.after(100, poll)

    def close():
        thread = active["thread"]
        if thread and thread.is_alive():
            cancel()
            append("Keep this window open until cancellation finishes, then close it.")
        else:
            root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    append("Start with Export MP4. Check tools to see which optional features are installed.")
    poll()
    root.mainloop()
