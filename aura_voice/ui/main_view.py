"""AURA VOICE v3 — Centered single-column main view."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

import customtkinter as ctk

from assets.styles import (
    APP_VERSION,
    BG_DEEP, SURFACE, SURFACE2, ACCENT, ACCENT_HOV, BORDER, BORDER2,
    TEXT, TEXT_SUB, TEXT_DIM, TEXT_GHOST,
    ACCENT_DIM,
    FONTS, PAD, RADIUS,
    SURFACE3,
)

# ─── Voice / Style data ────────────────────────────────────────────────────────

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

SPEED_OPTIONS = [
    "0.50×", "0.75×", "0.90×", "1.00×",
    "1.10×", "1.25×", "1.50×", "1.75×", "2.00×",
]

DEFAULT_OUTPUT_DIR = str(Path.home() / "Documents" / "AuraVoice")

_MAX_CHARS = 5000


# ─── GenerationRecord ─────────────────────────────────────────────────────────

class GenerationRecord:
    def __init__(
        self,
        title: str,
        audio_path: Path,
        thumbnail_path: Optional[Path],
        duration_str: str,
        format_label: str = "WAV",
    ):
        self.title          = title
        self.audio_path     = Path(audio_path)
        self.thumbnail_path = Path(thumbnail_path) if thumbnail_path else None
        self.duration_str   = duration_str
        self.format_label   = format_label
        self.timestamp      = time.time()


# ─── Main View ────────────────────────────────────────────────────────────────

class MainView(ctk.CTkFrame):
    """
    The centered single-column content column.

    Structure (top → bottom):
      1. Upload strip
      2. Main textarea + char counter
      3. Three dropdown pills (voice / speed / emotion)
      4. Generate button
      5. Output card (hidden until generation completes)
    """

    COLUMN_FRACTION = 0.72
    COLUMN_MAX      = 760

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG_DEEP, corner_radius=0, **kwargs)

        # Public callback — set by app_window before first use
        self.on_generate: Optional[Callable] = None

        # Internal state
        self._output_dir        = DEFAULT_OUTPUT_DIR
        self._output_format     = "WAV"
        self._loaded_file_path: Optional[str] = None
        self._clone_ref_path:   Optional[str] = None
        self._placeholder_active = True
        self._history: List[GenerationRecord] = []

        # Playback state
        self._playing        = False
        self._paused         = False
        self._play_start_ms  = 0.0
        self._play_offset_ms = 0
        self._play_duration  = 0
        self._current_output: Optional[Path] = None

        # Generation progress state
        self._gen_total = 0

        # StringVars
        self._voice_var   = ctk.StringVar(value="Natural Female")
        self._speed_var   = ctk.StringVar(value="1.00×")
        self._emotion_var = ctk.StringVar(value="Neutral")

        self._build()

        # Re-center column when window resizes
        self.bind("<Configure>", self._on_resize)

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # Outer frame fills all available space
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Scrollable outer area to handle small windows
        self._outer = ctk.CTkScrollableFrame(
            self,
            fg_color=BG_DEEP,
            corner_radius=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=BORDER2,
        )
        self._outer.grid(row=0, column=0, sticky="nsew")
        self._outer.columnconfigure(0, weight=1)

        # Left spacer | _col | right spacer  — use grid so spacers absorb extra width
        self._outer.columnconfigure(0, weight=1)   # left spacer
        self._outer.columnconfigure(1, weight=0)   # content column (fixed max width)
        self._outer.columnconfigure(2, weight=1)   # right spacer

        # Content column placed in center grid cell
        self._col = ctk.CTkFrame(self._outer, fg_color=BG_DEEP, corner_radius=0)
        self._col.grid(row=0, column=1, sticky="nsew", padx=0, pady=40)
        # _col fills its children horizontally
        self._col.columnconfigure(0, weight=1)

        # Left / right invisible spacer cells (needed for centering)
        ctk.CTkFrame(self._outer, fg_color="transparent", width=0).grid(row=0, column=0)
        ctk.CTkFrame(self._outer, fg_color="transparent", width=0).grid(row=0, column=2)

        self._build_upload_strip()
        self._build_textarea()
        self._build_dropdown_row()
        self._build_generate_btn()
        self._build_progress_area()
        self._build_output_card()

    def _build_upload_strip(self):
        """Dashed-border pill strip for file loading."""
        self._upload_frame = ctk.CTkFrame(
            self._col,
            fg_color=SURFACE,
            corner_radius=12,
            border_color=BORDER2,
            border_width=2,
            height=44,
        )
        self._upload_frame.pack(fill="x", padx=0, pady=(0, 10))
        self._upload_frame.pack_propagate(False)

        self._upload_label = ctk.CTkLabel(
            self._upload_frame,
            text="📎  Drop a .txt file here, or click to browse",
            font=FONTS["sm"],
            text_color=TEXT_DIM,
        )
        self._upload_label.place(relx=0.5, rely=0.5, anchor="center")

        # Clear file button (hidden until file loaded)
        self._clear_file_btn = ctk.CTkButton(
            self._upload_frame,
            text="×",
            width=24, height=24,
            fg_color="transparent",
            hover_color=BORDER2,
            text_color=TEXT_DIM,
            corner_radius=12,
            font=(FONTS["base"][0], 14, "bold"),
            command=self._clear_file,
        )

        # Click to browse
        for widget in [self._upload_frame, self._upload_label]:
            widget.bind("<Button-1>", self._on_upload_click)
            widget.configure(cursor="hand2")

    def _on_upload_click(self, event=None):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Load Script",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            if self._placeholder_active:
                self._textarea.delete("0.0", "end")
                self._placeholder_active = False
                try:
                    self._textarea._textbox.configure(fg=TEXT)
                except Exception:
                    pass
            else:
                self._textarea.delete("0.0", "end")
            self._textarea.insert("0.0", content)
            self._update_char_count()
            self._loaded_file_path = path

            short = Path(path).name
            if len(short) > 42:
                short = short[:39] + "…"
            self._upload_label.configure(
                text=f"  {short}",
                text_color=TEXT,
            )
            self._clear_file_btn.place(relx=0.98, rely=0.5, anchor="e")
        except Exception as exc:
            print(f"[MainView] Load file error: {exc}")

    def _clear_file(self):
        self._loaded_file_path = None
        self._upload_label.configure(
            text="📎  Drop a .txt file here, or click to browse",
            text_color=TEXT_DIM,
        )
        self._clear_file_btn.place_forget()

    def _build_textarea(self):
        """Main script textarea with placeholder and char counter."""
        ta_container = ctk.CTkFrame(
            self._col,
            fg_color=SURFACE,
            corner_radius=16,
            border_color=BORDER,
            border_width=2,
        )
        ta_container.pack(fill="x", padx=0, pady=(0, 10))
        ta_container.pack_propagate(True)

        self._textarea = ctk.CTkTextbox(
            ta_container,
            height=200,
            font=(FONTS["md"][0], 14),
            wrap="word",
            fg_color="transparent",
            border_width=0,
            text_color=TEXT_GHOST,
            scrollbar_button_color=BORDER2,
            scrollbar_button_hover_color=BORDER,
            corner_radius=0,
        )
        self._textarea.pack(fill="x", expand=False, padx=12, pady=(10, 4))
        self._textarea.insert("0.0", "Type or paste your script here…")

        try:
            self._textarea._textbox.configure(insertbackground=TEXT)
        except Exception:
            pass

        self._textarea.bind("<FocusIn>",  self._on_textarea_focus_in)
        self._textarea.bind("<FocusOut>", self._on_textarea_focus_out)
        self._textarea.bind("<KeyRelease>", self._update_char_count)

        # Char count row
        count_row = ctk.CTkFrame(ta_container, fg_color="transparent", height=20)
        count_row.pack(fill="x", padx=12, pady=(0, 8))
        count_row.pack_propagate(False)

        self._char_count_label = ctk.CTkLabel(
            count_row,
            text=f"0 / {_MAX_CHARS}",
            font=(FONTS["xs"][0], 11),
            text_color=TEXT_DIM,
            anchor="e",
        )
        self._char_count_label.pack(side="right")

    def _on_textarea_focus_in(self, event=None):
        if self._placeholder_active:
            self._textarea.delete("0.0", "end")
            self._placeholder_active = False
            try:
                self._textarea._textbox.configure(fg=TEXT)
                self._textarea.configure(text_color=TEXT)
            except Exception:
                pass

    def _on_textarea_focus_out(self, event=None):
        text = self._textarea.get("0.0", "end").strip()
        if not text and not self._placeholder_active:
            self._textarea.insert("0.0", "Type or paste your script here…")
            self._textarea.configure(text_color=TEXT_GHOST)
            try:
                self._textarea._textbox.configure(fg=TEXT_GHOST)
            except Exception:
                pass
            self._placeholder_active = True
            self._char_count_label.configure(text=f"0 / {_MAX_CHARS}")

    def _update_char_count(self, event=None):
        if self._placeholder_active:
            self._char_count_label.configure(text=f"0 / {_MAX_CHARS}")
            return
        text = self._textarea.get("0.0", "end")
        n = len(text.rstrip("\n"))
        color = TEXT_DIM if n < _MAX_CHARS * 0.9 else "#EF4444"
        self._char_count_label.configure(
            text=f"{n:,} / {_MAX_CHARS:,}",
            text_color=color,
        )

    def _build_dropdown_row(self):
        """Three equal-width pill OptionMenus in a horizontal row."""
        pill_row = ctk.CTkFrame(self._col, fg_color="transparent")
        pill_row.pack(fill="x", padx=0, pady=(0, 10))
        pill_row.columnconfigure(0, weight=1)
        pill_row.columnconfigure(1, weight=1)
        pill_row.columnconfigure(2, weight=1)

        pill_kw = dict(
            fg_color=SURFACE,
            button_color=SURFACE,
            button_hover_color=SURFACE2,
            text_color=TEXT,
            dropdown_fg_color=SURFACE2,
            dropdown_hover_color="#2A2A2A",
            dropdown_text_color=TEXT,
            corner_radius=40,
            height=42,
            font=(FONTS["base"][0], 13),
            dropdown_font=(FONTS["base"][0], 13),
        )

        # Voice pill
        voice_values = [f"🎙 {v}" for v in VOICE_PROFILES]
        self._voice_display_var = ctk.StringVar(
            value=f"🎙 {self._voice_var.get()}"
        )
        self._voice_menu = ctk.CTkOptionMenu(
            pill_row,
            values=voice_values,
            variable=self._voice_display_var,
            command=self._on_voice_select,
            **pill_kw,
        )
        self._voice_menu.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        # Speed pill
        self._speed_menu = ctk.CTkOptionMenu(
            pill_row,
            values=[f"⚡ {s}" for s in SPEED_OPTIONS],
            variable=ctk.StringVar(value="⚡ 1.00×"),
            command=self._on_speed_select,
            **pill_kw,
        )
        self._speed_menu.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        # Emotion pill
        emotion_values = [f"✦ {e}" for e in DELIVERY_STYLES]
        self._emotion_display_var = ctk.StringVar(
            value=f"✦ {self._emotion_var.get()}"
        )
        self._emotion_menu = ctk.CTkOptionMenu(
            pill_row,
            values=emotion_values,
            variable=self._emotion_display_var,
            command=self._on_emotion_select,
            **pill_kw,
        )
        self._emotion_menu.grid(row=0, column=2, sticky="ew")

    def _on_voice_select(self, display_val: str):
        raw = display_val.replace("🎙 ", "").strip()
        self._voice_var.set(raw)

    def _on_speed_select(self, display_val: str):
        raw = display_val.replace("⚡ ", "").strip()
        self._speed_var.set(raw)

    def _on_emotion_select(self, display_val: str):
        raw = display_val.replace("✦ ", "").strip()
        self._emotion_var.set(raw)

    def _build_generate_btn(self):
        self._gen_btn = ctk.CTkButton(
            self._col,
            text="✦  Generate",
            height=52,
            corner_radius=14,
            fg_color="#FFFFFF",
            hover_color="#E5E5E5",
            text_color="#000000",
            font=(FONTS["generate"][0], 15, "bold"),
            command=self._on_generate_click,
        )
        self._gen_btn.pack(fill="x", padx=0, pady=(0, 10))

    def _build_progress_area(self):
        """Generation progress bar + chunk label — hidden until generating."""
        self._progress_frame = ctk.CTkFrame(
            self._col,
            fg_color=SURFACE3,
            corner_radius=10,
        )
        # Not packed — revealed by set_generating(True)

        self._progress_bar = ctk.CTkProgressBar(
            self._progress_frame,
            height=6,
            fg_color=BORDER2,
            progress_color="#FFFFFF",
            corner_radius=3,
        )
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=PAD["md"], pady=(PAD["sm"], 4))

        self._progress_label = ctk.CTkLabel(
            self._progress_frame,
            text="Starting…",
            font=(FONTS["mono_xs"][0], 11),
            text_color=TEXT_SUB,
            anchor="center",
        )
        self._progress_label.pack(pady=(0, PAD["sm"]))

    def _on_generate_click(self):
        if self.on_generate:
            self.on_generate()

    def _build_output_card(self):
        """Output card — hidden initially, revealed by show_output()."""
        self._output_card = ctk.CTkFrame(
            self._col,
            fg_color=SURFACE2,
            corner_radius=14,
            border_color=BORDER2,
            border_width=1,
        )
        # Not packed yet — shown via show_output()

        # ── Inner layout: three zones packed horizontally ──
        inner = ctk.CTkFrame(self._output_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: play button
        left_zone = ctk.CTkFrame(inner, fg_color="transparent")
        left_zone.pack(side="left", padx=(0, 10))

        self._play_btn = ctk.CTkButton(
            left_zone,
            text="▶",
            width=40, height=40,
            fg_color="#FFFFFF",
            hover_color="#E5E5E5",
            text_color="#000000",
            corner_radius=20,
            font=(FONTS["base"][0], 16),
            command=self._toggle_play,
        )
        self._play_btn.pack()

        # Right: action icon buttons
        right_zone = ctk.CTkFrame(inner, fg_color="transparent")
        right_zone.pack(side="right", padx=(10, 0))

        icon_kw = dict(
            width=32, height=32,
            fg_color="transparent",
            hover_color=BORDER2,
            text_color=TEXT_DIM,
            corner_radius=8,
            font=(FONTS["base"][0], 13),
        )

        ctk.CTkButton(
            right_zone, text="↓", **icon_kw,
            command=self._do_download,
        ).pack(side="left", padx=(0, 2))

        ctk.CTkButton(
            right_zone, text="📂", **icon_kw,
            command=self._do_open_folder,
        ).pack(side="left", padx=(0, 2))

        ctk.CTkButton(
            right_zone, text="■", **icon_kw,
            command=self._stop_playback,
        ).pack(side="left")

        # Center: progress bar + labels
        center_zone = ctk.CTkFrame(inner, fg_color="transparent")
        center_zone.pack(side="left", fill="both", expand=True)

        self._player_bar = ctk.CTkProgressBar(
            center_zone,
            height=5,
            fg_color=BORDER2,
            progress_color="#FFFFFF",
            corner_radius=3,
        )
        self._player_bar.set(0)
        self._player_bar.pack(fill="x", pady=(0, 4))

        info_row = ctk.CTkFrame(center_zone, fg_color="transparent")
        info_row.pack(fill="x")

        self._output_filename_label = ctk.CTkLabel(
            info_row,
            text="",
            font=FONTS["xs"],
            text_color=TEXT_SUB,
            anchor="w",
        )
        self._output_filename_label.pack(side="left")

        self._duration_badge = ctk.CTkLabel(
            info_row,
            text="",
            font=FONTS["xs_bold"],
            text_color=TEXT_SUB,
            fg_color=BORDER2,
            corner_radius=RADIUS["full"],
        )
        self._duration_badge.pack(side="right")

    # ── Resize handler ─────────────────────────────────────────────────────────

    def _on_resize(self, event=None):
        w = self.winfo_width()
        if w < 10:
            return
        col_w = min(int(w * self.COLUMN_FRACTION), self.COLUMN_MAX)
        self._col.configure(width=col_w)

    # ── Playback ───────────────────────────────────────────────────────────────

    def _pygame_init(self) -> bool:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            return True
        except Exception as exc:
            print(f"[MainView Player] pygame init failed: {exc}")
            return False

    def _get_duration_ms(self, path: Path) -> int:
        try:
            from pydub import AudioSegment
            return len(AudioSegment.from_file(str(path)))
        except Exception:
            return 0

    def _toggle_play(self):
        if self._playing:
            self._pause_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        if not self._current_output or not self._current_output.exists():
            return
        if not self._pygame_init():
            return

        import pygame
        try:
            pygame.mixer.music.load(str(self._current_output))
            pygame.mixer.music.play()
        except Exception as exc:
            print(f"[MainView Player] play error: {exc}")
            return

        self._playing        = True
        self._paused         = False
        self._play_start_ms  = time.time() * 1000
        self._play_offset_ms = 0
        self._play_duration  = self._get_duration_ms(self._current_output)

        self._play_btn.configure(text="⏸")
        self._tick_player()

    def _pause_playback(self):
        try:
            import pygame
        except ImportError:
            return

        if not self._playing:
            return

        if self._paused:
            pygame.mixer.music.unpause()
            self._paused        = False
            self._play_start_ms = time.time() * 1000 - self._play_offset_ms
            self._play_btn.configure(text="⏸")
            self._tick_player()
        else:
            pygame.mixer.music.pause()
            self._play_offset_ms = int(time.time() * 1000 - self._play_start_ms)
            self._paused = True
            self._play_btn.configure(text="▶")

    def _stop_playback(self):
        try:
            import pygame
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._playing        = False
        self._paused         = False
        self._play_offset_ms = 0
        try:
            self._play_btn.configure(text="▶")
            self._player_bar.set(0)
        except Exception:
            pass

    def _tick_player(self):
        if not self._playing or self._paused:
            return
        try:
            import pygame
            if not pygame.mixer.music.get_busy():
                self.after(0, self._stop_playback)
                return
            elapsed = int(time.time() * 1000 - self._play_start_ms)
            dur = self._play_duration
            if dur > 0:
                self._player_bar.set(min(elapsed / dur, 1.0))
        except Exception:
            pass
        self.after(200, self._tick_player)

    # ── Action buttons ─────────────────────────────────────────────────────────

    def _do_download(self):
        if not self._current_output:
            return
        from tkinter import filedialog
        ext  = self._current_output.suffix
        dest = filedialog.asksaveasfilename(
            title="Save Audio",
            defaultextension=ext,
            initialfile=self._current_output.name,
            filetypes=[(f"{ext.upper().lstrip('.')} Files", f"*{ext}"), ("All", "*.*")],
        )
        if dest:
            import shutil
            shutil.copy2(str(self._current_output), dest)

    def _do_open_folder(self):
        if not self._current_output:
            folder = Path(self._output_dir)
        else:
            folder = self._current_output.parent
        try:
            if sys.platform == "darwin":
                subprocess.call(["open", str(folder)])
            elif sys.platform == "win32":
                os.startfile(str(folder))
            else:
                subprocess.call(["xdg-open", str(folder)])
        except Exception as exc:
            print(f"[MainView] Open folder error: {exc}")

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_script_text(self) -> str:
        if self._placeholder_active:
            return ""
        return self._textarea.get("0.0", "end").strip()

    def get_settings(self) -> dict:
        speed_raw = self._speed_var.get().replace("×", "").strip()
        try:
            speed = float(speed_raw)
        except ValueError:
            speed = 1.0
        return {
            "voice_profile":  self._voice_var.get(),
            "delivery_style": self._emotion_var.get(),
            "language":       "English",
            "speed":          speed,
            "pitch_shift":    0.0,
            "pause_ms":       300,
            "output_format":  self._output_format,
            "sample_rate":    22050,
            "output_dir":     self._output_dir,
            "clone_ref_path": self._clone_ref_path,
        }

    def set_generating(
        self,
        is_generating: bool,
        chunk: int = 0,
        total: int = 0,
        eta: float = 0.0,
    ):
        if is_generating:
            self._gen_btn.configure(
                text="  Generating…  ",
                state="disabled",
                fg_color=ACCENT_DIM,
                text_color=TEXT_SUB,
            )
            self._gen_total = max(total, 1)
            self._progress_bar.set(0)
            self._progress_label.configure(text="Starting…")
            if not self._progress_frame.winfo_ismapped():
                self._progress_frame.pack(fill="x", padx=0, pady=(0, 10))
        else:
            self._gen_btn.configure(
                text="✦  Generate",
                state="normal",
                fg_color="#FFFFFF",
                text_color="#000000",
            )
            if self._progress_frame.winfo_ismapped():
                self._progress_frame.pack_forget()

    def update_chunk_progress(self, c: int, total: int, eta: float):
        """Update the progress bar and chunk label during generation."""
        if total <= 0:
            return
        self._gen_total = total
        frac = c / total
        self._progress_bar.set(frac)
        pct = int(frac * 100)
        if eta > 0:
            eta_sec = int(eta)
            eta_str = f"{eta_sec}s"
        else:
            eta_str = "…"
        self._progress_label.configure(
            text=f"Chunk {c} of {total}  •  {pct}%  •  ETA: {eta_str}"
        )
        if not self._progress_frame.winfo_ismapped():
            self._progress_frame.pack(fill="x", padx=0, pady=(0, 10))

    def show_output(self, path: Path, duration_str: str):
        """Reveal the output card after a successful generation."""
        self._stop_playback()
        self._current_output = Path(path)

        # Store in history
        title = path.stem
        rec = GenerationRecord(
            title=title,
            audio_path=path,
            thumbnail_path=None,
            duration_str=duration_str,
            format_label=path.suffix.lstrip(".").upper(),
        )
        self._history.insert(0, rec)
        if len(self._history) > 50:
            self._history.pop()

        # Update card labels
        short_name = path.name
        if len(short_name) > 48:
            short_name = short_name[:45] + "…"
        self._output_filename_label.configure(text=short_name)
        self._duration_badge.configure(text=f"  {duration_str}  ")
        self._player_bar.set(0)
        self._play_btn.configure(text="▶")

        # Show card
        if not self._output_card.winfo_ismapped():
            self._output_card.pack(fill="x", padx=0, pady=(0, 0))

    def hide_output(self):
        self._stop_playback()
        if self._output_card.winfo_ismapped():
            self._output_card.pack_forget()

    def set_output_dir(self, path: str):
        self._output_dir = path

    def get_output_dir(self) -> str:
        return self._output_dir

    def set_output_format(self, fmt: str):
        self._output_format = fmt.upper()

    def set_clone_ref_path(self, path: Optional[str]):
        self._clone_ref_path = path

    def get_history(self) -> List[GenerationRecord]:
        return list(self._history)

    def load_script(self, text: str):
        """Programmatically set the script text."""
        if self._placeholder_active:
            self._textarea.delete("0.0", "end")
            self._placeholder_active = False
            try:
                self._textarea.configure(text_color=TEXT)
                self._textarea._textbox.configure(fg=TEXT)
            except Exception:
                pass
        else:
            self._textarea.delete("0.0", "end")
        self._textarea.insert("0.0", text)
        self._update_char_count()

    def clear_script(self):
        """Clear the textarea and restore the placeholder."""
        self._textarea.delete("0.0", "end")
        self._placeholder_active = False
        # Trigger focus-out logic to restore placeholder
        self._on_textarea_focus_out()
