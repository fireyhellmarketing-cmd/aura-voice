"""
AURA VOICE — Right panel: voice settings and Generate button.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

from assets.styles import COLORS, FONTS, PAD
from core.tts_engine import VOICE_PROFILES, EMOTION_PREFIXES, LANGUAGE_CODES


class RightPanel(ctk.CTkFrame):

    def __init__(self, master, on_generate: Optional[Callable] = None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_generate = on_generate

        self._voice_var    = tk.StringVar(value="Natural Female")
        self._emotion_var  = tk.StringVar(value="Neutral")
        self._speed_var    = tk.DoubleVar(value=1.0)
        self._lang_var     = tk.StringVar(value="English")
        self._fmt_var      = tk.StringVar(value="wav")
        self._folder_var   = tk.StringVar(value=str(Path.home() / "Desktop"))
        self._ref_wav_var  = tk.StringVar(value="")

        self._clone_card: Optional[ctk.CTkFrame] = None
        self._build()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["scrollbar"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.columnconfigure(0, weight=1)

        row = 0

        # ── Header ──────────────────────────────────────────────────────────
        ctk.CTkLabel(
            scroll, text="Settings",
            font=ctk.CTkFont(*FONTS["h2"]),
            text_color=COLORS["text_sub"],
            anchor="w",
        ).grid(row=row, column=0, sticky="w", pady=(0, PAD["md"])); row += 1

        # ── Voice ────────────────────────────────────────────────────────────
        row = self._field(scroll, row, "Voice Profile")
        ctk.CTkOptionMenu(
            scroll,
            values=list(VOICE_PROFILES.keys()),
            variable=self._voice_var,
            **self._om_style(),
            command=self._voice_changed,
        ).grid(row=row, column=0, sticky="ew", pady=(0, PAD["md"])); row += 1

        # Clone card (hidden by default)
        self._clone_card = self._build_clone_card(scroll)
        self._clone_card.grid(row=row, column=0, sticky="ew", pady=(0, PAD["md"]))
        self._clone_card.grid_remove()
        row += 1

        # ── Emotion ──────────────────────────────────────────────────────────
        row = self._field(scroll, row, "Delivery Style")
        ctk.CTkOptionMenu(
            scroll,
            values=list(EMOTION_PREFIXES.keys()),
            variable=self._emotion_var,
            **self._om_style(),
        ).grid(row=row, column=0, sticky="ew", pady=(0, PAD["md"])); row += 1

        # ── Speed ────────────────────────────────────────────────────────────
        row = self._field(scroll, row, "Speaking Speed")
        speed_wrap = ctk.CTkFrame(scroll, fg_color="transparent")
        speed_wrap.grid(row=row, column=0, sticky="ew", pady=(0, PAD["md"])); row += 1
        speed_wrap.columnconfigure(0, weight=1)

        self._speed_val = ctk.CTkLabel(
            speed_wrap,
            text="1.0×",
            font=ctk.CTkFont(*FONTS["caption_med"]),
            text_color=COLORS["accent_2"],
            width=36,
        )
        self._speed_val.grid(row=0, column=1, padx=(PAD["sm"], 0))

        ctk.CTkSlider(
            speed_wrap,
            from_=0.5, to=2.0, number_of_steps=30,
            variable=self._speed_var,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent"],
            fg_color=COLORS["border"],
            command=lambda v: self._speed_val.configure(text=f"{v:.1f}×"),
        ).grid(row=0, column=0, sticky="ew")

        tick_row = ctk.CTkFrame(speed_wrap, fg_color="transparent")
        tick_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        tick_row.columnconfigure(1, weight=1)
        for txt, col in [("0.5×", 0), ("1.0×", 1), ("2.0×", 2)]:
            anchor = ["w", "center", "e"][col]
            ctk.CTkLabel(tick_row, text=txt,
                         font=ctk.CTkFont(*FONTS["tiny"]),
                         text_color=COLORS["text_muted"],
                         anchor=anchor,
                         ).grid(row=0, column=col, sticky="ew")
        tick_row.columnconfigure(1, weight=1)

        # ── Language ─────────────────────────────────────────────────────────
        row = self._field(scroll, row, "Language")
        ctk.CTkOptionMenu(
            scroll,
            values=list(LANGUAGE_CODES.keys()),
            variable=self._lang_var,
            **self._om_style(),
        ).grid(row=row, column=0, sticky="ew", pady=(0, PAD["md"])); row += 1

        # ── Format ───────────────────────────────────────────────────────────
        row = self._field(scroll, row, "Output Format")
        fmt_row = ctk.CTkFrame(scroll, fg_color="transparent")
        fmt_row.grid(row=row, column=0, sticky="ew", pady=(0, PAD["md"])); row += 1

        for fmt in ("wav", "mp3"):
            ctk.CTkRadioButton(
                fmt_row,
                text=fmt.upper(), value=fmt,
                variable=self._fmt_var,
                font=ctk.CTkFont(*FONTS["body"]),
                text_color=COLORS["text"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                border_color=COLORS["border"],
            ).pack(side="left", padx=(0, PAD["xl"]))

        # ── Output folder ─────────────────────────────────────────────────────
        row = self._field(scroll, row, "Output Folder")
        folder_wrap = ctk.CTkFrame(scroll, fg_color="transparent")
        folder_wrap.grid(row=row, column=0, sticky="ew", pady=(0, PAD["lg"])); row += 1
        folder_wrap.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            folder_wrap,
            textvariable=self._folder_var,
            font=ctk.CTkFont(*FONTS["tiny"]),
            text_color=COLORS["text_muted"],
            anchor="w",
            wraplength=240,
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            folder_wrap, text="Change…",
            width=74, height=26,
            font=ctk.CTkFont(*FONTS["btn_sm"]),
            fg_color=COLORS["card"],
            hover_color=COLORS["accent_dim"],
            text_color=COLORS["text_sub"],
            border_width=1, border_color=COLORS["border"],
            corner_radius=6,
            command=self._pick_folder,
        ).grid(row=0, column=1, padx=(PAD["sm"], 0))

        # Divider
        ctk.CTkFrame(scroll, height=1, fg_color=COLORS["border"]
                     ).grid(row=row, column=0, sticky="ew", pady=(0, PAD["lg"])); row += 1

        # ── Generate ─────────────────────────────────────────────────────────
        self._gen_btn = ctk.CTkButton(
            scroll,
            text="✦   Generate Audio",
            font=ctk.CTkFont(*FONTS["generate"]),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#ffffff",
            corner_radius=8,
            height=50,
            command=self._handle_generate,
        )
        self._gen_btn.grid(row=row, column=0, sticky="ew", pady=(0, PAD["xl"]))

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _field(self, parent, row: int, label: str) -> int:
        ctk.CTkLabel(
            parent, text=label,
            font=ctk.CTkFont(*FONTS["caption_med"]),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=row, column=0, sticky="w", pady=(0, 4))
        return row + 1

    def _om_style(self) -> dict:
        return dict(
            font=ctk.CTkFont(*FONTS["body"]),
            fg_color=COLORS["card"],
            button_color=COLORS["card_hover"],
            button_hover_color=COLORS["accent_dim"],
            text_color=COLORS["text"],
            dropdown_fg_color=COLORS["card"],
            dropdown_text_color=COLORS["text"],
            dropdown_hover_color=COLORS["card_hover"],
            corner_radius=6,
            height=36,
        )

    def _build_clone_card(self, parent) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="Voice Clone Reference",
            font=ctk.CTkFont(*FONTS["caption_med"]),
            text_color=COLORS["accent_2"],
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w",
               padx=PAD["md"], pady=(PAD["sm"], 2))

        ctk.CTkLabel(
            card, text="Upload 6–30 sec of clean speech to clone that voice",
            font=ctk.CTkFont(*FONTS["tiny"]),
            text_color=COLORS["text_muted"],
            anchor="w",
            wraplength=260,
        ).grid(row=1, column=0, columnspan=2, sticky="w",
               padx=PAD["md"], pady=(0, PAD["sm"]))

        self._ref_label = ctk.CTkLabel(
            card, text="No file selected",
            font=ctk.CTkFont(*FONTS["tiny"]),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self._ref_label.grid(row=2, column=0, sticky="ew", padx=PAD["md"])

        ctk.CTkButton(
            card, text="Browse…",
            width=72, height=26,
            font=ctk.CTkFont(*FONTS["btn_sm"]),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#ffffff",
            corner_radius=6,
            command=self._pick_ref_wav,
        ).grid(row=2, column=1, padx=PAD["md"], pady=(0, PAD["sm"]))

        return card

    # ── Public ───────────────────────────────────────────────────────────────

    def get_settings(self) -> Dict[str, Any]:
        ref = self._ref_wav_var.get()
        return {
            "voice_profile": self._voice_var.get(),
            "emotion":       self._emotion_var.get(),
            "speed":         round(self._speed_var.get(), 2),
            "language":      self._lang_var.get(),
            "output_format": self._fmt_var.get(),
            "output_folder": self._folder_var.get(),
            "reference_wav": ref if ref else None,
        }

    def load_settings(self, s: Dict[str, Any]):
        if "voice_profile" in s:
            self._voice_var.set(s["voice_profile"])
            self._voice_changed(s["voice_profile"])
        if "emotion"  in s: self._emotion_var.set(s["emotion"])
        if "speed"    in s:
            self._speed_var.set(float(s["speed"]))
            self._speed_val.configure(text=f"{float(s['speed']):.1f}×")
        if "language" in s: self._lang_var.set(s["language"])
        if "output_format" in s: self._fmt_var.set(s["output_format"])
        if "output_folder" in s and s["output_folder"]:
            self._folder_var.set(s["output_folder"])
        if "reference_wav" in s and s["reference_wav"]:
            self._ref_wav_var.set(s["reference_wav"])
            self._ref_label.configure(text=Path(s["reference_wav"]).name)

    def set_generating(self, active: bool):
        if active:
            self._gen_btn.configure(
                text="⏳   Generating…",
                state="disabled",
                fg_color=COLORS["text_muted"],
            )
        else:
            self._gen_btn.configure(
                text="✦   Generate Audio",
                state="normal",
                fg_color=COLORS["accent"],
            )

    # ── Callbacks ────────────────────────────────────────────────────────────

    def _voice_changed(self, v: str):
        if v == "Custom Voice Clone":
            self._clone_card.grid()
        else:
            self._clone_card.grid_remove()

    def _pick_folder(self):
        d = filedialog.askdirectory(title="Output Folder", initialdir=self._folder_var.get())
        if d:
            self._folder_var.set(d)

    def _pick_ref_wav(self):
        p = filedialog.askopenfilename(
            title="Reference WAV",
            filetypes=[("WAV", "*.wav"), ("All", "*.*")],
        )
        if p:
            self._ref_wav_var.set(p)
            self._ref_label.configure(text=Path(p).name)

    def _handle_generate(self):
        if self._on_generate:
            self._on_generate()
