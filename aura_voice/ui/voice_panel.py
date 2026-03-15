"""AURA VOICE — Right-side voice controls panel."""
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

DELIVERY_STYLES = list(EMOTION_SPEEDS.keys())
VOICE_NAMES = list(VOICE_PROFILES.keys())

class VoicePanel(ctk.CTkFrame):
    """Right panel: voice, speed, emotion, format, output folder controls."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=SURFACE,
            corner_radius=0,
            border_color=BORDER,
            border_width=1,
            **kwargs,
        )
        self.configure(width=260)
        self.pack_propagate(False)
        self._voice_var   = ctk.StringVar(value="Natural Female")
        self._speed_var   = ctk.DoubleVar(value=1.0)
        self._emotion_var = ctk.StringVar(value="Neutral")
        self._format_var  = ctk.StringVar(value="WAV")
        self._output_dir  = str(Path.home() / "Documents" / "AuraVoice")
        self._clone_ref:  Optional[str] = None
        self._build()

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
            fill="x", padx=PAD["xl"], pady=(PAD["md"], 0)
        )

    def _build(self):
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
            corner_radius=RADIUS["md"], height=36,
            font=FONTS["base"],
            dropdown_font=FONTS["base"],
        )

        self._section_lbl(scroll, "VOICE SETTINGS")

        # Voice profile
        self._field_lbl(scroll, "Voice Profile")
        ctk.CTkOptionMenu(
            scroll, values=VOICE_NAMES, variable=self._voice_var,
            command=self._on_voice_change, **om_kw,
        ).pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))

        # Clone ref card (hidden)
        self._clone_frame = ctk.CTkFrame(
            scroll, fg_color=SURFACE2, corner_radius=RADIUS["md"],
            border_color=BORDER2, border_width=1,
        )
        inner_c = ctk.CTkFrame(self._clone_frame, fg_color="transparent")
        inner_c.pack(fill="x", padx=PAD["md"], pady=PAD["md"])
        ctk.CTkLabel(
            inner_c, text="Reference WAV (6-30s clean speech)",
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
            ref_row, text="Browse", width=60, height=26,
            fg_color=ACCENT, hover_color=ACCENT_HOV,
            text_color="#000000", corner_radius=RADIUS["sm"],
            font=FONTS["xs_bold"],
            command=self._pick_clone_ref,
        ).pack(side="right")

        # Speed
        self._section_lbl(scroll, "SPEED")
        speed_row = ctk.CTkFrame(scroll, fg_color="transparent")
        speed_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        self._speed_label = ctk.CTkLabel(
            speed_row, text="1.00x",
            font=FONTS["xs_bold"], text_color=TEXT_SUB, width=40,
        )
        self._speed_label.pack(side="right")
        ctk.CTkSlider(
            speed_row, from_=0.5, to=2.0,
            variable=self._speed_var,
            button_color=ACCENT, button_hover_color=ACCENT_HOV,
            progress_color=ACCENT, fg_color=BORDER2,
            command=lambda v: self._speed_label.configure(text=f"{v:.2f}x"),
        ).pack(side="left", fill="x", expand=True)

        # Delivery style
        self._section_lbl(scroll, "DELIVERY STYLE")
        ctk.CTkOptionMenu(
            scroll, values=DELIVERY_STYLES, variable=self._emotion_var,
            **om_kw,
        ).pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))

        self._divider(scroll)
        self._section_lbl(scroll, "OUTPUT")

        # Format
        self._field_lbl(scroll, "Format")
        fmt_row = ctk.CTkFrame(scroll, fg_color="transparent")
        fmt_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        for fmt in ["WAV", "MP3"]:
            ctk.CTkRadioButton(
                fmt_row, text=fmt, value=fmt, variable=self._format_var,
                font=FONTS["sm"], text_color=TEXT_SUB,
                fg_color=ACCENT, hover_color=ACCENT_HOV,
            ).pack(side="left", padx=(0, 16))

        # Output folder
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

    def _shorten(self, path: str, maxlen: int = 24) -> str:
        home = str(Path.home())
        if path.startswith(home):
            path = "~" + path[len(home):]
        return ("..." + path[-maxlen+1:]) if len(path) > maxlen else path

    def _on_voice_change(self, val: str):
        if val == "Custom (Clone)":
            self._clone_frame.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        else:
            self._clone_frame.pack_forget()

    def _pick_clone_ref(self):
        p = filedialog.askopenfilename(
            title="Reference WAV",
            filetypes=[("WAV", "*.wav"), ("All", "*.*")],
        )
        if p:
            self._clone_ref = p
            self._clone_ref_label.configure(text=Path(p).name)

    def _pick_folder(self):
        d = filedialog.askdirectory(title="Output Folder", initialdir=self._output_dir)
        if d:
            self._output_dir = d
            self._folder_label.configure(text=self._shorten(d))

    def get_settings(self) -> dict:
        return {
            "voice_profile":  self._voice_var.get(),
            "delivery_style": self._emotion_var.get(),
            "language":       "English",
            "speed":          round(self._speed_var.get(), 2),
            "output_format":  self._format_var.get(),
            "output_dir":     self._output_dir,
            "clone_ref_path": self._clone_ref,
        }

    def set_output_dir(self, path: str):
        self._output_dir = path
        self._folder_label.configure(text=self._shorten(path))

    def set_output_format(self, fmt: str):
        self._format_var.set(fmt.upper())
