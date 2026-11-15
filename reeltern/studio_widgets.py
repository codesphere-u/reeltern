"""Custom Obsidian Studio UI widgets for Reeltern Studio (macOS, Windows, Linux)."""
import sys
import tkinter as tk

THEME = {
    'bg': '#090d16',
    'panel': '#0f1623',
    'card': '#151e30',
    'card_hover': '#1c2840',
    'elevated': '#1b263b',
    'border': '#23324c',
    'border_bright': '#33486b',
    'accent': '#38bdf8',
    'accent_hover': '#7dd3fc',
    'accent_soft': '#102a43',
    'indigo': '#818cf8',
    'indigo_hover': '#a5b4fc',
    'mint': '#34d399',
    'mint_soft': '#0f3329',
    'amber': '#fbbf24',
    'danger': '#f87171',
    'danger_soft': '#33151b',
    'text': '#f1f5f9',
    'muted': '#94a3b8',
    'subtle': '#64748b',
}


def pick_fonts():
    """Return platform-appropriate UI and monospace font family names."""
    if sys.platform == 'darwin':
        return 'SF Pro Text', 'Menlo'
    if sys.platform == 'win32':
        return 'Segoe UI', 'Consolas'
    return 'DejaVu Sans', 'DejaVu Sans Mono'


UI_FONT, MONO_FONT = pick_fonts()


def ui_font(size=10, weight='normal'):
    return (UI_FONT, size, weight) if weight != 'normal' else (UI_FONT, size)


def mono_font(size=10, weight='normal'):
    return (MONO_FONT, size, weight) if weight != 'normal' else (MONO_FONT, size)


def draw_logo_mark(canvas, size=24):
    """Draw the crisp vector Reeltern aperture/play mark on a Canvas."""
    canvas.delete('all')
    s = float(size)
    canvas.create_rectangle(2, 2, s - 2, s - 2, fill='#111a2c', outline='#33486b', width=1)
    pad = s * 0.18
    canvas.create_oval(pad, pad, s - pad, s - pad, outline=THEME['accent'], width=2)
    pts = [s * 0.41, s * 0.30, s * 0.41, s * 0.70, s * 0.72, s * 0.50]
    canvas.create_polygon(pts, fill=THEME['text'], outline='')


class PillButton(tk.Frame):
    """Flat, consistent cross-platform button with hover states and active pill variants."""

    VARIANTS = {
        'primary': (THEME['accent'], '#04101d', THEME['accent_hover'], THEME['accent']),
        'indigo': (THEME['indigo'], '#090d16', THEME['indigo_hover'], THEME['indigo']),
        'mint': (THEME['mint'], '#04101d', '#6ee7b7', THEME['mint']),
        'danger': (THEME['danger_soft'], '#fecdd3', '#4c1d24', '#7f1d1d'),
        'default': (THEME['card'], THEME['text'], THEME['card_hover'], THEME['border']),
        'active_chip': (THEME['accent_soft'], THEME['accent'], '#163858', THEME['accent']),
        'ghost': (THEME['panel'], THEME['muted'], THEME['card'], THEME['panel']),
    }

    def __init__(self, parent, text='', command=None, variant='default', padx=11, pady=5, font_size=10, bold=False, state='normal', **kwargs):
        bg, fg, hover_bg, border = self.VARIANTS.get(variant, self.VARIANTS['default'])
        super().__init__(parent, bg=border, highlightthickness=0, bd=0, **kwargs)
        self._variant = variant
        self._command = command
        self._state = state
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._border = border

        weight = 'bold' if (bold or variant in ('primary', 'indigo', 'mint', 'active_chip')) else 'normal'
        self.label = tk.Label(
            self,
            text=text,
            bg=bg,
            fg=fg,
            padx=padx,
            pady=pady,
            font=ui_font(font_size, weight),
            cursor='hand2',
        )
        self.label.pack(fill='both', expand=True, padx=1, pady=1)

        for widget in (self, self.label):
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)
            widget.bind('<Button-1>', self._on_press)
            widget.bind('<ButtonRelease-1>', self._on_release)

        if self._state != 'normal':
            self._apply_colors()

    def _on_enter(self, _=None):
        if self._state == 'normal':
            self.label.configure(bg=self._hover_bg)

    def _on_leave(self, _=None):
        if self._state == 'normal':
            self.label.configure(bg=self._bg)

    def _on_press(self, _=None):
        if self._state == 'normal':
            self.label.configure(bg=self._border)

    def _on_release(self, event=None):
        if self._state != 'normal':
            return
        self.label.configure(bg=self._hover_bg)
        if event is not None:
            w, h = self.winfo_width(), self.winfo_height()
            if not (0 <= event.x <= w and 0 <= event.y <= h):
                self.label.configure(bg=self._bg)
                return
        if callable(self._command):
            self._command()

    def invoke(self):
        if self._state == 'normal' and callable(self._command):
            self._command()

    def set_variant(self, variant):
        self._variant = variant
        bg, fg, hover_bg, border = self.VARIANTS.get(variant, self.VARIANTS['default'])
        self._bg, self._fg, self._hover_bg, self._border = bg, fg, hover_bg, border
        self._apply_colors()

    def _apply_colors(self):
        if self._state == 'disabled':
            super().configure(bg=THEME['border'])
            self.label.configure(bg=THEME['panel'], fg=THEME['subtle'], cursor='arrow')
        else:
            super().configure(bg=self._border)
            self.label.configure(bg=self._bg, fg=self._fg, cursor='hand2')

    def configure(self, cnf=None, **kw):
        if 'text' in kw:
            self.label.configure(text=kw.pop('text'))
        if 'command' in kw:
            self._command = kw.pop('command')
        if 'state' in kw:
            self._state = kw.pop('state')
            self._apply_colors()
        if 'variant' in kw:
            self.set_variant(kw.pop('variant'))
        if kw:
            super().configure(cnf, **kw)
        return None

    def cget(self, key):
        if key == 'state':
            return self._state
        if key == 'text':
            return self.label.cget('text')
        if key == 'command':
            return self._command
        if key == 'variant':
            return self._variant
        return super().cget(key)

    config = configure


class ToggleSwitch(tk.Frame):
    """Compact studio toggle pill + label synchronized with a tk.BooleanVar."""

    def __init__(self, parent, text, variable, command=None, bg=THEME['panel']):
        super().__init__(parent, bg=bg)
        self.variable = variable
        self.command = command
        self._bg = bg

        self.canvas = tk.Canvas(self, width=36, height=20, bg=bg, highlightthickness=0, cursor='hand2')
        self.canvas.pack(side='left')
        self.lbl = tk.Label(self, text=text, bg=bg, fg=THEME['text'], font=ui_font(10), cursor='hand2')
        self.lbl.pack(side='left', padx=(6, 0))

        self.canvas.bind('<Button-1>', self._toggle)
        self.lbl.bind('<Button-1>', self._toggle)
        self.variable.trace_add('write', lambda *_: self._redraw())
        self._redraw()

    def _toggle(self, _=None):
        self.variable.set(not bool(self.variable.get()))
        if callable(self.command):
            self.command()

    def _redraw(self):
        c = self.canvas
        c.delete('all')
        on = bool(self.variable.get())
        track_fill = THEME['accent_soft'] if on else THEME['card']
        track_outline = THEME['accent'] if on else THEME['border']
        knob_fill = THEME['accent'] if on else THEME['muted']
        c.create_rectangle(2, 3, 34, 17, fill=track_fill, outline=track_outline, width=1)
        kx = 25 if on else 10
        c.create_oval(kx - 5, 5, kx + 5, 15, fill=knob_fill, outline='')


class ParamSlider(tk.Frame):
    """Scrubbable vector slider synchronized with a tk.StringVar and reset on double-click."""

    def __init__(
        self,
        parent,
        label,
        variable,
        min_val,
        max_val,
        default_val,
        *,
        step=0.01,
        fmt='{:.2f}',
        on_change=None,
        bg=THEME['panel'],
    ):
        super().__init__(parent, bg=bg)
        self.variable = variable
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.default_val = float(default_val)
        self.step = float(step)
        self.fmt = fmt
        self.on_change = on_change
        self._updating = False

        top = tk.Frame(self, bg=bg)
        top.pack(fill='x')
        tk.Label(top, text=label, bg=bg, fg=THEME['muted'], font=ui_font(9)).pack(side='left')
        self.val_lbl = tk.Label(top, text=self.fmt.format(self.default_val), bg=THEME['card'], fg=THEME['accent'], font=mono_font(9, 'bold'), padx=6, pady=1, cursor='hand2')
        self.val_lbl.pack(side='right')
        self.val_lbl.bind('<Double-Button-1>', lambda _e: self.reset())

        self.track = tk.Canvas(self, height=20, bg=bg, highlightthickness=0, cursor='sb_h_double_arrow')
        self.track.pack(fill='x', pady=(2, 0))
        self.track.bind('<Button-1>', self._on_drag)
        self.track.bind('<B1-Motion>', self._on_drag)
        self.track.bind('<Double-Button-1>', lambda _e: self.reset())
        self.track.bind('<Configure>', lambda _e: self._draw())

        self.variable.trace_add('write', lambda *_: self._sync_from_var())
        self._sync_from_var()

    def _current(self):
        try:
            v = float(self.variable.get())
        except (TypeError, ValueError):
            v = self.default_val
        return max(self.min_val, min(self.max_val, v))

    def _sync_from_var(self):
        if self._updating:
            return
        val = self._current()
        self.val_lbl.configure(text=self.fmt.format(val))
        self._draw()

    def _draw(self):
        c = self.track
        c.delete('all')
        w = max(110, int(c.winfo_width() or 140))
        mid = 10
        x0, x1 = 7, w - 7
        span = max(1, x1 - x0)
        ratio = (self._current() - self.min_val) / max(1e-6, self.max_val - self.min_val)
        ratio = max(0.0, min(1.0, ratio))
        tx = x0 + ratio * span

        c.create_line(x0, mid, x1, mid, fill=THEME['border'], width=4, capstyle='round')
        c.create_line(x0, mid, tx, mid, fill=THEME['accent'], width=4, capstyle='round')
        c.create_oval(tx - 6, mid - 6, tx + 6, mid + 6, fill=THEME['text'], outline=THEME['accent'], width=2)

    def _on_drag(self, event):
        w = max(110, int(self.track.winfo_width() or 140))
        x0, x1 = 7, w - 7
        ratio = max(0.0, min(1.0, (event.x - x0) / max(1, x1 - x0)))
        raw = self.min_val + ratio * (self.max_val - self.min_val)
        snapped = round(raw / self.step) * self.step
        snapped = max(self.min_val, min(self.max_val, round(snapped, 4)))
        self._updating = True
        self.variable.set(f'{snapped:.2f}' if self.step >= 0.01 else str(snapped))
        self._updating = False
        self.val_lbl.configure(text=self.fmt.format(snapped))
        self._draw()
        if callable(self.on_change):
            self.on_change()

    def reset(self):
        self._updating = True
        self.variable.set(f'{self.default_val:.2f}')
        self._updating = False
        self.val_lbl.configure(text=self.fmt.format(self.default_val))
        self._draw()
        if callable(self.on_change):
            self.on_change()


class MetricTile(tk.Frame):
    """Dashboard metric tile displaying a semantic KPI and status indicator."""

    def __init__(self, parent, title, initial='—'):
        super().__init__(parent, bg=THEME['border'])
        inner = tk.Frame(self, bg=THEME['card'], padx=9, pady=7)
        inner.pack(fill='both', expand=True, padx=1, pady=1)
        tk.Label(inner, text=title, bg=THEME['card'], fg=THEME['muted'], font=ui_font(8, 'bold')).pack(anchor='w')
        self.val_var = tk.StringVar(value=initial)
        self.val_lbl = tk.Label(inner, textvariable=self.val_var, bg=THEME['card'], fg=THEME['text'], font=mono_font(12, 'bold'))
        self.val_lbl.pack(anchor='w', pady=(2, 0))

    def set_value(self, text, color=THEME['text']):
        self.val_var.set(text)
        self.val_lbl.configure(fg=color)


class ScrollablePane(tk.Frame):
    """Canvas-backed inspector container that prevents vertical control clipping at compact heights."""

    def __init__(self, parent, bg=THEME['panel']):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win_id = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', self._sync_scrollregion)
        self.canvas.bind('<Configure>', self._sync_width)
        self.canvas.bind('<Enter>', lambda _e: self._bind_wheel(True))
        self.canvas.bind('<Leave>', lambda _e: self._bind_wheel(False))

    def _sync_scrollregion(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _sync_width(self, event):
        if event.width > 1:
            self.canvas.itemconfigure(self._win_id, width=event.width)

    def _bind_wheel(self, active):
        if active:
            self.canvas.bind_all('<MouseWheel>', self._on_wheel)
        else:
            self.canvas.unbind_all('<MouseWheel>')

    def _on_wheel(self, event):
        bbox = self.canvas.bbox('all')
        if not bbox or (bbox[3] - bbox[1]) <= self.canvas.winfo_height():
            return
        delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, 'units')
