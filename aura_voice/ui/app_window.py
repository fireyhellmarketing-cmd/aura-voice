"""AURA VOICE v3 — Main application window (centered single-column layout)."""

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
    BG_DEEP, SURFACE, BORDER, BORDER2,
    ACCENT, ACCENT_HOV,
    TEXT, TEXT_SUB, TEXT_DIM,
    ACCENT_DIM,
    SUCCESS, SUCCESS_BG, WARNING, ERROR,
    apply_ctk_theme,
)
from core.model_manager import load_config, MODEL_CATALOG
from core.tts_engine import TTSEngine, LANGUAGE_CODES
from ui.main_view import MainView
from ui.settings_sheet import SettingsSheet
from ui.terminal_widget import TerminalWidget


# ─── Queue message types ────────────────────────────────────────────────────────
_Q_CHUNK_START  = "chunk_start"
_Q_CHUNK_DONE   = "chunk_done"
_Q_STITCH_START = "stitch_start"
_Q_STITCH_PROG  = "stitch_prog"
_Q_EXPORT_START = "export_start"
_Q_COMPLETE     = "complete"
_Q_ERROR        = "error"
_Q_MODEL_STATUS = "model_status"
_Q_DL_PROGRESS  = "dl_progress"


# ─── Stderr interceptor ────────────────────────────────────────────────────────

class _StderrCapture:
    """Wraps sys.stderr; parses tqdm progress lines and posts to the UI queue."""

    _PCT_RE  = re.compile(r'(\d+)%')
    _SIZE_RE = re.compile(r'([\d.]+)([KMGT]?)iB/([\d.]+)([KMGT]?)iB')
    _UNITS   = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}

    def __init__(self, ui_queue: queue.Queue):
        self._q    = ui_queue
        # sys.__stderr__ is always a real stream; cast to satisfy type-checkers.
        import io
        self._real: io.TextIOBase = sys.__stderr__  # type: ignore[assignment]

    def write(self, text: str):
        self._real.write(text)  # type: ignore[union-attr]
        self._parse(text)

    def flush(self):
        self._real.flush()  # type: ignore[union-attr]

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
            self._q.put((_Q_DL_PROGRESS, (int(p.group(1)), 100)))


# ─── Main Application Window ───────────────────────────────────────────────────

class AuraVoiceApp(ctk.CTk):
    """
    AURA VOICE v3 main window — centered single-column layout.

    ┌─────────────────────────────────────────────────────┐
    │  TITLE BAR  (macOS controls · AURA VOICE · ⚙)       │
    ├─────────────────────────────────────────────────────┤
    │                                                     │
    │          ┌───── centered column ─────┐             │
    │          │  upload strip             │             │
    │          │  textarea                 │             │
    │          │  [voice] [speed] [emotion]│             │
    │          │  [  Generate  ]           │             │
    │          │  output card              │             │
    │          └───────────────────────────┘             │
    │                                                     │
    ├─────────────────────────────────────────────────────┤
    │  TERMINAL (collapsible)                             │
    └─────────────────────────────────────────────────────┘

    Settings sheet slides in from the right when the gear icon is clicked.
    """

    WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION}"

    def __init__(self, config: Optional[dict] = None):
        super().__init__()

        apply_ctk_theme()

        # ── Config ──
        self._config = config or load_config()

        # ── State ──
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        self._cancel        = threading.Event()
        self._q: queue.Queue = queue.Queue()
        self._synth_thread: Optional[threading.Thread] = None
        self._last_output:  Optional[Path] = None
        self._project_path: Optional[Path] = None

        # Generation progress tracking (for status messages)
        self._gen_total  = 1
        self._gen_done   = 0
        self._gen_start  = 0.0

        # ── Engine ──
        self._engine = TTSEngine()

        # ── Window ──
        self.title(self.WINDOW_TITLE)
        self.geometry(f"{WINDOW['width']}x{WINDOW['height']}")
        self.minsize(WINDOW['min_width'], WINDOW['min_height'])
        self.configure(fg_color=BG_DEEP)

        self._build_menu()
        self._build_ui()
        self._start_poll()

        # Load model after window is ready
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
        v.add_command(label="Toggle Dark / Light",   command=self._toggle_theme)
        v.add_command(label="Show / Hide Terminal",  command=self._toggle_terminal)
        v.add_separator()
        v.add_command(label="Settings",              command=self._toggle_settings)
        v.add_command(label="History",               command=self._show_history)

        h = _m("Help")
        h.add_command(label="About AURA VOICE",      command=self._show_about)
        h.add_command(label="Check Model Cache",     command=self._check_cache_info)

        self.config(menu=mb)

        self.bind_all("<Command-n>", lambda _: self._new_project())
        self.bind_all("<Command-o>", lambda _: self._open_project())
        self.bind_all("<Command-s>", lambda _: self._save_project())

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.rowconfigure(0, weight=0)  # title bar
        self.rowconfigure(1, weight=1)  # body
        self.rowconfigure(2, weight=0)  # terminal
        self.columnconfigure(0, weight=1)

        # Title bar
        self._build_titlebar()

        # Body — holds main view
        body = ctk.CTkFrame(self, fg_color=BG_DEEP, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        # Main centered view
        self._main_view = MainView(body)
        self._main_view.grid(row=0, column=0, sticky="nsew")
        self._main_view.on_generate = self._start_synthesis
        self._main_view.set_output_dir(
            self._config.get("output_dir", str(Path.home() / "Documents" / "AuraVoice"))
        )
        self._main_view.set_output_format(
            self._config.get("output_format", "WAV")
        )

        # Terminal (collapsible, row 2)
        self._terminal = TerminalWidget(
            self,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        self._terminal.grid(row=2, column=0, sticky="ew")

        # Settings sheet (placed over body, starts off-screen)
        self._settings_sheet = SettingsSheet(
            self,
            config=self._config,
            on_close=None,
            on_config_change=self._on_settings_change,
        )

    def _build_titlebar(self):
        tbar = ctk.CTkFrame(self, fg_color=BG_DEEP, corner_radius=0, height=52)
        tbar.grid(row=0, column=0, sticky="ew")
        tbar.grid_propagate(False)
        tbar.columnconfigure(0, weight=1)   # spacer left
        tbar.columnconfigure(1, weight=0)   # centered title
        tbar.columnconfigure(2, weight=1)   # spacer right (gear lives here)

        # Left spacer (macOS traffic-light area)
        left_pad = ctk.CTkFrame(tbar, fg_color="transparent", width=80)
        left_pad.grid(row=0, column=0, sticky="w")

        # ── Center: brand name ──
        brand = ctk.CTkFrame(tbar, fg_color="transparent")
        brand.grid(row=0, column=1)

        # Model status pill (left of title)
        self._model_pill = ctk.CTkLabel(
            brand,
            text="  ◌ Loading…  ",
            font=FONTS["xs"],
            text_color=WARNING,
            fg_color=SURFACE,
            corner_radius=10,
        )
        self._model_pill.pack(side="left", padx=(0, PAD["md"]))

        # App name — Georgia italic (CTk font tuples only support a single style keyword)
        ctk.CTkLabel(
            brand,
            text=APP_NAME,
            font=("Georgia", 20, "italic"),
            text_color=TEXT,
        ).pack(side="left")

        # ── Right: gear icon button ──
        right_area = ctk.CTkFrame(tbar, fg_color="transparent")
        right_area.grid(row=0, column=2, sticky="e", padx=(0, PAD["xl"]))

        self._gear_btn = ctk.CTkButton(
            right_area,
            text="⚙",
            width=34, height=34,
            fg_color="transparent",
            hover_color=BORDER2,
            text_color=TEXT_DIM,
            corner_radius=17,
            font=(FONTS["base"][0], 18),
            command=self._toggle_settings,
        )
        self._gear_btn.pack(side="right")

        # Bind hover to change color
        self._gear_btn.bind("<Enter>", lambda *_: self._gear_btn.configure(text_color=ACCENT_HOV))
        self._gear_btn.bind("<Leave>", lambda *_: self._gear_btn.configure(text_color=TEXT_DIM))

    # ── Settings sheet ─────────────────────────────────────────────────────────

    def _toggle_settings(self):
        if self._settings_sheet.is_open():
            self._settings_sheet.close()
        else:
            self._settings_sheet.open()

    def _on_settings_change(self, new_config: dict):
        self._config.update(new_config)
        if "output_dir" in new_config:
            self._main_view.set_output_dir(new_config["output_dir"])
        if "output_format" in new_config:
            self._main_view.set_output_format(new_config["output_format"])

    # ── History overlay ────────────────────────────────────────────────────────

    def _show_history(self):
        """Show a toplevel history window."""
        records = self._main_view.get_history()
        win = ctk.CTkToplevel(self)
        win.title("Generation History")
        win.geometry("640x500")
        win.configure(fg_color=BG_DEEP)
        win.grab_set()
        win.focus_set()

        hdr = ctk.CTkFrame(win, fg_color="transparent", height=48)
        hdr.pack(fill="x", padx=PAD["page"])
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr, text="Generation History",
            font=FONTS["lg_bold"], text_color=TEXT,
        ).pack(side="left", pady=10)

        ctk.CTkLabel(
            hdr,
            text=f"{len(records)} item{'s' if len(records) != 1 else ''}",
            font=FONTS["sm"], text_color=TEXT_DIM,
        ).pack(side="right", pady=10)

        ctk.CTkFrame(win, fg_color=BORDER, height=1).pack(fill="x")

        scroll = ctk.CTkScrollableFrame(
            win, fg_color="transparent",
            scrollbar_button_color=BORDER2,
            scrollbar_button_hover_color=BORDER,
        )
        scroll.pack(fill="both", expand=True, padx=PAD["page"], pady=PAD["md"])

        if not records:
            ctk.CTkLabel(
                scroll,
                text="No generations yet.",
                font=FONTS["base"], text_color=TEXT_DIM,
            ).pack(pady=40)
            return

        for rec in records:
            row = ctk.CTkFrame(
                scroll,
                fg_color=SURFACE,
                corner_radius=12,
                border_color=BORDER2,
                border_width=1,
            )
            row.pack(fill="x", pady=(0, PAD["md"]))

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, padx=PAD["card"], pady=PAD["card"])

            title = rec.title[:55] + ("…" if len(rec.title) > 55 else "")
            ctk.CTkLabel(info, text=title, font=FONTS["sm_bold"], text_color=TEXT, anchor="w").pack(anchor="w")
            ctk.CTkLabel(info, text=rec.audio_path.name, font=FONTS["mono_xs"], text_color=TEXT_DIM, anchor="w").pack(anchor="w")

            meta = ctk.CTkFrame(info, fg_color="transparent")
            meta.pack(anchor="w", pady=(2, 0))
            ctk.CTkLabel(
                meta, text=f"  {rec.duration_str}  ",
                font=FONTS["xs_bold"], text_color=ACCENT, fg_color=ACCENT_DIM,
                corner_radius=10,
            ).pack(side="left", padx=(0, 4))
            ctk.CTkLabel(
                meta, text=f"  {rec.format_label}  ",
                font=FONTS["xs_bold"], text_color="#f59e0b", fg_color="#451a03",
                corner_radius=10,
            ).pack(side="left")

            btn_col = ctk.CTkFrame(row, fg_color="transparent")
            btn_col.pack(side="right", padx=PAD["card"], pady=PAD["card"])

            ctk.CTkButton(
                btn_col, text="▶  Play",
                width=88, height=30,
                fg_color=ACCENT, hover_color=ACCENT_HOV,
                text_color="#FFFFFF", corner_radius=8,
                font=FONTS["sm_bold"],
                command=lambda r=rec: self._history_play(r),
            ).pack(pady=(0, 4))

            ctk.CTkButton(
                btn_col, text="📂  Open",
                width=88, height=30,
                fg_color="transparent", hover_color=BORDER2,
                text_color=TEXT_SUB, border_color=BORDER2, border_width=1,
                corner_radius=8, font=FONTS["xs"],
                command=lambda r=rec: self._history_open_folder(r),
            ).pack()

    def _history_play(self, rec):
        if not rec.audio_path.exists():
            messagebox.showerror("Not Found", f"File not found:\n{rec.audio_path}")
            return
        _plat = sys.platform
        try:
            if _plat == "darwin":
                subprocess.Popen(["afplay", str(rec.audio_path)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif _plat == "win32":
                os.startfile(str(rec.audio_path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["aplay", str(rec.audio_path)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            messagebox.showerror("Playback Error", str(exc))

    def _history_open_folder(self, rec):
        _plat = sys.platform
        try:
            folder = rec.audio_path.parent
            if _plat == "darwin":
                subprocess.call(["open", str(folder)])
            elif _plat == "win32":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            else:
                subprocess.call(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Open Folder Error", str(exc))

    # ── Model management ───────────────────────────────────────────────────────

    def _check_model(self):
        model_name = self._config.get("selected_model", "VCTK VITS — Fast English (Default)")
        spec = MODEL_CATALOG.get(model_name, {})
        from core.model_manager import is_model_downloaded
        if is_model_downloaded(spec.get("model_id", "")):
            self._load_model_bg(model_name)
        else:
            if messagebox.askyesno(
                "Model Not Downloaded",
                f"The model '{model_name}' is not downloaded.\n\n"
                f"Download it now? (~{spec.get('size_gb', 0)} GB)\n\n"
                "You can also change the model in Settings.",
            ):
                self._download_model_bg(model_name, spec)
            else:
                self._model_pill.configure(
                    text="  ⚠ No model  ",
                    text_color=WARNING,
                    fg_color="transparent",
                )

    def _load_model_bg(self, model_name: str = ""):
        self._model_pill.configure(text="  ◌ Loading…  ", text_color=WARNING)
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
        size_gb = (spec or {}).get("size_gb", 0)
        self._model_pill.configure(text="  ⬇ Downloading…  ", text_color=WARNING)
        self._terminal.write(
            f"[System] Downloading {model_name} (~{size_gb} GB)…\n", "blue"
        )

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

        script = self._main_view.get_script_text()
        if not script.strip():
            messagebox.showwarning("Empty Script", "Please enter a script first.")
            return

        settings = self._main_view.get_settings()

        # Voice cloning: requires a reference audio file
        if settings["voice_profile"] == "Custom (Clone)":
            ref = settings.get("clone_ref_path")
            if not ref or not Path(ref).exists():
                messagebox.showwarning(
                    "No Reference Audio",
                    "Voice cloning requires a reference audio file.\n\n"
                    "Set a clone reference path in settings.",
                )
                return
            self._terminal.write(
                "[Generate] Voice clone mode — XTTS v2 will load on first use (~1.87 GB)\n",
                "blue",
            )

        # Prepare output path
        from core.tts_engine import chunk_text
        chunks     = chunk_text(script)
        total      = len(chunks)
        output_dir = Path(settings["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_stem = output_dir / f"aura_voice_{ts}"

        self._cancel.clear()
        self._gen_total = total
        self._gen_done  = 0
        self._gen_start = __import__("time").time()

        self._main_view.set_generating(True)
        self._terminal.write(
            f"[Generate] Script: {len(script)} chars, {total} chunk(s)\n", "blue"
        )

        ref_wav = (
            Path(settings["clone_ref_path"])
            if settings.get("clone_ref_path")
            else None
        )
        lang_code = LANGUAGE_CODES.get(settings.get("language", "English"), "en")

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
        self._main_view.set_generating(False)
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
                name  = self._config.get("selected_model", "VCTK VITS")
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
                    fg_color="transparent",
                )
                self._terminal.write(f"[Model] Error: {err}\n", "red")
                messagebox.showerror("Model Error", err)
            else:
                self._model_pill.configure(
                    text=f"  ◌ {payload[:28]}  ",
                    text_color=WARNING,
                )

        elif kind == _Q_DL_PROGRESS:
            done, total = payload
            pct = (done / total * 100) if total > 0 else 0
            self._model_pill.configure(
                text=f"  ⬇ {pct:.0f}%  ",
                text_color=WARNING,
            )

        elif kind == _Q_CHUNK_START:
            c, t = payload
            self._gen_done = c - 1
            self._terminal.write(f"  chunk {c}/{t}\n", "green")

        elif kind == _Q_CHUNK_DONE:
            c, t, _eta = payload
            self._gen_done = c
            del t, _eta  # consumed by engine; not displayed in this layout

        elif kind == _Q_STITCH_START:
            self._terminal.write("[Generate] Stitching audio…\n", "blue")

        elif kind == _Q_STITCH_PROG:
            pass  # no separate progress bar in new layout

        elif kind == _Q_EXPORT_START:
            self._terminal.write(f"[Generate] Exporting {payload}…\n", "blue")

        elif kind == _Q_COMPLETE:
            path: Path = payload
            self._last_output = path
            self._main_view.set_generating(False)
            self._terminal.write(f"[Generate] Done: {path}\n", "green")
            self._finalize_output(path)

        elif kind == _Q_ERROR:
            self._main_view.set_generating(False)
            self._terminal.write(f"[Generate] Error: {payload}\n", "red")
            messagebox.showerror("Synthesis Error", payload)

    # ── Output finalization ────────────────────────────────────────────────────

    def _finalize_output(self, audio_path: Path):
        """Compute duration (in background) then call show_output on main thread."""
        def _bg():
            dur_str = self._get_duration_str(audio_path)
            self.after(0, lambda: self._main_view.show_output(audio_path, dur_str))
            # Auto-play if configured
            if self._config.get("auto_play", False):
                self.after(200, lambda: self._main_view._start_playback())

        threading.Thread(target=_bg, daemon=True).start()

    def _get_duration_str(self, audio_path: Path) -> str:
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
        if messagebox.askyesno("New Project", "Discard the current script?"):
            self._main_view.load_script("")
            self._main_view._placeholder_active = False
            self._main_view._on_textarea_focus_out()
            self._project_path = None
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
                self._main_view.load_script(data["script"])
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
        script = self._main_view.get_script_text()
        if not script.strip():
            messagebox.showwarning("Empty", "Nothing to save — script is empty.")
            return
        try:
            data = {
                "format":   "auravoice_v2",
                "version":  APP_VERSION,
                "script":   script,
                "settings": self._main_view.get_settings(),
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
                self._main_view.load_script(content)
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
            else Path(self._main_view._output_dir)
        )
        _plat = sys.platform
        try:
            if _plat == "darwin":
                subprocess.call(["open", str(folder)])
            elif _plat == "win32":
                getattr(os, "startfile")(str(folder))
            else:
                subprocess.call(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Open Folder Error", str(exc))

    # ── Misc ───────────────────────────────────────────────────────────────────

    def _toggle_terminal(self):
        self._terminal._toggle()

    def _toggle_theme(self):
        mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if mode == "Dark" else "dark")

    def _check_cache_info(self):
        from core.model_manager import get_model_cache_path
        lines = []
        for name, spec in MODEL_CATALOG.items():
            path  = get_model_cache_path(spec["model_id"])
            dl    = path.exists()
            size  = ""
            if dl:
                try:
                    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                    size  = f" ({total / 1e9:.2f} GB on disk)"
                except Exception:
                    pass
            lines.append(f"{'✓' if dl else '○'} {name}{size}")
        messagebox.showinfo("Model Cache", "\n".join(lines))

    def _show_about(self):
        import platform
        win = ctk.CTkToplevel(self)
        win.title("About AURA VOICE")
        win.geometry("460x420")
        win.resizable(False, False)
        win.configure(fg_color=BG_DEEP)
        win.grab_set()
        win.focus_set()

        hdr = ctk.CTkFrame(win, fg_color=SURFACE, corner_radius=0, height=72)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr, text="◈",
            font=(FONTS["xl_bold"][0], 28), text_color=TEXT,
        ).pack(side="left", padx=(PAD["xl"], PAD["sm"]))

        col = ctk.CTkFrame(hdr, fg_color="transparent")
        col.pack(side="left", pady=12)

        ctk.CTkLabel(
            col, text=APP_NAME,
            font=("Georgia", 18, "italic"), text_color=TEXT, anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            col, text=f"v{APP_VERSION}  ·  {APP_TAGLINE}",
            font=FONTS["xs"], text_color=TEXT_DIM, anchor="w",
        ).pack(anchor="w")

        content = ctk.CTkFrame(win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=PAD["xl"], pady=PAD["xl"])

        info_lines = [
            f"Python  {sys.version.split()[0]}",
            f"Platform  {platform.system()} {platform.machine()}",
            f"Build  16 Mar 2026",
        ]
        for line in info_lines:
            ctk.CTkLabel(
                content, text=line,
                font=FONTS["mono_xs"], text_color=TEXT_DIM, anchor="w",
            ).pack(anchor="w", pady=1)

        ctk.CTkFrame(content, fg_color=BORDER, height=1).pack(fill="x", pady=PAD["md"])

        for dot, label in [
            ("●", "100% Offline"),
            ("●", "No API Keys Required"),
            ("●", "No Subscriptions"),
        ]:
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(anchor="w", pady=1)
            ctk.CTkLabel(row, text=dot, font=FONTS["xs"], text_color=SUCCESS, width=14).pack(side="left")
            ctk.CTkLabel(row, text=label, font=FONTS["xs"], text_color=TEXT_SUB).pack(side="left", padx=(4, 0))

        ctk.CTkButton(
            win, text="Close",
            height=36, corner_radius=8,
            fg_color=ACCENT, hover_color=ACCENT_HOV,
            text_color="#FFFFFF", font=FONTS["sm_bold"],
            command=win.destroy,
        ).pack(pady=(0, PAD["xl"]))
