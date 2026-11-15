"""Reeltern Studio — flagship local desktop NLE workstation & AI Director GUI."""
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
from .client_config import CLIENTS, CLIENT_DESTINATIONS, configuration
from .demo import run_demo
from .director import DIRECTOR_STYLES, audit_job_render, compose_plan
from .effects import CAPTION_MODES, CAPTION_STYLES, COLOR_GRADES, FIT_MODES, FLIPS, MOTIONS, ROTATIONS, TRANSITIONS
from .preview import GRADE_META, PreviewEngine, clip_at_time
from .render import Renderer
from .studio_widgets import (
    THEME,
    MetricTile,
    ParamSlider,
    PillButton,
    ScrollablePane,
    ToggleSwitch,
    draw_logo_mark,
    mono_font,
    ui_font,
)
from .workspace import PRESETS, Workspace

COLORS = THEME
CLIP_PALETTE = ['#1b3358', '#272f59', '#16423f', '#3a2b52', '#47321f', '#1c3f60']


def resolve_default_workspace(workspace=None):
    """Choose a writable workspace folder when launched without an explicit writable directory."""
    if workspace is not None and workspace != 'reeltern-workspace':
        return Path(workspace)
    if not getattr(sys, 'frozen', False):
        try:
            if os.access(Path.cwd(), os.W_OK):
                return Path(workspace or 'reeltern-workspace')
        except OSError:
            pass
    return Path.home() / 'ReelternWorkspace'


def _fmt_tc(seconds):
    sec = max(0.0, float(seconds))
    mins = int(sec // 60)
    rem = sec - mins * 60
    return f'{mins:02d}:{rem:05.2f}'


class Studio:
    def __init__(self, root, workspace=None):
        self.root = root
        self.ws = Workspace(resolve_default_workspace(workspace))
        self.renderer = Renderer(self.ws)
        self.preview_engine = PreviewEngine()
        self.plan = None
        self.job = None
        self.reported_job = None
        self.rendered_path = None
        self.busy = False
        self.playing = False
        self.events = queue.Queue()

        self.thumb_images = []
        self.tl_thumb_images = []
        self.tl_thumb_cache = {}
        self.monitor_photo = None
        self.qa_sheet_photo = None
        self.welcome_hitboxes = []
        self.clip_hitboxes = []
        self.storyboard_hitboxes = []
        self.playhead_sec = 0.0
        self.current_visuals = None
        self.monitor_mode = tk.StringVar(value='timeline')
        self.show_guides = tk.BooleanVar(value=True)
        self.selected_director = tk.StringVar(value='viral_reel')

        self._poll_after = None
        self._play_after = None
        self._monitor_after = None
        self._closing = False

        self.root.title('Reeltern Studio — AI Director & Local NLE Workstation')
        self.root.geometry('1360x840')
        self.root.minsize(1060, 700)
        self.root.configure(bg=COLORS['bg'])
        self._configure_styles()

        self.preset = tk.StringVar(value='landscape')
        self.fit = tk.StringVar(value='contain')
        self.summary = tk.StringVar(value='No timeline loaded · Import footage or click Load Demo')
        self.status = tk.StringVar(value='Ready')
        self.playhead_text = tk.StringVar(value='00:00.00 / 00:00.00')
        self.ws_label = tk.StringVar(value=self.ws.root.name)
        self.telemetry_text = tk.StringVar(value='Select a clip to inspect visual telemetry')
        self.monitor_badge = tk.StringVar(value='LIVE TIMELINE · landscape (1280×720)')

        self.fields = {
            'start': tk.StringVar(value='0.0'),
            'end': tk.StringVar(value='0.0'),
            'speed': tk.StringVar(value='1.0'),
        }
        self.fx_fields = {
            'grade': tk.StringVar(value='none'),
            'motion': tk.StringVar(value='none'),
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
            'voice_cleanup': tk.BooleanVar(value=False),
            'progress_bar': tk.BooleanVar(value=False),
            'caption_mode': tk.StringVar(value='soft'),
            'caption_style': tk.StringVar(value='clean'),
        }

        self.dir_intro_var = tk.StringVar(value='')
        self.dir_budget_var = tk.StringVar(value='')
        self.dir_music_var = tk.StringVar(value='none')

        self._build_layout()
        self._bind_shortcuts()
        self._bind_live_traces()
        self.refresh_assets()
        self._schedule_monitor_refresh()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind('<Destroy>', lambda e: self._cleanup_resources() if e.widget is self.root else None, add='+')
        self._poll_after = self.root.after(180, self.poll)

    def _configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('.', background=COLORS['panel'], foreground=COLORS['text'], fieldbackground=COLORS['card'], bordercolor=COLORS['border'], font=ui_font(10))
        style.configure('TCombobox', fieldbackground=COLORS['bg'], background=COLORS['card'], foreground=COLORS['text'], arrowcolor=COLORS['accent'], padding=4)
        style.map('TCombobox', fieldbackground=[('readonly', COLORS['bg'])], foreground=[('readonly', COLORS['text'])])
        style.configure('TEntry', fieldbackground=COLORS['bg'], foreground=COLORS['text'], insertcolor=COLORS['accent'], padding=4)
        style.configure('Treeview', background=COLORS['card'], foreground=COLORS['text'], fieldbackground=COLORS['card'], rowheight=25, borderwidth=0, font=ui_font(10))
        style.configure('Treeview.Heading', background=COLORS['panel'], foreground=COLORS['accent'], font=ui_font(9, 'bold'), relief='flat')
        style.map('Treeview', background=[('selected', '#1e3a5f')], foreground=[('selected', COLORS['text'])])
        style.configure('Horizontal.TProgressbar', troughcolor=COLORS['card'], background=COLORS['accent'], thickness=7, borderwidth=0)

    def _build_layout(self):
        self._build_header()

        # Pack footer & timeline dock with side='bottom' before main expands so they never collapse vertically
        self._build_footer()
        self._build_timeline_dock()

        # Main 3-column workstation pane (Media Bin | Program Monitor | Inspector)
        main = tk.Frame(self.root, bg=COLORS['bg'], padx=12)
        main.pack(fill='both', expand=True)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=0, minsize=288)
        main.grid_columnconfigure(1, weight=1, minsize=340)
        main.grid_columnconfigure(2, weight=0, minsize=384)

        self._build_left_bin(main)
        self._build_center_monitor(main)
        self._build_right_inspector(main)

    def _build_header(self):
        top = tk.Frame(self.root, bg=COLORS['panel'], height=50)
        top.pack(fill='x')
        tk.Frame(self.root, bg=COLORS['border'], height=1).pack(fill='x')

        hdr = tk.Frame(top, bg=COLORS['panel'], padx=14, pady=8)
        hdr.pack(fill='x')

        brand = tk.Frame(hdr, bg=COLORS['panel'])
        brand.pack(side='left')
        logo = tk.Canvas(brand, width=26, height=26, bg=COLORS['panel'], highlightthickness=0)
        logo.pack(side='left', padx=(0, 8))
        draw_logo_mark(logo, 26)
        tk.Label(brand, text='REELTERN STUDIO', bg=COLORS['panel'], fg=COLORS['text'], font=ui_font(12, 'bold')).pack(side='left')

        ws_chip = tk.Frame(brand, bg=COLORS['card'], padx=8, pady=3)
        ws_chip.pack(side='left', padx=(12, 0))
        tk.Label(ws_chip, text='WS:', bg=COLORS['card'], fg=COLORS['subtle'], font=mono_font(9)).pack(side='left')
        tk.Label(ws_chip, textvariable=self.ws_label, bg=COLORS['card'], fg=COLORS['accent'], font=mono_font(9, 'bold')).pack(side='left', padx=(4, 6))
        PillButton(ws_chip, text='Switch…', variant='ghost', padx=6, pady=1, font_size=9, command=lambda: self.guarded(self.switch_workspace)).pack(side='left')

        right_hdr = tk.Frame(hdr, bg=COLORS['panel'])
        right_hdr.pack(side='right')
        PillButton(right_hdr, text='Plans & Diff', padx=9, pady=4, font_size=9, command=self.history).pack(side='left', padx=3)
        PillButton(right_hdr, text='Undo ⌘Z', padx=9, pady=4, font_size=9, command=lambda: self.guarded(self.undo)).pack(side='left', padx=3)
        PillButton(right_hdr, text='Connect AI', variant='indigo', padx=10, pady=4, font_size=9, command=self.connect_ai_dialog).pack(side='left', padx=(3, 0))

        # Secondary command ribbon
        ribbon = tk.Frame(self.root, bg=COLORS['bg'], padx=12, pady=7)
        ribbon.pack(fill='x')
        actions = tk.Frame(ribbon, bg=COLORS['bg'])
        actions.pack(side='left')
        PillButton(actions, text='+ Import Video', variant='primary', padx=11, pady=4, font_size=10, command=self.import_file).pack(side='left', padx=(0, 5))
        PillButton(actions, text='Load Demo', variant='mint', padx=10, pady=4, font_size=10, command=lambda: self.guarded(self.load_demo)).pack(side='left', padx=3)
        PillButton(actions, text='+ Audio', padx=9, pady=4, font_size=9, command=self.import_audio_file).pack(side='left', padx=3)
        PillButton(actions, text='+ Title Card', padx=9, pady=4, font_size=9, command=self.title_card_dialog).pack(side='left', padx=3)
        PillButton(actions, text='AI Director', padx=9, pady=4, font_size=9, command=lambda: self._switch_tab('director')).pack(side='left', padx=3)
        PillButton(actions, text='Silence Trim', padx=9, pady=4, font_size=9, command=self.suggest).pack(side='left', padx=3)
        PillButton(actions, text='Transcript & AI', padx=9, pady=4, font_size=9, command=self.transcript_editor).pack(side='left', padx=3)

        fmt = tk.Frame(ribbon, bg=COLORS['bg'])
        fmt.pack(side='right')
        tk.Label(fmt, text='Format:', bg=COLORS['bg'], fg=COLORS['muted'], font=ui_font(9)).pack(side='left', padx=(0, 5))
        ttk.Combobox(fmt, textvariable=self.preset, values=list(PRESETS), state='readonly', width=10).pack(side='left', padx=(0, 5))
        ttk.Combobox(fmt, textvariable=self.fit, values=FIT_MODES, state='readonly', width=9).pack(side='left')

    def _build_left_bin(self, parent):
        outer = tk.Frame(parent, bg=COLORS['panel'], width=288, highlightthickness=1, highlightbackground=COLORS['border'])
        outer.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        outer.grid_propagate(False)
        outer.pack_propagate(False)

        left_scroll = ScrollablePane(outer, bg=COLORS['panel'])
        left_scroll.pack(fill='both', expand=True)
        left = left_scroll.inner

        top = tk.Frame(left, bg=COLORS['panel'], padx=10, pady=7)
        top.pack(fill='x')
        tk.Label(top, text='MEDIA BIN', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(9, 'bold')).pack(side='left')
        tk.Label(top, text='Double-click to add', bg=COLORS['panel'], fg=COLORS['subtle'], font=ui_font(8)).pack(side='right')

        self.assets = ttk.Treeview(left, columns=('name', 'dur', 'audio'), show='headings', height=5)
        self.assets.heading('name', text='Clip / Track')
        self.assets.heading('dur', text='Dur')
        self.assets.heading('audio', text='Kind')
        self.assets.column('name', width=144)
        self.assets.column('dur', width=50, anchor='e')
        self.assets.column('audio', width=68)
        self.assets.pack(fill='x', padx=8)
        self.assets.bind('<<TreeviewSelect>>', self.select_asset)
        self.assets.bind('<Double-1>', lambda _e: self.assemble())

        bin_btns = tk.Frame(left, bg=COLORS['panel'], padx=8, pady=6)
        bin_btns.pack(fill='x')
        PillButton(bin_btns, text='Assemble Timeline', variant='primary', padx=9, pady=4, font_size=9, command=self.assemble).pack(side='left', fill='x', expand=True, padx=(0, 4))
        PillButton(bin_btns, text='Inspect', padx=9, pady=4, font_size=9, command=lambda: self.guarded(self.load_selected_visuals)).pack(side='left')

        tk.Label(left, text='STORYBOARD & TELEMETRY', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(9, 'bold')).pack(anchor='w', padx=10, pady=(4, 2))
        tk.Label(left, textvariable=self.telemetry_text, bg=COLORS['panel'], fg=COLORS['muted'], font=mono_font(8), wraplength=266, justify='left').pack(anchor='w', padx=10, pady=(0, 4))
        self.storyboard_canvas = tk.Canvas(left, bg=COLORS['bg'], height=136, highlightthickness=1, highlightbackground=COLORS['border'], cursor='hand2')
        self.storyboard_canvas.pack(fill='x', padx=8)
        self.storyboard_canvas.bind('<Button-1>', self._on_storyboard_click)

        tk.Label(left, text='AUDIO WAVEFORM (CLICK TO SCRUB)', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(8, 'bold')).pack(anchor='w', padx=10, pady=(7, 3))
        self.waveform_canvas = tk.Canvas(left, bg=COLORS['bg'], height=74, highlightthickness=1, highlightbackground=COLORS['border'], cursor='sb_h_double_arrow')
        self.waveform_canvas.pack(fill='x', padx=8, pady=(0, 8))
        self.waveform_canvas.bind('<Button-1>', self._on_waveform_click)
        self.waveform_canvas.bind('<B1-Motion>', self._on_waveform_click)

    def _build_center_monitor(self, parent):
        center = tk.Frame(parent, bg=COLORS['panel'], highlightthickness=1, highlightbackground=COLORS['border'])
        center.grid(row=0, column=1, sticky='nsew', padx=(0, 8))

        hdr = tk.Frame(center, bg=COLORS['panel'], padx=10, pady=7)
        hdr.pack(fill='x')

        mode_bar = tk.Frame(hdr, bg=COLORS['panel'])
        mode_bar.pack(side='right')
        self.btn_mode_tl = PillButton(mode_bar, text='Live', variant='active_chip', padx=7, pady=2, font_size=8, command=lambda: self._set_monitor_mode('timeline'))
        self.btn_mode_tl.pack(side='left', padx=2)
        self.btn_mode_render = PillButton(mode_bar, text='Rendered', variant='default', padx=7, pady=2, font_size=8, state='disabled', command=lambda: self._set_monitor_mode('rendered'))
        self.btn_mode_render.pack(side='left', padx=2)
        self.btn_guides = PillButton(mode_bar, text='Guides', variant='active_chip', padx=7, pady=2, font_size=8, command=self._toggle_guides)
        self.btn_guides.pack(side='left', padx=(4, 0))

        tk.Label(hdr, textvariable=self.monitor_badge, bg=COLORS['panel'], fg=COLORS['text'], font=mono_font(8, 'bold'), anchor='w').pack(side='left', fill='x', expand=True, padx=(0, 6))

        # Pack transport bar with side='bottom' before expanding canvas so buttons never collapse vertically
        bar = tk.Frame(center, bg=COLORS['panel'], padx=8, pady=7)
        bar.pack(side='bottom', fill='x')

        self.monitor_canvas = tk.Canvas(center, bg='#060911', height=190, highlightthickness=1, highlightbackground=COLORS['border'])
        self.monitor_canvas.pack(fill='both', expand=True, padx=10)
        self.monitor_canvas.bind('<Configure>', lambda _e: self._schedule_monitor_refresh(15))
        self.monitor_canvas.bind('<Button-1>', self._on_monitor_click)

        tr_left = tk.Frame(bar, bg=COLORS['panel'])
        tr_left.pack(side='left')
        PillButton(tr_left, text='⏮', padx=5, pady=3, font_size=9, command=lambda: self._seek_playhead(0.0)).pack(side='left', padx=1)
        PillButton(tr_left, text='◀', padx=5, pady=3, font_size=9, command=lambda: self._nudge_playhead(-0.1)).pack(side='left', padx=1)
        self.btn_play = PillButton(tr_left, text='▶ Play', variant='primary', padx=9, pady=3, font_size=9, command=self.toggle_play)
        self.btn_play.pack(side='left', padx=2)
        PillButton(tr_left, text='▶', padx=5, pady=3, font_size=9, command=lambda: self._nudge_playhead(0.1)).pack(side='left', padx=1)
        PillButton(tr_left, text='⏭', padx=5, pady=3, font_size=9, command=self._seek_end).pack(side='left', padx=1)

        tk.Label(bar, textvariable=self.playhead_text, bg=COLORS['card'], fg=COLORS['amber'], font=mono_font(8, 'bold'), padx=5, pady=3).pack(side='left', padx=4)

        tr_right = tk.Frame(bar, bg=COLORS['panel'])
        tr_right.pack(side='right')
        PillButton(tr_right, text='[ In', padx=6, pady=3, font_size=9, command=lambda: self.guarded(self.mark_in_at_playhead)).pack(side='left', padx=1)
        PillButton(tr_right, text='Out ]', padx=6, pady=3, font_size=9, command=lambda: self.guarded(self.mark_out_at_playhead)).pack(side='left', padx=1)
        PillButton(tr_right, text='✂ Split', variant='default', padx=7, pady=3, font_size=9, command=lambda: self.guarded(self.split_at_playhead)).pack(side='left', padx=(3, 0))

    def _build_right_inspector(self, parent):
        right = tk.Frame(parent, bg=COLORS['panel'], width=384, highlightthickness=1, highlightbackground=COLORS['border'])
        right.grid(row=0, column=2, sticky='nsew')
        right.grid_propagate(False)
        right.pack_propagate(False)

        tab_bar = tk.Frame(right, bg=COLORS['bg'], padx=6, pady=6)
        tab_bar.pack(fill='x')
        self.tab_buttons = {}
        self.tab_frames = {}
        for col, (key, label) in enumerate((
            ('director', '✦ Director'),
            ('look', 'Look & FX'),
            ('trim', 'Trim & Clip'),
            ('mix', 'Mix & QA'),
        )):
            btn = PillButton(tab_bar, text=label, padx=4, pady=4, font_size=9, command=lambda k=key: self._switch_tab(k))
            btn.grid(row=0, column=col, sticky='ew', padx=2)
            tab_bar.grid_columnconfigure(col, weight=1, uniform='tabs')
            self.tab_buttons[key] = btn

        self.inspector_scroll = ScrollablePane(right, bg=COLORS['panel'])
        self.inspector_scroll.pack(fill='both', expand=True, padx=10, pady=(4, 8))
        self.inspector_body = self.inspector_scroll.inner

        self.tab_frames['director'] = self._build_director_tab(self.inspector_body)
        self.tab_frames['look'] = self._build_look_tab(self.inspector_body)
        self.tab_frames['trim'] = self._build_trim_tab(self.inspector_body)
        self.tab_frames['mix'] = self._build_mix_qa_tab(self.inspector_body)

        self._switch_tab('director')

    def _switch_tab(self, name):
        for k, frm in self.tab_frames.items():
            frm.pack_forget()
            self.tab_buttons[k].set_variant('active_chip' if k == name else 'default')
        self.tab_frames[name].pack(fill='both', expand=True)
        self.inspector_scroll.canvas.yview_moveto(0)
        self.inspector_scroll._sync_scrollregion()

    def _build_director_tab(self, parent):
        frm = tk.Frame(parent, bg=COLORS['panel'])
        tk.Label(frm, text='One-Click AI Director Profiles', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(10, 'bold')).pack(anchor='w', pady=(2, 5))

        self.director_cards = {}
        descriptions = {
            'viral_reel': '9:16 blur_fill · Vivid · Kinetic · Progress bar',
            'cinematic': '1080p cover · Crossfade · Warm/teal · -16 LUFS',
            'tutorial': '16:9 contain · Crisp studio · Boxed captions',
            'documentary': '1080p warm look · Pan/zoom · Clean narration',
            'noir_trailer': 'B&W Noir · Dissolve · Bold punchy titles',
        }
        for key in DIRECTOR_STYLES:
            card = tk.Frame(frm, bg=COLORS['border'], cursor='hand2')
            card.pack(fill='x', pady=2)
            inner = tk.Frame(card, bg=COLORS['card'], padx=8, pady=5, cursor='hand2')
            inner.pack(fill='x', padx=1, pady=1)
            row = tk.Frame(inner, bg=COLORS['card'])
            row.pack(fill='x')
            title = tk.Label(row, text=key, bg=COLORS['card'], fg=COLORS['text'], font=mono_font(9, 'bold'), cursor='hand2')
            title.pack(side='left')
            spec = DIRECTOR_STYLES[key]
            pill = tk.Label(row, text=f"{spec['preset']} · {spec['grade']}", bg=COLORS['elevated'], fg=COLORS['accent'], font=mono_font(8), padx=5, pady=1)
            pill.pack(side='right')
            sub = tk.Label(inner, text=descriptions.get(key, ''), bg=COLORS['card'], fg=COLORS['muted'], font=ui_font(8), anchor='w', wraplength=340, justify='left')
            sub.pack(fill='x', pady=(2, 0))
            self.director_cards[key] = (card, inner, title, sub, row)
            for w in (card, inner, row, title, pill, sub):
                w.bind('<Button-1>', lambda _e, k=key: self._select_director_style(k))

        self._select_director_style(self.selected_director.get())

        opts = tk.Frame(frm, bg=COLORS['panel'])
        opts.pack(fill='x', pady=(8, 4))
        for lbl, var in (('Intro Slate:', self.dir_intro_var), ('Max Secs:', self.dir_budget_var)):
            r = tk.Frame(opts, bg=COLORS['panel'])
            r.pack(fill='x', pady=3)
            tk.Label(r, text=lbl, bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=11, anchor='w').pack(side='left')
            ttk.Entry(r, textvariable=var).pack(side='left', fill='x', expand=True)

        mr = tk.Frame(opts, bg=COLORS['panel'])
        mr.pack(fill='x', pady=3)
        tk.Label(mr, text='Soundtrack:', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=11, anchor='w').pack(side='left')
        self.dir_music_combo = ttk.Combobox(mr, textvariable=self.dir_music_var, values=['none'], state='readonly')
        self.dir_music_combo.pack(side='left', fill='x', expand=True)

        ctas = tk.Frame(frm, bg=COLORS['panel'])
        ctas.pack(fill='x', pady=(8, 0))
        PillButton(ctas, text='✦ Compose Selected Footage', variant='indigo', padx=12, pady=6, font_size=10, command=lambda: self.guarded(self._compose_selected_director)).pack(fill='x', pady=(0, 5))
        PillButton(ctas, text='Auto-Cut Silences (Selected Clip)', padx=10, pady=4, font_size=9, command=self.suggest).pack(fill='x')
        return frm

    def _select_director_style(self, style_key):
        self.selected_director.set(style_key)
        for k, (outer, inner, title, sub, row) in self.director_cards.items():
            active = k == style_key
            outer.configure(bg=COLORS['accent'] if active else COLORS['border'])
            bg = COLORS['accent_soft'] if active else COLORS['card']
            inner.configure(bg=bg)
            row.configure(bg=bg)
            title.configure(bg=bg, fg=COLORS['accent'] if active else COLORS['text'])
            sub.configure(bg=bg)

    def _compose_selected_director(self):
        ids = list(self.selected_assets())
        video_ids = [i for i in ids if self.ws.asset(i).get('kind') != 'audio']
        if not video_ids:
            raise ValueError('Select at least one video clip in the Media Bin first')
        audio_assets = [a for a in self.ws.assets() if a.get('kind') == 'audio']
        music_id = None
        if self.dir_music_var.get() != 'none':
            short = self.dir_music_var.get().rsplit('(', 1)[-1].rstrip(')')
            music_id = next((a['id'] for a in audio_assets if a['id'].startswith(short)), None)
        budget = float(self.dir_budget_var.get()) if self.dir_budget_var.get().strip() else None
        style = self.selected_director.get()
        intro = self.dir_intro_var.get()

        def done(res):
            self.refresh_assets()
            self.show_plan(res['plan'])
            self.playhead_sec = 0.0
            self._schedule_monitor_refresh(10)

        self.task(lambda: compose_plan(self.ws, video_ids, style, self.preset.get(), budget, intro, music_asset_id=music_id), done)

    def _build_look_tab(self, parent):
        frm = tk.Frame(parent, bg=COLORS['panel'])
        tk.Label(frm, text='Color Grade Presets (Live Preview)', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(9, 'bold')).pack(anchor='w', pady=(2, 5))

        grid = tk.Frame(frm, bg=COLORS['panel'])
        grid.pack(fill='x')
        self.grade_cards = {}
        for idx, (key, (label, swatch, _)) in enumerate(GRADE_META.items()):
            r, c = divmod(idx, 2)
            card = tk.Frame(grid, bg=COLORS['border'], cursor='hand2')
            card.grid(row=r, column=c, sticky='ew', padx=2, pady=2)
            grid.grid_columnconfigure(c, weight=1, uniform='grades')
            inner = tk.Frame(card, bg=COLORS['card'], padx=6, pady=4, cursor='hand2')
            inner.pack(fill='x', padx=1, pady=1)
            bars = tk.Frame(inner, bg=COLORS['card'])
            bars.pack(side='left', padx=(0, 6))
            for col in swatch:
                tk.Frame(bars, bg=col, width=7, height=11).pack(side='left', padx=1)
            lbl = tk.Label(inner, text=label, bg=COLORS['card'], fg=COLORS['text'], font=ui_font(9), cursor='hand2')
            lbl.pack(side='left')
            self.grade_cards[key] = (card, inner, lbl, bars)
            for w in (card, inner, lbl, bars):
                w.bind('<Button-1>', lambda _e, gkey=key: self._pick_grade(gkey))

        sliders = tk.Frame(frm, bg=COLORS['panel'])
        sliders.pack(fill='x', pady=(8, 4))
        specs = (
            ('Brightness', self.fx_fields['brightness'], -0.5, 0.5, 0.0, 0.02, '{:+.2f}'),
            ('Contrast', self.fx_fields['contrast'], 0.5, 2.0, 1.0, 0.05, '{:.2f}×'),
            ('Saturation', self.fx_fields['saturation'], 0.0, 2.0, 1.0, 0.05, '{:.2f}×'),
            ('Volume', self.fx_fields['volume'], 0.0, 2.0, 1.0, 0.05, '{:.2f}×'),
            ('Fade In', self.fx_fields['fade_in'], 0.0, 3.0, 0.0, 0.1, '{:.1f}s'),
            ('Fade Out', self.fx_fields['fade_out'], 0.0, 3.0, 0.0, 0.1, '{:.1f}s'),
        )
        for idx, (lbl, var, mn, mx, df, step, fmt) in enumerate(specs):
            r, c = divmod(idx, 2)
            sl = ParamSlider(sliders, lbl, var, mn, mx, df, step=step, fmt=fmt, on_change=lambda: self._schedule_monitor_refresh(35))
            sl.grid(row=r, column=c, sticky='ew', padx=3, pady=3)
            sliders.grid_columnconfigure(c, weight=1)

        tr = tk.Frame(frm, bg=COLORS['panel'])
        tr.pack(fill='x', pady=(4, 2))
        tk.Label(tr, text='Motion', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9)).pack(side='left')
        ttk.Combobox(tr, textvariable=self.fx_fields['motion'], values=MOTIONS, state='readonly', width=10).pack(side='left', padx=(4, 8))
        tk.Label(tr, text='Flip', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9)).pack(side='left')
        ttk.Combobox(tr, textvariable=self.fx_fields['flip'], values=FLIPS, state='readonly', width=9).pack(side='left', padx=(4, 8))
        tk.Label(tr, text='Rot', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9)).pack(side='left')
        ttk.Combobox(tr, textvariable=self.fx_fields['rotate'], values=[str(x) for x in ROTATIONS], state='readonly', width=4).pack(side='left', padx=(4, 0))

        ov = tk.Frame(frm, bg=COLORS['panel'])
        ov.pack(fill='x', pady=(6, 6))
        tk.Label(ov, text='Lower-Third:', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9)).pack(side='left', padx=(0, 6))
        ttk.Entry(ov, textvariable=self.fx_fields['title_overlay']).pack(side='left', fill='x', expand=True)

        PillButton(frm, text='Apply Look & FX to Selected Clip', variant='primary', padx=10, pady=5, font_size=9, command=lambda: self.guarded(self.apply_clip_effects)).pack(fill='x', pady=(2, 0))
        self._highlight_grade(self.fx_fields['grade'].get())
        return frm

    def _pick_grade(self, key):
        self.fx_fields['grade'].set(key)
        self._highlight_grade(key)
        self._schedule_monitor_refresh(10)

    def _highlight_grade(self, key):
        for k, (outer, inner, lbl, bars) in self.grade_cards.items():
            active = k == key
            outer.configure(bg=COLORS['accent'] if active else COLORS['border'])
            bg = COLORS['accent_soft'] if active else COLORS['card']
            inner.configure(bg=bg)
            bars.configure(bg=bg)
            lbl.configure(bg=bg, fg=COLORS['accent'] if active else COLORS['text'])

    def _build_trim_tab(self, parent):
        frm = tk.Frame(parent, bg=COLORS['panel'])
        tk.Label(frm, text='Clip Range, Speed & Structure', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(9, 'bold')).pack(anchor='w', pady=(2, 6))

        rng = tk.Frame(frm, bg=COLORS['panel'])
        rng.pack(fill='x', pady=2)
        for lbl, key in (('In (s)', 'start'), ('Out (s)', 'end'), ('Speed', 'speed')):
            col = tk.Frame(rng, bg=COLORS['panel'])
            col.pack(side='left', fill='x', expand=True, padx=2)
            tk.Label(col, text=lbl, bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(8)).pack(anchor='w')
            ttk.Entry(col, textvariable=self.fields[key], width=8).pack(fill='x')

        mk = tk.Frame(frm, bg=COLORS['panel'])
        mk.pack(fill='x', pady=(6, 4))
        PillButton(mk, text='[ Mark In', padx=6, pady=4, font_size=9, command=lambda: self.guarded(self.mark_in_at_playhead)).grid(row=0, column=0, sticky='ew', padx=(0, 3))
        PillButton(mk, text='Mark Out ]', padx=6, pady=4, font_size=9, command=lambda: self.guarded(self.mark_out_at_playhead)).grid(row=0, column=1, sticky='ew', padx=(3, 0))
        mk.grid_columnconfigure(0, weight=1, uniform='mk')
        mk.grid_columnconfigure(1, weight=1, uniform='mk')

        tk.Label(frm, text='Speed Presets', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(8, 'bold')).pack(anchor='w', pady=(8, 3))
        spd = tk.Frame(frm, bg=COLORS['panel'])
        spd.pack(fill='x')
        for idx, val in enumerate(('0.5', '0.75', '1.0', '1.25', '1.5', '2.0')):
            PillButton(spd, text=f'{val}×', padx=3, pady=3, font_size=8, command=lambda v=val: self._set_speed(v)).grid(row=0, column=idx, sticky='ew', padx=1)
            spd.grid_columnconfigure(idx, weight=1, uniform='spd')

        PillButton(frm, text='Apply Trim & Transform Revision', variant='primary', padx=10, pady=5, font_size=9, command=lambda: self.guarded(self.revise)).pack(fill='x', pady=(10, 8))

        tk.Label(frm, text='Clip Operations', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(8, 'bold')).pack(anchor='w', pady=(4, 4))
        ops1 = tk.Frame(frm, bg=COLORS['panel'])
        ops1.pack(fill='x', pady=2)
        PillButton(ops1, text='✂ Split (S)', padx=8, pady=4, font_size=9, command=lambda: self.guarded(self.split_at_playhead)).pack(side='left', fill='x', expand=True, padx=(0, 3))
        PillButton(ops1, text='Duplicate', padx=8, pady=4, font_size=9, command=lambda: self.guarded(self.duplicate_clip)).pack(side='left', fill='x', expand=True, padx=3)

        ops2 = tk.Frame(frm, bg=COLORS['panel'])
        ops2.pack(fill='x', pady=2)
        PillButton(ops2, text='◀ Move Up', padx=8, pady=4, font_size=9, command=lambda: self.guarded(lambda: self.move(-1))).pack(side='left', fill='x', expand=True, padx=(0, 3))
        PillButton(ops2, text='Move Down ▶', padx=8, pady=4, font_size=9, command=lambda: self.guarded(lambda: self.move(1))).pack(side='left', fill='x', expand=True, padx=3)

        ops3 = tk.Frame(frm, bg=COLORS['panel'])
        ops3.pack(fill='x', pady=(4, 0))
        PillButton(ops3, text='Remove Clip', variant='danger', padx=8, pady=4, font_size=9, command=lambda: self.guarded(self.remove)).pack(side='left', fill='x', expand=True, padx=(0, 3))
        PillButton(ops3, text='Undo Revision', padx=8, pady=4, font_size=9, command=lambda: self.guarded(self.undo)).pack(side='left', fill='x', expand=True, padx=(3, 0))
        return frm

    def _build_mix_qa_tab(self, parent):
        frm = tk.Frame(parent, bg=COLORS['panel'])
        tk.Label(frm, text='Timeline Mix, Transitions & Captions', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(9, 'bold')).pack(anchor='w', pady=(2, 5))

        tr = tk.Frame(frm, bg=COLORS['panel'])
        tr.pack(fill='x', pady=2)
        tk.Label(tr, text='Transition:', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9)).pack(side='left')
        ttk.Combobox(tr, textvariable=self.tl_fields['transition'], values=list(TRANSITIONS), state='readonly', width=12).pack(side='left', padx=(6, 6))
        tk.Label(tr, text='Dur:', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9)).pack(side='left')
        ttk.Entry(tr, textvariable=self.tl_fields['transition_duration'], width=5).pack(side='left', padx=(4, 0))

        cp = tk.Frame(frm, bg=COLORS['panel'])
        cp.pack(fill='x', pady=(5, 4))
        tk.Label(cp, text='Captions:', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9)).pack(side='left')
        ttk.Combobox(cp, textvariable=self.tl_fields['caption_mode'], values=CAPTION_MODES, state='readonly', width=8).pack(side='left', padx=(6, 8))
        tk.Label(cp, text='Style:', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9)).pack(side='left')
        ttk.Combobox(cp, textvariable=self.tl_fields['caption_style'], values=CAPTION_STYLES, state='readonly', width=9).pack(side='left', padx=(4, 0))

        togs = tk.Frame(frm, bg=COLORS['panel'])
        togs.pack(fill='x', pady=(4, 6))
        ToggleSwitch(togs, 'Loudnorm (-16 LUFS)', self.tl_fields['normalize_audio']).pack(anchor='w', pady=2)
        ToggleSwitch(togs, 'Voice Cleanup EQ', self.tl_fields['voice_cleanup']).pack(anchor='w', pady=2)
        ToggleSwitch(togs, 'Progress Bar Overlay', self.tl_fields['progress_bar'], command=lambda: self._schedule_monitor_refresh(10)).pack(anchor='w', pady=2)

        PillButton(frm, text='Apply Timeline Style', variant='primary', padx=10, pady=5, font_size=9, command=lambda: self.guarded(self.apply_timeline_style)).pack(fill='x', pady=(2, 8))

        tk.Frame(frm, bg=COLORS['border'], height=1).pack(fill='x', pady=4)
        qa_hdr = tk.Frame(frm, bg=COLORS['panel'])
        qa_hdr.pack(fill='x', pady=(4, 4))
        PillButton(qa_hdr, text='Audit QA', variant='indigo', padx=8, pady=2, font_size=8, command=lambda: self.guarded(self.audit_render)).pack(side='right')
        tk.Label(qa_hdr, text='RENDER QA & RECEIPT', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(9, 'bold')).pack(side='left')

        tiles = tk.Frame(frm, bg=COLORS['panel'])
        tiles.pack(fill='x', pady=(2, 6))
        self.tile_lufs = MetricTile(tiles, 'LOUDNESS')
        self.tile_peak = MetricTile(tiles, 'TRUE PEAK')
        self.tile_luma = MetricTile(tiles, 'LUMA AVG')
        self.tile_black = MetricTile(tiles, 'BLACK FRAMES')
        self.tile_lufs.grid(row=0, column=0, sticky='ew', padx=2, pady=2)
        self.tile_peak.grid(row=0, column=1, sticky='ew', padx=2, pady=2)
        self.tile_luma.grid(row=1, column=0, sticky='ew', padx=2, pady=2)
        self.tile_black.grid(row=1, column=1, sticky='ew', padx=2, pady=2)
        tiles.grid_columnconfigure(0, weight=1, uniform='qakpi')
        tiles.grid_columnconfigure(1, weight=1, uniform='qakpi')

        self.qa_summary_var = tk.StringVar(value='Render a Preview or Export Final to populate LUFS & visual QA.')
        tk.Label(frm, textvariable=self.qa_summary_var, bg=COLORS['card'], fg=COLORS['muted'], font=ui_font(8), wraplength=340, justify='left', padx=8, pady=6).pack(fill='x')
        self.qa_sheet_canvas = tk.Canvas(frm, bg=COLORS['bg'], height=76, highlightthickness=1, highlightbackground=COLORS['border'])
        self.qa_sheet_canvas.pack(fill='x', pady=(6, 0))
        return frm

    def _build_timeline_dock(self):
        dock = tk.Frame(self.root, bg=COLORS['panel'], padx=12, pady=6, highlightthickness=1, highlightbackground=COLORS['border'])
        dock.pack(side='bottom', fill='x', padx=12, pady=(8, 0))

        hdr = tk.Frame(dock, bg=COLORS['panel'])
        hdr.pack(fill='x', pady=(0, 4))
        tk.Label(hdr, text='MULTI-TRACK TIMELINE', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(9, 'bold')).pack(side='left')
        tk.Label(hdr, textvariable=self.summary, bg=COLORS['panel'], fg=COLORS['text'], font=mono_font(9)).pack(side='right')

        self.timeline_canvas = tk.Canvas(dock, bg=COLORS['bg'], height=106, highlightthickness=1, highlightbackground=COLORS['border'], cursor='sb_h_double_arrow')
        self.timeline_canvas.pack(fill='x')
        self.timeline_canvas.bind('<Button-1>', self._on_timeline_canvas_click)
        self.timeline_canvas.bind('<B1-Motion>', self._on_timeline_canvas_click)
        self.timeline_canvas.bind('<Configure>', lambda _e: self._draw_timeline_canvas())

        # Compact live cut-sheet table synchronized with multi-track canvas & automated checks
        self.timeline = ttk.Treeview(
            dock,
            columns=('clip', 'in', 'out', 'speed', 'at', 'fx', 'reason'),
            show='headings',
            height=2,
        )
        for key, label, width in (
            ('clip', 'Clip', 150),
            ('in', 'In', 65),
            ('out', 'Out', 65),
            ('speed', 'Speed', 55),
            ('at', 'Start', 65),
            ('fx', 'Look / FX', 165),
            ('reason', 'Reason / Note', 280),
        ):
            self.timeline.heading(key, text=label)
            self.timeline.column(key, width=width)
        self.timeline.pack(fill='x', pady=(5, 0))
        self.timeline.bind('<<TreeviewSelect>>', self.select_clip)

    def _build_footer(self):
        footer = tk.Frame(self.root, bg=COLORS['bg'], padx=12, pady=7)
        footer.pack(side='bottom', fill='x')

        actions = tk.Frame(footer, bg=COLORS['bg'])
        actions.pack(side='right')
        PillButton(actions, text='Preview Draft', variant='primary', padx=10, pady=4, font_size=9, command=lambda: self.start_render(True)).pack(side='left', padx=2)
        PillButton(actions, text='Export Final 1080p', variant='mint', padx=10, pady=4, font_size=9, command=lambda: self.start_render(False)).pack(side='left', padx=2)
        PillButton(actions, text='Audit QA', variant='indigo', padx=8, pady=4, font_size=9, command=lambda: self.guarded(self.audit_render)).pack(side='left', padx=2)
        PillButton(actions, text='Receipt', padx=8, pady=4, font_size=9, command=self.show_receipt).pack(side='left', padx=2)
        self.open_button = PillButton(actions, text='Open Video', padx=8, pady=4, font_size=9, state='disabled', command=self.open_video)
        self.open_button.pack(side='left', padx=2)
        PillButton(actions, text='Folder', padx=7, pady=4, font_size=9, command=self.open_results).pack(side='left', padx=2)
        PillButton(actions, text='Cancel', variant='danger', padx=7, pady=4, font_size=9, command=self.cancel).pack(side='left', padx=(2, 0))

        self.progress = ttk.Progressbar(footer, mode='determinate', maximum=100, length=150)
        self.progress.pack(side='left', padx=(0, 8))
        tk.Label(footer, textvariable=self.status, bg=COLORS['bg'], fg=COLORS['muted'], font=ui_font(9), anchor='w').pack(side='left', fill='x', expand=True, padx=(0, 8))

    def _bind_shortcuts(self):
        self.root.bind('<Control-z>', lambda _e: self.guarded(self.undo))
        self.root.bind('<Command-z>', lambda _e: self.guarded(self.undo))
        self.root.bind('<space>', lambda e: None if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) else self.toggle_play())
        self.root.bind('<Left>', lambda e: None if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) else self._nudge_playhead(-0.1))
        self.root.bind('<Right>', lambda e: None if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) else self._nudge_playhead(0.1))
        self.root.bind('<s>', lambda e: None if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) else self.guarded(self.split_at_playhead))
        self.root.bind('<i>', lambda e: None if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) else self.guarded(self.mark_in_at_playhead))
        self.root.bind('<o>', lambda e: None if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) else self.guarded(self.mark_out_at_playhead))

    def _bind_live_traces(self):
        self.preset.trace_add('write', lambda *_: self._schedule_monitor_refresh(15))
        self.fit.trace_add('write', lambda *_: self._schedule_monitor_refresh(15))
        for k in ('grade', 'motion', 'flip', 'rotate', 'title_overlay'):
            self.fx_fields[k].trace_add('write', lambda *_e, key=k: self._on_fx_var_changed(key))

    def _on_fx_var_changed(self, key):
        if key == 'grade':
            self._highlight_grade(self.fx_fields['grade'].get())
        self._schedule_monitor_refresh(20)

    def _set_monitor_mode(self, mode):
        if mode == 'rendered' and not (self.rendered_path and Path(self.rendered_path).is_file()):
            return
        self.monitor_mode.set(mode)
        self.btn_mode_tl.set_variant('active_chip' if mode == 'timeline' else 'default')
        self.btn_mode_render.set_variant('active_chip' if mode == 'rendered' else 'default')
        self._schedule_monitor_refresh(10)

    def _toggle_guides(self):
        nxt = not bool(self.show_guides.get())
        self.show_guides.set(nxt)
        self.btn_guides.set_variant('active_chip' if nxt else 'default')
        self._schedule_monitor_refresh(10)

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
        audio_choices = ['none']
        for a in self.ws.assets():
            is_audio = a.get('kind') == 'audio'
            kind = 'Audio' if is_audio else ('Video+Aud' if a['audio'] else 'Silent')
            self.assets.insert('', 'end', iid=a['id'], values=(a['name'], f'{a["duration"]:.2f}s', kind))
            if is_audio:
                audio_choices.append(f'{a["name"]} ({a["id"][:8]})')
        if hasattr(self, 'dir_music_combo'):
            self.dir_music_combo.configure(values=audio_choices)
            if self.dir_music_var.get() not in audio_choices:
                self.dir_music_var.set('none')

    def import_file(self):
        path = filedialog.askopenfilename(title='Choose video file', filetypes=[('Video files', '*.mp4 *.mov *.mkv *.webm *.avi *.m4v'), ('All files', '*.*')])
        if not path:
            return

        def _after(asset):
            self.refresh_assets()
            self.assets.selection_set(asset['id'])
            self.status.set(f'Imported {asset["name"]} ({asset["duration"]:.2f}s)')
            self.task(lambda: self.ws.inspect_visuals(asset['id'], thumbs=6, samples=60), self.display_visuals)
            if not self.plan:
                self._schedule_monitor_refresh(15)

        self.guarded(lambda: self.task(lambda: self.ws.import_media(path), _after))

    def import_audio_file(self):
        path = filedialog.askopenfilename(title='Choose soundtrack / audio file', filetypes=[('Audio files', '*.wav *.mp3 *.m4a *.aac *.flac *.ogg'), ('All files', '*.*')])
        if not path:
            return

        def _after(asset):
            self.refresh_assets()
            self.assets.selection_set(asset['id'])
            self.dir_music_var.set(f'{asset["name"]} ({asset["id"][:8]})')
            self.status.set(f'Imported audio track {asset["name"]} ({asset["duration"]:.2f}s)')

        self.guarded(lambda: self.task(lambda: self.ws.import_audio(path), _after))

    def select_asset(self, _=None):
        ids = self.assets.selection()
        if ids:
            asset_id = ids[0]
            cache_file = self.ws.path('analysis', self.ws.visuals_cache_id(asset_id, 6, 60))
            if cache_file.exists():
                self.guarded(lambda: self.display_visuals(self.ws.inspect_visuals(asset_id, thumbs=6, samples=60)))
            self._schedule_monitor_refresh(15)

    def load_selected_visuals(self):
        ids = self.selected_assets()
        self.task(lambda: self.ws.inspect_visuals(ids[0], thumbs=6, samples=60), self.display_visuals)

    def display_visuals(self, visuals):
        self.current_visuals = visuals
        self._draw_storyboard(visuals)
        self._draw_waveform(visuals)
        tel = visuals.get('telemetry', {})
        wf = visuals.get('waveform', {})
        if tel:
            self.telemetry_text.set(
                f'Luma {tel.get("luma_avg", 0):.2f} · {tel.get("motion_level", "static")} · Cuts:{len(tel.get("scene_cuts", []))} · Peak {wf.get("peak_db", 0):.1f}dB'
            )
        else:
            self.telemetry_text.set(f'Audio · {visuals.get("duration", 0):.2f}s · Peak {wf.get("peak_db", 0):.1f}dB')

    def _draw_storyboard(self, visuals):
        c = self.storyboard_canvas
        c.delete('all')
        self.thumb_images.clear()
        self.storyboard_hitboxes.clear()
        thumbs = visuals.get('storyboard', [])
        if not thumbs:
            c.create_text(140, 68, text='Audio asset (scrub waveform below)', fill=COLORS['muted'], font=ui_font(9))
            return
        cols = 3
        cell_w, cell_h = 86, 48
        for idx, item in enumerate(thumbs[:6]):
            col, row = idx % cols, idx // cols
            x0, y0 = 8 + col * (cell_w + 6), 6 + row * (cell_h + 17)
            try:
                img = tk.PhotoImage(file=item['path']).subsample(2, 2)
                self.thumb_images.append(img)
                c.create_rectangle(x0 - 1, y0 - 1, x0 + cell_w + 1, y0 + cell_h + 1, outline=COLORS['border'], fill=COLORS['card'])
                c.create_image(x0 + cell_w // 2, y0 + cell_h // 2, image=img)
            except tk.TclError:
                c.create_rectangle(x0, y0, x0 + cell_w, y0 + cell_h, outline=COLORS['border'], fill=COLORS['card'])
            c.create_text(x0 + cell_w // 2, y0 + cell_h + 8, text=f'{item["time"]:.1f}s', fill=COLORS['muted'], font=mono_font(8))
            self.storyboard_hitboxes.append((x0, y0, x0 + cell_w, y0 + cell_h, float(item['time'])))

    def _on_storyboard_click(self, event):
        for x0, y0, x1, y1, ts in self.storyboard_hitboxes:
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self._seek_playhead(ts)
                return

    def _draw_waveform(self, visuals):
        c = self.waveform_canvas
        c.delete('all')
        w = max(260, int(c.winfo_width() or 276))
        h = int(c.winfo_height() or 76)
        mid = h // 2
        wf = visuals.get('waveform', {})
        peaks = wf.get('samples', [])
        if not wf.get('has_audio') or not peaks:
            c.create_line(10, mid, w - 10, mid, fill=COLORS['border'])
            c.create_text(w // 2, mid - 12, text='Silent track (no audio stream)', fill=COLORS['muted'], font=ui_font(9))
            return
        step = max(2, (w - 16) / len(peaks))
        for i, amp in enumerate(peaks):
            x = 8 + i * step
            bar = max(2, amp * (h * 0.40))
            color = COLORS['amber'] if amp > 0.78 else COLORS['accent'] if amp > 0.15 else COLORS['border']
            c.create_line(x, mid - bar, x, mid + bar, fill=color, width=max(1.5, step * 0.65))
        dur = max(0.05, float(visuals.get('duration', 1.0)))
        px = 8 + max(0.0, min(1.0, self.playhead_sec / dur)) * (w - 16)
        c.create_line(px, 4, px, h - 4, fill=COLORS['amber'], width=2)
        c.create_text(w - 8, 9, anchor='e', text=f'Peak {wf.get("peak_db", 0):.1f} dB', fill=COLORS['muted'], font=mono_font(8))

    def _on_waveform_click(self, event):
        if not self.current_visuals:
            return
        w = max(260, int(self.waveform_canvas.winfo_width() or 276))
        ratio = max(0.0, min(1.0, (event.x - 8) / max(1, w - 16)))
        self._seek_playhead(round(ratio * self.current_visuals['duration'], 2))

    # ---- Monitor Compositor & Transport ----

    def _active_total_duration(self):
        if self.plan and self.plan.get('clips'):
            return max(0.05, float(self.plan['duration']))
        if self.current_visuals:
            return max(0.05, float(self.current_visuals.get('duration', 1.0)))
        return 0.0

    def _seek_playhead(self, seconds):
        total = self._active_total_duration()
        self.playhead_sec = round(max(0.0, min(total, float(seconds))), 2)
        self.playhead_text.set(f'{_fmt_tc(self.playhead_sec)} / {_fmt_tc(total)}')
        self._draw_timeline_canvas()
        if self.current_visuals:
            self._draw_waveform(self.current_visuals)
        self._schedule_monitor_refresh(10)

    def _seek_end(self):
        self._seek_playhead(self._active_total_duration())

    def _nudge_playhead(self, delta):
        self._seek_playhead(self.playhead_sec + delta)

    def toggle_play(self):
        if self._active_total_duration() <= 0.0:
            return
        self.playing = not self.playing
        self.btn_play.configure(text='⏸ Pause' if self.playing else '▶ Play')
        if self.playing:
            if self.playhead_sec >= self._active_total_duration() - 0.04:
                self.playhead_sec = 0.0
            self._play_step()
        elif self._play_after is not None:
            self.root.after_cancel(self._play_after)
            self._play_after = None

    def _play_step(self):
        if self._closing or not self.playing:
            return
        total = self._active_total_duration()
        nxt = self.playhead_sec + 0.05
        if nxt > total:
            nxt = 0.0
        self.playhead_sec = round(nxt, 2)
        self.playhead_text.set(f'{_fmt_tc(self.playhead_sec)} / {_fmt_tc(total)}')
        self._draw_timeline_canvas()
        self._refresh_monitor_now()
        self._play_after = self.root.after(50, self._play_step)

    def _schedule_monitor_refresh(self, delay_ms=25):
        if self._closing:
            return
        if self._monitor_after is not None:
            try:
                self.root.after_cancel(self._monitor_after)
            except tk.TclError:
                pass
        self._monitor_after = self.root.after(delay_ms, self._refresh_monitor_now)

    def _live_preview_clip_override(self, clip_index, clip):
        merged = dict(clip)
        sel = self.timeline.selection()
        if sel and int(sel[0]) == clip_index:
            merged['grade'] = self.fx_fields['grade'].get()
            merged['motion'] = self.fx_fields['motion'].get()
            merged['flip'] = self.fx_fields['flip'].get()
            try:
                merged['rotate'] = int(self.fx_fields['rotate'].get() or 0)
            except ValueError:
                pass
            for key, default in (('fade_in', 0.0), ('fade_out', 0.0), ('brightness', 0.0), ('contrast', 1.0), ('saturation', 1.0)):
                try:
                    merged[key] = float(self.fx_fields[key].get())
                except ValueError:
                    merged[key] = default
            merged['title_overlay'] = self.fx_fields['title_overlay'].get()
        return merged

    def _refresh_monitor_now(self):
        self._monitor_after = None
        if self._closing:
            return
        c = self.monitor_canvas
        c.delete('all')
        self.welcome_hitboxes.clear()
        w = max(360, int(c.winfo_width() or 540))
        h = max(220, int(c.winfo_height() or 320))

        preset = self.preset.get()
        fit = self.fit.get()
        dims = PRESETS.get(preset, (1280, 720))

        if self.monitor_mode.get() == 'rendered' and self.rendered_path and Path(self.rendered_path).is_file():
            rendered = self.preview_engine.render_clip_frame(
                self.rendered_path,
                self.playhead_sec,
                w - 28,
                h - 28,
                preset=preset,
                fit='contain',
                clip=None,
            )
            self.monitor_badge.set(f'RENDERED ✓ · {preset} ({dims[0]}×{dims[1]})')
            if rendered:
                self._draw_monitor_frame(c, w, h, *rendered, overlay_text='', progress_ratio=None)
                return

        if self.plan and self.plan.get('clips'):
            resolved = clip_at_time(self.plan, self.playhead_sec)
            if resolved:
                idx, clip, src_sec, prog, local_tl, clip_dur = resolved
                eff_clip = self._live_preview_clip_override(idx, clip)
                media_path = self.ws.path('assets', clip['asset_id'], '.media')
                rendered = self.preview_engine.render_clip_frame(
                    media_path,
                    src_sec,
                    w - 28,
                    h - 28,
                    preset=preset,
                    fit=fit,
                    clip=eff_clip,
                    progress=prog,
                    local_time=local_tl,
                    clip_duration=clip_dur,
                )
                grade_tag = eff_clip.get('grade', 'none')
                self.monitor_badge.set(f'LIVE #{idx + 1} · {preset} · {fit} · {grade_tag}')
                if rendered:
                    p_ratio = (self.playhead_sec / max(0.05, float(self.plan['duration']))) if self.tl_fields['progress_bar'].get() else None
                    self._draw_monitor_frame(
                        c,
                        w,
                        h,
                        *rendered,
                        overlay_text=eff_clip.get('title_overlay', ''),
                        progress_ratio=p_ratio,
                        caption_mode=self.tl_fields['caption_mode'].get(),
                        caption_style=self.tl_fields['caption_style'].get(),
                    )
                    return

        ids = self.assets.selection()
        if ids:
            asset = self.ws.asset(ids[0])
            if asset.get('kind') != 'audio':
                media_path = self.ws.path('assets', asset['id'], '.media')
                rendered = self.preview_engine.render_clip_frame(
                    media_path,
                    min(self.playhead_sec, max(0.0, asset['duration'] - 0.05)),
                    w - 28,
                    h - 28,
                    preset=preset,
                    fit=fit,
                )
                self.monitor_badge.set(f'SOURCE · {asset["name"]} · {preset}')
                if rendered:
                    self._draw_monitor_frame(c, w, h, *rendered)
                    return

        self.monitor_badge.set(f'STUDIO READY · {preset} ({dims[0]}×{dims[1]})')
        self._draw_welcome_stage(c, w, h)

    def _draw_monitor_frame(self, canvas, cw, ch, fw, fh, ppm_bytes, overlay_text='', progress_ratio=None, caption_mode='none', caption_style='clean'):
        self.monitor_photo = tk.PhotoImage(data=ppm_bytes, format='PPM')
        cx, cy = cw // 2, ch // 2
        x0, y0 = cx - fw // 2, cy - fh // 2
        x1, y1 = x0 + fw, y0 + fh
        canvas.create_rectangle(x0 - 2, y0 - 2, x1 + 2, y1 + 2, outline=COLORS['border_bright'], fill='#04060c', width=1)
        canvas.create_image(cx, cy, image=self.monitor_photo)

        if self.show_guides.get():
            for frac in (1 / 3, 2 / 3):
                gx = x0 + fw * frac
                gy = y0 + fh * frac
                canvas.create_line(gx, y0 + 6, gx, y1 - 6, fill='#475569', dash=(2, 4))
                canvas.create_line(x0 + 6, gy, x1 - 6, gy, fill='#475569', dash=(2, 4))
            canvas.create_rectangle(x0 + 10, y0 + 10, x1 - 10, y1 - 10, outline='#334155', dash=(3, 5))

        if overlay_text:
            bw = min(fw - 28, max(160, len(overlay_text) * 8 + 24))
            bx0 = x0 + 14
            by1 = y1 - 30
            by0 = by1 - 24
            canvas.create_rectangle(bx0, by0, bx0 + bw, by1, fill='#090d16', outline=COLORS['accent'], width=1)
            canvas.create_rectangle(bx0, by0, bx0 + 4, by1, fill=COLORS['accent'], outline='')
            canvas.create_text(bx0 + 12, (by0 + by1) // 2, anchor='w', text=overlay_text[:44], fill=COLORS['text'], font=ui_font(10, 'bold'))

        if caption_mode in ('burn', 'both') and self.plan and self.plan.get('transcript_ids'):
            cap_text = f'CAPTIONS ({caption_style.upper()})'
            canvas.create_rectangle(cx - 86, y1 - 26, cx + 86, y1 - 8, fill='#0b1120', outline=COLORS['indigo'])
            canvas.create_text(cx, y1 - 17, text=cap_text, fill=COLORS['indigo'], font=mono_font(8, 'bold'))

        if progress_ratio is not None:
            canvas.create_rectangle(x0, y1 - 4, x1, y1, fill='#1e293b', outline='')
            canvas.create_rectangle(x0, y1 - 4, x0 + max(4, int(fw * progress_ratio)), y1, fill=COLORS['accent'], outline='')

    def _draw_welcome_stage(self, canvas, w, h):
        cx, cy = w // 2, h // 2
        canvas.create_text(cx, cy - 82, text='REELTERN STUDIO', fill=COLORS['accent'], font=mono_font(10, 'bold'))
        canvas.create_text(cx, cy - 56, text='Local Reversible Video NLE & AI Director', fill=COLORS['text'], font=ui_font(15, 'bold'))
        canvas.create_text(
            cx,
            cy - 32,
            text='Non-destructive SHA-256 editing · Real-time blur_fill, grades & motion preview · 31 MCP tools',
            fill=COLORS['muted'],
            font=ui_font(9),
        )
        cards = [
            ('Import Video', 'Add .mp4 / .mov clips', COLORS['accent'], self.import_file),
            ('Load Synthetic Demo', 'Instant 4s timeline', COLORS['mint'], lambda: self.guarded(self.load_demo)),
            ('Connect AI (MCP)', 'Antigravity / Claude', COLORS['indigo'], self.connect_ai_dialog),
        ]
        cw = min(168, max(125, (w - 80) // 3))
        ch = 72
        gap = 12
        total_w = len(cards) * cw + (len(cards) - 1) * gap
        start_x = cx - total_w // 2
        y0 = cy + 2
        for i, (title, sub, accent, action) in enumerate(cards):
            x0 = start_x + i * (cw + gap)
            x1, y1 = x0 + cw, y0 + ch
            canvas.create_rectangle(x0, y0, x1, y1, fill=COLORS['card'], outline=COLORS['border_bright'], width=1)
            canvas.create_rectangle(x0, y0, x1, y0 + 3, fill=accent, outline='')
            canvas.create_text((x0 + x1) // 2, y0 + 27, text=title, fill=COLORS['text'], font=ui_font(10, 'bold'))
            canvas.create_text((x0 + x1) // 2, y0 + 48, text=sub, fill=COLORS['muted'], font=ui_font(8))
            self.welcome_hitboxes.append((x0, y0, x1, y1, action))

    def _on_monitor_click(self, event):
        for x0, y0, x1, y1, action in self.welcome_hitboxes:
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                action()
                return
        if self._active_total_duration() > 0:
            self.toggle_play()

    # ---- Dialogs & Editing Operations ----

    def title_card_dialog(self):
        win = tk.Toplevel(self.root)
        win.title('Create Title / Chapter Card')
        win.geometry('480x360')
        win.configure(bg=COLORS['panel'])
        frm = tk.Frame(win, bg=COLORS['panel'], padx=18, pady=16)
        frm.pack(fill='both', expand=True)
        tk.Label(frm, text='Generate Slate / Title Card Asset', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(13, 'bold')).pack(anchor='w', pady=(0, 10))
        title_var = tk.StringVar(value='Chapter One')
        sub_var = tk.StringVar(value='Created locally in Reeltern Studio')
        dur_var = tk.StringVar(value='3.0')
        bg_var = tk.StringVar(value='#0f172a')
        acc_var = tk.StringVar(value='#38bdf8')
        for lbl, var in (('Heading', title_var), ('Subtitle', sub_var), ('Duration (s)', dur_var), ('Backdrop Hex', bg_var), ('Accent Hex', acc_var)):
            row = tk.Frame(frm, bg=COLORS['panel'])
            row.pack(fill='x', pady=4)
            tk.Label(row, text=lbl, bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=14, anchor='w').pack(side='left')
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

        PillButton(frm, text='Create Title Card Asset', variant='primary', padx=12, pady=6, command=lambda: self.guarded(create)).pack(anchor='e', pady=(14, 0))

    def director_dialog(self):
        ids = list(self.selected_assets())
        video_ids = [i for i in ids if self.ws.asset(i).get('kind') != 'audio']
        if not video_ids:
            raise ValueError('Select at least one video asset first')
        audio_assets = [a for a in self.ws.assets() if a.get('kind') == 'audio']
        win = tk.Toplevel(self.root)
        win.title('AI Director — Auto-Compose Production Edit')
        win.geometry('500x360')
        win.configure(bg=COLORS['panel'])
        frm = tk.Frame(win, bg=COLORS['panel'], padx=18, pady=16)
        frm.pack(fill='both', expand=True)
        tk.Label(frm, text='One-Click AI Director Composition', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(13, 'bold')).pack(anchor='w', pady=(0, 10))
        style_var = tk.StringVar(value=self.selected_director.get())
        preset_var = tk.StringVar(value=self.preset.get())
        intro_var = tk.StringVar(value=self.dir_intro_var.get())
        budget_var = tk.StringVar(value=self.dir_budget_var.get())
        music_var = tk.StringVar(value=self.dir_music_var.get())

        row_s = tk.Frame(frm, bg=COLORS['panel']); row_s.pack(fill='x', pady=4)
        tk.Label(row_s, text='Director Style', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=15, anchor='w').pack(side='left')
        ttk.Combobox(row_s, textvariable=style_var, values=list(DIRECTOR_STYLES), state='readonly').pack(side='left', fill='x', expand=True)

        row_p = tk.Frame(frm, bg=COLORS['panel']); row_p.pack(fill='x', pady=4)
        tk.Label(row_p, text='Preset Override', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=15, anchor='w').pack(side='left')
        ttk.Combobox(row_p, textvariable=preset_var, values=list(PRESETS), state='readonly').pack(side='left', fill='x', expand=True)

        for lbl, var in (('Intro Slate (opt)', intro_var), ('Max Sec (opt)', budget_var)):
            row = tk.Frame(frm, bg=COLORS['panel']); row.pack(fill='x', pady=4)
            tk.Label(row, text=lbl, bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=15, anchor='w').pack(side='left')
            ttk.Entry(row, textvariable=var).pack(side='left', fill='x', expand=True)

        row_m = tk.Frame(frm, bg=COLORS['panel']); row_m.pack(fill='x', pady=4)
        tk.Label(row_m, text='Background Music', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=15, anchor='w').pack(side='left')
        music_choices = ['none'] + [f'{a["name"]} ({a["id"][:8]})' for a in audio_assets]
        ttk.Combobox(row_m, textvariable=music_var, values=music_choices, state='readonly').pack(side='left', fill='x', expand=True)

        def run_director():
            budget = float(budget_var.get()) if budget_var.get().strip() else None
            music_id = None
            if music_var.get() != 'none':
                short = music_var.get().rsplit('(', 1)[-1].rstrip(')')
                music_id = next((a['id'] for a in audio_assets if a['id'].startswith(short)), None)

            def done(res):
                self.refresh_assets()
                self.show_plan(res['plan'])
                if win.winfo_exists():
                    win.destroy()

            self.task(lambda: compose_plan(self.ws, video_ids, style_var.get(), preset_var.get(), budget, intro_var.get(), music_asset_id=music_id), done)

        PillButton(frm, text='Compose Polished Edit', variant='indigo', padx=12, pady=6, command=lambda: self.guarded(run_director)).pack(anchor='e', pady=(14, 0))

    def selected_assets(self):
        ids = self.assets.selection()
        if not ids:
            raise ValueError('Select footage first')
        return ids

    def assemble(self):
        def action():
            ids = self.selected_assets()
            plan = self.ws.create_plan([{'asset_id': i} for i in ids], self.preset.get(), self.fit.get())
            self.playhead_sec = 0.0
            self.show_plan(plan)

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
        self.tl_fields['voice_cleanup'].set(bool(plan.get('voice_cleanup', False)))
        self.tl_fields['progress_bar'].set(bool(plan.get('progress_bar', False)))
        self.tl_fields['caption_mode'].set(plan.get('caption_mode', 'soft'))
        self.tl_fields['caption_style'].set(plan.get('caption_style', 'clean'))

        self.timeline.delete(*self.timeline.get_children())
        for i, c in enumerate(plan['clips']):
            asset = self.ws.asset(c['asset_id'])
            tags = []
            if c.get('grade', 'none') != 'none':
                tags.append(c['grade'])
            if c.get('motion', 'none') != 'none':
                tags.append(c['motion'])
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
                    f'#{i + 1} {asset["name"]}',
                    f'{c["start"]:.3f}',
                    f'{c["end"]:.3f}',
                    f'{c["speed"]:.2g}×',
                    f'{c["timeline_start"]:.2f}s',
                    fx_label,
                    c['reason'],
                ),
            )
            self._ensure_clip_thumb(c['asset_id'], (float(c['start']) + float(c['end'])) * 0.5)

        if plan['clips'] and not self.timeline.selection():
            self.timeline.selection_set('0')
            self.select_clip()

        trans = plan.get('transition', 'cut')
        cap = plan.get('caption_mode', 'soft')
        music_tag = ' · ♪ music' if plan.get('music_asset_id') else ''
        self.summary.set(
            f'{len(plan["clips"])} clips · {plan["duration"]:.2f}s · {plan["preset"]} ({plan["fit"]}) · {trans} · cap:{cap}{music_tag} · rev {plan["id"][:8]}'
        )
        self.status.set(plan['notes'])
        self.playhead_sec = min(self.playhead_sec, float(plan['duration']))
        self.playhead_text.set(f'{_fmt_tc(self.playhead_sec)} / {_fmt_tc(plan["duration"])}')
        self._draw_timeline_canvas()
        self._schedule_monitor_refresh(10)

    def _ensure_clip_thumb(self, asset_id, ts):
        key = (asset_id, round(ts, 1))
        if key in self.tl_thumb_cache:
            return
        media_path = self.ws.path('assets', asset_id, '.media')
        res = self.preview_engine.render_thumbnail(media_path, ts, 64, 36)
        if res:
            _, _, ppm = res
            try:
                self.tl_thumb_cache[key] = tk.PhotoImage(data=ppm, format='PPM')
            except tk.TclError:
                pass

    def _draw_timeline_canvas(self):
        c = self.timeline_canvas
        c.delete('all')
        self.clip_hitboxes.clear()
        self.tl_thumb_images.clear()
        w = max(580, int(c.winfo_width() or 860))
        h = int(c.winfo_height() or 116)

        lane_left = 44
        pad_r = 12
        track_w = max(140, w - lane_left - pad_r)

        # Left track labels
        c.create_rectangle(0, 0, lane_left, h, fill=COLORS['panel'], outline='')
        c.create_line(lane_left, 0, lane_left, h, fill=COLORS['border'])
        for label, y, col in (('V1', 42, COLORS['accent']), ('T1', 78, COLORS['indigo']), ('A1', 100, COLORS['mint'])):
            c.create_text(lane_left // 2, y, text=label, fill=col, font=mono_font(8, 'bold'))

        if not self.plan or not self.plan.get('clips'):
            c.create_text((lane_left + w) // 2, h // 2, text='Assemble footage or click Load Demo to edit multi-track timeline', fill=COLORS['muted'], font=ui_font(9))
            return

        total = max(0.05, float(self.plan['duration']))
        # Ruler
        c.create_rectangle(lane_left, 0, w, 20, fill=COLORS['panel'], outline='')
        c.create_line(lane_left, 20, w, 20, fill=COLORS['border'])
        ticks = min(12, max(2, int(total)))
        for idx in range(ticks + 1):
            t = total * idx / ticks
            tx = lane_left + (t / total) * track_w
            c.create_line(tx, 14, tx, 20, fill=COLORS['subtle'])
            c.create_text(tx, 8, text=f'{t:.1f}s', fill=COLORS['muted'], font=mono_font(7))

        selected_idx = int(self.timeline.selection()[0]) if self.timeline.selection() else -1
        transition = self.plan.get('transition', 'cut')
        for i, clip in enumerate(self.plan['clips']):
            dur = clip['frames'] / 30.0
            x0 = lane_left + (clip['timeline_start'] / total) * track_w
            x1 = max(x0 + 22, lane_left + ((clip['timeline_start'] + dur) / total) * track_w - 2)
            fill = CLIP_PALETTE[i % len(CLIP_PALETTE)]
            outline = COLORS['amber'] if i == selected_idx else COLORS['accent'] if clip.get('grade', 'none') != 'none' or clip.get('motion', 'none') != 'none' else COLORS['border_bright']
            width = 2 if i == selected_idx else 1

            c.create_rectangle(x0, 24, x1, 64, fill=fill, outline=outline, width=width)
            thumb = self.tl_thumb_cache.get((clip['asset_id'], round((float(clip['start']) + float(clip['end'])) * 0.5, 1)))
            text_x = x0 + 6
            if thumb and (x1 - x0) >= 84:
                self.tl_thumb_images.append(thumb)
                c.create_image(x0 + 34, 44, image=thumb)
                text_x = x0 + 70

            asset = self.ws.asset(clip['asset_id'])
            c.create_text(text_x, 36, anchor='w', text=f'#{i + 1} {asset["name"][:14]}', fill=COLORS['text'], font=ui_font(8, 'bold'))
            sub = f'{dur:.2f}s · {clip["speed"]:.2g}×' + (f' · {clip["grade"]}' if clip.get('grade', 'none') != 'none' else '')
            c.create_text(text_x, 51, anchor='w', text=sub, fill=COLORS['muted'], font=mono_font(7))
            self.clip_hitboxes.append((x0, x1, i))

            if i > 0 and transition != 'cut':
                c.create_polygon(x0 - 5, 44, x0, 39, x0 + 5, 44, x0, 49, fill=COLORS['amber'], outline='#04101d')

            # T1 overlay / captions stripe
            if clip.get('title_overlay') or self.plan.get('caption_mode', 'none') != 'none':
                t_label = clip.get('title_overlay') or f'cap:{self.plan.get("caption_style", "clean")}'
                c.create_rectangle(x0, 69, x1, 86, fill='#1f1d45', outline='#4f46e5', width=1)
                if (x1 - x0) > 48:
                    c.create_text(x0 + 5, 77, anchor='w', text=t_label[:16], fill='#c7d2fe', font=mono_font(7))

        # A1 soundtrack / ducked lane
        if self.plan.get('music_asset_id'):
            c.create_rectangle(lane_left, 91, lane_left + track_w, 108, fill=COLORS['mint_soft'], outline=COLORS['mint'], width=1)
            c.create_text(lane_left + 8, 99, anchor='w', text='♪ Soundtrack · Sidechain Ducked -16 LUFS', fill=COLORS['mint'], font=mono_font(7, 'bold'))
        else:
            c.create_rectangle(lane_left, 91, lane_left + track_w, 108, fill='#102235', outline=COLORS['border'], width=1)
            c.create_text(lane_left + 8, 99, anchor='w', text='A1 Clip Audio' + (' · Voice Cleanup EQ + Loudnorm' if self.plan.get('voice_cleanup') else ''), fill=COLORS['muted'], font=mono_font(7))

        # Scrubbable playhead cursor
        ph = max(0.0, min(total, self.playhead_sec))
        px = lane_left + (ph / total) * track_w
        c.create_line(px, 12, px, h - 2, fill=COLORS['amber'], width=2)
        c.create_polygon(px - 6, 4, px + 6, 4, px, 14, fill=COLORS['amber'], outline='')

    def _on_timeline_canvas_click(self, event):
        if not self.plan:
            return
        w = max(580, int(self.timeline_canvas.winfo_width() or 860))
        lane_left, pad_r = 44, 12
        track_w = max(140, w - lane_left - pad_r)
        ratio = max(0.0, min(1.0, (event.x - lane_left) / track_w))
        for x0, x1, idx in self.clip_hitboxes:
            if x0 <= event.x <= x1:
                self.timeline.selection_set(str(idx))
                self.select_clip()
                break
        self._seek_playhead(round(ratio * self.plan['duration'], 2))

    def _set_speed(self, val):
        self.fields['speed'].set(val)

    def _selected_clip_source_offset(self, minimum=0.0):
        idx = self.selection()
        plan_clip = self.plan['clips'][idx]
        offset = (self.playhead_sec - float(plan_clip['timeline_start'])) * float(plan_clip['speed'])
        return idx, plan_clip, max(minimum, offset)

    def mark_in_at_playhead(self):
        self.clips()
        _idx, c, offset = self._selected_clip_source_offset(0.0)
        new_in = round(min(float(c['end']) - 0.1, float(c['start']) + offset), 3)
        self.fields['start'].set(str(new_in))
        self.revise()

    def mark_out_at_playhead(self):
        self.clips()
        _idx, c, offset = self._selected_clip_source_offset(0.1)
        dur = float(self.ws.asset(c['asset_id'])['duration'])
        new_out = round(max(float(c['start']) + 0.1, min(dur, float(c['start']) + offset)), 3)
        self.fields['end'].set(str(new_out))
        self.revise()

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
            self.fx_fields['motion'].set(clip.get('motion', 'none'))
            self.fx_fields['flip'].set(clip.get('flip', 'none'))
            self.fx_fields['rotate'].set(str(clip.get('rotate', 0)))
            self.fx_fields['fade_in'].set(str(clip.get('fade_in', 0.0)))
            self.fx_fields['fade_out'].set(str(clip.get('fade_out', 0.0)))
            self.fx_fields['volume'].set(str(clip.get('volume', 1.0)))
            self.fx_fields['brightness'].set(str(clip.get('brightness', 0.0)))
            self.fx_fields['contrast'].set(str(clip.get('contrast', 1.0)))
            self.fx_fields['saturation'].set(str(clip.get('saturation', 1.0)))
            self.fx_fields['title_overlay'].set(clip.get('title_overlay', ''))
            self._highlight_grade(self.fx_fields['grade'].get())
            self._draw_timeline_canvas()
            self._schedule_monitor_refresh(15)

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
        clips[index]['motion'] = self.fx_fields['motion'].get()
        clips[index]['flip'] = self.fx_fields['flip'].get()
        clips[index]['rotate'] = int(self.fx_fields['rotate'].get())
        clips[index]['reason'] = 'User revised range/motion'
        self.save_revision(clips, 'Manual trim/motion')

    def apply_clip_effects(self):
        index = self.selection()
        changes = {
            'grade': self.fx_fields['grade'].get(),
            'motion': self.fx_fields['motion'].get(),
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
            voice_cleanup=bool(self.tl_fields['voice_cleanup'].get()),
            progress_bar=bool(self.tl_fields['progress_bar'].get()),
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

        PillButton(btns, text='Compare vs Parent', padx=10, pady=4, command=diff_parent).pack(side='left')
        PillButton(btns, text='Open Selected Plan', variant='primary', padx=10, pady=4, command=restore).pack(side='right')

    def audit_render(self):
        if not self.job:
            raise ValueError('Render a preview or final video first')

        def show_qa(report):
            self._switch_tab('mix')
            passed = bool(report['passed'])
            lufs_txt = f"{report['lufs']:.1f} LUFS" if report.get('lufs') is not None else 'N/A'
            peak_txt = f"{report['true_peak_db']:.1f} dBFS" if report.get('true_peak_db') is not None else 'N/A'
            self.tile_lufs.set_value(lufs_txt, COLORS['mint'] if report.get('lufs') is not None else COLORS['muted'])
            self.tile_peak.set_value(peak_txt, COLORS['mint'] if (report.get('true_peak_db') or -99) <= -0.5 else COLORS['amber'])
            self.tile_luma.set_value(f"{report['luma_avg']:.2f}", COLORS['text'])
            self.tile_black.set_value(str(report['black_frames']), COLORS['mint'] if report['black_frames'] == 0 else COLORS['danger'])

            issues = '; '.join(report['issues']) or 'All visual & EBU R128 loudness checks passed.'
            tips = '; '.join(report['suggestions']) or 'Ready for final export.'
            status_tag = 'PASSED ✓' if passed else 'NEEDS REVIEW !'
            self.qa_summary_var.set(f'{status_tag} · {issues}\nNext: {tips}')
            self.status.set(f'Audit QA {status_tag} · {lufs_txt} · Black frames: {report["black_frames"]}')

            sheet = Path(report['contact_sheet']) if report.get('contact_sheet') else None
            c = self.qa_sheet_canvas
            c.delete('all')
            if sheet and sheet.is_file():
                try:
                    self.qa_sheet_photo = tk.PhotoImage(file=str(sheet)).subsample(3, 3)
                    c.create_image(max(150, int(c.winfo_width() or 300)) // 2, 38, image=self.qa_sheet_photo)
                except tk.TclError:
                    pass

        self.task(lambda: audit_job_render(self.ws, self.renderer, self.job), show_qa)

    def show_receipt(self):
        if not self.job:
            self.status.set('No render job selected yet.')
            return
        state = self.renderer.status(self.job)
        if state['status'] != 'complete':
            self.status.set(f'Job status: {state["status"]}')
            return
        receipt = json.loads(Path(state['receipt']).read_text(encoding='utf-8'))
        self._switch_tab('mix')
        self.qa_summary_var.set(
            f"SHA-256: {receipt['sha256'][:20]}… · {receipt['output']['width']}×{receipt['output']['height']} · "
            f"{receipt['output']['duration']:.2f}s · Reused {receipt['cache_hits']} segments · Verified: {', '.join(receipt['verified'])}"
        )
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
            frame = tk.Frame(window, bg=COLORS['panel'], padx=18, pady=16)
            frame.pack(fill='both', expand=True)
            tk.Label(frame, text='Select the words to keep', bg=COLORS['panel'], fg=COLORS['text'], font=ui_font(15, 'bold')).pack(anchor='w')
            tk.Label(frame, text='Import a timecoded SRT transcript. Reeltern does not transcribe speech. Captions follow your cuts.', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(10), wraplength=850, justify='left').pack(anchor='w', pady=8)
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

            buttons = tk.Frame(frame, bg=COLORS['panel'])
            buttons.pack(fill='x')
            PillButton(buttons, text='Import SRT', padx=10, pady=5, command=load_srt).pack(side='left', padx=(0, 8))
            PillButton(buttons, text='Keep selected cues', variant='primary', padx=10, pady=5, command=lambda: self.guarded(chosen_plan)).pack(side='left')
            tk.Label(frame, text='Or describe a draft for your local Ollama model', bg=COLORS['panel'], fg=COLORS['text'], font=ui_font(11, 'bold')).pack(anchor='w', pady=(16, 6))
            brief = tk.StringVar()
            ttk.Entry(frame, textvariable=brief).pack(fill='x')
            options = tk.Frame(frame, bg=COLORS['panel'])
            options.pack(fill='x', pady=10)
            model, seconds = tk.StringVar(), tk.StringVar(value='60')
            tk.Label(options, text='Installed model', bg=COLORS['panel'], fg=COLORS['muted']).pack(side='left')
            ttk.Entry(options, textvariable=model, width=24).pack(side='left', padx=8)
            tk.Label(options, text='Maximum seconds', bg=COLORS['panel'], fg=COLORS['muted']).pack(side='left')
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

            PillButton(options, text='Create AI draft', variant='indigo', padx=10, pady=5, command=lambda: self.guarded(ask_agent)).pack(side='right')
            tk.Label(frame, text='Sends compact cues to your local Ollama service. Review captions before export.', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9)).pack(anchor='w')
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
            self.rendered_path = None
            self.open_button.configure(state='disabled')
            self.btn_mode_render.configure(state='disabled')
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
        if self._closing:
            return
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
                self.btn_mode_render.configure(state='normal')
                self.rendered_path = state.get('output')
                if self.reported_job != self.job:
                    self.status.set(f'Complete ✓ · {state["elapsed_seconds"]:.1f}s · verified video & audio · {state["cache_hits"]} reused')
                    self.reported_job = self.job
                    self._set_monitor_mode('rendered')
            elif state['status'] in ('failed', 'cancelled'):
                self.status.set(state.get('error', state['status']))
        self._poll_after = self.root.after(180, self.poll)

    def load_demo(self):
        def _demo_work():
            report = run_demo(self.ws.root, renderer=self.renderer)
            plan = self.ws.plan(report['plan_id'])
            vid_id = plan['clips'][0]['asset_id']
            visuals = self.ws.inspect_visuals(vid_id, thumbs=6, samples=60)
            return report, plan, vid_id, visuals

        def _after(payload):
            report, plan, vid_id, visuals = payload
            self.refresh_assets()
            self.assets.selection_set(vid_id)
            self.display_visuals(visuals)
            self.show_plan(plan)
            self.job = report.get('job_id')
            self.reported_job = self.job
            self.rendered_path = report.get('video')
            if self.rendered_path:
                self.btn_mode_render.configure(state='normal')
                self.open_button.configure(state='normal')
            self.playhead_sec = 0.0
            self.status.set(f'Demo loaded ({report["edit_seconds"]:.2f}s edit, {report["cache_hits"]} cached segments)')
            self._schedule_monitor_refresh(10)

        self.task(_demo_work, _after)

    def switch_workspace(self):
        if self.busy or (self.job and self.renderer.status(self.job)['status'] in ('queued', 'running', 'verifying')):
            raise ValueError('Wait for the active operation or render to finish first')
        folder = filedialog.askdirectory(title='Choose Reeltern Workspace Folder', initialdir=str(self.ws.root.parent))
        if not folder:
            return
        if self.playing:
            self.toggle_play()
        self.preview_engine.close()
        self.renderer.close()
        self.ws = Workspace(folder)
        self.renderer = Renderer(self.ws)
        self.ws_label.set(self.ws.root.name)
        self.plan = None
        self.job = None
        self.reported_job = None
        self.rendered_path = None
        self.current_visuals = None
        self.tl_thumb_cache.clear()
        self.timeline.delete(*self.timeline.get_children())
        self.storyboard_canvas.delete('all')
        self.waveform_canvas.delete('all')
        self.btn_mode_render.configure(state='disabled')
        self.open_button.configure(state='disabled')
        self._set_monitor_mode('timeline')
        self._draw_timeline_canvas()
        self.refresh_assets()
        self.summary.set('No timeline loaded · Import footage or click Load Demo')
        self.status.set('Switched workspace · ' + str(self.ws.root))
        self.telemetry_text.set('Select a clip to inspect visual telemetry')
        self._schedule_monitor_refresh(15)

    def connect_ai_dialog(self):
        win = tk.Toplevel(self.root)
        win.title('Connect AI Assistant (MCP) — Antigravity, Claude Code, Codex, Cursor, VS Code')
        win.geometry('760x560')
        win.configure(bg=COLORS['panel'])
        frm = tk.Frame(win, bg=COLORS['panel'], padx=18, pady=16)
        frm.pack(fill='both', expand=True)

        tk.Label(frm, text='Local stdio MCP Configuration', bg=COLORS['panel'], fg=COLORS['accent'], font=ui_font(14, 'bold')).pack(anchor='w')
        tk.Label(
            frm,
            text='Reeltern runs locally via stdio MCP (31 tools, 2 visual PNG resources, 4 prompts). Close Studio before launching a write-enabled MCP session against the same workspace.',
            bg=COLORS['panel'],
            fg=COLORS['muted'],
            font=ui_font(9),
            wraplength=700,
            justify='left',
        ).pack(anchor='w', pady=(4, 12))

        client_var = tk.StringVar(value='antigravity')
        default_media = self.ws.root / 'demo-input'
        media_var = tk.StringVar(value=str(default_media if default_media.is_dir() else self.ws.root))
        model_var = tk.StringVar(value='')
        dest_var = tk.StringVar(value=CLIENT_DESTINATIONS['antigravity'])

        row_c = tk.Frame(frm, bg=COLORS['panel']); row_c.pack(fill='x', pady=4)
        tk.Label(row_c, text='AI Client', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=14, anchor='w').pack(side='left')
        client_box = ttk.Combobox(row_c, textvariable=client_var, values=list(CLIENTS), state='readonly', width=20)
        client_box.pack(side='left')
        tk.Label(row_c, textvariable=dest_var, bg=COLORS['panel'], fg=COLORS['mint'], font=mono_font(9)).pack(side='left', padx=12)

        row_m = tk.Frame(frm, bg=COLORS['panel']); row_m.pack(fill='x', pady=4)
        tk.Label(row_m, text='Media Root', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=14, anchor='w').pack(side='left')
        ttk.Entry(row_m, textvariable=media_var).pack(side='left', fill='x', expand=True, padx=(0, 6))

        def browse_media():
            picked = filedialog.askdirectory(parent=win, title='Select Existing Footage Folder', initialdir=media_var.get())
            if picked:
                media_var.set(picked)
                refresh_preview()

        PillButton(row_m, text='Browse…', padx=9, pady=4, font_size=9, command=browse_media).pack(side='right')

        row_o = tk.Frame(frm, bg=COLORS['panel']); row_o.pack(fill='x', pady=4)
        tk.Label(row_o, text='Ollama (opt)', bg=COLORS['panel'], fg=COLORS['muted'], font=ui_font(9), width=14, anchor='w').pack(side='left')
        ttk.Entry(row_o, textvariable=model_var).pack(side='left', fill='x', expand=True)

        text = tk.Text(frm, bg=COLORS['bg'], fg=COLORS['text'], insertbackground=COLORS['accent'], font=mono_font(10), relief='flat', padx=10, pady=10)
        text.pack(fill='both', expand=True, pady=(10, 10))

        def refresh_preview(*_):
            client = client_var.get()
            dest_var.set('Destination: ' + CLIENT_DESTINATIONS.get(client, ''))
            model = model_var.get().strip() or None
            try:
                output = configuration(client, self.ws.root, media_var.get(), model)
            except Exception as exc:
                output = f'Configuration error: {exc}'
            text.configure(state='normal')
            text.delete('1.0', 'end')
            text.insert('1.0', output)
            text.configure(state='disabled')

        client_box.bind('<<ComboboxSelected>>', refresh_preview)
        media_var.trace_add('write', refresh_preview)
        model_var.trace_add('write', refresh_preview)
        refresh_preview()

        btns = tk.Frame(frm, bg=COLORS['panel'])
        btns.pack(fill='x')

        def copy_cfg():
            content = text.get('1.0', 'end-1c')
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.status.set(f'Copied {client_var.get()} MCP configuration to clipboard')

        PillButton(btns, text='Copy Configuration', variant='primary', padx=12, pady=5, command=copy_cfg).pack(side='left')
        PillButton(btns, text='Close', padx=12, pady=5, command=win.destroy).pack(side='right')

    def _cleanup_resources(self):
        self._closing = True
        self.playing = False
        for attr in ('_poll_after', '_play_after', '_monitor_after'):
            after_id = getattr(self, attr, None)
            if after_id is not None:
                setattr(self, attr, None)
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
        self.preview_engine.close()
        self.renderer.close()

    def close(self):
        if self.busy:
            self.status.set('Wait for import or analysis to finish before closing.')
            return
        self._cleanup_resources()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def launch(workspace=None):
    root = tk.Tk()
    app = Studio(root, workspace)
    smoke_ms = os.environ.get('REELTERN_STUDIO_SMOKE_MS', '').strip()
    if smoke_ms.isdigit() and int(smoke_ms) > 0:
        root.after(int(smoke_ms), app.close)
    root.mainloop()
