"""AURA VOICE — Left controls panel: script editor + generation settings."""

import os
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

from assets.styles import (
    BG, PANEL, CARD, CARD_HOVER, INPUT_BG,
    ACCENT, ACCENT_HOVER, ACCENT_DIM,
    ACCENT2,
    TEXT, TEXT_SUB, TEXT_MUTED,
    BORDER, BORDER_LIGHT,
    SUCCESS, ERROR,
    FONTS, PAD, RADIUS,
    CONTROLS_WIDTH,
    btn_primary, btn_secondary, btn_ghost, card_frame, input_field,
)


# ─── Voice / Style / Language data ─────────────────────────────────────────────

VOICE_PROFILES = [
    "Natural Female",
    "Natural Male",
    "Warm Female",
    "Deep Male",
    "Youthful Female",
    "Authoritative Male",
    "Calm Female — British",
    "Energetic Male — American",
    "Soft Whispery Female",
    "Professional Narrator",
    "Custom (Clone)",
]

DELIVERY_STYLES = [
    "Neutral",
    "Happy & Upbeat",
    "Serious & Authoritative",
    "Sad & Reflective",
    "Excited & Enthusiastic",
    "Calm & Meditative",
    "Warm & Friendly",
    "Professional",
]

LANGUAGES = [
    "English",
    "Spanish",
    "French",
    "German",
    "Hindi",
    "Portuguese",
    "Italian",
    "Dutch",
    "Polish",
    "Russian",
    "Turkish",
    "Korean",
    "Japanese",
    "Chinese",
]

DEFAULT_OUTPUT_DIR = str(Path.home() / "Documents" / "AuraVoice")

# Estimated reading speed (words per minute)
_WPM = 150


# ─── Controls Panel ────────────────────────────────────────────────────────────

class ControlsPanel(ctk.CTkFrame):
    """
    Left-hand controls panel (320 px fixed width).

    Contains:
      • "Script" / "Advanced" tab switcher
      • Script tab  — textarea, word count, load buttons
      • Advanced tab — voice/style/language/speed/pitch/pause/format settings
      • Bottom sticky area — output folder + Generate button (always visible)
    """

    def __init__(
        self,
        parent,
        on_generate: Callable[[], None],
        on_load_txt: Optional[Callable[[], None]] = None,
        on_load_project: Optional[Callable[[], None]] = None,
        on_output_folder_change: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(
            parent,
            fg_color=PANEL,
            corner_radius=0,
            width=CONTROLS_WIDTH,
            **kwargs,
        )
        self.pack_propagate(False)

        self.on_generate              = on_generate
        self.on_load_txt              = on_load_txt
        self.on_load_project          = on_load_project
        self.on_output_folder_change  = on_output_folder_change

        # State vars (set before _build so _build can reference them)
        self._active_tab    = "Script"
        self._output_dir    = DEFAULT_OUTPUT_DIR
        self._voice_var     = ctk.StringVar(value="Natural Female")
        self._style_var     = ctk.StringVar(value="Neutral")
        self._language_var  = ctk.StringVar(value="English")
        self._format_var    = ctk.StringVar(value="WAV")
        self._quality_var   = ctk.StringVar(value="22050")
        self._speed_var     = ctk.DoubleVar(value=1.0)
        self._pitch_var     = ctk.DoubleVar(value=0.0)
        self._pause_var     = ctk.DoubleVar(value=300.0)

        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Tab switcher row ──
        tab_bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=44)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self._tab_btns: dict[str, ctk.CTkButton] = {}
        for tab_name in ["Script", "Advanced"]:
            btn = ctk.CTkButton(
                tab_bar,
                text=tab_name,
                height=44,
                fg_color="transparent",
                hover_color=CARD_HOVER,
                text_color=ACCENT if tab_name == self._active_tab else TEXT_MUTED,
                corner_radius=0,
                font=FONTS["md_bold"] if tab_name == self._active_tab else FONTS["md"],
                command=lambda t=tab_name: self._switch_tab(t),
            )
            btn.pack(side="left", fill="y", padx=0)
            self._tab_btns[tab_name] = btn

        # Active tab underline (a thin violet line under the active tab button)
        self._tab_underline = ctk.CTkFrame(
            tab_bar, fg_color=ACCENT, height=2, corner_radius=0,
        )

        # ── Scrollable content area ──
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=BORDER_LIGHT,
        )
        self.scroll.pack(fill="both", expand=True)

        # Build both tab contents inside scroll
        self._script_content  = self._build_script_tab(self.scroll)
        self._advanced_content = self._build_advanced_tab(self.scroll)

        # ── Bottom sticky: output dir + generate ──
        self._build_bottom_bar()

        # Show initial tab
        self._switch_tab(self._active_tab)

    # ── Script Tab ─────────────────────────────────────────────────────────────

    def _build_script_tab(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color="transparent")

        # Section label
        self._section_label(frame, "Script")

        # Textarea
        self.script_box = ctk.CTkTextbox(
            frame,
            height=300,
            font=FONTS["mono"],
            wrap="word",
            **input_field(),
        )
        self.script_box.pack(fill="x", padx=PAD["xl"], pady=(0, 6))
        self.script_box.insert("0.0", "")
        self.script_box._textbox.configure(
            insertbackground=ACCENT,
        )
        # Placeholder
        self._add_placeholder(self.script_box, "Paste your script or load a file…")

        # Bind to update word count
        self.script_box.bind("<KeyRelease>", self._update_word_count)

        # Word count / duration row
        stat_row = ctk.CTkFrame(frame, fg_color="transparent")
        stat_row.pack(fill="x", padx=PAD["xl"])

        self.word_count_label = ctk.CTkLabel(
            stat_row,
            text="0 words",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
        )
        self.word_count_label.pack(side="left")

        self.duration_label = ctk.CTkLabel(
            stat_row,
            text="~0s",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
        )
        self.duration_label.pack(side="right")

        # Load buttons row
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=PAD["xl"], pady=(PAD["lg"], 0))

        ctk.CTkButton(
            btn_row,
            text="↑ Load .txt",
            width=110, height=32,
            **btn_secondary(),
            command=self._do_load_txt,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="⬡ Load project",
            width=120, height=32,
            **btn_secondary(),
            command=self._do_load_project,
        ).pack(side="left", padx=(8, 0))

        return frame

    def _add_placeholder(self, textbox: ctk.CTkTextbox, placeholder: str):
        """Add grey placeholder text that disappears on first edit."""
        textbox.insert("0.0", placeholder)
        textbox._textbox.configure(fg=TEXT_MUTED)
        self._placeholder_active = True
        self._placeholder_text   = placeholder

        def on_focus_in(e):
            if self._placeholder_active:
                textbox.delete("0.0", "end")
                try:
                    textbox._textbox.configure(fg=TEXT)
                except Exception:
                    pass
                self._placeholder_active = False

        textbox.bind("<FocusIn>", on_focus_in)

    def _update_word_count(self, event=None):
        text = self.get_script_text()
        words = len(text.split()) if text.strip() else 0
        secs  = int(words / _WPM * 60)
        mins, s = divmod(secs, 60)
        dur_str = f"~{mins}m {s}s" if mins else f"~{secs}s"
        self.word_count_label.configure(text=f"{words:,} words")
        self.duration_label.configure(text=dur_str)

    def _do_load_txt(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Load Script",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                if self._placeholder_active:
                    self.script_box.delete("0.0", "end")
                    self._placeholder_active = False
                else:
                    self.script_box.delete("0.0", "end")
                try:
                    self.script_box._textbox.configure(fg=TEXT)
                except Exception:
                    pass
                self.script_box.insert("0.0", content)
                self._update_word_count()
            except Exception as exc:
                print(f"[Controls] Load txt error: {exc}")
        if self.on_load_txt:
            self.on_load_txt()

    def _do_load_project(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Load Project",
            filetypes=[
                ("AURA VOICE Project", "*.avp"),
                ("JSON", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if path:
            try:
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "script" in data:
                    if self._placeholder_active:
                        self.script_box.delete("0.0", "end")
                        self._placeholder_active = False
                    else:
                        self.script_box.delete("0.0", "end")
                    self.script_box.insert("0.0", data["script"])
                    self._update_word_count()
                # Load settings if present
                if "voice_profile" in data:
                    self._voice_var.set(data["voice_profile"])
                if "delivery_style" in data:
                    self._style_var.set(data["delivery_style"])
                if "language" in data:
                    self._language_var.set(data["language"])
                if "speed" in data:
                    self._speed_var.set(data["speed"])
            except Exception as exc:
                print(f"[Controls] Load project error: {exc}")
        if self.on_load_project:
            self.on_load_project()

    # ── Advanced Tab ───────────────────────────────────────────────────────────

    def _build_advanced_tab(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color="transparent")

        # ── Voice Profile ──
        self._section_label(frame, "Voice Profile")
        self._voice_menu = ctk.CTkOptionMenu(
            frame,
            values=VOICE_PROFILES,
            variable=self._voice_var,
            fg_color=INPUT_BG,
            button_color=CARD_HOVER,
            button_hover_color=BORDER_LIGHT,
            dropdown_fg_color=CARD,
            dropdown_hover_color=CARD_HOVER,
            text_color=TEXT,
            font=FONTS["base"],
            dropdown_font=FONTS["base"],
            corner_radius=RADIUS["md"],
            command=self._on_voice_change,
        )
        self._voice_menu.pack(fill="x", padx=PAD["xl"])

        # Voice Clone card (visible when "Custom (Clone)" is selected)
        self._clone_card = self._build_clone_card(frame)

        # ── Delivery Style ──
        self._section_label(frame, "Delivery Style")
        self._style_menu = ctk.CTkOptionMenu(
            frame,
            values=DELIVERY_STYLES,
            variable=self._style_var,
            fg_color=INPUT_BG,
            button_color=CARD_HOVER,
            button_hover_color=BORDER_LIGHT,
            dropdown_fg_color=CARD,
            dropdown_hover_color=CARD_HOVER,
            text_color=TEXT,
            font=FONTS["base"],
            dropdown_font=FONTS["base"],
            corner_radius=RADIUS["md"],
        )
        self._style_menu.pack(fill="x", padx=PAD["xl"])

        # ── Language ──
        self._section_label(frame, "Language")
        self._lang_menu = ctk.CTkOptionMenu(
            frame,
            values=LANGUAGES,
            variable=self._language_var,
            fg_color=INPUT_BG,
            button_color=CARD_HOVER,
            button_hover_color=BORDER_LIGHT,
            dropdown_fg_color=CARD,
            dropdown_hover_color=CARD_HOVER,
            text_color=TEXT,
            font=FONTS["base"],
            dropdown_font=FONTS["base"],
            corner_radius=RADIUS["md"],
        )
        self._lang_menu.pack(fill="x", padx=PAD["xl"])

        # ── Speed slider ──
        self._section_label(frame, "Speed")
        speed_row = ctk.CTkFrame(frame, fg_color="transparent")
        speed_row.pack(fill="x", padx=PAD["xl"])

        self._speed_slider = ctk.CTkSlider(
            speed_row,
            from_=0.5, to=2.0,
            variable=self._speed_var,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            progress_color=ACCENT,
            fg_color=CARD,
            command=lambda v: self._speed_val_label.configure(
                text=f"{v:.2f}×"
            ),
        )
        self._speed_slider.pack(side="left", fill="x", expand=True)

        self._speed_val_label = ctk.CTkLabel(
            speed_row, text="1.00×",
            font=FONTS["sm"], text_color=TEXT_SUB, width=40,
        )
        self._speed_val_label.pack(side="right", padx=(6, 0))

        # ── Pitch slider ──
        self._section_label(frame, "Pitch Shift")
        pitch_row = ctk.CTkFrame(frame, fg_color="transparent")
        pitch_row.pack(fill="x", padx=PAD["xl"])

        self._pitch_slider = ctk.CTkSlider(
            pitch_row,
            from_=-10, to=10,
            variable=self._pitch_var,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            progress_color=ACCENT,
            fg_color=CARD,
            command=lambda v: self._pitch_val_label.configure(
                text=f"{v:+.1f} st"
            ),
        )
        self._pitch_slider.pack(side="left", fill="x", expand=True)

        self._pitch_val_label = ctk.CTkLabel(
            pitch_row, text="+0.0 st",
            font=FONTS["sm"], text_color=TEXT_SUB, width=50,
        )
        self._pitch_val_label.pack(side="right", padx=(6, 0))

        ctk.CTkLabel(
            frame,
            text="Semitones relative to original voice",
            font=FONTS["xs"], text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=PAD["xl"], pady=(0, 4))

        # ── Pause slider ──
        self._section_label(frame, "Pause Between Sentences")
        pause_row = ctk.CTkFrame(frame, fg_color="transparent")
        pause_row.pack(fill="x", padx=PAD["xl"])

        self._pause_slider = ctk.CTkSlider(
            pause_row,
            from_=0, to=800,
            variable=self._pause_var,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            progress_color=ACCENT,
            fg_color=CARD,
            command=lambda v: self._pause_val_label.configure(
                text=f"{int(v)} ms"
            ),
        )
        self._pause_slider.pack(side="left", fill="x", expand=True)

        self._pause_val_label = ctk.CTkLabel(
            pause_row, text="300 ms",
            font=FONTS["sm"], text_color=TEXT_SUB, width=50,
        )
        self._pause_val_label.pack(side="right", padx=(6, 0))

        # ── Output Format ──
        self._section_label(frame, "Output Format")
        fmt_row = ctk.CTkFrame(frame, fg_color="transparent")
        fmt_row.pack(fill="x", padx=PAD["xl"])

        for fmt in ["WAV", "MP3"]:
            ctk.CTkRadioButton(
                fmt_row,
                text=fmt,
                variable=self._format_var,
                value=fmt,
                font=FONTS["base"],
                text_color=TEXT_SUB,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
            ).pack(side="left", padx=(0, 16))

        # ── Audio Quality ──
        self._section_label(frame, "Audio Quality")
        qual_row = ctk.CTkFrame(frame, fg_color="transparent")
        qual_row.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["3xl"]))

        quality_options = [
            ("Standard — 22 kHz", "22050"),
            ("High — 44 kHz",     "44100"),
        ]
        for label_text, val in quality_options:
            ctk.CTkRadioButton(
                qual_row,
                text=label_text,
                variable=self._quality_var,
                value=val,
                font=FONTS["sm"],
                text_color=TEXT_SUB,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
            ).pack(anchor="w", pady=2)

        return frame

    def _build_clone_card(self, parent) -> ctk.CTkFrame:
        """Voice clone reference audio card."""
        card = ctk.CTkFrame(
            parent,
            **card_frame(),
        )

        ctk.CTkLabel(
            card,
            text="Voice Clone Reference",
            font=FONTS["sm_bold"],
            text_color=TEXT,
        ).pack(anchor="w", padx=PAD["card"], pady=(PAD["card"], 2))

        ctk.CTkLabel(
            card,
            text="Upload a 5–30 second WAV/MP3 sample",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=PAD["card"])

        ref_row = ctk.CTkFrame(card, fg_color="transparent")
        ref_row.pack(fill="x", padx=PAD["card"], pady=PAD["md"])

        self._clone_path_label = ctk.CTkLabel(
            ref_row,
            text="No file selected",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self._clone_path_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            ref_row,
            text="Browse",
            width=70, height=28,
            **btn_secondary(),
            command=self._browse_clone_file,
        ).pack(side="right")

        card.pack_forget()  # hidden by default
        return card

    def _on_voice_change(self, value: str):
        if value == "Custom (Clone)":
            self._clone_card.pack(
                fill="x",
                padx=PAD["xl"],
                pady=(0, PAD["md"]),
                after=self._voice_menu,
            )
        else:
            self._clone_card.pack_forget()

    def _browse_clone_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Reference Audio",
            filetypes=[
                ("Audio files", "*.wav *.mp3 *.flac *.m4a"),
                ("All files", "*.*"),
            ],
        )
        if path:
            short = Path(path).name
            self._clone_path_label.configure(text=short)
            self._clone_ref_path = path
        else:
            self._clone_ref_path = None

    # ── Bottom bar (always visible) ────────────────────────────────────────────

    def _build_bottom_bar(self):
        sep = ctk.CTkFrame(self, fg_color=BORDER, height=1, corner_radius=0)
        sep.pack(fill="x")

        bottom = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0)
        bottom.pack(fill="x")

        # Output folder row
        folder_row = ctk.CTkFrame(bottom, fg_color="transparent")
        folder_row.pack(fill="x", padx=PAD["xl"], pady=(PAD["md"], 0))

        ctk.CTkLabel(
            folder_row,
            text="Output",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
            width=45,
        ).pack(side="left")

        self._output_label = ctk.CTkLabel(
            folder_row,
            text=self._shorten_path(self._output_dir),
            font=FONTS["xs"],
            text_color=TEXT_SUB,
            anchor="w",
        )
        self._output_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            folder_row,
            text="Change",
            width=60, height=24,
            **btn_ghost(),
            command=self._change_output_folder,
        ).pack(side="right")

        # Generate button
        _gen_style = btn_primary()
        _gen_style["font"] = (FONTS["generate"][0], 15, "bold")
        self.generate_btn = ctk.CTkButton(
            bottom,
            text="✦  Generate",
            height=48,
            **_gen_style,
            command=self.on_generate,
        )
        self.generate_btn.pack(
            fill="x",
            padx=PAD["xl"],
            pady=PAD["xl"],
        )

    def _shorten_path(self, path: str, max_len: int = 28) -> str:
        p = str(path)
        home = str(Path.home())
        if p.startswith(home):
            p = "~" + p[len(home):]
        if len(p) > max_len:
            p = "…" + p[-(max_len - 1):]
        return p

    def _change_output_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self._output_dir,
        )
        if folder:
            self._output_dir = folder
            self._output_label.configure(text=self._shorten_path(folder))
            if self.on_output_folder_change:
                self.on_output_folder_change(folder)

    # ── Tab switching ──────────────────────────────────────────────────────────

    def _section_label(self, parent, text: str):
        ctk.CTkLabel(
            parent,
            text=text.upper(),
            font=FONTS["xs_bold"],
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=PAD["xl"], pady=(PAD["xl"], PAD["sm"]))

    def _switch_tab(self, tab_name: str):
        self._active_tab = tab_name

        for name, btn in self._tab_btns.items():
            if name == tab_name:
                btn.configure(
                    text_color=ACCENT,
                    font=FONTS["md_bold"],
                )
            else:
                btn.configure(
                    text_color=TEXT_MUTED,
                    font=FONTS["md"],
                )

        # Show/hide content
        if tab_name == "Script":
            self._advanced_content.pack_forget()
            self._script_content.pack(fill="x", pady=(PAD["md"], 0))
        else:
            self._script_content.pack_forget()
            self._advanced_content.pack(fill="x", pady=(PAD["md"], 0))

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_script_text(self) -> str:
        """Return the current script text (empty string if placeholder active)."""
        if self._placeholder_active:
            return ""
        return self.script_box.get("0.0", "end").strip()

    def get_settings(self) -> dict:
        """Return a dict of all current generation settings."""
        return {
            "voice_profile":    self._voice_var.get(),
            "delivery_style":   self._style_var.get(),
            "language":         self._language_var.get(),
            "speed":            round(self._speed_var.get(), 2),
            "pitch_shift":      round(self._pitch_var.get(), 1),
            "pause_ms":         int(self._pause_var.get()),
            "output_format":    self._format_var.get(),
            "sample_rate":      int(self._quality_var.get()),
            "output_dir":       self._output_dir,
            "clone_ref_path":   getattr(self, "_clone_ref_path", None),
        }

    def set_output_dir(self, path: str):
        self._output_dir = path
        self._output_label.configure(text=self._shorten_path(path))

    def set_generating(self, is_generating: bool):
        """Disable/enable the generate button during synthesis."""
        if is_generating:
            self.generate_btn.configure(
                text="  Generating…  ",
                state="disabled",
                fg_color=ACCENT_DIM,
            )
        else:
            self.generate_btn.configure(
                text="✦  Generate",
                state="normal",
                fg_color=ACCENT,
            )

    def load_settings(self, settings: dict):
        """Populate controls from a settings dict (e.g. loaded from project)."""
        if "voice_profile" in settings:
            self._voice_var.set(settings["voice_profile"])
            self._on_voice_change(settings["voice_profile"])
        if "delivery_style" in settings:
            self._style_var.set(settings["delivery_style"])
        if "language" in settings:
            self._language_var.set(settings["language"])
        if "speed" in settings:
            self._speed_var.set(float(settings["speed"]))
        if "pitch_shift" in settings:
            self._pitch_var.set(float(settings["pitch_shift"]))
        if "pause_ms" in settings:
            self._pause_var.set(float(settings["pause_ms"]))
        if "output_format" in settings:
            self._format_var.set(settings["output_format"])
        if "sample_rate" in settings:
            self._quality_var.set(str(settings["sample_rate"]))
