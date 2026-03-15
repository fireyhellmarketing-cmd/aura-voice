"""AURA VOICE — Right-side voice controls panel (detailed voice settings)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

from assets.styles import (
    SURFACE, SURFACE2, SURFACE3, BORDER, BORDER2,
    TEXT, TEXT_SUB, TEXT_DIM,
    ACCENT, ACCENT_HOV,
    FONTS, PAD, RADIUS,
)
from core.tts_engine import VOICE_PROFILES, EMOTION_SPEEDS, LANGUAGE_CODES
from pathlib import Path as _Path
from core.tts_engine import TTSEngine as _TTSEngine

_PROFILES_DIR = _Path.home() / "Documents" / "AuraVoice" / "profiles"
_SAVED_PREFIX  = "👤 "   # prefix for saved voice profiles in the dropdown

DELIVERY_STYLES = list(EMOTION_SPEEDS.keys())
VOICE_NAMES     = list(VOICE_PROFILES.keys())

# Emotion dot positions on the 2D grid (label, x 0-1, y 0-1, color)
_EMOTION_DOTS = [
    ("Neutral",    0.50, 0.50, "#888888"),
    ("Happy",      0.72, 0.20, "#F59E0B"),
    ("Excited",    0.88, 0.12, "#EF4444"),
    ("Calm",       0.25, 0.55, "#10B981"),
    ("Sad",        0.20, 0.78, "#A855F7"),
    ("Serious",    0.38, 0.30, "#3B82F6"),
    ("Warm",       0.60, 0.35, "#F97316"),
    ("Whisper",    0.15, 0.40, "#EC4899"),
]


class _EmotionGrid(tk.Canvas):
    """2-D emotion blend grid — dots the user can click to pick a style."""

    _DOT_R = 6

    def __init__(self, parent, emotion_var: ctk.StringVar, **kwargs):
        kwargs.setdefault("bg", "#111111")
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("highlightbackground", BORDER2)
        kwargs.setdefault("bd", 0)
        super().__init__(parent, **kwargs)
        self._var      = emotion_var
        self._selected = "Neutral"
        self.bind("<Configure>",  self._redraw)
        self.bind("<Button-1>",   self._on_click)

    def _redraw(self, _event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return

        # Axis labels
        self.create_text(4, h - 4, text="Dark", fill="#444444",
                         font=("SF Mono", 7), anchor="sw")
        self.create_text(4, 4, text="High", fill="#444444",
                         font=("SF Mono", 7), anchor="nw")
        self.create_text(w - 4, h - 4, text="Emotions", fill="#444444",
                         font=("SF Mono", 7), anchor="se")

        # Grid lines (subtle)
        for frac in (0.25, 0.5, 0.75):
            xi = int(w * frac)
            yi = int(h * frac)
            self.create_line(xi, 0, xi, h, fill="#1E1E1E", dash=(2, 4))
            self.create_line(0, yi, w, yi, fill="#1E1E1E", dash=(2, 4))

        # Dots
        r = self._DOT_R
        for label, fx, fy, color in _EMOTION_DOTS:
            x = int(fx * w)
            y = int(fy * h)
            is_sel = (label == self._selected)
            outline = "#FFFFFF" if is_sel else ""
            ow      = 2 if is_sel else 0
            self.create_oval(x - r, y - r, x + r, y + r,
                             fill=color, outline=outline, width=ow)
            if is_sel:
                self.create_text(x, y - r - 4, text=label, fill="#FFFFFF",
                                 font=("SF Mono", 7), anchor="s")

    def _on_click(self, event):
        w = self.winfo_width()
        h = self.winfo_height()
        best, best_d = None, 9999
        r = self._DOT_R * 2.5
        for label, fx, fy, _ in _EMOTION_DOTS:
            dx = event.x - fx * w
            dy = event.y - fy * h
            d  = (dx * dx + dy * dy) ** 0.5
            if d < best_d:
                best_d, best = d, label
        if best and best_d < r * 2:
            self._selected = best
            self._var.set(best)
            self._redraw()


class VoicePanel(ctk.CTkFrame):
    """Right panel: detailed voice controls matching the reference UI."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=SURFACE,
            corner_radius=0,
            border_color=BORDER,
            border_width=1,
            **kwargs,
        )
        self.configure(width=280)
        self.pack_propagate(False)

        self._voice_var       = ctk.StringVar(value="Natural Female")
        self._speed_var       = ctk.DoubleVar(value=1.0)
        self._stability_var   = ctk.DoubleVar(value=0.75)
        self._exaggeration_var= ctk.DoubleVar(value=0.50)
        self._emotion_var     = ctk.StringVar(value="Neutral")
        self._format_var      = ctk.StringVar(value="WAV")
        self._output_dir      = str(Path.home() / "Documents" / "AuraVoice")
        self._clone_ref:      Optional[str] = None
        self.on_save_profile: Optional[callable] = None   # callback(profile_name)
        self._saved_profiles: dict = {}   # {name: npz_path}
        self._refresh_saved_profiles()
        self._build()

    def _refresh_saved_profiles(self):
        """Load saved profiles from disk and rebuild the voice dropdown values."""
        self._saved_profiles = _TTSEngine.list_speaker_profiles(_PROFILES_DIR)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _section_lbl(self, parent, text: str):
        ctk.CTkLabel(
            parent, text=text,
            font=FONTS["xs_bold"], text_color=TEXT_DIM,
        ).pack(anchor="w", padx=PAD["xl"], pady=(PAD["lg"], PAD["sm"]))

    def _field_lbl(self, parent, text: str):
        ctk.CTkLabel(
            parent, text=text,
            font=FONTS["xs"], text_color=TEXT_DIM,
        ).pack(anchor="w", padx=PAD["xl"], pady=(0, 2))

    def _divider(self, parent):
        ctk.CTkFrame(parent, fg_color=BORDER, height=1).pack(
            fill="x", padx=PAD["xl"], pady=(PAD["md"], 0),
        )

    def _slider_row(self, parent, label: str, var: ctk.DoubleVar,
                    from_: float, to_: float, fmt: str = "{:.2f}") -> ctk.CTkLabel:
        """Build a label + slider + value label row. Returns the value label."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["sm"]))
        ctk.CTkLabel(row, text=label, font=FONTS["xs"],
                     text_color=TEXT_DIM, width=88, anchor="w").pack(side="left")
        val_lbl = ctk.CTkLabel(row, text=fmt.format(var.get()),
                               font=FONTS["xs_bold"], text_color=TEXT_SUB, width=36)
        val_lbl.pack(side="right")
        ctk.CTkSlider(
            row, from_=from_, to=to_, variable=var,
            button_color=ACCENT, button_hover_color=ACCENT_HOV,
            progress_color=ACCENT, fg_color=BORDER2,
            command=lambda v, lbl=val_lbl, f=fmt: lbl.configure(text=f.format(v)),
        ).pack(side="left", fill="x", expand=True)
        return val_lbl

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # Panel header bar
        hdr = ctk.CTkFrame(self, fg_color="#0D0D0D", corner_radius=0, height=26)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr, text="DETAILED VOICE DETAILS",
            font=("SF Mono", 9), text_color="#2E2E2E",
        ).pack(side="left", padx=10)

        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=BORDER2,
            scrollbar_button_hover_color=BORDER,
        )
        scroll.pack(fill="both", expand=True)

        om_kw = dict(
            fg_color=SURFACE2, button_color=SURFACE2,
            button_hover_color=SURFACE3,
            text_color=TEXT,
            dropdown_fg_color=SURFACE2,
            dropdown_hover_color=SURFACE3,
            dropdown_text_color=TEXT,
            corner_radius=RADIUS["md"], height=34,
            font=FONTS["sm"],
            dropdown_font=FONTS["sm"],
        )

        # ── MODEL ──
        self._section_lbl(scroll, "MODEL")
        self._voice_menu = ctk.CTkOptionMenu(
            scroll, values=self._build_voice_list(), variable=self._voice_var,
            command=self._on_voice_change, **om_kw,
        )
        self._voice_menu.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["sm"]))

        # Clone ref card (hidden until Custom Clone selected)
        self._clone_frame = ctk.CTkFrame(
            scroll, fg_color=SURFACE2, corner_radius=RADIUS["md"],
            border_color=BORDER2, border_width=1,
        )
        inner_c = ctk.CTkFrame(self._clone_frame, fg_color="transparent")
        inner_c.pack(fill="x", padx=PAD["md"], pady=PAD["md"])
        ctk.CTkLabel(
            inner_c, text="Reference audio (6-30s clean speech)",
            font=FONTS["xs"], text_color=TEXT_DIM, anchor="w",
        ).pack(anchor="w")
        ref_row = ctk.CTkFrame(inner_c, fg_color="transparent")
        ref_row.pack(fill="x", pady=(4, 0))
        self._clone_ref_label = ctk.CTkLabel(
            ref_row, text="No file selected",
            font=FONTS["xs"], text_color=TEXT_DIM, anchor="w",
        )
        self._clone_ref_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            ref_row, text="Browse", width=64, height=26,
            fg_color=ACCENT, hover_color=ACCENT_HOV,
            text_color="#000000", corner_radius=RADIUS["sm"],
            font=FONTS["xs_bold"],
            command=self._pick_clone_ref,
        ).pack(side="right")

        # "Save as Profile" button — shown after ref is picked
        self._save_profile_btn = ctk.CTkButton(
            inner_c,
            text="💾  Save as Voice Profile...",
            height=28,
            fg_color="transparent",
            hover_color=SURFACE3,
            text_color=TEXT_SUB,
            border_color=BORDER2,
            border_width=1,
            corner_radius=RADIUS["sm"],
            font=FONTS["xs"],
            command=self._on_save_profile_click,
        )
        # not packed yet — shown after a ref file is chosen

        # ── SPEAKER / delivery ──
        self._section_lbl(scroll, "SPEAKER")
        ctk.CTkOptionMenu(
            scroll, values=DELIVERY_STYLES, variable=self._emotion_var,
            **om_kw,
        ).pack(fill="x", padx=PAD["xl"], pady=(0, PAD["sm"]))

        # ── EMOTION & STYLE MAPPING ──
        self._section_lbl(scroll, "EMOTION & STYLE MAPPING")
        ctk.CTkLabel(
            scroll, text="Click a dot to blend emotions",
            font=FONTS["xs"], text_color=TEXT_DIM,
        ).pack(anchor="w", padx=PAD["xl"], pady=(0, PAD["sm"]))

        grid_frame = ctk.CTkFrame(
            scroll, fg_color=SURFACE2,
            corner_radius=RADIUS["sm"],
            border_color=BORDER2, border_width=1,
        )
        grid_frame.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))

        self._emotion_grid = _EmotionGrid(
            grid_frame, emotion_var=self._emotion_var,
            width=240, height=120,
        )
        self._emotion_grid.pack(fill="x", padx=2, pady=2)

        # ── CONTROLS ──
        self._section_lbl(scroll, "CONTROLS")
        self._slider_row(scroll, "Speed",        self._speed_var,
                         0.5,  2.0, "{:.2f}x")
        self._slider_row(scroll, "Stability",    self._stability_var,
                         0.0,  1.0, "{:.2f}")
        self._slider_row(scroll, "Exaggeration", self._exaggeration_var,
                         0.0,  1.0, "{:.2f}")

        # ── OUTPUT ──
        self._divider(scroll)
        self._section_lbl(scroll, "OUTPUT")

        self._field_lbl(scroll, "Format")
        fmt_row = ctk.CTkFrame(scroll, fg_color="transparent")
        fmt_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        for fmt in ["WAV", "MP3"]:
            ctk.CTkRadioButton(
                fmt_row, text=fmt, value=fmt, variable=self._format_var,
                font=FONTS["sm"], text_color=TEXT_SUB,
                fg_color=ACCENT, hover_color=ACCENT_HOV,
            ).pack(side="left", padx=(0, 16))

        self._field_lbl(scroll, "Output Folder")
        folder_row = ctk.CTkFrame(scroll, fg_color="transparent")
        folder_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["lg"]))
        self._folder_label = ctk.CTkLabel(
            folder_row, text=self._shorten(self._output_dir),
            font=FONTS["xs"], text_color=TEXT_DIM, anchor="w",
        )
        self._folder_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            folder_row, text="...", width=28, height=26,
            fg_color=SURFACE3, hover_color=BORDER2,
            text_color=TEXT_SUB, corner_radius=RADIUS["sm"],
            font=FONTS["base"],
            command=self._pick_folder,
        ).pack(side="right")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _shorten(self, path: str, maxlen: int = 22) -> str:
        home = str(Path.home())
        if path.startswith(home):
            path = "~" + path[len(home):]
        return ("..." + path[-(maxlen - 1):]) if len(path) > maxlen else path

    def _on_voice_change(self, val: str):
        if val == "Custom (Clone)":
            self._clone_frame.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        else:
            self._clone_frame.pack_forget()

    def _get_profile_npz(self) -> Optional[str]:
        """Return npz path if a saved profile is selected, else None."""
        val = self._voice_var.get()
        if val.startswith(_SAVED_PREFIX):
            name = val[len(_SAVED_PREFIX):]
            return self._saved_profiles.get(name)
        return None

    def _pick_clone_ref(self):
        """Open file dialog accepting WAV, MP3, M4A, FLAC, OGG audio files."""
        p = filedialog.askopenfilename(
            title="Select Reference Audio",
            filetypes=[
                ("Audio files", "*.wav *.mp3 *.m4a *.flac *.ogg *.aif *.aiff"),
                ("WAV",  "*.wav"),
                ("MP3",  "*.mp3"),
                ("M4A",  "*.m4a"),
                ("FLAC", "*.flac"),
                ("All",  "*.*"),
            ],
        )
        if p:
            self._clone_ref = p
            name = Path(p).name
            self._clone_ref_label.configure(
                text=(name[:26] + "...") if len(name) > 26 else name,
                text_color=TEXT,
            )
            self._save_profile_btn.pack(fill="x", pady=(8, 0))

    def _pick_folder(self):
        d = filedialog.askdirectory(title="Output Folder", initialdir=self._output_dir)
        if d:
            self._output_dir = d
            self._folder_label.configure(text=self._shorten(d))

    def _build_voice_list(self) -> list:
        """Build the full voice dropdown list: standard + saved profiles."""
        names = list(VOICE_NAMES)
        if self._saved_profiles:
            for name in self._saved_profiles:
                names.append(_SAVED_PREFIX + name)
        return names

    def _on_save_profile_click(self):
        """Open a name-entry dialog and trigger save."""
        win = ctk.CTkToplevel(self.winfo_toplevel())
        win.title("Save Voice Profile")
        win.geometry("340x160")
        win.resizable(False, False)
        win.configure(fg_color="#0A0A0A")
        win.grab_set()
        win.focus_set()

        from assets.styles import BG_DEEP, SURFACE, BORDER, BORDER2, TEXT, TEXT_DIM
        ctk.CTkLabel(
            win, text="Profile Name",
            font=FONTS["sm_bold"], text_color=TEXT,
        ).pack(anchor="w", padx=20, pady=(20, 4))

        entry = ctk.CTkEntry(
            win, fg_color=SURFACE, border_color=BORDER2,
            text_color=TEXT, font=FONTS["base"], height=34,
        )
        entry.pack(fill="x", padx=20, pady=(0, 16))
        entry.insert(0, "My Voice")
        entry.focus_set()
        entry.select_range(0, "end")

        def _save():
            name = entry.get().strip()
            if not name:
                return
            win.destroy()
            if self.on_save_profile:
                self.on_save_profile(name)

        entry.bind("<Return>", lambda _: _save())
        ctk.CTkButton(
            win, text="Save",
            height=34, fg_color="#FFFFFF", hover_color="#E5E5E5",
            text_color="#000000", corner_radius=8,
            font=FONTS["sm_bold"],
            command=_save,
        ).pack(fill="x", padx=20)

    def refresh_profiles(self):
        """Reload saved profiles from disk and update the voice dropdown."""
        self._refresh_saved_profiles()
        if hasattr(self, "_voice_menu"):
            self._voice_menu.configure(values=self._build_voice_list())

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        val = self._voice_var.get()
        profile_npz = self._get_profile_npz()
        # For saved profiles, report voice_profile as "Custom (Clone)" so engine uses XTTS
        voice_profile = "Custom (Clone)" if profile_npz else val
        return {
            "voice_profile":   voice_profile,
            "delivery_style":  self._emotion_var.get(),
            "language":        "English",
            "speed":           round(self._speed_var.get(), 2),
            "output_format":   self._format_var.get(),
            "output_dir":      self._output_dir,
            "clone_ref_path":  self._clone_ref,
            "profile_npz_path": profile_npz,
        }

    def set_output_dir(self, path: str):
        self._output_dir = path
        self._folder_label.configure(text=self._shorten(path))

    def set_output_format(self, fmt: str):
        self._format_var.set(fmt.upper())

    def set_clone_ref_path(self, path: Optional[str]):
        self._clone_ref = path
