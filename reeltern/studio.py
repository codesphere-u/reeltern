"""Desktop cut-plan editor; every edit creates a revision rather than changing media."""
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
from .workspace import Workspace, PRESETS
from .render import Renderer


class Studio:
    def __init__(self, root, workspace):
        self.root, self.ws = root, Workspace(workspace)
        self.renderer = Renderer(self.ws)
        self.plan = None
        self.job = None
        self.reported_job = None
        self.busy = False
        self.events = queue.Queue()
        root.title('Reeltern · Your footage. In full flight.')
        root.geometry('1140x820')
        root.minsize(900, 680)
        root.configure(bg='#111827')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', background='#111827', foreground='#e5e7eb', fieldbackground='#1f2937')
        style.configure('TButton', padding=(12, 8), background='#26364d')
        style.map('TButton', background=[('active', '#36516e')])
        style.configure('Treeview', background='#182235', fieldbackground='#182235', foreground='#e5e7eb', rowheight=32)
        style.map('Treeview', background=[('selected', '#235f68')])
        outer = ttk.Frame(root, padding=22)
        outer.pack(fill='both', expand=True)
        header = ttk.Frame(outer)
        header.pack(fill='x')
        ttk.Label(header, text='REELTERN', font=('Helvetica', 25, 'bold'), foreground='#7dd3c7').pack(side='left')
        ttk.Label(header, text='  /  Your footage. In full flight.', font=('Helvetica', 12)).pack(side='left')
        ttk.Button(header, text='Open results folder', command=self.open_results).pack(side='right')
        ttk.Label(outer, text='Import → propose cuts → review the plan → preview → export', foreground='#a8b5c8').pack(anchor='w', pady=(8, 18))
        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        self.action_buttons = []
        for label, fn in [('Import footage', self.import_files), ('Keep all / assemble', self.assemble), ('Suggest quiet cuts', self.suggest), ('Earlier plans', self.history), ('Transcript & AI', self.transcript_editor)]:
            button = ttk.Button(controls, text=label, command=fn)
            button.pack(side='left', padx=(0, 8))
            self.action_buttons.append(button)
        self.preset = tk.StringVar(value='landscape')
        self.fit = tk.StringVar(value='contain')
        ttk.Combobox(controls, textvariable=self.preset, values=list(PRESETS), state='readonly', width=12).pack(side='right', padx=5)
        ttk.Combobox(controls, textvariable=self.fit, values=['contain', 'cover'], state='readonly', width=10).pack(side='right')
        ttk.Label(outer, text='FOOTAGE · Select one or more sources (Command/Ctrl-click)', foreground='#a8b5c8').pack(anchor='w', pady=(18, 6))
        self.assets = ttk.Treeview(outer, columns=('name', 'length', 'size', 'audio'), show='headings', height=4, selectmode='extended')
        for key, label, width in [('name', 'Video', 480), ('length', 'Seconds', 100), ('size', 'Dimensions', 140), ('audio', 'Audio', 100)]:
            self.assets.heading(key, text=label)
            self.assets.column(key, width=width)
        self.assets.pack(fill='x')
        self.summary = tk.StringVar(value='Import a video to begin. Originals remain untouched.')
        ttk.Label(outer, textvariable=self.summary, font=('Helvetica', 13, 'bold')).pack(anchor='w', pady=(18, 8))
        self.timeline = ttk.Treeview(outer, columns=('source', 'in', 'out', 'speed', 'time', 'why'), show='headings', height=7, selectmode='browse')
        for key, label, width in [('source', 'Source', 160), ('in', 'In', 65), ('out', 'Out', 65), ('speed', 'Speed', 65), ('time', 'Output time', 110), ('why', 'Reason', 400)]:
            self.timeline.heading(key, text=label)
            self.timeline.column(key, width=width)
        self.timeline.pack(fill='both', expand=True)
        self.timeline.bind('<<TreeviewSelect>>', self.select_clip)
        edit = ttk.Frame(outer)
        edit.pack(fill='x', pady=10)
        self.fields = {}
        for field, label in [('start', 'In (s)'), ('end', 'Out (s)'), ('speed', 'Speed')]:
            ttk.Label(edit, text=label).pack(side='left', padx=(0, 4))
            var = tk.StringVar()
            self.fields[field] = var
            ttk.Entry(edit, textvariable=var, width=8).pack(side='left', padx=(0, 12))
        for label, fn in [('Apply revision', self.revise), ('Move up', lambda: self.move(-1)), ('Move down', lambda: self.move(1)), ('Remove clip', self.remove), ('Undo to parent', self.undo)]:
            ttk.Button(edit, text=label, command=lambda f=fn: self.guarded(f)).pack(side='left', padx=3)
        footer = ttk.Frame(outer)
        footer.pack(fill='x')
        ttk.Button(footer, text='Preview edit', command=lambda: self.start_render(True)).pack(side='left', padx=(0, 8))
        ttk.Button(footer, text='Export final MP4', command=lambda: self.start_render(False)).pack(side='left', padx=(0, 8))
        ttk.Button(footer, text='Cancel render', command=self.cancel).pack(side='left')
        self.open_button = ttk.Button(footer, text='Play completed video', command=self.open_video, state='disabled')
        self.open_button.pack(side='right')
        self.progress = ttk.Progressbar(outer, mode='determinate')
        self.progress.pack(fill='x', pady=(12, 5))
        self.status = tk.StringVar(value='Local editing • contain keeps the full image; cover crops the center • SDR / 30 fps')
        ttk.Label(outer, textvariable=self.status, wraplength=1060).pack(anchor='w')
        self.refresh_assets()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def guarded(self, fn):
        try:
            fn()
        except Exception as exc:
            messagebox.showerror('Reeltern', str(exc))

    def task(self, fn, done):
        if self.busy:
            self.status.set('Please wait for the current import or analysis.')
            return
        self.busy = True
        self.status.set('Working locally…')
        def worker():
            try:
                self.events.put((done, fn(), None))
            except Exception as exc:
                self.events.put((done, None, str(exc)))
        threading.Thread(target=worker, daemon=False).start()

    def refresh_assets(self):
        self.assets.delete(*self.assets.get_children())
        for asset in self.ws.assets():
            self.assets.insert('', 'end', iid=asset['id'], values=(asset['name'], f'{asset["duration"]:.2f}', f'{asset["width"]} × {asset["height"]}', 'Yes' if asset['audio'] else 'No'))

    def import_files(self):
        paths = filedialog.askopenfilenames(title='Choose local video files')
        if paths:
            self.task(lambda: [self.ws.import_media(p) for p in paths], lambda _: self.refresh_assets())

    def selected_assets(self):
        ids = self.assets.selection()
        if not ids:
            raise ValueError('Select footage first')
        return ids

    def assemble(self):
        def action():
            ids = self.selected_assets()
            self.show_plan(self.ws.create_plan([{'asset_id': i} for i in ids], self.preset.get(), self.fit.get()))
        self.guarded(action)

    def suggest(self):
        def action():
            ids = self.selected_assets()
            if len(ids) != 1:
                raise ValueError('Select one video for silence-assisted cuts')
            preset = self.preset.get()
            self.task(lambda: self.ws.suggest(ids[0], preset), self.show_plan)
        self.guarded(action)

    def show_plan(self, plan):
        self.plan = plan
        self.preset.set(plan['preset']); self.fit.set(plan['fit'])
        self.timeline.delete(*self.timeline.get_children())
        for i, c in enumerate(plan['clips']):
            asset = self.ws.asset(c['asset_id'])
            self.timeline.insert('', 'end', iid=str(i), values=(asset['name'], f'{c["start"]:.3f}', f'{c["end"]:.3f}', c['speed'], f'{c["timeline_start"]:.2f}s', c['reason']))
        self.summary.set(f'{len(plan["clips"])} clips · {plan["duration"]:.2f}s · {plan["preset"]} · revision {plan["id"][:8]}')
        self.status.set(plan['notes'])

    def clips(self):
        if not self.plan:
            raise ValueError('Create or select a plan first')
        return [{k: v for k, v in c.items() if k in ('asset_id', 'start', 'end', 'speed', 'reason')} for c in self.plan['clips']]

    def selection(self):
        selection = self.timeline.selection()
        if not selection:
            raise ValueError('Select a clip in the timeline')
        return int(selection[0])

    def select_clip(self, _=None):
        if self.plan and self.timeline.selection():
            clip = self.plan['clips'][self.selection()]
            for key, var in self.fields.items():
                var.set(str(clip[key]))

    def save_revision(self, clips, note):
        parent = self.plan['id']
        previous = self.plan['duration']
        plan = self.ws.create_plan(clips, self.preset.get(), self.fit.get(), parent, note, self.plan.get('transcript_ids', []))
        self.show_plan(plan)
        self.status.set(f'{note} · {previous:.2f}s → {plan["duration"]:.2f}s. Earlier revision preserved.')

    def revise(self):
        clips = self.clips()
        index = self.selection()
        clips[index].update({k: float(v.get()) for k, v in self.fields.items()})
        clips[index]['reason'] = 'User revised source range or playback speed'
        self.save_revision(clips, 'Manual revision')

    def move(self, offset):
        clips = self.clips()
        a, b = self.selection(), self.selection() + offset
        if 0 <= b < len(clips):
            clips[a], clips[b] = clips[b], clips[a]
            self.save_revision(clips, 'Reordered clips')
            self.timeline.selection_set(str(b))

    def remove(self):
        clips = self.clips()
        del clips[self.selection()]
        self.save_revision(clips, 'Removed clip')

    def undo(self):
        if self.plan and self.plan['parent']:
            self.show_plan(self.ws.plan(self.plan['parent']))
        else:
            self.status.set('This plan has no parent. All saved plans are available under Earlier plans.')

    def history(self):
        window = tk.Toplevel(self.root)
        window.title('Saved plans — select to restore')
        window.geometry('720x340')
        table = ttk.Treeview(window, columns=('id', 'duration', 'notes'), show='headings')
        for key in ('id', 'duration', 'notes'):
            table.heading(key, text=key.title())
        table.pack(fill='both', expand=True)
        for p in self.ws.plans():
            table.insert('', 'end', iid=p['id'], values=(p['id'][:12], f'{p["duration"]:.2f}s', p['notes']))
        def restore():
            if table.selection():
                self.show_plan(self.ws.plan(table.selection()[0]))
                window.destroy()
        ttk.Button(window, text='Open selected plan', command=restore).pack(pady=8)

    def transcript_editor(self):
        def open_editor():
            ids = self.selected_assets()
            if len(ids) != 1:
                raise ValueError('Select one video for transcript editing')
            from . import transcript
            from .agent import EditorialAgent
            asset_id = ids[0]
            window = tk.Toplevel(self.root)
            window.title('Edit from transcript · local AI drafts')
            window.geometry('920x620')
            frame = ttk.Frame(window, padding=18)
            frame.pack(fill='both', expand=True)
            ttk.Label(frame, text='Select the words to keep', font=('Helvetica', 18, 'bold')).pack(anchor='w')
            ttk.Label(frame, text='Import a timecoded SRT transcript. Reeltern does not transcribe speech. Captions follow your cuts.', wraplength=850).pack(anchor='w', pady=8)
            current = {'transcript': None}
            table = ttk.Treeview(frame, columns=('range', 'text'), show='headings', selectmode='extended')
            table.heading('range', text='Source time'); table.column('range', width=140)
            table.heading('text', text='Transcript'); table.column('text', width=690)
            table.pack(fill='both', expand=True, pady=10)
            def display(value):
                current['transcript'] = value
                table.delete(*table.get_children())
                for cue in value['cues']:
                    table.insert('', 'end', iid=cue['id'], values=(f'{cue["start"]:.2f}–{cue["end"]:.2f}s', cue['text']))
            def load_srt():
                filename = filedialog.askopenfilename(parent=window, filetypes=[('SubRip transcript', '*.srt')])
                if filename:
                    self.guarded(lambda: display(transcript.register(self.ws, asset_id, transcript.parse_srt(Path(filename).read_text(encoding='utf-8-sig')))))
            def chosen_plan():
                if not current['transcript']:
                    raise ValueError('Import an SRT transcript first')
                plan = transcript.select(self.ws, current['transcript']['id'], list(table.selection()), self.preset.get())
                self.show_plan(plan)
                window.destroy()
            buttons = ttk.Frame(frame); buttons.pack(fill='x')
            ttk.Button(buttons, text='Import SRT', command=load_srt).pack(side='left', padx=(0,8))
            ttk.Button(buttons, text='Keep selected cues', command=lambda: self.guarded(chosen_plan)).pack(side='left')
            ttk.Label(frame, text='Or describe a draft for your local Ollama model', font=('Helvetica', 12, 'bold')).pack(anchor='w', pady=(18,6))
            brief = tk.StringVar()
            ttk.Entry(frame, textvariable=brief).pack(fill='x')
            options = ttk.Frame(frame); options.pack(fill='x', pady=10)
            model, seconds = tk.StringVar(), tk.StringVar(value='60')
            ttk.Label(options, text='Installed model').pack(side='left')
            ttk.Entry(options, textvariable=model, width=24).pack(side='left', padx=8)
            ttk.Label(options, text='Maximum seconds').pack(side='left')
            ttk.Entry(options, textvariable=seconds, width=8).pack(side='left', padx=8)
            def ask_agent():
                if not current['transcript']:
                    raise ValueError('Import an SRT transcript first')
                service = EditorialAgent(self.ws, model.get())
                transcript_id, request, budget, preset = current['transcript']['id'], brief.get(), float(seconds.get()), self.preset.get()
                def done(result):
                    self.show_plan(result['plan'])
                    if window.winfo_exists():
                        window.destroy()
                self.task(lambda: service.draft(transcript_id, request, budget, preset), done)
            ttk.Button(options, text='Create AI draft', command=lambda: self.guarded(ask_agent)).pack(side='right')
            ttk.Label(frame, text='Sends transcript text to your local Ollama service. Creates a draft only. Review context and captions before exporting.', wraplength=850).pack(anchor='w')
            existing = sorted((self.ws.root / 'transcripts').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
            for path in existing:
                value = transcript.get(self.ws, path.stem)
                if value['asset_id'] == asset_id:
                    display(value)
                    break
        self.guarded(open_editor)

    def start_render(self, preview):
        def action():
            if self.job and self.renderer.status(self.job)['status'] in ('queued', 'running', 'verifying'):
                raise ValueError('Wait for the current render or cancel it')
            clips = self.clips()
            if self.plan['preset'] != self.preset.get() or self.plan['fit'] != self.fit.get():
                self.save_revision(clips, 'Changed output format')
            state = self.renderer.submit(self.plan['id'], preview)
            self.job = state['id']
            self.open_button.configure(state='disabled')
            self.status.set('Render queued')
        self.guarded(action)

    def cancel(self):
        if self.job:
            self.guarded(lambda: self.renderer.cancel(self.job))

    def open_video(self):
        state = self.renderer.status(self.job)
        if state['status'] == 'complete':
            webbrowser.open(Path(state['output']).as_uri())

    def open_results(self):
        webbrowser.open((self.ws.root / 'jobs').as_uri())

    def poll(self):
        while not self.events.empty():
            done, result, error = self.events.get_nowait()
            self.busy = False
            if error:
                self.status.set(error)
            else:
                self.status.set('Ready')
                self.guarded(lambda: done(result))
        if self.job:
            state = self.renderer.status(self.job)
            self.progress['value'] = state['completed_clips'] / state['total_clips'] * 100
            if state['status'] in ('queued', 'running', 'verifying'):
                self.status.set(f'{state["status"].title()} · {state["completed_clips"]}/{state["total_clips"]} clips · {state["cache_hits"]} reused')
            elif state['status'] == 'complete':
                self.open_button.configure(state='normal')
                if self.reported_job != self.job:
                    self.status.set(f'Complete · {state["elapsed_seconds"]:.1f}s · verified video and audio · {state["cache_hits"]} clips reused')
                    self.reported_job = self.job
            elif state['status'] in ('failed', 'cancelled'):
                self.status.set(state.get('error', state['status']))
        self.root.after(200, self.poll)

    def close(self):
        if self.busy:
            self.status.set('Wait for import or analysis to finish before closing.')
            return
        self.renderer.close()
        self.root.destroy()


def launch(workspace='reeltern-workspace'):
    root = tk.Tk()
    Studio(root, workspace)
    root.mainloop()
