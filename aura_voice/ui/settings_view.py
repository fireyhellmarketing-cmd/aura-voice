"""AURA VOICE — Settings panel view."""

import os
import json
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

from assets.styles import (
    APP_NAME, APP_VERSION,
    BG, PANEL, CARD, CARD_HOVER, INPUT_BG,
    ACCENT, ACCENT_HOVER, ACCENT_DIM,
    ACCENT2,
    TEXT, TEXT_SUB, TEXT_MUTED,
    BORDER, BORDER_LIGHT,
    SUCCESS, SUCCESS_BG, WARNING, ERROR, ERROR_BG,
    FONTS, PAD, RADIUS, ACCENT_PRESETS,
    btn_primary, btn_secondary, btn_ghost, card_frame, input_field,
)
from core.model_manager import (
    MODEL_CATALOG, is_model_downloaded,
    load_config, save_config,
)


# ─── Accordion section ─────────────────────────────────────────────────────────

class _AccordionSection(ctk.CTkFrame):
    """A collapsible accordion section with a title bar and content frame."""

    def __init__(self, parent, title: str, expanded: bool = True, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._expanded = expanded

        # Header row
        self._header = ctk.CTkFrame(
            self, fg_color=CARD, corner_radius=RADIUS["md"],
        )
        self._header.pack(fill="x", pady=(0, 2))

        self._title_label = ctk.CTkLabel(
            self._header,
            text=title,
            font=FONTS["md_bold"],
            text_color=TEXT,
        )
        self._title_label.pack(side="left", padx=PAD["xl"], pady=PAD["lg"])

        self._toggle_btn = ctk.CTkButton(
            self._header,
            text="▲" if expanded else "▼",
            width=32, height=28,
            **{**btn_ghost(), "font": FONTS["sm"]},
            command=self._toggle,
        )
        self._toggle_btn.pack(side="right", padx=PAD["md"])

        # Content
        self.content = ctk.CTkFrame(self, fg_color=CARD, corner_radius=RADIUS["md"])
        if expanded:
            self.content.pack(fill="x", pady=(0, PAD["md"]))

        # Make header clickable
        for w in [self._header, self._title_label]:
            w.bind("<Button-1>", lambda e: self._toggle())

    def _toggle(self):
        self._expanded = not self._expanded
        self._toggle_btn.configure(text="▲" if self._expanded else "▼")
        if self._expanded:
            self.content.pack(fill="x", pady=(0, PAD["md"]))
        else:
            self.content.pack_forget()


# ─── Settings View ─────────────────────────────────────────────────────────────

class SettingsView(ctk.CTkFrame):
    """Full settings panel that replaces the output panel when navigated to."""

    def __init__(
        self,
        parent,
        config: dict,
        on_config_change: Optional[Callable[[dict], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, fg_color=BG, corner_radius=0, **kwargs)

        self.config          = dict(config)
        self.on_config_change = on_config_change

        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # Page header
        header = ctk.CTkFrame(self, fg_color="transparent", height=56)
        header.pack(fill="x", padx=PAD["page"], pady=(PAD["xl"], 0))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Settings",
            font=FONTS["2xl_bold"],
            text_color=TEXT,
        ).pack(side="left", pady=8)

        ctk.CTkButton(
            header,
            text="Save Changes",
            width=130, height=36,
            **btn_primary(),
            command=self._save_all,
        ).pack(side="right")

        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x", padx=PAD["page"])

        # Scrollable content
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=BORDER_LIGHT,
        )
        self._scroll.pack(fill="both", expand=True, padx=PAD["page"], pady=PAD["md"])

        self._build_output_section()
        self._build_model_section()
        self._build_audio_quality_section()
        self._build_appearance_section()
        self._build_about_section()

    # ── Output Settings ────────────────────────────────────────────────────────

    def _build_output_section(self):
        sec = _AccordionSection(self._scroll, "Output Settings", expanded=True)
        sec.pack(fill="x", pady=(0, PAD["md"]))
        c = sec.content

        # Default output folder
        self._row_label(c, "Default Output Folder")
        folder_row = ctk.CTkFrame(c, fg_color="transparent")
        folder_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))

        self._output_folder_label = ctk.CTkLabel(
            folder_row,
            text=self.config.get("output_dir", str(Path.home() / "Documents" / "AuraVoice")),
            font=FONTS["mono_sm"],
            text_color=TEXT_SUB,
            anchor="w",
        )
        self._output_folder_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            folder_row,
            text="Browse",
            width=80, height=30,
            **btn_secondary(),
            command=self._browse_output_folder,
        ).pack(side="right")

        # Filename pattern
        self._row_label(c, "Filename Pattern")
        self._filename_entry = ctk.CTkEntry(
            c,
            placeholder_text="aura_voice_{date}_{time}",
            **input_field(),
            height=34,
        )
        self._filename_entry.pack(fill="x", padx=PAD["xl"], pady=(0, 4))
        self._filename_entry.insert(
            0, self.config.get("filename_pattern", "aura_voice_{date}_{time}")
        )
        ctk.CTkLabel(
            c,
            text="Available tokens: {date} {time} {voice} {title}",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=PAD["xl"], pady=(0, PAD["md"]))

        # Auto-open toggle
        self._auto_open_var = ctk.BooleanVar(
            value=self.config.get("auto_open_folder", False)
        )
        ctk.CTkCheckBox(
            c,
            text="Auto-open output folder after generation",
            variable=self._auto_open_var,
            font=FONTS["base"],
            text_color=TEXT_SUB,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            checkmark_color=TEXT,
        ).pack(anchor="w", padx=PAD["xl"], pady=(0, PAD["xl"]))

    def _browse_output_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Select Default Output Folder",
            initialdir=self.config.get("output_dir", str(Path.home())),
        )
        if folder:
            self.config["output_dir"] = folder
            self._output_folder_label.configure(text=folder)

    # ── Model Settings ─────────────────────────────────────────────────────────

    def _build_model_section(self):
        sec = _AccordionSection(self._scroll, "Model Settings", expanded=True)
        sec.pack(fill="x", pady=(0, PAD["md"]))
        c = sec.content

        # Current model display
        current = self.config.get("selected_model", "XTTS v2 — Multilingual Pro")
        spec    = MODEL_CATALOG.get(current, {})
        downloaded = is_model_downloaded(spec.get("model_id", ""))
        device  = self.config.get("device", "cpu").upper()

        current_row = ctk.CTkFrame(c, fg_color=CARD_HOVER, corner_radius=RADIUS["md"])
        current_row.pack(fill="x", padx=PAD["xl"], pady=(PAD["md"], 0))

        left = ctk.CTkFrame(current_row, fg_color="transparent")
        left.pack(side="left", padx=PAD["md"], pady=PAD["md"])

        ctk.CTkLabel(
            left, text=current,
            font=FONTS["base_bold"], text_color=TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            left,
            text=spec.get("quality_label", "★★★★★") + f"  {spec.get('size_gb', 0):.2f} GB",
            font=FONTS["sm"], text_color=TEXT_MUTED,
        ).pack(anchor="w")

        # Status badge
        badge_text  = "  ✓ Ready  " if downloaded else "  ⬇ Not Downloaded  "
        badge_color = SUCCESS if downloaded else WARNING
        badge_bg    = SUCCESS_BG if downloaded else "#451a03"

        ctk.CTkLabel(
            current_row,
            text=badge_text,
            font=FONTS["xs_bold"],
            text_color=badge_color,
            fg_color=badge_bg,
            corner_radius=RADIUS["full"],
        ).pack(side="right", padx=PAD["md"])

        # Device chip
        device_row = ctk.CTkFrame(c, fg_color="transparent")
        device_row.pack(fill="x", padx=PAD["xl"], pady=(PAD["sm"], 0))

        ctk.CTkLabel(
            device_row,
            text="Running on:",
            font=FONTS["sm"], text_color=TEXT_MUTED,
        ).pack(side="left")

        ctk.CTkLabel(
            device_row,
            text=f"  {device}  ",
            font=FONTS["sm_bold"],
            text_color=ACCENT,
            fg_color=ACCENT_DIM,
            corner_radius=RADIUS["full"],
        ).pack(side="left", padx=PAD["sm"])

        # Available models list
        self._row_label(c, "Available Models")

        for name, mspec in MODEL_CATALOG.items():
            self._build_model_row(c, name, mspec)

    def _build_model_row(self, parent, name: str, spec: dict):
        downloaded = is_model_downloaded(spec["model_id"])
        is_active  = name == self.config.get("selected_model")

        row = ctk.CTkFrame(
            parent,
            fg_color=CARD_HOVER if is_active else "transparent",
            corner_radius=RADIUS["md"],
        )
        row.pack(fill="x", padx=PAD["xl"], pady=2)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", padx=PAD["md"], pady=PAD["sm"])

        ctk.CTkLabel(
            left, text=name,
            font=FONTS["sm_bold"] if is_active else FONTS["sm"],
            text_color=ACCENT if is_active else TEXT_SUB,
        ).pack(anchor="w")

        ctk.CTkLabel(
            left,
            text=f"{spec.get('quality_label','')}  {spec.get('size_gb',0):.2f} GB",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
        ).pack(anchor="w")

        right_row = ctk.CTkFrame(row, fg_color="transparent")
        right_row.pack(side="right", padx=PAD["md"])

        if is_active:
            ctk.CTkLabel(
                right_row, text="  Active  ",
                font=FONTS["xs_bold"],
                text_color=SUCCESS,
                fg_color=SUCCESS_BG,
                corner_radius=RADIUS["full"],
            ).pack(side="right", padx=4)
        elif downloaded:
            ctk.CTkButton(
                right_row, text="Use",
                width=52, height=26,
                **{**btn_secondary(), "font": FONTS["xs_bold"]},
                command=lambda n=name: self._switch_model(n),
            ).pack(side="right", padx=4)
            ctk.CTkButton(
                right_row, text="Delete",
                width=60, height=26,
                fg_color="transparent",
                hover_color=ERROR_BG,
                text_color=TEXT_MUTED,
                border_color=BORDER,
                border_width=1,
                corner_radius=RADIUS["sm"],
                font=FONTS["xs"],
                command=lambda n=name, s=spec: self._delete_model(n, s),
            ).pack(side="right", padx=2)
        else:
            ctk.CTkButton(
                right_row,
                text=f"⬇ {spec.get('size_gb',0):.1f} GB",
                width=90, height=26,
                fg_color=ACCENT_DIM,
                hover_color=ACCENT,
                text_color=TEXT,
                corner_radius=RADIUS["sm"],
                font=FONTS["xs"],
                command=lambda n=name, s=spec: self._download_model(n, s),
            ).pack(side="right", padx=4)

    def _switch_model(self, name: str):
        self.config["selected_model"] = name
        self._emit_change()
        self._refresh_model_section()

    def _delete_model(self, name: str, spec: dict):
        import shutil, tkinter.messagebox as mb
        if mb.askyesno("Delete Model?", f"Delete downloaded files for '{name}'?"):
            from core.model_manager import get_model_cache_path
            path = get_model_cache_path(spec["model_id"])
            try:
                if path.exists():
                    shutil.rmtree(str(path))
            except Exception as exc:
                print(f"[Settings] Delete model error: {exc}")
        self._refresh_model_section()

    def _download_model(self, name: str, spec: dict):
        """Trigger model download in background."""
        def run():
            try:
                from TTS.api import TTS
                TTS(model_name=spec["model_id"], progress_bar=False, gpu=False)
                self.after(0, self._refresh_model_section)
            except Exception as exc:
                print(f"[Settings] Download error: {exc}")

        import threading
        threading.Thread(target=run, daemon=True).start()

    def _refresh_model_section(self):
        """Rebuild only the model section (avoids full rebuild)."""
        # Simplest approach: rebuild all sections
        for w in self._scroll.winfo_children():
            w.destroy()
        self._build_output_section()
        self._build_model_section()
        self._build_audio_quality_section()
        self._build_appearance_section()
        self._build_about_section()

    # ── Audio Quality ──────────────────────────────────────────────────────────

    def _build_audio_quality_section(self):
        sec = _AccordionSection(self._scroll, "Audio Quality", expanded=False)
        sec.pack(fill="x", pady=(0, PAD["md"]))
        c = sec.content

        # Sample rate
        self._row_label(c, "Sample Rate")
        self._sr_var = ctk.StringVar(value=str(self.config.get("sample_rate", 22050)))
        sr_row = ctk.CTkFrame(c, fg_color="transparent")
        sr_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        for label_t, val in [("Standard  22 kHz", "22050"), ("High  44 kHz", "44100")]:
            ctk.CTkRadioButton(
                sr_row,
                text=label_t,
                variable=self._sr_var,
                value=val,
                font=FONTS["base"],
                text_color=TEXT_SUB,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
            ).pack(side="left", padx=(0, 20))

        # MP3 bitrate
        self._row_label(c, "MP3 Bitrate (when exporting MP3)")
        self._br_var = ctk.StringVar(value=self.config.get("mp3_bitrate", "192k"))
        br_row = ctk.CTkFrame(c, fg_color="transparent")
        br_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        for br in ["128k", "192k", "320k"]:
            ctk.CTkRadioButton(
                br_row,
                text=br,
                variable=self._br_var,
                value=br,
                font=FONTS["base"],
                text_color=TEXT_SUB,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
            ).pack(side="left", padx=(0, 16))

        # Fade in/out
        self._row_label(c, "Fade In / Fade Out")
        fade_row = ctk.CTkFrame(c, fg_color="transparent")
        fade_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["xl"]))

        self._fade_in_var  = ctk.IntVar(value=self.config.get("fade_in_ms", 0))
        self._fade_out_var = ctk.IntVar(value=self.config.get("fade_out_ms", 0))

        self._fade_enabled_var = ctk.BooleanVar(
            value=bool(self._fade_in_var.get() or self._fade_out_var.get())
        )

        ctk.CTkCheckBox(
            fade_row,
            text="Add fade in/out",
            variable=self._fade_enabled_var,
            font=FONTS["base"],
            text_color=TEXT_SUB,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            checkmark_color=TEXT,
        ).pack(side="left")

        ctk.CTkLabel(fade_row, text="In:", font=FONTS["sm"], text_color=TEXT_MUTED).pack(side="left", padx=(16, 4))
        ctk.CTkEntry(fade_row, textvariable=self._fade_in_var, width=54, height=28, **input_field()).pack(side="left")
        ctk.CTkLabel(fade_row, text="ms  Out:", font=FONTS["sm"], text_color=TEXT_MUTED).pack(side="left", padx=4)
        ctk.CTkEntry(fade_row, textvariable=self._fade_out_var, width=54, height=28, **input_field()).pack(side="left")
        ctk.CTkLabel(fade_row, text="ms", font=FONTS["sm"], text_color=TEXT_MUTED).pack(side="left", padx=4)

    # ── Appearance ─────────────────────────────────────────────────────────────

    def _build_appearance_section(self):
        sec = _AccordionSection(self._scroll, "Appearance", expanded=False)
        sec.pack(fill="x", pady=(0, PAD["md"]))
        c = sec.content

        # Theme toggle
        self._row_label(c, "Theme")
        self._theme_var = ctk.StringVar(value=self.config.get("theme", "dark"))
        theme_row = ctk.CTkFrame(c, fg_color="transparent")
        theme_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        for theme_name in ["dark", "light"]:
            ctk.CTkRadioButton(
                theme_row,
                text=theme_name.capitalize(),
                variable=self._theme_var,
                value=theme_name,
                font=FONTS["base"],
                text_color=TEXT_SUB,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
                command=lambda: self._apply_theme_preview(),
            ).pack(side="left", padx=(0, 20))

        # Accent color
        self._row_label(c, "Accent Color")
        swatch_row = ctk.CTkFrame(c, fg_color="transparent")
        swatch_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["xl"]))

        self._accent_var   = ctk.StringVar(value=self.config.get("accent_color", "#7c3aed"))
        self._swatch_btns: list[ctk.CTkButton] = []

        for hex_color, color_name in ACCENT_PRESETS:
            is_active = (hex_color == self._accent_var.get())
            btn = ctk.CTkButton(
                swatch_row,
                text="✓" if is_active else "",
                width=36, height=36,
                fg_color=hex_color,
                hover_color=hex_color,
                text_color="white",
                corner_radius=RADIUS["full"],
                font=FONTS["sm_bold"],
                command=lambda h=hex_color: self._select_accent(h),
            )
            btn.pack(side="left", padx=4)
            self._swatch_btns.append(btn)

            ctk.CTkLabel(
                swatch_row,
                text=color_name,
                font=FONTS["xs"],
                text_color=TEXT_MUTED,
            ).pack(side="left", padx=(0, 8))

    def _apply_theme_preview(self):
        try:
            import customtkinter as ctk_m
            ctk_m.set_appearance_mode(self._theme_var.get())
        except Exception:
            pass

    def _select_accent(self, hex_color: str):
        self._accent_var.set(hex_color)
        for btn, (h, _) in zip(self._swatch_btns, ACCENT_PRESETS):
            btn.configure(text="✓" if h == hex_color else "")

    # ── About ──────────────────────────────────────────────────────────────────

    def _build_about_section(self):
        import platform, sys as _sys
        sec = _AccordionSection(self._scroll, "About", expanded=False)
        sec.pack(fill="x", pady=(0, PAD["xl"]))
        c = sec.content

        # ── Header ──
        hdr = ctk.CTkFrame(c, fg_color="#111118", corner_radius=RADIUS["md"])
        hdr.pack(fill="x", padx=PAD["xl"], pady=(PAD["md"], PAD["xs"]))

        name_row = ctk.CTkFrame(hdr, fg_color="transparent")
        name_row.pack(fill="x", padx=PAD["md"], pady=(PAD["md"], PAD["xs"]))

        ctk.CTkLabel(
            name_row, text="◈  AURA VOICE",
            font=(FONTS["lg_bold"][0], 16, "bold"),
            text_color="#e2e8f0",
        ).pack(side="left")

        ctk.CTkLabel(
            name_row, text=f"v{APP_VERSION}",
            font=FONTS["mono_xs"],
            text_color="#334155",
        ).pack(side="right")

        ctk.CTkLabel(
            hdr,
            text=f"build 16 Mar 2026  ·  Python {_sys.version.split()[0]}  ·  {platform.system()} {platform.machine()}",
            font=FONTS["mono_xs"],
            text_color="#334155",
            anchor="w",
        ).pack(anchor="w", padx=PAD["md"], pady=(0, PAD["md"]))

        # ── Status dots ──
        status_frame = ctk.CTkFrame(c, fg_color="transparent")
        status_frame.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["xs"]))

        for dot, label, color in [
            ("●", "100% Offline",     "#10b981"),
            ("●", "No API Keys",      "#10b981"),
            ("●", "No Subscriptions", "#10b981"),
        ]:
            row = ctk.CTkFrame(status_frame, fg_color="transparent")
            row.pack(side="left", padx=(0, PAD["xl"]))
            ctk.CTkLabel(row, text=dot, font=FONTS["xs"], text_color=color, width=12).pack(side="left")
            ctk.CTkLabel(row, text=label, font=FONTS["xs"], text_color="#94a3b8").pack(side="left", padx=(3, 0))

        # ── Components ──
        stack = ctk.CTkFrame(c, fg_color="#0d0d14", corner_radius=RADIUS["md"])
        stack.pack(fill="x", padx=PAD["xl"], pady=(PAD["xs"], PAD["xs"]))

        ctk.CTkLabel(
            stack, text="COMPONENTS",
            font=FONTS["xs_bold"], text_color="#334155", anchor="w",
        ).pack(anchor="w", padx=PAD["md"], pady=(PAD["sm"], 2))

        components = [
            ("Coqui TTS 0.22",  "Neural TTS engine"),
            ("VCTK VITS",       "109 English speakers"),
            ("CustomTkinter",   "Modern dark UI"),
            ("pydub / pygame",  "Audio processing + playback"),
            ("PyTorch 2.6",     "ML inference (MPS/CPU)"),
            ("Pillow",          "Thumbnail generation"),
            ("espeak-ng",       "Phonemizer backend"),
        ]
        for name, desc in components:
            row = ctk.CTkFrame(stack, fg_color="transparent")
            row.pack(fill="x", padx=PAD["md"], pady=1)
            ctk.CTkLabel(row, text="·", font=FONTS["xs"], text_color="#334155", width=10).pack(side="left")
            ctk.CTkLabel(row, text=name, font=FONTS["mono_xs"], text_color="#94a3b8").pack(side="left", padx=(4, 0))
            ctk.CTkLabel(row, text=desc, font=FONTS["xs"], text_color="#475569").pack(side="right")

        ctk.CTkFrame(stack, fg_color="transparent", height=6).pack()

        # ── GitHub ──
        ctk.CTkLabel(
            c,
            text="github.com/fireyhellmarketing-cmd/aura-voice",
            font=FONTS["mono_xs"],
            text_color="#334155",
            cursor="hand2",
        ).pack(pady=(PAD["xs"], PAD["md"]))

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _row_label(self, parent, text: str):
        ctk.CTkLabel(
            parent,
            text=text.upper(),
            font=FONTS["xs_bold"],
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=PAD["xl"], pady=(PAD["xl"], PAD["sm"]))

    # ── Save ───────────────────────────────────────────────────────────────────

    def _save_all(self):
        """Collect all settings and persist."""
        try:
            self.config["output_dir"]        = self._output_folder_label.cget("text")
            self.config["filename_pattern"]  = self._filename_entry.get().strip() or "aura_voice_{date}_{time}"
            self.config["auto_open_folder"]  = self._auto_open_var.get()
        except Exception:
            pass

        try:
            self.config["sample_rate"]  = int(self._sr_var.get())
            self.config["mp3_bitrate"]  = self._br_var.get()
            fade_on = self._fade_enabled_var.get()
            self.config["fade_in_ms"]   = self._fade_in_var.get() if fade_on else 0
            self.config["fade_out_ms"]  = self._fade_out_var.get() if fade_on else 0
        except Exception:
            pass

        try:
            self.config["theme"]        = self._theme_var.get()
            self.config["accent_color"] = self._accent_var.get()
        except Exception:
            pass

        save_config(self.config)
        if self.on_config_change:
            self.on_config_change(self.config)

    def _emit_change(self):
        save_config(self.config)
        if self.on_config_change:
            self.on_config_change(self.config)

    def update_config(self, new_config: dict):
        """Externally update the config dict."""
        self.config.update(new_config)

    # Import missing style reference
    def _import_error_bg(self):
        try:
            from assets.styles import ERROR_BG
            return ERROR_BG
        except Exception:
            return "#450a0a"


# Make ERROR_BG available at module level
try:
    from assets.styles import ERROR_BG
except ImportError:
    ERROR_BG = "#450a0a"
