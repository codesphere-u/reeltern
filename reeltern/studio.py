"""Reeltern Studio — modern local desktop workstation over the core editing engine."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
from .effects import CAPTION_MODES, CAPTION_STYLES, COLOR_GRADES, FLIPS, ROTATIONS, TRANSITIONS
from .workspace import PRESETS, Workspace
from .render import Renderer

COLORS = {
    'bg': '#0b1120',
    'panel': '#111827',
    'card': '#172033',
    'border': '#26344d',
    'accent': '#38bdf8',
    'indigo': '#818cf8',
    'mint': '#34d399',
    'amber': '#fbbf24',
    'danger': '#f87171',
    'text': '#f1f5f9',
    'muted': '#94a3b8',
}

CLIP_PALETTE = ['#1e3a5f', '#273059', '#194542', '#3f2e56', '#4a3520', '#1e4263']


class Studio:
    def __init__(self, root, workspace='reeltern-workspace'):
        self.root = root
        self.ws = Workspace(workspace)
        self.renderer = Renderer(self.ws)
        self.plan = None
        self.job = None
        self.reported_job = None
        self.busy = False
        self.events = queue.Queue()
        self.thumb_images = []
        self.clip_hitboxes = []
        self.playhead_sec = 0.0
        self.current_visuals = None

        self.root.title('Reeltern Studio — Advanced Local Video Workflow Toolkit')
        self.root.geometry('1280x880')
        self.root.minsize(1040, 720)
        self.root.configure(bg=COLORS['bg'])
        self._configure_styles()

        self.preset = tk.StringVar(value='landscape')
        self.fit = tk.StringVar(value='contain')
        self.summary = tk.StringVar(value='Import footage or generate a title card to begin.')
        self.status = tk.StringVar(value='Ready · Local workspace: ' + str(self.ws.root.name))
        self.playhead_text = tk.StringVar(value='Playhead: 0.00s')

        self.fields = {
            'start': tk.StringVar(),
            'end': tk.StringVar(),
            'speed': tk.StringVar(value='1.0'),
        }
        self.fx_fields = {
            'grade': tk.StringVar(value='none'),
            'flip': tk.StringVar(value='none'),
            'rotate': tk.StringVar(value='0'),
            'fade_in': tk.StringVar(value='0.0'),
            'fade_out': tk.StringVar(value='0.0'),
            'volume': tk.StringVar(value='1.0'),
            'brightness': tk.StringVar(value='0.0'),
            'contrast': tk.StringVar(value='1.0'),
            'saturation': tk.StringVar(value='1.0'),
            'title_overlay': tk.StringVar(value=''),
        }
        self.tl_fields = {
            'transition': tk.StringVar(value='cut'),
            'transition_duration': tk.StringVar(value='0.4'),
            'normalize_audio': tk.BooleanVar(value=False),
            'caption_mode': tk.StringVar(value='soft'),
            'caption_style': tk.StringVar(value='clean'),
        }

        self._build_layout()
        self._bind_shortcuts()
        self.refresh_assets()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(180, self.poll)

    def _configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('.', background=COLORS['bg'], foreground=COLORS['text'], fieldbackground=COLORS['card'], bordercolor=COLORS['border'], font=('Helvetica', 11))
        style.configure('Panel.TFrame', background=COLORS['panel'])
        style.configure('Card.TFrame', background=COLORS['card'])
        style.configure('Header.TLabel', background=COLORS['bg'], foreground=COLORS['text'], font=('Helvetica', 16, 'bold'))
        style.configure('Section.TLabel', background=COLORS['panel'], foreground=COLORS['accent'], font=('Helvetica', 11, 'bold'))
        style.configure('Muted.TLabel', background=COLORS['panel'], foreground=COLORS['muted'], font=('Helvetica', 10))
        style.configure('TLabel', background=COLORS['panel'], foreground=COLORS['text'])
        style.configure('Status.TLabel', background=COLORS['bg'], foreground=COLORS['muted'], font=('Helvetica', 10))
        style.configure('TButton', background=COLORS['card'], foreground=COLORS['text'], padding=(10, 6), borderwidth=1)
        style.map('TButton', background=[('active', COLORS['border']), ('pressed', COLORS['accent'])])
        style.configure('Accent.TButton', background=COLORS['accent'], foreground='#04101d', font=('Helvetica', 11, 'bold'), padding=(12, 6))
        style.map('Accent.TButton', background=[('active', '#7dd3fc')])
        style.configure('Treeview', background=COLORS['card'], foreground=COLORS['text'], fieldbackground=COLORS['card'], rowheight=26, borderwidth=0)
        style.configure('Treeview.Heading', background=COLORS['panel'], foreground=COLORS['accent'], font=('Helvetica', 10, 'bold'))
        style.map('Treeview', background=[('selected', '#1e3a5f')], foreground=[('selected', COLORS['text'])])
        style.configure('TNotebook', background=COLORS['panel'], borderwidth=0)
        style.configure('TNotebook.Tab', background=COLORS['card'], foreground=COLORS['muted'], padding=(12, 6))
        style.map('TNotebook.Tab', background=[('selected', '#1e3a5f')], foreground=[('selected', COLORS['text'])])
        style.configure('TEntry', fieldbackground=COLORS['bg'], foreground=COLORS['text'], insertcolor=COLORS['accent'])
        style.configure('TCombobox', fieldbackground=COLORS['bg'], background=COLORS['card'], foreground=COLORS['text'])
        style.configure('TCheckbutton', background=COLORS['panel'], foreground=COLORS['text'])
        style.configure('Horizontal.TProgressbar', troughcolor=COLORS['card'], background=COLORS['accent'], thickness=8)

    def _build_layout(self):
        # Top command header
        top = tk.Frame(self.root, bg=COLORS['bg'], padx=14, pady=10)
        top.pack(fill='x')
        left_hdr = tk.Frame(top, bg=COLORS['bg'])
        left_hdr.pack(side='left')
        tk.Label(left_hdr, text='REELTERN STUDIO', bg=COLORS['bg'], fg=COLORS['accent'], font=('Helvetica', 13, 'bold')).pack(side='left')
        tk.Label(left_hdr, text='  ·  Immutable Timeline & Media Toolkit', bg=COLORS['bg'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left')

        bar = tk.Frame(top, bg=COLORS['bg'])
        bar.pack(side='right')
        ttk.Button(bar, text='Import Footage', style='Accent.TButton', command=self.import_file).pack(side='left', padx=3)
        ttk.Button(bar, text='+ Title Card', command=self.title_card_dialog).pack(side='left', padx=3)
        ttk.Button(bar, text='Silence Trim', command=self.suggest).pack(side='left', padx=3)
        ttk.Button(bar, text='Transcript & AI', command=self.transcript_editor).pack(side='left', padx=3)
        ttk.Button(bar, text='Plans & Diff', command=self.history).pack(side='left', padx=3)
        ttk.Button(bar, text='Render Folder', command=self.open_results).pack(side='left', padx=3)

        fmt_bar = tk.Frame(self.root, bg=COLORS['card'], padx=14, pady=6)
        fmt_bar.pack(fill='x', padx=14, pady=(0, 8))
        tk.Label(fmt_bar, textvariable=self.summary, bg=COLORS['card'], fg=COLORS['text'], font=('Helvetica', 11, 'bold')).pack(side='left')
        fmt_right = tk.Frame(fmt_bar, bg=COLORS['card'])
        fmt_right.pack(side='right')
        tk.Label(fmt_right, text='Output:', bg=COLORS['card'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 4))
        ttk.Combobox(fmt_right, textvariable=self.preset, values=list(PRESETS), state='readonly', width=10).pack(side='left', padx=3)
        ttk.Combobox(fmt_right, textvariable=self.fit, values=('contain', 'cover'), state='readonly', width=9).pack(side='left', padx=3)

        # Split main workspace
        body = tk.Frame(self.root, bg=COLORS['bg'], padx=14)
        body.pack(fill='both', expand=True)

        # Left column: Media Bin + Storyboard & Waveform
        left = tk.Frame(body, bg=COLORS['panel'], width=320, highlightthickness=1, highlightbackground=COLORS['border'])
        left.pack(side='left', fill='y', padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(left, text='MEDIA BIN', bg=COLORS['panel'], fg=COLORS['accent'], font=('Helvetica', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 4))
        self.assets = ttk.Treeview(left, columns=('name', 'dur', 'audio'), show='headings', height=8)
        self.assets.heading('name', text='Asset')
        self.assets.heading('dur', text='Dur')
        self.assets.heading('audio', text='Audio')
        self.assets.column('name', width=165)
        self.assets.column('dur', width=60)
        self.assets.column('audio', width=65)
        self.assets.pack(fill='x', padx=10)
        self.assets.bind('<<TreeviewSelect>>', self.select_asset)

        bin_btns = tk.Frame(left, bg=COLORS['panel'])
        bin_btns.pack(fill='x', padx=10, pady=8)
        ttk.Button(bin_btns, text='Assemble Timeline', style='Accent.TButton', command=self.assemble).pack(side='left', fill='x', expand=True, padx=(0, 4))
        ttk.Button(bin_btns, text='Inspect Visuals', command=lambda: self.guarded(self.load_selected_visuals)).pack(side='left')

        tk.Label(left, text='STORYBOARD & WAVEFORM', bg=COLORS['panel'], fg=COLORS['accent'], font=('Helvetica', 10, 'bold')).pack(anchor='w', padx=10, pady=(6, 4))
        self.storyboard_canvas = tk.Canvas(left, bg=COLORS['bg'], height=154, highlightthickness=1, highlightbackground=COLORS['border'])
        self.storyboard_canvas.pack(fill='x', padx=10)
        self.waveform_canvas = tk.Canvas(left, bg=COLORS['bg'], height=92, highlightthickness=1, highlightbackground=COLORS['border'])
        self.waveform_canvas.pack(fill='x', padx=10, pady=(6, 10))
        self.waveform_canvas.bind('<Button-1>', self._on_waveform_click)

        # Right column: Interactive Timeline Canvas + Cut Sheet + Multi-Tab Inspector
        right = tk.Frame(body, bg=COLORS['panel'], highlightthickness=1, highlightbackground=COLORS['border'])
        right.pack(side='left', fill='both', expand=True)

        tl_top = tk.Frame(right, bg=COLORS['panel'], padx=10, pady=8)
        tl_top.pack(fill='x')
        tk.Label(tl_top, text='VISUAL TIMELINE', bg=COLORS['panel'], fg=COLORS['accent'], font=('Helvetica', 10, 'bold')).pack(side='left')
        tk.Label(tl_top, textvariable=self.playhead_text, bg=COLORS['card'], fg=COLORS['amber'], font=('Helvetica', 10, 'bold'), padx=8, pady=2).pack(side='right')

        self.timeline_canvas = tk.Canvas(right, bg=COLORS['bg'], height=120, highlightthickness=1, highlightbackground=COLORS['border'])
        self.timeline_canvas.pack(fill='x', padx=10)
        self.timeline_canvas.bind('<Button-1>', self._on_timeline_canvas_click)
        self.timeline_canvas.bind('<Configure>', lambda _e: self._draw_timeline_canvas())

        self.timeline = ttk.Treeview(
            right,
            columns=('clip', 'in', 'out', 'speed', 'at', 'fx', 'reason'),
            show='headings',
            height=6,
        )
        for key, label, width in (
            ('clip', 'Clip', 135),
            ('in', 'In', 66),
            ('out', 'Out', 66),
            ('speed', 'Speed', 55),
            ('at', 'Start', 65),
            ('fx', 'Look / FX', 130),
            ('reason', 'Notes / Reason', 230),
        ):
            self.timeline.heading(key, text=label)
            self.timeline.column(key, width=width)
        self.timeline.pack(fill='both', expand=True, padx=10, pady=8)
        self.timeline.bind('<<TreeviewSelect>>', self.select_clip)

        # Inspector notebook
        self.inspector = ttk.Notebook(right)
        self.inspector.pack(fill='x', padx=10, pady=(0, 10))

        tab_trim = ttk.Frame(self.inspector, style='Panel.TFrame', padding=10)
        tab_fx = ttk.Frame(self.inspector, style='Panel.TFrame', padding=10)
        tab_tl = ttk.Frame(self.inspector, style='Panel.TFrame', padding=10)
        self.inspector.add(tab_trim, text='  Trim & Split  ')
        self.inspector.add(tab_fx, text='  Color, Audio & Lower Third  ')
        self.inspector.add(tab_tl, text='  Transitions & Burned Captions  ')

        self._build_trim_tab(tab_trim)
        self._build_fx_tab(tab_fx)
        self._build_timeline_tab(tab_tl)

        # Bottom Render & Verification Footer
        footer = tk.Frame(self.root, bg=COLORS['bg'], padx=14, pady=10)
        footer.pack(fill='x')
        self.progress = ttk.Progressbar(footer, mode='determinate', maximum=100, length=240)
        self.progress.pack(side='left', padx=(0, 10))
        tk.Label(footer, textvariable=self.status, bg=COLORS['bg'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', fill='x', expand=True)

        actions = tk.Frame(footer, bg=COLORS['bg'])
        actions.pack(side='right')
        ttk.Button(actions, text='Preview', style='Accent.TButton', command=lambda: self.start_render(True)).pack(side='left', padx=3)
        ttk.Button(actions, text='Export Final', command=lambda: self.start_render(False)).pack(side='left', padx=3)
        ttk.Button(actions, text='Cancel', command=self.cancel).pack(side='left', padx=3)
        ttk.Button(actions, text='Receipt', command=self.show_receipt).pack(side='left', padx=3)
        self.open_button = ttk.Button(actions, text='Open Video', command=self.open_video, state='disabled')
        self.open_button.pack(side='left', padx=(3, 0))

    def _build_trim_tab(self, parent):
        row1 = tk.Frame(parent, bg=COLORS['panel'])
        row1.pack(fill='x')
        for label, key in (('In (s)', 'start'), ('Out (s)', 'end'), ('Speed (0.25–4x)', 'speed')):
            tk.Label(row1, text=label, bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 4))
            ttk.Entry(row1, textvariable=self.fields[key], width=8).pack(side='left', padx=(0, 10))
        tk.Label(row1, text='Flip', bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 4))
        ttk.Combobox(row1, textvariable=self.fx_fields['flip'], values=FLIPS, state='readonly', width=10).pack(side='left', padx=(0, 8))
        tk.Label(row1, text='Rotate', bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 4))
        ttk.Combobox(row1, textvariable=self.fx_fields['rotate'], values=[str(r) for r in ROTATIONS], state='readonly', width=5).pack(side='left')

        row2 = tk.Frame(parent, bg=COLORS['panel'])
        row2.pack(fill='x', pady=(8, 0))
        ttk.Button(row2, text='Apply Trim / Motion', style='Accent.TButton', command=lambda: self.guarded(self.revise)).pack(side='left', padx=(0, 5))
        ttk.Button(row2, text='Split at Playhead (S)', command=lambda: self.guarded(self.split_at_playhead)).pack(side='left', padx=3)
        ttk.Button(row2, text='Duplicate', command=lambda: self.guarded(self.duplicate_clip)).pack(side='left', padx=3)
        ttk.Button(row2, text='Up', command=lambda: self.guarded(lambda: self.move(-1))).pack(side='left', padx=3)
        ttk.Button(row2, text='Down', command=lambda: self.guarded(lambda: self.move(1))).pack(side='left', padx=3)
        ttk.Button(row2, text='Delete', command=lambda: self.guarded(self.remove)).pack(side='left', padx=3)
        ttk.Button(row2, text='Undo Revision', command=lambda: self.guarded(self.undo)).pack(side='right')

    def _build_fx_tab(self, parent):
        row1 = tk.Frame(parent, bg=COLORS['panel'])
        row1.pack(fill='x')
        tk.Label(row1, text='Color Grade:', bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 6))
        for g in COLOR_GRADES:
            ttk.Radiobutton(row1, text=g.title(), variable=self.fx_fields['grade'], value=g).pack(side='left', padx=3)

        row2 = tk.Frame(parent, bg=COLORS['panel'])
        row2.pack(fill='x', pady=(8, 0))
        for label, key in (
            ('Fade In (s)', 'fade_in'),
            ('Fade Out (s)', 'fade_out'),
            ('Volume (0–2)', 'volume'),
            ('Bright', 'brightness'),
            ('Contrast', 'contrast'),
            ('Sat', 'saturation'),
        ):
            tk.Label(row2, text=label, bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 3))
            ttk.Entry(row2, textvariable=self.fx_fields[key], width=5).pack(side='left', padx=(0, 8))

        row3 = tk.Frame(parent, bg=COLORS['panel'])
        row3.pack(fill='x', pady=(8, 0))
        tk.Label(row3, text='Lower-Third Overlay:', bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 6))
        ttk.Entry(row3, textvariable=self.fx_fields['title_overlay'], width=42).pack(side='left', fill='x', expand=True, padx=(0, 10))
        ttk.Button(row3, text='Apply Clip Effects', style='Accent.TButton', command=lambda: self.guarded(self.apply_clip_effects)).pack(side='right')

    def _build_timeline_tab(self, parent):
        row1 = tk.Frame(parent, bg=COLORS['panel'])
        row1.pack(fill='x')
        tk.Label(row1, text='Join Transition:', bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 4))
        ttk.Combobox(row1, textvariable=self.tl_fields['transition'], values=list(TRANSITIONS), state='readonly', width=11).pack(side='left', padx=(0, 10))
        tk.Label(row1, text='Duration (s):', bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 4))
        ttk.Entry(row1, textvariable=self.tl_fields['transition_duration'], width=6).pack(side='left', padx=(0, 12))
        ttk.Checkbutton(row1, text='EBU R128 Audio Loudnorm (-16 LUFS)', variable=self.tl_fields['normalize_audio']).pack(side='left')

        row2 = tk.Frame(parent, bg=COLORS['panel'])
        row2.pack(fill='x', pady=(8, 0))
        tk.Label(row2, text='Caption Delivery:', bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 4))
        ttk.Combobox(row2, textvariable=self.tl_fields['caption_mode'], values=CAPTION_MODES, state='readonly', width=8).pack(side='left', padx=(0, 10))
        tk.Label(row2, text='Burn Style:', bg=COLORS['panel'], fg=COLORS['muted'], font=('Helvetica', 10)).pack(side='left', padx=(0, 4))
        ttk.Combobox(row2, textvariable=self.tl_fields['caption_style'], values=CAPTION_STYLES, state='readonly', width=9).pack(side='left', padx=(0, 10))
        ttk.Button(row2, text='Apply Timeline Style', style='Accent.TButton', command=lambda: self.guarded(self.apply_timeline_style)).pack(side='right')

    def _bind_shortcuts(self):
        self.root.bind('<Control-z>', lambda _e: self.guarded(self.undo))
        self.root.bind('<Command-z>', lambda _e: self.guarded(self.undo))
        self.root.bind('<s>', lambda e: None if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) else self.guarded(self.split_at_playhead))

    def guarded(self, fn):
        try:
            fn()
        except Exception as exc:
            self.status.set(str(exc))

    def task(self, work, done):
        if self.busy:
            raise ValueError('Another operation is running')
        self.busy = True
        self.status.set('Working…')

        def runner():
            try:
                self.events.put((done, work(), None))
            except Exception as exc:
                self.events.put((done, None, str(exc)))

        threading.Thread(target=runner, daemon=True).start()

    def refresh_assets(self):
        self.assets.delete(*self.assets.get_children())
        for a in self.ws.assets():
            self.assets.insert('', 'end', iid=a['id'], values=(a['name'], f'{a["duration"]:.2f}s', 'Audio' if a['audio'] else 'Silent'))

    def import_file(self):
        path = filedialog.askopenfilename(title='Choose video file', filetypes=[('Video files', '*.mp4 *.mov *.mkv *.webm *.avi'), ('All files', '*.*')])
        if not path:
            return
        def _after(asset):
            self.refresh_assets()
            self.assets.selection_set(asset['id'])
            self.status.set(f'Imported {asset["name"]} ({asset["duration"]:.2f}s)')
            self.task(lambda: self.ws.inspect_visuals(asset['id'], thumbs=6, samples=60), self.display_visuals)
        self.guarded(lambda: self.task(lambda: self.ws.import_media(path), _after))

    def select_asset(self, _=None):
        ids = self.assets.selection()
        if ids:
            asset_id = ids[0]
            cache_file = self.ws.path('analysis', self.ws.visuals_cache_id(asset_id, 6, 60))
            if cache_file.exists():
                self.guarded(lambda: self.display_visuals(self.ws.inspect_visuals(asset_id, thumbs=6, samples=60)))

    def load_selected_visuals(self):
        ids = self.selected_assets()
        self.task(lambda: self.ws.inspect_visuals(ids[0], thumbs=6, samples=60), self.display_visuals)

    def display_visuals(self, visuals):
        self.current_visuals = visuals
        self._draw_storyboard(visuals)
        self._draw_waveform(visuals)

    def _draw_storyboard(self, visuals):
        c = self.storyboard_canvas
        c.delete('all')
        self.thumb_images.clear()
        thumbs = visuals.get('storyboard', [])
        if not thumbs:
            c.create_text(150, 75, text='No frames cached', fill=COLORS['muted'], font=('Helvetica', 10))
            return
        cols = 3
        cell_w, cell_h = 94, 54
        for idx, item in enumerate(thumbs[:6]):
            col, row = idx % cols, idx // cols
            x0, y0 = 10 + col * (cell_w + 6), 8 + row * (cell_h + 18)
            try:
                img = tk.PhotoImage(file=item['path']).subsample(2, 2)
                self.thumb_images.append(img)
                c.create_rectangle(x0 - 1, y0 - 1, x0 + cell_w + 1, y0 + cell_h + 1, outline=COLORS['border'], fill=COLORS['card'])
                c.create_image(x0 + cell_w // 2, y0 + cell_h // 2, image=img)
            except tk.TclError:
                c.create_rectangle(x0, y0, x0 + cell_w, y0 + cell_h, outline=COLORS['border'], fill=COLORS['card'])
            c.create_text(x0 + cell_w // 2, y0 + cell_h + 8, text=f'{item["time"]:.1f}s', fill=COLORS['muted'], font=('Helvetica', 8))

    def _draw_waveform(self, visuals):
        c = self.waveform_canvas
        c.delete('all')
        w = max(280, int(c.winfo_width() or 296))
        h = int(c.winfo_height() or 92)
        mid = h // 2
        wf = visuals.get('waveform', {})
        peaks = wf.get('samples', [])
        if not wf.get('has_audio') or not peaks:
            c.create_line(10, mid, w - 10, mid, fill=COLORS['border'])
            c.create_text(w // 2, mid - 12, text='Silent track (no audio stream)', fill=COLORS['muted'], font=('Helvetica', 9))
            return
        step = max(2, (w - 16) / len(peaks))
        for i, amp in enumerate(peaks):
            x = 8 + i * step
            bar = max(2, amp * (h * 0.42))
            color = COLORS['amber'] if amp > 0.78 else COLORS['accent'] if amp > 0.15 else COLORS['border']
            c.create_line(x, mid - bar, x, mid + bar, fill=color, width=max(1.5, step * 0.65))
        c.create_text(w - 10, 10, anchor='e', text=f'Peak {wf.get("peak_db", 0):.1f} dB', fill=COLORS['muted'], font=('Helvetica', 8))

    def _on_waveform_click(self, event):
        if not self.current_visuals:
            return
        w = max(280, int(self.waveform_canvas.winfo_width() or 296))
        ratio = max(0.0, min(1.0, (event.x - 8) / max(1, w - 16)))
        self.playhead_sec = round(ratio * self.current_visuals['duration'], 2)
        self.playhead_text.set(f'Playhead: {self.playhead_sec:.2f}s')
        self._draw_timeline_canvas()

    def title_card_dialog(self):
        win = tk.Toplevel(self.root)
        win.title('Create Title / Chapter Card')
        win.geometry('480x360')
        win.configure(bg=COLORS['panel'])
        frm = tk.Frame(win, bg=COLORS['panel'], padx=18, pady=16)
        frm.pack(fill='both', expand=True)
        tk.Label(frm, text='Generate Slate / Title Card Asset', bg=COLORS['panel'], fg=COLORS['accent'], font=('Helvetica', 14, 'bold')).pack(anchor='w', pady=(0, 10))
        title_var = tk.StringVar(value='Chapter One')
        sub_var = tk.StringVar(value='Created locally in Reeltern Studio')
        dur_var = tk.StringVar(value='3.0')
        bg_var = tk.StringVar(value='#0f172a')
        acc_var = tk.StringVar(value='#38bdf8')
        for lbl, var in (('Heading', title_var), ('Subtitle', sub_var), ('Duration (s)', dur_var), ('Backdrop Hex', bg_var), ('Accent Hex', acc_var)):
            row = tk.Frame(frm, bg=COLORS['panel'])
            row.pack(fill='x', pady=4)
            tk.Label(row, text=lbl, bg=COLORS['panel'], fg=COLORS['muted'], width=14, anchor='w').pack(side='left')
            ttk.Entry(row, textvariable=var).pack(side='left', fill='x', expand=True)

        def create():
            preset = self.preset.get()
            def done(asset):
                self.refresh_assets()
                self.assets.selection_set(asset['id'])
                self.status.set(f'Created title card ({asset["duration"]:.1f}s)')
                if win.winfo_exists():
                    win.destroy()
            self.task(lambda: self.ws.create_card(title_var.get(), sub_var.get(), float(dur_var.get()), preset, bg_var.get(), acc_var.get()), done)

        ttk.Button(frm, text='Create Title Card Asset', style='Accent.TButton', command=lambda: self.guarded(create)).pack(anchor='e', pady=(14, 0))

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
        self.preset.set(plan['preset'])
        self.fit.set(plan['fit'])
        self.tl_fields['transition'].set(plan.get('transition', 'cut'))
        self.tl_fields['transition_duration'].set(str(plan.get('transition_duration', 0.4)))
        self.tl_fields['normalize_audio'].set(bool(plan.get('normalize_audio', False)))
        self.tl_fields['caption_mode'].set(plan.get('caption_mode', 'soft'))
        self.tl_fields['caption_style'].set(plan.get('caption_style', 'clean'))

        self.timeline.delete(*self.timeline.get_children())
        for i, c in enumerate(plan['clips']):
            asset = self.ws.asset(c['asset_id'])
            tags = []
            if c.get('grade', 'none') != 'none':
                tags.append(c['grade'])
            if c.get('fade_in', 0) > 0 or c.get('fade_out', 0) > 0:
                tags.append('fade')
            if c.get('rotate', 0):
                tags.append(f"{c['rotate']}°")
            if c.get('title_overlay'):
                tags.append('Title')
            fx_label = ' · '.join(tags) if tags else 'Clean'
            self.timeline.insert(
                '',
                'end',
                iid=str(i),
                values=(
                    f'#{i+1} {asset["name"]}',
                    f'{c["start"]:.3f}',
                    f'{c["end"]:.3f}',
                    f'{c["speed"]:.2g}×',
                    f'{c["timeline_start"]:.2f}s',
                    fx_label,
                    c['reason'],
                ),
            )
        trans = plan.get('transition', 'cut')
        cap = plan.get('caption_mode', 'soft')
        self.summary.set(
            f'{len(plan["clips"])} clips · {plan["duration"]:.2f}s · {plan["preset"]} ({plan["fit"]}) · {trans} · captions:{cap} · rev {plan["id"][:8]}'
        )
        self.status.set(plan['notes'])
        self._draw_timeline_canvas()

    def _draw_timeline_canvas(self):
        c = self.timeline_canvas
        c.delete('all')
        self.clip_hitboxes.clear()
        w = max(560, int(c.winfo_width() or 760))
        h = int(c.winfo_height() or 120)
        if not self.plan or not self.plan.get('clips'):
            c.create_text(w // 2, h // 2, text='Assemble or select a plan to inspect proportional timeline blocks', fill=COLORS['muted'], font=('Helvetica', 10))
            return

        total = max(0.05, float(self.plan['duration']))
        pad_x = 14
        track_w = max(120, w - 2 * pad_x)
        c.create_line(pad_x, 22, w - pad_x, 22, fill=COLORS['border'])
        ticks = min(10, max(2, int(total)))
        for idx in range(ticks + 1):
            t = total * idx / ticks
            tx = pad_x + (t / total) * track_w
            c.create_line(tx, 16, tx, 24, fill=COLORS['muted'])
            c.create_text(tx, 10, text=f'{t:.1f}s', fill=COLORS['muted'], font=('Helvetica', 8))

        selected_idx = int(self.timeline.selection()[0]) if self.timeline.selection() else -1
        for i, clip in enumerate(self.plan['clips']):
            dur = clip['frames'] / 30.0
            x0 = pad_x + (clip['timeline_start'] / total) * track_w
            x1 = max(x0 + 18, pad_x + ((clip['timeline_start'] + dur) / total) * track_w - 2)
            color = CLIP_PALETTE[i % len(CLIP_PALETTE)]
            outline = COLORS['amber'] if i == selected_idx else COLORS['accent'] if clip.get('grade') else COLORS['border']
            width = 2 if i == selected_idx else 1
            c.create_rectangle(x0, 32, x1, h - 16, fill=color, outline=outline, width=width)
            asset = self.ws.asset(clip['asset_id'])
            title = f'#{i+1} {asset["name"][:14]}'
            c.create_text(x0 + 6, 46, anchor='w', text=title, fill=COLORS['text'], font=('Helvetica', 9, 'bold'))
            sub = f'{dur:.2f}s @ {clip["speed"]:.2g}×' + (f' · {clip["grade"]}' if clip.get('grade') else '')
            c.create_text(x0 + 6, 66, anchor='w', text=sub, fill=COLORS['muted'], font=('Helvetica', 8))
            if clip.get('title_overlay'):
                c.create_text(x0 + 6, 84, anchor='w', text=f'T: {clip["title_overlay"][:16]}', fill=COLORS['mint'], font=('Helvetica', 8))
            self.clip_hitboxes.append((x0, x1, i))

        ph = max(0.0, min(total, self.playhead_sec))
        px = pad_x + (ph / total) * track_w
        c.create_line(px, 16, px, h - 8, fill=COLORS['amber'], width=2)
        c.create_polygon(px - 5, 16, px + 5, 16, px, 24, fill=COLORS['amber'], outline='')

    def _on_timeline_canvas_click(self, event):
        if not self.plan:
            return
        w = max(560, int(self.timeline_canvas.winfo_width() or 760))
        pad_x = 14
        track_w = max(120, w - 2 * pad_x)
        ratio = max(0.0, min(1.0, (event.x - pad_x) / track_w))
        self.playhead_sec = round(ratio * self.plan['duration'], 2)
        self.playhead_text.set(f'Playhead: {self.playhead_sec:.2f}s')
        for x0, x1, idx in self.clip_hitboxes:
            if x0 <= event.x <= x1:
                self.timeline.selection_set(str(idx))
                self.select_clip()
                break
        self._draw_timeline_canvas()

    def clips(self):
        if not self.plan:
            raise ValueError('Create or select a plan first')
        return self.ws._raw_clips(self.plan)

    def selection(self):
        selection = self.timeline.selection()
        if not selection:
            raise ValueError('Select a clip in the timeline')
        return int(selection[0])

    def select_clip(self, _=None):
        if self.plan and self.timeline.selection():
            clip = self.plan['clips'][self.selection()]
            self.fields['start'].set(str(clip['start']))
            self.fields['end'].set(str(clip['end']))
            self.fields['speed'].set(str(clip['speed']))
            self.fx_fields['grade'].set(clip.get('grade', 'none'))
            self.fx_fields['flip'].set(clip.get('flip', 'none'))
            self.fx_fields['rotate'].set(str(clip.get('rotate', 0)))
            self.fx_fields['fade_in'].set(str(clip.get('fade_in', 0.0)))
            self.fx_fields['fade_out'].set(str(clip.get('fade_out', 0.0)))
            self.fx_fields['volume'].set(str(clip.get('volume', 1.0)))
            self.fx_fields['brightness'].set(str(clip.get('brightness', 0.0)))
            self.fx_fields['contrast'].set(str(clip.get('contrast', 1.0)))
            self.fx_fields['saturation'].set(str(clip.get('saturation', 1.0)))
            self.fx_fields['title_overlay'].set(clip.get('title_overlay', ''))
            self._draw_timeline_canvas()

    def save_revision(self, clips, note):
        parent = self.plan['id']
        previous = self.plan['duration']
        plan = self.ws.create_plan(
            clips,
            self.preset.get(),
            self.fit.get(),
            parent,
            note,
            self.plan.get('transcript_ids', []),
            **self.ws.plan_options(self.plan),
        )
        self.show_plan(plan)
        self.status.set(f'{note} · {previous:.2f}s → {plan["duration"]:.2f}s. Earlier revision preserved.')

    def revise(self):
        clips = self.clips()
        index = self.selection()
        clips[index].update({k: float(v.get()) for k, v in self.fields.items()})
        clips[index]['flip'] = self.fx_fields['flip'].get()
        clips[index]['rotate'] = int(self.fx_fields['rotate'].get())
        clips[index]['reason'] = 'User revised range/motion'
        self.save_revision(clips, 'Manual trim/motion')

    def apply_clip_effects(self):
        index = self.selection()
        changes = {
            'grade': self.fx_fields['grade'].get(),
            'flip': self.fx_fields['flip'].get(),
            'rotate': int(self.fx_fields['rotate'].get()),
            'fade_in': float(self.fx_fields['fade_in'].get()),
            'fade_out': float(self.fx_fields['fade_out'].get()),
            'volume': float(self.fx_fields['volume'].get()),
            'brightness': float(self.fx_fields['brightness'].get()),
            'contrast': float(self.fx_fields['contrast'].get()),
            'saturation': float(self.fx_fields['saturation'].get()),
            'title_overlay': self.fx_fields['title_overlay'].get(),
        }
        plan = self.ws.update_clip(self.plan['id'], index, changes, notes=f'Styled clip {index + 1}')
        self.show_plan(plan)
        self.timeline.selection_set(str(index))

    def apply_timeline_style(self):
        if not self.plan:
            raise ValueError('Create or select a plan first')
        plan = self.ws.update_plan_style(
            self.plan['id'],
            preset=self.preset.get(),
            fit=self.fit.get(),
            transition=self.tl_fields['transition'].get(),
            transition_duration=float(self.tl_fields['transition_duration'].get()),
            normalize_audio=bool(self.tl_fields['normalize_audio'].get()),
            caption_mode=self.tl_fields['caption_mode'].get(),
            caption_style=self.tl_fields['caption_style'].get(),
        )
        self.show_plan(plan)

    def split_at_playhead(self):
        if not self.plan:
            raise ValueError('Create or select a plan first')
        index = self.selection()
        clip = self.plan['clips'][index]
        clip_dur = clip['frames'] / 30.0
        local_offset = self.playhead_sec - clip['timeline_start']
        if not 0.05 < local_offset < clip_dur - 0.05:
            local_offset = round(clip_dur / 2.0, 3)
        plan = self.ws.split_clip(self.plan['id'], index, local_offset)
        self.show_plan(plan)
        self.timeline.selection_set(str(index))

    def duplicate_clip(self):
        clips = self.clips()
        idx = self.selection()
        dup = dict(clips[idx])
        dup['reason'] = f"{dup.get('reason', 'Clip')} (Copy)"
        clips.insert(idx + 1, dup)
        self.save_revision(clips, f'Duplicated clip {idx + 1}')
        self.timeline.selection_set(str(idx + 1))

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
            self.status.set('This plan has no parent. Open Plans & Diff to inspect all versions.')

    def history(self):
        window = tk.Toplevel(self.root)
        window.title('Saved Plans & Revision Diff')
        window.geometry('780x420')
        window.configure(bg=COLORS['panel'])
        table = ttk.Treeview(window, columns=('id', 'duration', 'notes'), show='headings')
        for key in ('id', 'duration', 'notes'):
            table.heading(key, text=key.title())
        table.pack(fill='both', expand=True, padx=10, pady=10)
        for p in self.ws.plans():
            table.insert('', 'end', iid=p['id'], values=(p['id'][:12], f'{p["duration"]:.2f}s', p['notes']))

        btns = tk.Frame(window, bg=COLORS['panel'])
        btns.pack(fill='x', padx=10, pady=(0, 10))
        def restore():
            if table.selection():
                self.show_plan(self.ws.plan(table.selection()[0]))
                window.destroy()
        def diff_parent():
            if table.selection():
                sel = self.ws.plan(table.selection()[0])
                if not sel.get('parent'):
                    messagebox.showinfo('Plan Diff', 'Root plan has no parent revision.', parent=window)
                    return
                diff = self.ws.compare(sel['parent'], sel['id'])
                messagebox.showinfo(
                    'Revision Diff vs Parent',
                    f"Duration delta: {diff['duration_change']:+.2f}s ({diff['duration_before']:.2f}s -> {diff['duration_after']:.2f}s)\n"
                    f"Transitions: {diff['transition_change'][0]} -> {diff['transition_change'][1]}\n"
                    f"Captions: {diff['caption_mode_change'][0]} -> {diff['caption_mode_change'][1]}\n"
                    f"Clips: {len(diff['before_order'])} -> {len(diff['after_order'])}",
                    parent=window,
                )
        ttk.Button(btns, text='Compare vs Parent', command=diff_parent).pack(side='left')
        ttk.Button(btns, text='Open Selected Plan', style='Accent.TButton', command=restore).pack(side='right')

    def show_receipt(self):
        if not self.job:
            self.status.set('No render job selected yet.')
            return
        state = self.renderer.status(self.job)
        if state['status'] != 'complete':
            self.status.set(f'Job status: {state["status"]}')
            return
        import json
        receipt = json.loads(Path(state['receipt']).read_text(encoding='utf-8'))
        messagebox.showinfo(
            'Verification Receipt',
            f"SHA-256: {receipt['sha256'][:24]}...\n"
            f"Resolution: {receipt['output']['width']}x{receipt['output']['height']} · {receipt['output']['duration']:.2f}s\n"
            f"Verified: {', '.join(receipt['verified'])}\n"
            f"Cache hits: {receipt['cache_hits']}",
            parent=self.root,
        )

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
            window.configure(bg=COLORS['panel'])
            frame = ttk.Frame(window, style='Panel.TFrame', padding=18)
            frame.pack(fill='both', expand=True)
            ttk.Label(frame, text='Select the words to keep', font=('Helvetica', 16, 'bold')).pack(anchor='w')
            ttk.Label(frame, text='Import a timecoded SRT transcript. Reeltern does not transcribe speech. Captions follow your cuts.', wraplength=850).pack(anchor='w', pady=8)
            current = {'transcript': None}
            table = ttk.Treeview(frame, columns=('range', 'text'), show='headings', selectmode='extended')
            table.heading('range', text='Source time')
            table.column('range', width=140)
            table.heading('text', text='Transcript')
            table.column('text', width=690)
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
            buttons = ttk.Frame(frame, style='Panel.TFrame')
            buttons.pack(fill='x')
            ttk.Button(buttons, text='Import SRT', command=load_srt).pack(side='left', padx=(0, 8))
            ttk.Button(buttons, text='Keep selected cues', style='Accent.TButton', command=lambda: self.guarded(chosen_plan)).pack(side='left')
            ttk.Label(frame, text='Or describe a draft for your local Ollama model', font=('Helvetica', 12, 'bold')).pack(anchor='w', pady=(18, 6))
            brief = tk.StringVar()
            ttk.Entry(frame, textvariable=brief).pack(fill='x')
            options = ttk.Frame(frame, style='Panel.TFrame')
            options.pack(fill='x', pady=10)
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
            ttk.Button(options, text='Create AI draft', style='Accent.TButton', command=lambda: self.guarded(ask_agent)).pack(side='right')
            ttk.Label(frame, text='Sends compact cues to your local Ollama service. Review captions before export.', wraplength=850).pack(anchor='w')
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
        self.root.after(180, self.poll)

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
