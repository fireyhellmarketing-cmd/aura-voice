"""AURA VOICE v2 — Main application window."""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from assets.styles import (
    APP_NAME, APP_VERSION, APP_TAGLINE,
    FONTS, PAD, WINDOW,
    BG, PANEL, CARD,
    ACCENT,
    TEXT, TEXT_SUB, TEXT_MUTED,
    BORDER,
    SUCCESS, SUCCESS_BG, WARNING, ERROR,
    apply_ctk_theme,
)
from core.model_manager import load_config, save_config, MODEL_CATALOG
from core.tts_engine import TTSEngine, LANGUAGE_CODES
from ui.sidebar import Sidebar
from ui.controls_panel import ControlsPanel
from ui.output_panel import OutputPanel
from ui.bottom_bar import BottomBar
from ui.terminal_widget import TerminalWidget


# ─── Queue message types ────────────────────────────────────────────────────────
_Q_CHUNK_START   = "chunk_start"
_Q_CHUNK_DONE    = "chunk_done"
_Q_STITCH_START  = "stitch_start"
_Q_STITCH_PROG   = "stitch_prog"
_Q_EXPORT_START  = "export_start"
_Q_COMPLETE      = "complete"
_Q_ERROR         = "error"
_Q_MODEL_STATUS  = "model_status"
_Q_DL_PROGRESS   = "dl_progress"


# ─── Stderr interceptor ────────────────────────────────────────────────────────

class _StderrCapture:
    """Wraps sys.stderr; parses tqdm progress lines and posts to the UI queue."""

    _PCT_RE  = re.compile(r'(\d+)%')
    _SIZE_RE = re.compile(r'([\d.]+)([KMGT]?)iB/([\d.]+)([KMGT]?)iB')
    _UNITS   = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}

    def __init__(self, ui_queue: queue.Queue):
        self._q    = ui_queue
        self._real = sys.__stderr__

    def write(self, text: str):
        self._real.write(text)
        self._parse(text)

    def flush(self):
        self._real.flush()

    def _parse(self, text: str):
        m = self._SIZE_RE.search(text)
        if m:
            done  = float(m.group(1)) * self._UNITS.get(m.group(2), 1)
            total = float(m.group(3)) * self._UNITS.get(m.group(4), 1)
            if total > 0:
                self._q.put((_Q_DL_PROGRESS, (done, total)))
                return
        p = self._PCT_RE.search(text)
        if p:
            pct = int(p.group(1))
            self._q.put((_Q_DL_PROGRESS, (pct, 100)))


# ─── Main Application Window ───────────────────────────────────────────────────

class AuraVoiceApp(ctk.CTk):
    """
    AURA VOICE v2 main window.

    Layout:
    ┌───────────────────────────────────────────────────────────────┐
    │  TITLEBAR (app name, model pill, controls)                    │
    ├──┬────────────────────────┬──────────────────────────────────-┤
    │  │  CONTROLS PANEL        │  OUTPUT / SETTINGS / HISTORY      │
    │S │  (320px fixed)         │  (fills remaining width)          │
    │I │                        │                                   │
    │D │                        │                                   │
    │E │                        │                                   │
    │B │                        │                                   │
    │A │                        │                                   │
    │R │                        │                                   │
    ├──┴────────────────────────┴───────────────────────────────────┤
    │  BOTTOM BAR (progress, status, cancel, open folder)           │
    ├────────────────────────────────────────────────────────────────┤
    │  TERMINAL (collapsible)                                        │
    └────────────────────────────────────────────────────────────────┘
    """

    WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION}"

    def __init__(self, config: Optional[dict] = None):
        super().__init__()

        apply_ctk_theme()

        # ── Config ──
        self._config = config or load_config()

        # ── State ──
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        self._cancel         = threading.Event()
        self._q: queue.Queue = queue.Queue()
        self._synth_thread:  Optional[threading.Thread] = None
        self._last_output:   Optional[Path] = None
        self._project_path:  Optional[Path] = None
        self._current_section = "generate"

        # ── Engine ──
        self._engine = TTSEngine()

        # ── Window setup ──
        self.title(self.WINDOW_TITLE)
        self.geometry(f"{WINDOW['width']}x{WINDOW['height']}")
        self.minsize(WINDOW['min_width'], WINDOW['min_height'])
        self.configure(fg_color=BG)

        self._build_menu()
        self._build_ui()
        self._start_poll()

        # Attempt to load the configured model after a short delay
        self.after(400, self._check_model)

    # ── Menu ───────────────────────────────────────────────────────────────────

    def _build_menu(self):
        import tkinter as tk
        mb = tk.Menu(self)

        def _m(label):
            m = tk.Menu(mb, tearoff=0)
            mb.add_cascade(label=label, menu=m)
            return m

        f = _m("File")
        f.add_command(label="New Project",           command=self._new_project,    accelerator="Cmd+N")
        f.add_command(label="Open Project…",         command=self._open_project,   accelerator="Cmd+O")
        f.add_command(label="Save Project",          command=self._save_project,   accelerator="Cmd+S")
        f.add_command(label="Save Project As…",      command=self._save_project_as)
        f.add_separator()
        f.add_command(label="Import Script (.txt)…", command=self._import_txt)
        f.add_command(label="Export as WAV…",        command=lambda: self._export("wav"))
        f.add_command(label="Export as MP3…",        command=lambda: self._export("mp3"))
        f.add_separator()
        f.add_command(label="Quit",                  command=self.quit, accelerator="Cmd+Q")

        v = _m("View")
        v.add_command(label="Toggle Dark / Light",      command=self._toggle_theme)
        v.add_command(label="Show / Hide Terminal",     command=self._toggle_terminal)
        v.add_separator()
        v.add_command(label="Generate",                 command=lambda: self._navigate("generate"))
        v.add_command(label="History",                  command=lambda: self._navigate("history"))
        v.add_command(label="Settings",                 command=lambda: self._navigate("settings"))

        h = _m("Help")
        h.add_command(label="About AURA VOICE",         command=self._show_about)
        h.add_command(label="Check Model Cache",        command=self._check_cache_info)

        self.config(menu=mb)

        # Keyboard shortcuts
        self.bind_all("<Command-n>", lambda _: self._new_project())
        self.bind_all("<Command-o>", lambda _: self._open_project())
        self.bind_all("<Command-s>", lambda _: self._save_project())

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.rowconfigure(0, weight=0)   # titlebar
        self.rowconfigure(1, weight=1)   # body
        self.rowconfigure(2, weight=0)   # bottom bar
        self.rowconfigure(3, weight=0)   # terminal
        self.columnconfigure(0, weight=1)

        # ── Title bar ──
        self._build_titlebar()

        # ── Body row ──
        body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=0)   # sidebar
        body.columnconfigure(1, weight=0)   # controls panel
        body.columnconfigure(2, weight=1)   # output / settings

        # Sidebar
        self._sidebar = Sidebar(
            body,
            on_nav=self._navigate,
            initial_section="generate",
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        # Thin separator
        ctk.CTkFrame(
            body, fg_color=BORDER, width=1, corner_radius=0,
        ).grid(row=0, column=1, sticky="ns")

        # Controls panel (always visible)
        self._controls = ControlsPanel(
            body,
            on_generate=self._start_synthesis,
            on_load_txt=None,
            on_load_project=self._open_project,
            on_output_folder_change=self._on_output_folder_change,
        )
        self._controls.grid(row=0, column=2, sticky="nsew")
        # Apply saved output dir
        self._controls.set_output_dir(
            self._config.get("output_dir", str(Path.home() / "Documents" / "AuraVoice"))
        )

        # Thin separator
        ctk.CTkFrame(
            body, fg_color=BORDER, width=1, corner_radius=0,
        ).grid(row=0, column=3, sticky="ns")

        # Output panel (right side, takes remaining width)
        body.columnconfigure(3, weight=0)
        body.columnconfigure(4, weight=1)

        self._output = OutputPanel(
            body,
            on_play=None,
            on_save=None,
            on_delete=None,
        )
        self._output.grid(row=0, column=4, sticky="nsew")

        # Settings view (hidden, swaps with output)
        from ui.settings_view import SettingsView
        self._settings_view = SettingsView(
            body,
            config=self._config,
            on_config_change=self._on_settings_change,
        )

        # History view (simple placeholder)
        self._history_view = self._build_history_view(body)

        # ── Bottom bar ──
        self._bar = BottomBar(
            self,
            on_cancel=self._cancel_synthesis,
            on_open_file=self._open_folder,
        )
        self._bar.grid(row=2, column=0, sticky="ew")

        # ── Terminal ──
        self._terminal = TerminalWidget(
            self,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        self._terminal.grid(row=3, column=0, sticky="ew")

    def _build_titlebar(self):
        tbar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=52)
        tbar.grid(row=0, column=0, sticky="ew")
        tbar.grid_propagate(False)
        tbar.columnconfigure(1, weight=1)

        # Left accent stripe
        ctk.CTkFrame(tbar, width=3, fg_color=ACCENT, corner_radius=0).grid(
            row=0, column=0, sticky="ns",
        )

        # Brand area
        brand = ctk.CTkFrame(tbar, fg_color="transparent")
        brand.grid(row=0, column=1, sticky="w", padx=(PAD["lg"], 0))

        ctk.CTkLabel(
            brand,
            text=f"  {APP_NAME}",
            font=FONTS["xl_bold"],
            text_color=ACCENT,
        ).pack(side="left")

        ctk.CTkLabel(
            brand,
            text=f"  {APP_TAGLINE}",
            font=FONTS["sm"],
            text_color=TEXT_MUTED,
        ).pack(side="left")

        # Right side: model pill + version
        right = ctk.CTkFrame(tbar, fg_color="transparent")
        right.grid(row=0, column=2, padx=PAD["xl"], sticky="e")

        self._model_pill = ctk.CTkLabel(
            right,
            text="○  Loading model…",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
            fg_color=CARD,
            corner_radius=12,
        )
        self._model_pill.pack(side="left", padx=(0, PAD["lg"]))

        ctk.CTkLabel(
            right,
            text=f"v{APP_VERSION}",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
        ).pack(side="left")

    def _build_history_view(self, parent) -> ctk.CTkFrame:
        """Scrollable history list with play/open controls per item."""
        frame = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)

        # ── Header ──
        header = ctk.CTkFrame(frame, fg_color="transparent", height=52)
        header.pack(fill="x", padx=PAD["page"], pady=(PAD["xl"], 0))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Generation History",
            font=FONTS["2xl_bold"],
            text_color=TEXT,
        ).pack(side="left", pady=8)

        self._history_count_lbl = ctk.CTkLabel(
            header,
            text="0 items",
            font=FONTS["sm"],
            text_color=TEXT_MUTED,
        )
        self._history_count_lbl.pack(side="right", pady=8)

        ctk.CTkFrame(frame, fg_color=BORDER, height=1).pack(
            fill="x", padx=PAD["page"], pady=(PAD["xs"], PAD["md"]),
        )

        # ── Scrollable list ──
        self._history_scroll = ctk.CTkScrollableFrame(
            frame,
            fg_color="transparent",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=CARD,
        )
        self._history_scroll.pack(fill="both", expand=True, padx=PAD["page"], pady=(0, PAD["md"]))

        # Placeholder shown when empty
        self._history_empty_lbl = ctk.CTkLabel(
            self._history_scroll,
            text="No generations yet.\nGenerate audio and it will appear here.",
            font=FONTS["base"],
            text_color=TEXT_MUTED,
            justify="center",
        )
        self._history_empty_lbl.pack(pady=64)

        return frame

    def _refresh_history_view(self):
        """Rebuild the history list from the output panel's records."""
        # Clear existing rows
        for w in self._history_scroll.winfo_children():
            w.destroy()

        records = self._output.get_history()
        count = len(records)
        self._history_count_lbl.configure(
            text=f"{count} item{'s' if count != 1 else ''}"
        )

        if count == 0:
            ctk.CTkLabel(
                self._history_scroll,
                text="No generations yet.\nGenerate audio and it will appear here.",
                font=FONTS["base"],
                text_color=TEXT_MUTED,
                justify="center",
            ).pack(pady=64)
            return

        from assets.styles import CARD, CARD_HOVER, ACCENT_DIM, ACCENT2, INPUT_BG, RADIUS
        import time as _time

        for rec in records:
            row = ctk.CTkFrame(
                self._history_scroll,
                fg_color=CARD,
                corner_radius=RADIUS["lg"],
                border_color=BORDER,
                border_width=1,
            )
            row.pack(fill="x", pady=(0, PAD["md"]))

            # Thumbnail
            thumb_frame = ctk.CTkFrame(
                row,
                fg_color=INPUT_BG,
                corner_radius=RADIUS["md"],
                width=64, height=64,
            )
            thumb_frame.pack(side="left", padx=(PAD["card"], PAD["sm"]), pady=PAD["card"])
            thumb_frame.pack_propagate(False)

            if rec.thumbnail_path and rec.thumbnail_path.exists():
                try:
                    from PIL import Image
                    img = Image.open(str(rec.thumbnail_path)).convert("RGB").resize((64, 64), Image.LANCZOS)
                    cimg = ctk.CTkImage(light_image=img, dark_image=img, size=(64, 64))
                    lbl = ctk.CTkLabel(thumb_frame, image=cimg, text="")
                    lbl.image = cimg
                    lbl.place(relx=0.5, rely=0.5, anchor="center")
                except Exception:
                    ctk.CTkLabel(thumb_frame, text="◈", font=(FONTS["xl"][0], 22), text_color=ACCENT_DIM).place(relx=0.5, rely=0.5, anchor="center")
            else:
                ctk.CTkLabel(thumb_frame, text="◈", font=(FONTS["xl"][0], 22), text_color=ACCENT_DIM).place(relx=0.5, rely=0.5, anchor="center")

            # Info column
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, pady=PAD["card"])

            title_text = rec.title[:60] + ("…" if len(rec.title) > 60 else "")
            ctk.CTkLabel(
                info,
                text=title_text,
                font=FONTS["base_bold"],
                text_color=TEXT,
                anchor="w",
            ).pack(anchor="w")

            ctk.CTkLabel(
                info,
                text=rec.audio_path.name,
                font=FONTS["mono_xs"],
                text_color=TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w")

            meta = ctk.CTkFrame(info, fg_color="transparent")
            meta.pack(anchor="w", pady=(2, 0))

            ctk.CTkLabel(
                meta,
                text=f"  {rec.duration_str}  ",
                font=FONTS["xs_bold"],
                text_color=ACCENT,
                fg_color=ACCENT_DIM,
                corner_radius=RADIUS["full"],
            ).pack(side="left", padx=(0, 4))

            ctk.CTkLabel(
                meta,
                text=f"  {rec.format_label}  ",
                font=FONTS["xs_bold"],
                text_color=ACCENT2,
                fg_color="#451a03",
                corner_radius=RADIUS["full"],
            ).pack(side="left")

            # Buttons
            btn_col = ctk.CTkFrame(row, fg_color="transparent")
            btn_col.pack(side="right", padx=PAD["card"], pady=PAD["card"])

            ctk.CTkButton(
                btn_col,
                text="▶  Play",
                width=88, height=32,
                fg_color=ACCENT,
                hover_color="#9d5ef5",
                text_color=TEXT,
                corner_radius=RADIUS["md"],
                font=FONTS["sm_bold"],
                command=lambda r=rec: self._history_play(r),
            ).pack(pady=(0, 4))

            ctk.CTkButton(
                btn_col,
                text="📂  Open",
                width=88, height=32,
                fg_color=CARD,
                hover_color=CARD_HOVER,
                text_color=TEXT_SUB,
                border_color=BORDER,
                border_width=1,
                corner_radius=RADIUS["md"],
                font=FONTS["sm"],
                command=lambda r=rec: self._history_open_folder(r),
            ).pack()

    def _history_play(self, rec):
        """Play a history record directly using afplay."""
        import subprocess, sys as _sys
        if not rec.audio_path.exists():
            messagebox.showerror("Not Found", f"File not found:\n{rec.audio_path}")
            return
        try:
            if _sys.platform == "darwin":
                subprocess.Popen(["afplay", str(rec.audio_path)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif _sys.platform == "win32":
                os.startfile(str(rec.audio_path))
            else:
                subprocess.Popen(["aplay", str(rec.audio_path)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            messagebox.showerror("Playback Error", str(exc))

    def _history_open_folder(self, rec):
        """Reveal a history record's folder in Finder/Explorer."""
        try:
            folder = rec.audio_path.parent
            if sys.platform == "darwin":
                subprocess.call(["open", str(folder)])
            elif sys.platform == "win32":
                os.startfile(str(folder))
            else:
                subprocess.call(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Open Folder Error", str(exc))

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _navigate(self, section: str):
        """Switch the right-hand content area between views."""
        self._current_section = section
        self._sidebar.set_active(section)

        # Hide all right-side views
        for view in [self._output, self._settings_view, self._history_view]:
            view.grid_forget()

        # Show the appropriate view in column 4
        if section == "generate":
            self._output.grid(row=0, column=4, sticky="nsew")
        elif section == "settings":
            self._settings_view.grid(row=0, column=4, sticky="nsew")
        elif section == "history":
            self._history_view.grid(row=0, column=4, sticky="nsew")
            self._refresh_history_view()
        elif section == "about":
            self._show_about()
            self._output.grid(row=0, column=4, sticky="nsew")
            self._sidebar.set_active("generate")

    def _toggle_terminal(self):
        self._terminal._toggle()

    # ── Settings callback ──────────────────────────────────────────────────────

    def _on_settings_change(self, new_config: dict):
        self._config.update(new_config)
        self._controls.set_output_dir(
            new_config.get("output_dir", self._controls._output_dir)
        )

    def _on_output_folder_change(self, folder: str):
        self._config["output_dir"] = folder
        save_config(self._config)

    # ── Model management ───────────────────────────────────────────────────────

    def _check_model(self):
        """Load or prompt to download the configured model."""
        model_name = self._config.get("selected_model", "XTTS v2 — Multilingual Pro")
        spec = MODEL_CATALOG.get(model_name, {})
        from core.model_manager import is_model_downloaded
        if is_model_downloaded(spec.get("model_id", "")):
            self._load_model_bg(model_name)
        else:
            # Prompt to run wizard / download
            if messagebox.askyesno(
                "Model Not Downloaded",
                f"The model '{model_name}' is not downloaded.\n\n"
                "Download it now? (~" + str(spec.get("size_gb", 0)) + " GB)\n\n"
                "You can also change the model in Settings.",
            ):
                self._download_model_bg(model_name, spec)
            else:
                self._model_pill.configure(
                    text="  ⚠ No model  ",
                    text_color=WARNING,
                )

    def _load_model_bg(self, model_name: str = ""):
        self._model_pill.configure(
            text="  ◌ Loading…  ",
            text_color=WARNING,
        )
        self._terminal.write(f"[System] Loading model: {model_name}\n", "blue")

        def _load():
            try:
                self._engine.load_model(
                    progress_callback=lambda m: self._q.put((_Q_MODEL_STATUS, m))
                )
                self._q.put((_Q_MODEL_STATUS, "__done__"))
            except Exception as exc:
                self._q.put((_Q_MODEL_STATUS, f"__error__{exc}"))

        threading.Thread(target=_load, daemon=True).start()

    def _download_model_bg(self, model_name: str, spec: Optional[dict] = None):
        """Download model with progress shown in bottom bar."""
        self._bar.start_generation(1)
        self._bar._set_status(f"Downloading {model_name}…", TEXT_SUB)

        capture = _StderrCapture(self._q)
        sys.stderr = capture

        def _dl():
            try:
                self._engine.load_model(
                    progress_callback=lambda m: self._q.put((_Q_MODEL_STATUS, m))
                )
                self._q.put((_Q_MODEL_STATUS, "__done__"))
            except Exception as exc:
                self._q.put((_Q_MODEL_STATUS, f"__error__{exc}"))
            finally:
                sys.stderr = sys.__stderr__

        threading.Thread(target=_dl, daemon=True).start()

    # ── Synthesis ──────────────────────────────────────────────────────────────

    def _start_synthesis(self):
        if not self._engine.is_loaded:
            messagebox.showwarning(
                "Model Not Ready",
                "The voice model is still loading. Please wait a moment.",
            )
            return

        script = self._controls.get_script_text()
        if not script.strip():
            messagebox.showwarning("Empty Script", "Please enter a script first.")
            return

        settings = self._controls.get_settings()

        # Voice cloning: requires a reference audio file
        if settings["voice_profile"] == "Custom (Clone)":
            ref = settings.get("clone_ref_path")
            if not ref or not Path(ref).exists():
                messagebox.showwarning(
                    "No Reference Audio",
                    "Voice cloning requires a reference audio file.\n\n"
                    "Go to the Advanced tab → Voice Profile → Custom (Clone) "
                    "and click Browse to select a WAV or MP3 sample (5–30 seconds).",
                )
                return
            self._terminal.write(
                f"[Generate] Voice clone mode — XTTS v2 will load on first use (~1.87 GB)\n",
                "blue",
            )

        # Prepare output path
        from core.tts_engine import chunk_text
        chunks     = chunk_text(script)
        total      = len(chunks)
        output_dir = Path(settings["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_stem = output_dir / f"aura_voice_{ts}"

        self._cancel.clear()
        self._bar.start_generation(total)
        self._controls.set_generating(True)
        self._output.show_generating_state("Synthesising audio…")
        self._terminal.write(f"[Generate] Script: {len(script)} chars, {total} chunk(s)\n", "blue")

        # Map voice profile to internal settings
        ref_wav = (
            Path(settings["clone_ref_path"])
            if settings.get("clone_ref_path")
            else None
        )
        lang_code = LANGUAGE_CODES.get(settings["language"], "en")

        def _run():
            self._engine.synthesise(
                text=script,
                output_path=output_stem,
                voice_profile=settings["voice_profile"],
                emotion=settings["delivery_style"],
                speed=settings["speed"],
                language=lang_code,
                output_format=settings["output_format"].lower(),
                reference_wav=ref_wav,
                cancel_event=self._cancel,
                on_chunk_start=lambda c, t:   self._q.put((_Q_CHUNK_START, (c, t))),
                on_chunk_done= lambda c, t, e: self._q.put((_Q_CHUNK_DONE,  (c, t, e))),
                on_stitch_start=lambda:        self._q.put((_Q_STITCH_START, None)),
                on_stitch_progress=lambda c,t: self._q.put((_Q_STITCH_PROG, (c, t))),
                on_export_start=lambda f:      self._q.put((_Q_EXPORT_START, f)),
                on_complete=lambda p:          self._q.put((_Q_COMPLETE, p)),
                on_error=lambda m:             self._q.put((_Q_ERROR, m)),
            )

        self._synth_thread = threading.Thread(target=_run, daemon=True)
        self._synth_thread.start()

    def _cancel_synthesis(self):
        self._cancel.set()
        self._bar.set_cancelled()
        self._controls.set_generating(False)
        self._output.stop_generating_state()
        self._terminal.write("[Generate] Cancelled by user.\n", "yellow")

    # ── Queue poll ─────────────────────────────────────────────────────────────

    def _start_poll(self):
        self._poll()

    def _poll(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def _handle(self, kind: str, payload):
        if kind == _Q_MODEL_STATUS:
            if payload == "__done__":
                name = self._config.get("selected_model", "XTTS v2")
                short = name.split("—")[0].strip()
                self._model_pill.configure(
                    text=f"  ● {short}  ",
                    text_color=SUCCESS,
                    fg_color=SUCCESS_BG,
                )
                self._terminal.write(f"[Model] Ready: {name}\n", "green")
            elif payload.startswith("__error__"):
                err = payload.replace("__error__", "")
                self._model_pill.configure(
                    text="  ● Error  ",
                    text_color=ERROR,
                )
                self._terminal.write(f"[Model] Error: {err}\n", "red")
                messagebox.showerror("Model Error", err)
            else:
                self._model_pill.configure(
                    text=f"  ◌ {payload[:30]}  ",
                    text_color=WARNING,
                )

        elif kind == _Q_DL_PROGRESS:
            done, total = payload
            pct = (done / total * 100) if total > 0 else 0
            self._bar.set_progress(pct, f"Downloading model… {pct:.0f}%")

        elif kind == _Q_CHUNK_START:
            c, t = payload
            self._bar._set_status(f"Synthesising chunk {c} / {t}…", TEXT_SUB)
            self._terminal.write(f"  chunk {c}/{t}\n", "green")

        elif kind == _Q_CHUNK_DONE:
            c, t, eta = payload
            self._bar.update_chunk(c, t, eta)

        elif kind == _Q_STITCH_START:
            self._bar.set_stitching()
            self._terminal.write("[Generate] Stitching audio…\n", "blue")

        elif kind == _Q_STITCH_PROG:
            self._bar.set_stitch_progress(*payload)

        elif kind == _Q_EXPORT_START:
            self._bar.set_exporting(payload)
            self._terminal.write(f"[Generate] Exporting {payload}…\n", "blue")

        elif kind == _Q_COMPLETE:
            path: Path = payload
            self._last_output = path
            self._bar.set_complete(str(path.name))
            self._controls.set_generating(False)
            self._terminal.write(f"[Generate] Done: {path}\n", "green")

            # Generate thumbnail
            self._generate_thumbnail_and_update(path)

        elif kind == _Q_ERROR:
            self._bar.set_error(payload)
            self._controls.set_generating(False)
            self._output.stop_generating_state()
            self._terminal.write(f"[Generate] Error: {payload}\n", "red")
            messagebox.showerror("Synthesis Error", payload)

    # ── Thumbnail + output update ──────────────────────────────────────────────

    def _generate_thumbnail_and_update(self, audio_path: Path):
        """Generate a thumbnail in background, then update the output panel."""
        settings = self._controls.get_settings()
        emotion  = settings.get("delivery_style", "Neutral")
        profile  = settings.get("voice_profile", "Natural Female")

        thumb_dir  = audio_path.parent / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / (audio_path.stem + "_thumb.png")

        script_preview = self._controls.get_script_text()
        title = (script_preview[:40].strip() + "…") if len(script_preview) > 40 else script_preview.strip()
        if not title:
            title = audio_path.stem

        def _bg():
            try:
                from core.thumbnail_generator import generate_thumbnail
                generate_thumbnail(
                    output_path=thumb_path,
                    title=title,
                    emotion=emotion,
                    voice_profile=profile,
                )
            except Exception as exc:
                print(f"[AppWindow] Thumbnail error: {exc}")
            finally:
                self.after(0, lambda: self._do_update_output(audio_path, thumb_path, title))

        threading.Thread(target=_bg, daemon=True).start()

    def _do_update_output(self, audio_path: Path, thumb_path: Optional[Path], title: str):
        """Update output panel on the main thread."""
        self._output.stop_generating_state()

        # Calculate duration
        duration_str = self._get_duration_str(audio_path)
        fmt = audio_path.suffix.lstrip(".").upper()

        self._output.update_output(
            audio_path=audio_path,
            thumbnail_path=thumb_path,
            title=title,
            duration_str=duration_str,
            format_label=fmt,
        )

        # Navigate to generate view to show result
        if self._current_section != "generate":
            self._navigate("generate")

        # Auto-open folder if configured
        if self._config.get("auto_open_folder", False):
            self._open_folder()

    def _get_duration_str(self, audio_path: Path) -> str:
        """Return a human-readable duration for an audio file."""
        try:
            from pydub import AudioSegment
            seg  = AudioSegment.from_file(str(audio_path))
            ms   = len(seg)
            secs = ms // 1000
            mins, s = divmod(secs, 60)
            return f"{mins}m {s}s" if mins else f"{s}s"
        except Exception:
            return "—"

    # ── File operations ────────────────────────────────────────────────────────

    def _new_project(self):
        if messagebox.askyesno("New Project", "Discard the current script and settings?"):
            # Clear script
            try:
                self._controls.script_box.delete("0.0", "end")
                self._controls._placeholder_active = False
                self._controls._update_word_count()
            except Exception:
                pass
            self._project_path = None
            self._bar.reset()
            self.title(self.WINDOW_TITLE)

    def _open_project(self):
        p = filedialog.askopenfilename(
            title="Open Project",
            filetypes=[
                ("AURA VOICE Project", "*.avp *.auravoice"),
                ("JSON", "*.json"),
                ("All", "*.*"),
            ],
        )
        if not p:
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "script" in data:
                self._controls.script_box.delete("0.0", "end")
                self._controls.script_box.insert("0.0", data["script"])
                self._controls._placeholder_active = False
                self._controls._update_word_count()
            if "settings" in data:
                self._controls.load_settings(data["settings"])
            self._project_path = Path(p)
            self.title(f"{Path(p).stem}  —  {self.WINDOW_TITLE}")
        except Exception as exc:
            messagebox.showerror("Open Error", str(exc))

    def _save_project(self):
        if self._project_path:
            self._do_save(self._project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        p = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".avp",
            filetypes=[("AURA VOICE Project", "*.avp"), ("All", "*.*")],
        )
        if not p:
            return
        self._project_path = Path(p)
        self._do_save(self._project_path)
        self.title(f"{Path(p).stem}  —  {self.WINDOW_TITLE}")

    def _do_save(self, path: Path):
        script = self._controls.get_script_text()
        if not script.strip():
            messagebox.showwarning("Empty", "Nothing to save — script is empty.")
            return
        try:
            data = {
                "format":   "auravoice_v2",
                "version":  APP_VERSION,
                "script":   script,
                "settings": self._controls.get_settings(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            messagebox.showinfo("Saved", f"Project saved:\n{path}")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def _import_txt(self):
        p = filedialog.askopenfilename(
            title="Import Script",
            filetypes=[("Text files", "*.txt"), ("All", "*.*")],
        )
        if p:
            try:
                content = Path(p).read_text(encoding="utf-8", errors="replace")
                self._controls.script_box.delete("0.0", "end")
                self._controls.script_box.insert("0.0", content)
                self._controls._placeholder_active = False
                self._controls._update_word_count()
            except Exception as exc:
                messagebox.showerror("Import Error", str(exc))

    def _export(self, fmt: str):
        if not self._last_output:
            messagebox.showinfo("Export", "No audio generated yet.")
            return
        dest = filedialog.asksaveasfilename(
            title=f"Export {fmt.upper()}",
            defaultextension=f".{fmt}",
            filetypes=[(f"{fmt.upper()} Audio", f"*.{fmt}")],
        )
        if not dest:
            return
        try:
            import shutil
            src = self._last_output.with_suffix(f".{fmt}")
            if src.exists():
                shutil.copy2(str(src), dest)
            elif fmt == "mp3":
                from core.audio_utils import wav_to_mp3
                wav_to_mp3(self._last_output.with_suffix(".wav"), Path(dest))
            else:
                raise FileNotFoundError(f"Output file not found: {src}")
            messagebox.showinfo("Exported", f"Saved to:\n{dest}")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc))

    def _open_folder(self):
        folder = (
            self._last_output.parent
            if self._last_output
            else Path(self._controls._output_dir)
        )
        try:
            platform = sys.platform
            if platform == "darwin":
                subprocess.call(["open", str(folder)])
            elif platform == "win32":
                # Use getattr to avoid static-analysis unreachability warnings
                getattr(os, "startfile")(str(folder))
            else:
                subprocess.call(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Open Folder Error", str(exc))

    # ── Misc ───────────────────────────────────────────────────────────────────

    def _toggle_theme(self):
        mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if mode == "Dark" else "dark")

    def _show_about(self):
        import platform, sys as _sys
        win = ctk.CTkToplevel(self)
        win.title("About AURA VOICE")
        win.geometry("480x560")
        win.resizable(False, False)
        win.configure(fg_color="#0a0a0f")
        win.grab_set()
        win.focus_set()

        # ── Header bar ──────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(win, fg_color="#111118", corner_radius=0, height=72)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="◈",
            font=(FONTS["xl_bold"][0], 28),
            text_color="#e2e8f0",
        ).pack(side="left", padx=(PAD["xl"], PAD["sm"]))

        title_col = ctk.CTkFrame(hdr, fg_color="transparent")
        title_col.pack(side="left", pady=12)

        ctk.CTkLabel(
            title_col,
            text="AURA VOICE",
            font=(FONTS["2xl_bold"][0], 20, "bold"),
            text_color="#f1f5f9",
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_col,
            text=APP_TAGLINE,
            font=FONTS["xs"],
            text_color="#475569",
            anchor="w",
        ).pack(anchor="w")

        # ── Version / build row ─────────────────────────────────────────────
        ctk.CTkFrame(win, fg_color="#1e1e2e", height=1, corner_radius=0).pack(fill="x")
        ver_row = ctk.CTkFrame(win, fg_color="#0d0d14", corner_radius=0, height=36)
        ver_row.pack(fill="x")
        ver_row.pack_propagate(False)

        ctk.CTkLabel(
            ver_row,
            text=f"  v{APP_VERSION}",
            font=FONTS["mono_xs"],
            text_color="#64748b",
        ).pack(side="left", padx=4)

        ctk.CTkLabel(
            ver_row,
            text="·  build 16 Mar 2026  ·  Python " + _sys.version.split()[0] + f"  ·  {platform.machine()}",
            font=FONTS["mono_xs"],
            text_color="#334155",
        ).pack(side="left")

        # ── Status strip ────────────────────────────────────────────────────
        ctk.CTkFrame(win, fg_color="#1e1e2e", height=1, corner_radius=0).pack(fill="x")
        status_row = ctk.CTkFrame(win, fg_color="#0a0a0f", corner_radius=0)
        status_row.pack(fill="x", padx=PAD["xl"], pady=(PAD["md"], 0))

        model_name  = self._config.get("selected_model", "VCTK VITS").split("—")[0].strip()
        model_color = "#10b981" if self._engine.is_loaded else "#f59e0b"

        for dot, label, color in [
            ("●", "100% Offline",    "#10b981"),
            ("●", "No API Keys",     "#10b981"),
            ("●", "No Subscriptions","#10b981"),
            ("●" if self._engine.is_loaded else "○", model_name, model_color),
        ]:
            row = ctk.CTkFrame(status_row, fg_color="transparent")
            row.pack(anchor="w", pady=1)
            ctk.CTkLabel(row, text=dot, font=FONTS["xs"], text_color=color, width=14).pack(side="left")
            ctk.CTkLabel(row, text=label, font=FONTS["xs"], text_color="#94a3b8").pack(side="left", padx=(4,0))

        # ── Separator ───────────────────────────────────────────────────────
        ctk.CTkFrame(win, fg_color="#1e1e2e", height=1, corner_radius=0).pack(fill="x", pady=(PAD["md"], 0))

        # ── Two-column tech stack ───────────────────────────────────────────
        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="x", padx=PAD["xl"], pady=(PAD["md"], 0))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            body, text="COMPONENTS",
            font=FONTS["xs_bold"], text_color="#334155",
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, PAD["xs"]))
        ctk.CTkLabel(
            body, text="SYSTEM",
            font=FONTS["xs_bold"], text_color="#334155",
            anchor="w",
        ).grid(row=0, column=1, sticky="w", pady=(0, PAD["xs"]))

        components = [
            ("Coqui TTS",       "0.22.0"),
            ("VCTK VITS",       "en · 109 voices"),
            ("CustomTkinter",   "5.x"),
            ("pydub",           "audio"),
            ("PyTorch",         "2.6"),
            ("pygame",          "2.6 · playback"),
            ("Pillow",          "thumbnails"),
            ("espeak-ng",       "phonemizer"),
        ]
        sys_info = [
            ("Python",    _sys.version.split()[0]),
            ("Platform",  platform.system()),
            ("Arch",      platform.machine()),
            ("OS",        platform.mac_ver()[0] if platform.system()=="Darwin" else platform.release()),
            ("Processor", platform.processor()[:18] if platform.processor() else "—"),
            ("Build",     "16 Mar 2026"),
            ("Format",    ".avp / .wav / .mp3"),
            ("License",   "MIT / Apache 2.0"),
        ]

        for i, ((cname, cver), (sname, sval)) in enumerate(zip(components, sys_info), start=1):
            ctk.CTkLabel(
                body, text=f"· {cname}",
                font=FONTS["xs"], text_color="#94a3b8", anchor="w",
            ).grid(row=i, column=0, sticky="w")
            ctk.CTkLabel(
                body, text=cver,
                font=FONTS["mono_xs"], text_color="#475569", anchor="w",
            ).grid(row=i, column=0, sticky="e", padx=(0, PAD["xl"]))

            ctk.CTkLabel(
                body, text=f"· {sname}",
                font=FONTS["xs"], text_color="#94a3b8", anchor="w",
            ).grid(row=i, column=1, sticky="w")
            ctk.CTkLabel(
                body, text=sval,
                font=FONTS["mono_xs"], text_color="#475569", anchor="w",
            ).grid(row=i, column=1, sticky="e")

        # ── Footer ──────────────────────────────────────────────────────────
        ctk.CTkFrame(win, fg_color="#1e1e2e", height=1, corner_radius=0).pack(fill="x", pady=(PAD["lg"], 0))

        foot = ctk.CTkFrame(win, fg_color="#0d0d14", corner_radius=0)
        foot.pack(fill="x", padx=PAD["xl"], pady=PAD["md"])

        ctk.CTkLabel(
            foot,
            text="github.com/fireyhellmarketing-cmd/aura-voice",
            font=FONTS["mono_xs"],
            text_color="#334155",
            cursor="hand2",
        ).pack(side="left")

        ctk.CTkButton(
            foot, text="Close",
            width=72, height=28,
            fg_color="#1e1e2e",
            hover_color="#252540",
            text_color="#94a3b8",
            border_color="#252540",
            border_width=1,
            corner_radius=PAD["sm"],
            font=FONTS["xs_bold"],
            command=win.destroy,
        ).pack(side="right")

    def _check_cache_info(self):
        from core.model_manager import is_model_downloaded, get_downloaded_size_gb
        model_name = self._config.get("selected_model", "")
        spec  = MODEL_CATALOG.get(model_name, {})
        mid   = spec.get("model_id", "")
        dl    = is_model_downloaded(mid)
        sz    = get_downloaded_size_gb(mid) if dl else 0.0
        loaded = self._engine.is_loaded
        messagebox.showinfo(
            "Model Cache",
            f"Model: {model_name}\n"
            f"Cached on disk: {'Yes' if dl else 'No'}\n"
            f"Disk usage: {sz:.2f} GB\n"
            f"Loaded in memory: {'Yes' if loaded else 'No'}\n\n"
            f"Cache root: ~/.local/share/tts/",
        )
