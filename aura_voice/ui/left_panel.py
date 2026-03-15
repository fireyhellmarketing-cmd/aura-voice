"""
AURA VOICE — Left panel: script input.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk

from assets.styles import COLORS, FONTS, PAD
from core.audio_utils import estimate_duration_minutes, format_duration
from core.project_manager import load_project

_PLACEHOLDER = "Paste your script here, or load a .txt file…"


class LeftPanel(ctk.CTkFrame):

    def __init__(self, master, on_project_loaded: Optional[Callable] = None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_project_loaded = on_project_loaded
        self._placeholder_active = True
        self._build()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, PAD["sm"]))
        hdr.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="Script",
            font=ctk.CTkFont(*FONTS["h2"]),
            text_color=COLORS["text_sub"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._stats = ctk.CTkLabel(
            hdr, text="0 words",
            font=ctk.CTkFont(*FONTS["caption"]),
            text_color=COLORS["text_muted"],
        )
        self._stats.grid(row=0, column=1)

        # ── Text box ─────────────────────────────────────────────────────────
        box = ctk.CTkFrame(
            self,
            fg_color=COLORS["card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
        )
        box.grid(row=1, column=0, sticky="nsew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)

        self._tb = ctk.CTkTextbox(
            box,
            font=ctk.CTkFont(*FONTS["mono"]),
            text_color=COLORS["text_muted"],
            fg_color=COLORS["card"],
            wrap="word",
            border_width=0,
            scrollbar_button_color=COLORS["scrollbar"],
            scrollbar_button_hover_color=COLORS["accent"],
            activate_scrollbars=True,
        )
        self._tb.grid(row=0, column=0, sticky="nsew", padx=PAD["md"], pady=PAD["md"])
        self._tb.insert("0.0", _PLACEHOLDER)
        self._tb.bind("<FocusIn>",  self._clear_ph)
        self._tb.bind("<FocusOut>", self._restore_ph)
        self._tb.bind("<KeyRelease>", lambda _: self._update_stats())

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", pady=(PAD["sm"], 0))
        btn_row.columnconfigure((0, 1), weight=1)

        self._mk_btn(btn_row, "↑  Load .txt", self._load_txt).grid(
            row=0, column=0, sticky="ew", padx=(0, PAD["xs"]))
        self._mk_btn(btn_row, "⬡  Load .auravoice", self._load_av).grid(
            row=0, column=1, sticky="ew", padx=(PAD["xs"], 0))

    def _mk_btn(self, parent, label, cmd):
        return ctk.CTkButton(
            parent, text=label,
            font=ctk.CTkFont(*FONTS["btn_sm"]),
            fg_color=COLORS["card"],
            hover_color=COLORS["card_hover"],
            text_color=COLORS["text_sub"],
            border_width=1, border_color=COLORS["border"],
            corner_radius=6, height=32,
            command=cmd,
        )

    # ── Public ───────────────────────────────────────────────────────────────

    def get_text(self) -> str:
        if self._placeholder_active:
            return ""
        return self._tb.get("0.0", "end").strip()

    def set_text(self, text: str):
        self._placeholder_active = False
        self._tb.configure(text_color=COLORS["text"])
        self._tb.delete("0.0", "end")
        self._tb.insert("0.0", text)
        self._update_stats()

    def clear(self):
        self._tb.delete("0.0", "end")
        self._restore_ph(None)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _update_stats(self):
        t = self._tb.get("0.0", "end").strip()
        wc = len(t.split()) if t else 0
        dur = format_duration(estimate_duration_minutes(wc))
        self._stats.configure(text=f"{wc:,} words · ~{dur}")

    def _clear_ph(self, _):
        if self._placeholder_active:
            self._tb.delete("0.0", "end")
            self._tb.configure(text_color=COLORS["text"])
            self._placeholder_active = False

    def _restore_ph(self, _):
        if not self._tb.get("0.0", "end").strip():
            self._tb.insert("0.0", _PLACEHOLDER)
            self._tb.configure(text_color=COLORS["text_muted"])
            self._placeholder_active = True
            self._stats.configure(text="0 words")

    def _load_txt(self):
        p = filedialog.askopenfilename(
            title="Load Script",
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
        )
        if not p:
            return
        try:
            self.set_text(Path(p).read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            messagebox.showerror("AURA VOICE", str(e))

    def _load_av(self):
        p = filedialog.askopenfilename(
            title="Open Project",
            filetypes=[("AURA VOICE", "*.auravoice"), ("All", "*.*")],
        )
        if not p:
            return
        try:
            script, settings = load_project(Path(p))
            self.set_text(script)
            if self._on_project_loaded:
                self._on_project_loaded(script, settings)
        except Exception as e:
            messagebox.showerror("AURA VOICE", str(e))
