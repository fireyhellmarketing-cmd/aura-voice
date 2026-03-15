"""AURA VOICE v3 — Slide-in settings sheet (right overlay)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

from assets.styles import (
    APP_VERSION,
    BG_DEEP, SURFACE, SURFACE2, ACCENT, ACCENT_HOV, BORDER, BORDER2,
    TEXT, TEXT_SUB, TEXT_DIM,
    ACCENT_DIM, ACCENT_PRESETS,
    FONTS, PAD, RADIUS,
    SUCCESS, SUCCESS_BG, WARNING,
)
from core.model_manager import MODEL_CATALOG, is_model_downloaded, load_config, save_config


# ─── Sheet Background Color ────────────────────────────────────────────────────
_SHEET_BG  = "#0E0C18"
_SHEET_W   = 360
_SLIDE_MS  = 250
_SLIDE_STEPS = 15


class SettingsSheet(ctk.CTkFrame):
    """
    Full-height slide-in panel anchored to the right side of the window.
    Uses place() for positioning. Animates via after() loops.
    """

    def __init__(
        self,
        parent: ctk.CTk,
        config: dict,
        on_close: Optional[Callable] = None,
        on_config_change: Optional[Callable[[dict], None]] = None,
        **kwargs,
    ):
        super().__init__(
            parent,
            fg_color=_SHEET_BG,
            corner_radius=0,
            border_color=BORDER,
            border_width=1,
            width=_SHEET_W,
            **kwargs,
        )

        self._parent           = parent
        self.config            = dict(config)
        self._on_close         = on_close
        self._on_config_change = on_config_change

        self._visible    = False
        self._animating  = False

        self._speed_var  = ctk.DoubleVar(value=float(self.config.get("speed", 1.0)))
        self._format_var = ctk.StringVar(value=self.config.get("output_format", "WAV"))
        self._accent_var = ctk.StringVar(value=self.config.get("accent_color", "#7c3aed"))
        self._autoplay_var = ctk.BooleanVar(value=self.config.get("auto_play", False))
        self._history_var  = ctk.BooleanVar(value=self.config.get("save_history", True))

        self._build()

        # Start hidden off-screen right
        parent.update_idletasks()
        win_w = parent.winfo_width()
        self.place(x=win_w, y=0, relheight=1.0)
        self.lift()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Header ──
        header = ctk.CTkFrame(self, fg_color="transparent", height=52)
        header.pack(fill="x", padx=PAD["xl"])
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Settings",
            font=(FONTS["lg_bold"][0], 16, "bold"),
            text_color=TEXT,
        ).pack(side="left", pady=12)

        ctk.CTkButton(
            header,
            text="×",
            width=28, height=28,
            fg_color="transparent",
            hover_color=BORDER2,
            text_color=TEXT_DIM,
            corner_radius=14,
            font=(FONTS["base"][0], 16, "bold"),
            command=self.close,
        ).pack(side="right", pady=12)

        # Separator
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x")

        # ── Scrollable content ──
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=BORDER2,
            scrollbar_button_hover_color=BORDER,
        )
        self._scroll.pack(fill="both", expand=True, padx=0, pady=0)

        self._build_model_section()
        self._build_output_section()
        self._build_speed_section()
        self._build_accent_section()
        self._build_toggles_section()
        self._build_footer()

    # ── Section: Voice Model ───────────────────────────────────────────────────

    def _build_model_section(self):
        self._section_label("Voice Model")

        current = self.config.get("selected_model", "VCTK VITS — Fast English (Default)")
        spec     = MODEL_CATALOG.get(current, {})
        dl       = is_model_downloaded(spec.get("model_id", ""))

        model_card = ctk.CTkFrame(
            self._scroll,
            fg_color=SURFACE,
            corner_radius=RADIUS["md"],
            border_color=BORDER2,
            border_width=1,
        )
        model_card.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["sm"]))

        inner = ctk.CTkFrame(model_card, fg_color="transparent")
        inner.pack(fill="x", padx=PAD["md"], pady=PAD["md"])

        ctk.CTkLabel(
            inner,
            text=current,
            font=FONTS["sm_bold"],
            text_color=TEXT,
            anchor="w",
            wraplength=220,
        ).pack(anchor="w")

        badge_text  = "  ✓ Ready  " if dl else "  ⚠ Not Downloaded  "
        badge_color = SUCCESS if dl else WARNING
        badge_bg    = SUCCESS_BG if dl else "#451a03"

        ctk.CTkLabel(
            inner,
            text=badge_text,
            font=FONTS["xs_bold"],
            text_color=badge_color,
            fg_color=badge_bg,
            corner_radius=RADIUS["full"],
        ).pack(anchor="w", pady=(4, 0))

        ctk.CTkButton(
            model_card,
            text="Change Model",
            height=30,
            fg_color="transparent",
            hover_color=BORDER2,
            text_color=TEXT_SUB,
            border_color=BORDER2,
            border_width=1,
            corner_radius=RADIUS["md"],
            font=FONTS["sm"],
            command=self._open_model_selector,
        ).pack(fill="x", padx=PAD["md"], pady=(0, PAD["md"]))

    def _open_model_selector(self):
        """Show a proper CTkToplevel model picker dialog."""
        win = ctk.CTkToplevel(self._parent)
        win.title("Change Voice Model")
        win.geometry("500x520")
        win.resizable(False, True)
        win.configure(fg_color=BG_DEEP)
        win.grab_set()
        win.focus_set()

        # Header
        hdr = ctk.CTkFrame(win, fg_color=SURFACE, corner_radius=0, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr,
            text="Change Voice Model",
            font=(FONTS["lg_bold"][0], 15, "bold"),
            text_color=TEXT,
        ).pack(side="left", padx=PAD["xl"], pady=12)

        ctk.CTkFrame(win, fg_color=BORDER, height=1).pack(fill="x")

        # Scrollable model list
        scroll = ctk.CTkScrollableFrame(
            win,
            fg_color="transparent",
            scrollbar_button_color=BORDER2,
            scrollbar_button_hover_color=BORDER,
        )
        scroll.pack(fill="both", expand=True, padx=PAD["xl"], pady=PAD["md"])

        current = self.config.get("selected_model", "")

        for name, spec in MODEL_CATALOG.items():
            dl = is_model_downloaded(spec.get("model_id", ""))
            size_str = f"{spec.get('size_gb', 0):.2f} GB"
            is_current = (name == current)

            row = ctk.CTkFrame(
                scroll,
                fg_color=SURFACE if not is_current else "#1E2A1E",
                corner_radius=RADIUS["md"],
                border_color=SUCCESS if is_current else BORDER2,
                border_width=1,
            )
            row.pack(fill="x", pady=(0, PAD["sm"]))

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, padx=PAD["md"], pady=PAD["md"])

            ctk.CTkLabel(
                info,
                text=name,
                font=FONTS["sm_bold"],
                text_color=TEXT,
                anchor="w",
                wraplength=260,
            ).pack(anchor="w")

            meta_row = ctk.CTkFrame(info, fg_color="transparent")
            meta_row.pack(anchor="w", pady=(3, 0))

            ctk.CTkLabel(
                meta_row,
                text=f"  {size_str}  ",
                font=FONTS["xs"],
                text_color=TEXT_DIM,
                fg_color=BORDER,
                corner_radius=RADIUS["full"],
            ).pack(side="left", padx=(0, 4))

            badge_text  = "  ✓ Downloaded  " if dl else "  ⬇ Not Downloaded  "
            badge_color = SUCCESS if dl else WARNING
            badge_bg    = SUCCESS_BG if dl else "#451a03"
            ctk.CTkLabel(
                meta_row,
                text=badge_text,
                font=FONTS["xs_bold"],
                text_color=badge_color,
                fg_color=badge_bg,
                corner_radius=RADIUS["full"],
            ).pack(side="left")

            btn_col = ctk.CTkFrame(row, fg_color="transparent")
            btn_col.pack(side="right", padx=PAD["md"], pady=PAD["md"])

            if is_current:
                ctk.CTkLabel(
                    btn_col,
                    text="  Active  ",
                    font=FONTS["xs_bold"],
                    text_color=SUCCESS,
                    fg_color=SUCCESS_BG,
                    corner_radius=RADIUS["full"],
                ).pack()
            else:
                def _select(n=name, w=win):
                    self.config["selected_model"] = n
                    save_config(self.config)
                    self._emit_change()
                    w.destroy()

                ctk.CTkButton(
                    btn_col,
                    text="Select",
                    width=64, height=28,
                    fg_color=SURFACE2,
                    hover_color="#2A2A2A",
                    text_color=TEXT_SUB,
                    border_color=BORDER2,
                    border_width=1,
                    corner_radius=RADIUS["md"],
                    font=FONTS["sm"],
                    command=_select,
                ).pack()

        # Footer note
        ctk.CTkFrame(win, fg_color=BORDER, height=1).pack(fill="x", padx=PAD["xl"])
        ctk.CTkLabel(
            win,
            text="Close and reopen the app to load the new model.",
            font=FONTS["xs"],
            text_color=TEXT_DIM,
        ).pack(pady=PAD["md"])

    # ── Section: Output ────────────────────────────────────────────────────────

    def _build_output_section(self):
        self._section_label("Output")

        folder_row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        folder_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["sm"]))

        out_dir = self.config.get("output_dir", str(Path.home() / "Documents" / "AuraVoice"))
        short   = out_dir
        if len(short) > 28:
            home = str(Path.home())
            if short.startswith(home):
                short = "~" + short[len(home):]
            if len(short) > 28:
                short = "…" + short[-27:]

        self._folder_label = ctk.CTkLabel(
            folder_row,
            text=short,
            font=FONTS["xs"],
            text_color=TEXT_SUB,
            anchor="w",
        )
        self._folder_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            folder_row,
            text="Change",
            width=62, height=26,
            fg_color="transparent",
            hover_color=BORDER2,
            text_color=TEXT_SUB,
            border_color=BORDER2,
            border_width=1,
            corner_radius=RADIUS["md"],
            font=FONTS["xs"],
            command=self._browse_output_folder,
        ).pack(side="right")

        # Format pills
        fmt_row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        fmt_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["sm"]))

        for fmt in ["WAV", "MP3"]:
            ctk.CTkRadioButton(
                fmt_row,
                text=fmt,
                variable=self._format_var,
                value=fmt,
                font=FONTS["sm"],
                text_color=TEXT_SUB,
                fg_color=ACCENT,
                hover_color=ACCENT_HOV,
            ).pack(side="left", padx=(0, 20))

    def _browse_output_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.config.get("output_dir", str(Path.home())),
        )
        if folder:
            self.config["output_dir"] = folder
            short = folder
            home  = str(Path.home())
            if short.startswith(home):
                short = "~" + short[len(home):]
            if len(short) > 28:
                short = "…" + short[-27:]
            self._folder_label.configure(text=short)
            self._emit_change()

    # ── Section: Speed Fine-tune ───────────────────────────────────────────────

    def _build_speed_section(self):
        self._section_label("Speed Fine-tune")

        speed_row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        speed_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["sm"]))

        slider = ctk.CTkSlider(
            speed_row,
            from_=0.5, to=2.0,
            variable=self._speed_var,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOV,
            progress_color=ACCENT,
            fg_color=BORDER2,
            command=lambda v: speed_val.configure(text=f"{v:.2f}×"),
        )
        slider.pack(side="left", fill="x", expand=True)

        speed_val = ctk.CTkLabel(
            speed_row,
            text=f"{self._speed_var.get():.2f}×",
            font=FONTS["xs"],
            text_color=TEXT_SUB,
            width=42,
        )
        speed_val.pack(side="right", padx=(6, 0))

    # ── Section: Accent Color ──────────────────────────────────────────────────

    def _build_accent_section(self):
        self._section_label("Accent Color")

        swatch_row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        swatch_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["sm"]))

        self._swatch_btns: list[ctk.CTkButton] = []

        for hex_color, color_name in ACCENT_PRESETS:
            is_active = (hex_color == self._accent_var.get())
            btn = ctk.CTkButton(
                swatch_row,
                text="✓" if is_active else "",
                width=28, height=28,
                fg_color=hex_color,
                hover_color=hex_color,
                text_color="#FFFFFF",
                corner_radius=14,
                font=FONTS["xs_bold"],
                command=lambda h=hex_color: self._select_accent(h),
            )
            btn.pack(side="left", padx=(0, 6))
            self._swatch_btns.append(btn)

    def _select_accent(self, hex_color: str):
        self._accent_var.set(hex_color)
        for btn, (h, _) in zip(self._swatch_btns, ACCENT_PRESETS):
            btn.configure(text="✓" if h == hex_color else "")
        self.config["accent_color"] = hex_color
        self._emit_change()

    # ── Section: Toggles ──────────────────────────────────────────────────────

    def _build_toggles_section(self):
        self._section_label("Toggles")

        switch_kw = dict(
            font=FONTS["sm"],
            text_color=TEXT_SUB,
            fg_color=BORDER2,
            progress_color=ACCENT,
            button_color=ACCENT_HOV,
            button_hover_color=ACCENT,
        )

        ctk.CTkSwitch(
            self._scroll,
            text="Auto-play after generation",
            variable=self._autoplay_var,
            command=self._emit_change,
            **switch_kw,
        ).pack(anchor="w", padx=PAD["xl"], pady=(0, PAD["sm"]))

        ctk.CTkSwitch(
            self._scroll,
            text="Save history",
            variable=self._history_var,
            command=self._emit_change,
            **switch_kw,
        ).pack(anchor="w", padx=PAD["xl"], pady=(0, PAD["lg"]))

    # ── Footer ────────────────────────────────────────────────────────────────

    def _build_footer(self):
        ctk.CTkFrame(self._scroll, fg_color=BORDER, height=1).pack(
            fill="x", padx=PAD["xl"], pady=(PAD["sm"], PAD["md"])
        )
        ctk.CTkLabel(
            self._scroll,
            text=f"AURA VOICE  v{APP_VERSION}",
            font=(FONTS["xs"][0], 11),
            text_color=TEXT_DIM,
        ).pack(anchor="w", padx=PAD["xl"], pady=(0, PAD["lg"]))

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _section_label(self, text: str):
        ctk.CTkLabel(
            self._scroll,
            text=text.upper(),
            font=FONTS["xs_bold"],
            text_color=TEXT_DIM,
        ).pack(anchor="w", padx=PAD["xl"], pady=(PAD["xl"], PAD["sm"]))

    def _emit_change(self):
        self.config["speed"]          = round(self._speed_var.get(), 2)
        self.config["output_format"]  = self._format_var.get()
        self.config["auto_play"]      = self._autoplay_var.get()
        self.config["save_history"]   = self._history_var.get()
        save_config(self.config)
        if self._on_config_change:
            self._on_config_change(self.config)

    # ── Animation ─────────────────────────────────────────────────────────────

    def open(self):
        if self._visible or self._animating:
            return
        self._animating = True
        self._visible   = True

        self._parent.update_idletasks()
        win_w   = self._parent.winfo_width()
        start_x = win_w
        end_x   = win_w - _SHEET_W

        # Ensure it's placed and visible
        self.place(x=start_x, y=0, relheight=1.0)
        self.lift()

        step    = (start_x - end_x) / _SLIDE_STEPS
        delay   = _SLIDE_MS // _SLIDE_STEPS

        def _step(current_x: float, step_num: int):
            new_x = current_x - step
            self.place(x=int(new_x), y=0, relheight=1.0)
            if step_num < _SLIDE_STEPS:
                self.after(delay, lambda: _step(new_x, step_num + 1))
            else:
                self.place(x=end_x, y=0, relheight=1.0)
                self._animating = False

        _step(float(start_x), 1)

    def close(self):
        if not self._visible or self._animating:
            return
        self._animating = True

        self._parent.update_idletasks()
        win_w   = self._parent.winfo_width()
        start_x = win_w - _SHEET_W
        end_x   = win_w

        step  = (end_x - start_x) / _SLIDE_STEPS
        delay = _SLIDE_MS // _SLIDE_STEPS

        def _step(current_x: float, step_num: int):
            new_x = current_x + step
            self.place(x=int(new_x), y=0, relheight=1.0)
            if step_num < _SLIDE_STEPS:
                self.after(delay, lambda: _step(new_x, step_num + 1))
            else:
                self.place_forget()
                self._visible   = False
                self._animating = False
                if self._on_close:
                    self._on_close()

        self._emit_change()
        _step(float(start_x), 1)

    def is_open(self) -> bool:
        return self._visible

    def update_config(self, new_config: dict):
        self.config.update(new_config)
