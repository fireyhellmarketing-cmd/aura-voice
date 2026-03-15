"""AURA VOICE — Output panel: main generation display + recent history strip."""

import os
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from assets.styles import (
    BG, PANEL, CARD, CARD_HOVER, INPUT_BG,
    ACCENT, ACCENT_HOVER, ACCENT_DIM,
    ACCENT2,
    TEXT, TEXT_SUB, TEXT_MUTED,
    BORDER, BORDER_LIGHT,
    SUCCESS, SUCCESS_BG, ERROR, ERROR_BG,
    FONTS, PAD, RADIUS,
    btn_primary, btn_secondary, btn_ghost, card_frame,
)


# ─── Data model ────────────────────────────────────────────────────────────────

class GenerationRecord:
    """Lightweight record for a single completed generation."""

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
        self.favourite      = False


# ─── Waveform widget ───────────────────────────────────────────────────────────

class _WaveformWidget(ctk.CTkCanvas):
    """
    Simple animated waveform bar display.
    - Static (uniform bars) when not playing.
    - Animated (randomly bouncing bars) when playing.
    """

    BAR_COUNT   = 32
    BAR_COLOR   = "#7c3aed"
    BG_COLOR    = "#1e1e2c"
    ANIM_DELAY  = 60   # ms between frames

    def __init__(self, parent, width: int = 380, height: int = 56, **kwargs):
        super().__init__(
            parent,
            width=width, height=height,
            bg=self.BG_COLOR,
            highlightthickness=0,
            **kwargs,
        )
        self._width    = width
        self._height   = height
        self._playing  = False
        self._anim_id  = None
        self._heights  = [0.3] * self.BAR_COUNT
        self._targets  = [0.3] * self.BAR_COUNT
        self._draw_static()

    def _draw_static(self):
        self.delete("all")
        bar_w    = self._width / self.BAR_COUNT
        mid_h    = self._height * 0.35
        for i in range(self.BAR_COUNT):
            h   = mid_h * (0.4 + 0.3 * abs(((i - self.BAR_COUNT // 2) / (self.BAR_COUNT // 2))**2 - 0.5))
            x0  = i * bar_w + 1
            x1  = x0 + bar_w - 2
            y0  = (self._height - h) / 2
            y1  = (self._height + h) / 2
            self.create_rectangle(x0, y0, x1, y1, fill="#3b1f6b", outline="")

    def _draw_frame(self):
        import random
        self.delete("all")
        bar_w = self._width / self.BAR_COUNT
        for i in range(self.BAR_COUNT):
            # Smooth lerp toward target
            self._heights[i] += (self._targets[i] - self._heights[i]) * 0.3
            # Occasionally set a new random target
            if random.random() < 0.15:
                self._targets[i] = random.uniform(0.1, 0.9)

            h  = self._heights[i] * self._height * 0.8
            x0 = i * bar_w + 1
            x1 = x0 + bar_w - 2
            y0 = (self._height - h) / 2
            y1 = (self._height + h) / 2
            # Color gradient: brighter in center
            norm = abs(i / self.BAR_COUNT - 0.5) * 2
            alpha_int = int(180 + 75 * (1 - norm))
            self.create_rectangle(x0, y0, x1, y1, fill=self.BAR_COLOR, outline="")

    def _animate(self):
        if not self._playing:
            return
        self._draw_frame()
        self._anim_id = self.after(self.ANIM_DELAY, self._animate)

    def start_animation(self):
        if self._playing:
            return
        self._playing = True
        self._animate()

    def stop_animation(self):
        self._playing = False
        if self._anim_id:
            self.after_cancel(self._anim_id)
            self._anim_id = None
        self._draw_static()

    def resize(self, width: int, height: int):
        self._width  = width
        self._height = height
        self.configure(width=width, height=height)
        if not self._playing:
            self._draw_static()


# ─── Output Panel ──────────────────────────────────────────────────────────────

class OutputPanel(ctk.CTkFrame):
    """
    Right-hand main output area.

    Shows:
    - Breadcrumb path
    - Large generation card (thumbnail, controls, waveform)
    - Horizontal recent-generations strip
    """

    THUMB_DISPLAY_SIZE = 220   # px for the displayed thumbnail
    RECENT_CARD_SIZE   = 110   # px for recent generation mini-cards

    def __init__(
        self,
        parent,
        on_play:    Optional[Callable[[Path], None]] = None,
        on_save:    Optional[Callable[[Path], None]] = None,
        on_delete:  Optional[Callable[[Path], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, fg_color=BG, corner_radius=0, **kwargs)

        self.on_play   = on_play
        self.on_save   = on_save
        self.on_delete = on_delete

        self._current: Optional[GenerationRecord] = None
        self._history: List[GenerationRecord]     = []
        self._playing = False
        self._ctk_image: Optional[ctk.CTkImage]  = None

        # Playback state
        self._play_thread:    Optional[threading.Thread] = None
        self._play_proc:      Optional[object]           = None
        self._stop_event      = threading.Event()
        self._paused:         bool = False
        self._play_start_ms:  float = 0.0
        self._play_offset_ms: int   = 0
        self._play_duration:  int   = 0

        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # Breadcrumb
        bc_frame = ctk.CTkFrame(self, fg_color="transparent", height=36)
        bc_frame.pack(fill="x", padx=PAD["page"], pady=(PAD["md"], 0))
        bc_frame.pack_propagate(False)

        ctk.CTkLabel(
            bc_frame,
            text="Personal Project  /  Audio Studio",
            font=FONTS["sm"],
            text_color=TEXT_MUTED,
        ).pack(side="left", pady=8)

        # Thin separator
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x", padx=PAD["page"])

        # Main content area (scrollable)
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=BORDER_LIGHT,
        )
        self._scroll.pack(fill="both", expand=True, padx=PAD["page"], pady=PAD["md"])

        # Main generation card
        self._main_card = ctk.CTkFrame(self._scroll, **card_frame())
        self._main_card.pack(fill="x", pady=(0, PAD["xl"]))

        self._build_main_card_content()

        # Recent generations section
        recent_header = ctk.CTkFrame(self._scroll, fg_color="transparent")
        recent_header.pack(fill="x", pady=(0, PAD["md"]))

        ctk.CTkLabel(
            recent_header,
            text="Recent Generations",
            font=FONTS["md_bold"],
            text_color=TEXT,
        ).pack(side="left")

        self._recent_count_label = ctk.CTkLabel(
            recent_header,
            text="0 items",
            font=FONTS["sm"],
            text_color=TEXT_MUTED,
        )
        self._recent_count_label.pack(side="right")

        # Horizontal scroll strip for recent cards
        self._recent_scroll = ctk.CTkScrollableFrame(
            self._scroll,
            fg_color="transparent",
            height=self.RECENT_CARD_SIZE + 60,
            orientation="horizontal",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=BORDER_LIGHT,
        )
        self._recent_scroll.pack(fill="x")

        self._empty_label = ctk.CTkLabel(
            self._recent_scroll,
            text="Generated audio will appear here…",
            font=FONTS["base"],
            text_color=TEXT_MUTED,
        )
        self._empty_label.pack(pady=24)

    def _build_main_card_content(self):
        """Build (or rebuild) the interior of the main generation card."""
        for w in self._main_card.winfo_children():
            w.destroy()

        pad = PAD["card"]

        if self._current is None:
            # Empty state
            empty_frame = ctk.CTkFrame(self._main_card, fg_color="transparent")
            empty_frame.pack(expand=True, fill="both", padx=pad, pady=48)

            ctk.CTkLabel(
                empty_frame,
                text="◈",
                font=(FONTS["3xl"][0], 56),
                text_color=ACCENT_DIM,
            ).pack(pady=(0, 8))

            ctk.CTkLabel(
                empty_frame,
                text="Your generated audio will appear here",
                font=FONTS["lg"],
                text_color=TEXT_MUTED,
            ).pack()

            ctk.CTkLabel(
                empty_frame,
                text="Enter a script in the panel on the left and click Generate.",
                font=FONTS["base"],
                text_color=TEXT_MUTED,
            ).pack(pady=4)
            return

        rec = self._current

        # ── Two-column layout: thumbnail left, info right ──
        inner = ctk.CTkFrame(self._main_card, fg_color="transparent")
        inner.pack(fill="x", padx=pad, pady=pad)

        # Left: thumbnail
        thumb_frame = ctk.CTkFrame(
            inner,
            fg_color=INPUT_BG,
            corner_radius=RADIUS["lg"],
            width=self.THUMB_DISPLAY_SIZE,
            height=self.THUMB_DISPLAY_SIZE,
        )
        thumb_frame.pack(side="left")
        thumb_frame.pack_propagate(False)

        self._thumb_label = ctk.CTkLabel(thumb_frame, text="", fg_color="transparent")
        self._thumb_label.place(relx=0.5, rely=0.5, anchor="center")

        self._load_thumbnail_image(rec.thumbnail_path)

        # Play overlay button on thumbnail
        self._play_overlay = ctk.CTkButton(
            thumb_frame,
            text="▶",
            width=52, height=52,
            font=(FONTS["xl"][0], 24),
            fg_color=ACCENT + "cc",
            hover_color=ACCENT,
            text_color=TEXT,
            corner_radius=RADIUS["full"],
            command=self._toggle_play,
        )
        self._play_overlay.place(relx=0.5, rely=0.5, anchor="center")

        # Right: info
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(pad, 0))

        # Title
        title_text = rec.title[:55] + ("…" if len(rec.title) > 55 else "")
        ctk.CTkLabel(
            right,
            text=title_text,
            font=FONTS["lg_bold"],
            text_color=TEXT,
            anchor="w",
            wraplength=320,
        ).pack(anchor="w", pady=(4, 2))

        # File name
        ctk.CTkLabel(
            right,
            text=rec.audio_path.name,
            font=FONTS["mono_sm"],
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        # Badges row
        badge_row = ctk.CTkFrame(right, fg_color="transparent")
        badge_row.pack(anchor="w", pady=6)

        self._make_badge(badge_row, rec.duration_str, ACCENT, ACCENT_DIM).pack(side="left", padx=(0, 4))
        self._make_badge(badge_row, rec.format_label, ACCENT2, "#451a03").pack(side="left", padx=(0, 4))

        # Waveform
        self._waveform = _WaveformWidget(right, width=340, height=52)
        self._waveform.pack(anchor="w", pady=(8, 0))

        # ── In-app player ──
        player_frame = ctk.CTkFrame(right, fg_color="transparent")
        player_frame.pack(fill="x", pady=(PAD["md"], 0))

        # Progress bar
        self._player_bar = ctk.CTkProgressBar(
            player_frame,
            height=6,
            fg_color=PANEL,
            progress_color=ACCENT,
            corner_radius=3,
        )
        self._player_bar.set(0)
        self._player_bar.pack(fill="x", pady=(0, 4))

        # Time label + controls row
        ctrl_row = ctk.CTkFrame(player_frame, fg_color="transparent")
        ctrl_row.pack(fill="x")

        # Play/Pause button (stored so we can update its label)
        self._play_btn = ctk.CTkButton(
            ctrl_row,
            text="▶",
            width=38, height=32,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=TEXT,
            corner_radius=RADIUS["md"],
            font=(FONTS["base"][0], 14),
            command=self._toggle_play,
        )
        self._play_btn.pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            ctrl_row,
            text="⏹",
            width=38, height=32,
            fg_color=CARD,
            hover_color=CARD_HOVER,
            text_color=TEXT_SUB,
            border_color=BORDER,
            border_width=1,
            corner_radius=RADIUS["md"],
            font=(FONTS["base"][0], 13),
            command=self._stop_playback,
        ).pack(side="left", padx=(0, 8))

        self._player_time = ctk.CTkLabel(
            ctrl_row,
            text=f"0:00 / {self._fmt_ms(self._get_duration_ms(rec.audio_path))}",
            font=FONTS["mono_xs"],
            text_color=TEXT_MUTED,
        )
        self._player_time.pack(side="left")

        # Action buttons
        action_row = ctk.CTkFrame(right, fg_color="transparent")
        action_row.pack(anchor="w", pady=(PAD["sm"], 0), fill="x")

        buttons = [
            ("⬇  Save",   self._do_save,      "#252540", CARD_HOVER),
            ("🗑  Delete", self._do_delete,    "#252540", "#450a0a"),
        ]
        for label, cmd, fg, hov in buttons:
            ctk.CTkButton(
                action_row,
                text=label,
                height=30, width=90,
                fg_color=fg,
                hover_color=hov,
                text_color=TEXT_SUB,
                corner_radius=RADIUS["md"],
                font=FONTS["sm"],
                command=cmd,
            ).pack(side="left", padx=(0, 6))

    def _make_badge(
        self, parent, text: str, fg: str, bg: str
    ) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            parent,
            text=f"  {text}  ",
            font=FONTS["xs_bold"],
            text_color=fg,
            fg_color=bg,
            corner_radius=RADIUS["full"],
        )

    # ── Thumbnail loading ──────────────────────────────────────────────────────

    def _load_thumbnail_image(self, thumb_path: Optional[Path]):
        """Load thumbnail from disk and display it."""
        if not thumb_path or not Path(thumb_path).exists():
            # Placeholder
            self._ctk_image = None
            return
        try:
            from PIL import Image
            img = Image.open(str(thumb_path)).convert("RGB")
            img = img.resize(
                (self.THUMB_DISPLAY_SIZE, self.THUMB_DISPLAY_SIZE),
                Image.LANCZOS,
            )
            self._ctk_image = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(self.THUMB_DISPLAY_SIZE, self.THUMB_DISPLAY_SIZE),
            )
            if hasattr(self, "_thumb_label"):
                self._thumb_label.configure(image=self._ctk_image)
        except Exception as exc:
            print(f"[OutputPanel] Thumbnail load error: {exc}")

    # ── Playback (pygame-based in-app player) ──────────────────────────────────

    def _pygame_init(self) -> bool:
        """Initialise pygame.mixer once; return True on success."""
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            return True
        except Exception as exc:
            print(f"[Player] pygame init failed: {exc}")
            return False

    def _get_duration_ms(self, path: Path) -> int:
        """Return audio duration in milliseconds."""
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
        if not self._current:
            return
        if not self._current.audio_path.exists():
            return

        if not self._pygame_init():
            return

        import pygame
        try:
            pygame.mixer.music.load(str(self._current.audio_path))
            pygame.mixer.music.play()
        except Exception as exc:
            print(f"[Player] load/play error: {exc}")
            return

        self._playing        = True
        self._paused         = False
        self._play_start_ms  = time.time() * 1000
        self._play_offset_ms = 0
        self._play_duration  = self._get_duration_ms(self._current.audio_path)
        self._stop_event.clear()

        for btn in ("_play_overlay", "_play_btn"):
            if hasattr(self, btn):
                getattr(self, btn).configure(text="⏸")
        if hasattr(self, "_waveform"):
            self._waveform.start_animation()

        self._tick_player()

        if self.on_play:
            self.on_play(self._current.audio_path)

    def _pause_playback(self):
        import pygame
        if not self._playing:
            return
        if getattr(self, "_paused", False):
            # Resume
            pygame.mixer.music.unpause()
            self._paused        = False
            self._play_start_ms = time.time() * 1000 - self._play_offset_ms
            for btn in ("_play_overlay", "_play_btn"):
                if hasattr(self, btn): getattr(self, btn).configure(text="⏸")
            if hasattr(self, "_waveform"):
                self._waveform.start_animation()
        else:
            # Pause
            pygame.mixer.music.pause()
            self._play_offset_ms = int(time.time() * 1000 - self._play_start_ms)
            self._paused = True
            for btn in ("_play_overlay", "_play_btn"):
                if hasattr(self, btn): getattr(self, btn).configure(text="▶")
            if hasattr(self, "_waveform"):
                self._waveform.stop_animation()

    def _stop_playback(self):
        try:
            import pygame
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._playing        = False
        self._paused         = False
        self._play_offset_ms = 0
        if self._play_proc is not None:
            try:
                self._play_proc.terminate()
            except Exception:
                pass
            self._play_proc = None
        for btn in ("_play_overlay", "_play_btn"):
            if hasattr(self, btn): getattr(self, btn).configure(text="▶")
        if hasattr(self, "_waveform"):
            self._waveform.stop_animation()
        # Reset progress bar + time
        if hasattr(self, "_player_bar"):
            try:
                self._player_bar.set(0)
                self._player_time.configure(text="0:00 / " + self._fmt_ms(getattr(self, "_play_duration", 0)))
            except Exception:
                pass

    def _tick_player(self):
        """Poll playback position every 200ms and update the progress bar."""
        if not self._playing or getattr(self, "_paused", False):
            return
        try:
            import pygame
            if not pygame.mixer.music.get_busy():
                # Finished naturally
                self.after(0, self._stop_playback)
                return
            elapsed = int(time.time() * 1000 - self._play_start_ms)
            dur     = getattr(self, "_play_duration", 0)
            if dur > 0:
                frac = min(elapsed / dur, 1.0)
                if hasattr(self, "_player_bar"):
                    self._player_bar.set(frac)
                if hasattr(self, "_player_time"):
                    self._player_time.configure(
                        text=f"{self._fmt_ms(elapsed)} / {self._fmt_ms(dur)}"
                    )
        except Exception:
            pass
        self.after(200, self._tick_player)

    @staticmethod
    def _fmt_ms(ms: int) -> str:
        s    = ms // 1000
        mins = s // 60
        secs = s  % 60
        return f"{mins}:{secs:02d}"

    # ── Save / Delete / Favourite ──────────────────────────────────────────────

    def _do_save(self):
        if not self._current:
            return
        from tkinter import filedialog
        ext   = self._current.audio_path.suffix
        dest  = filedialog.asksaveasfilename(
            title="Save Audio File",
            defaultextension=ext,
            initialfile=self._current.audio_path.name,
            filetypes=[(f"{ext.upper().lstrip('.')} Files", f"*{ext}"), ("All files", "*.*")],
        )
        if dest:
            import shutil
            shutil.copy2(str(self._current.audio_path), dest)
        if self.on_save:
            self.on_save(self._current.audio_path)

    def _do_delete(self):
        if not self._current:
            return
        import tkinter.messagebox as mb
        if mb.askyesno("Delete?", f"Delete '{self._current.title}'?"):
            try:
                self._current.audio_path.unlink(missing_ok=True)
                if self._current.thumbnail_path:
                    self._current.thumbnail_path.unlink(missing_ok=True)
            except Exception:
                pass
            if self._current in self._history:
                self._history.remove(self._current)
            self._current = None
            self._rebuild_recent_strip()
            self._build_main_card_content()
        if self.on_delete:
            self.on_delete(self._current.audio_path if self._current else Path("."))

    def _do_favourite(self):
        if not self._current:
            return
        self._current.favourite = not self._current.favourite

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_output(
        self,
        audio_path: Path,
        thumbnail_path: Optional[Path],
        title: str,
        duration_str: str,
        format_label: str = "WAV",
    ):
        """Called by the main window when a generation completes."""
        if self._playing:
            self._stop_playback()

        rec = GenerationRecord(
            title=title,
            audio_path=audio_path,
            thumbnail_path=thumbnail_path,
            duration_str=duration_str,
            format_label=format_label,
        )
        self._history.insert(0, rec)
        if len(self._history) > 50:
            self._history.pop()

        self._current = rec
        self._build_main_card_content()
        self._rebuild_recent_strip()

    def _rebuild_recent_strip(self):
        """Refresh the horizontal recent-generations thumbnail strip."""
        for w in self._recent_scroll.winfo_children():
            w.destroy()

        count = len(self._history)
        self._recent_count_label.configure(text=f"{count} item{'s' if count != 1 else ''}")

        if count == 0:
            ctk.CTkLabel(
                self._recent_scroll,
                text="Generated audio will appear here…",
                font=FONTS["base"],
                text_color=TEXT_MUTED,
            ).pack(pady=24)
            return

        for rec in self._history:
            self._build_recent_card(rec)

    def _build_recent_card(self, rec: GenerationRecord):
        SIZE = self.RECENT_CARD_SIZE

        is_current = rec is self._current
        card = ctk.CTkFrame(
            self._recent_scroll,
            fg_color=CARD_HOVER if is_current else CARD,
            corner_radius=RADIUS["lg"],
            border_color=ACCENT if is_current else BORDER,
            border_width=2 if is_current else 1,
            width=SIZE + 20,
        )
        card.pack(side="left", padx=5, pady=4)
        card.pack_propagate(False)

        # Thumbnail
        thumb_label = ctk.CTkLabel(
            card,
            text="",
            fg_color=INPUT_BG,
            width=SIZE,
            height=SIZE,
            corner_radius=RADIUS["md"],
        )
        thumb_label.pack(padx=6, pady=(6, 2))

        # Load thumb image
        if rec.thumbnail_path and rec.thumbnail_path.exists():
            try:
                from PIL import Image
                img = Image.open(str(rec.thumbnail_path)).convert("RGB")
                img = img.resize((SIZE, SIZE), Image.LANCZOS)
                cimg = ctk.CTkImage(light_image=img, dark_image=img, size=(SIZE, SIZE))
                thumb_label.configure(image=cimg)
                thumb_label.image = cimg  # prevent GC
            except Exception:
                pass

        # Title
        short_title = rec.title[:16] + ("…" if len(rec.title) > 16 else "")
        ctk.CTkLabel(
            card,
            text=short_title,
            font=FONTS["xs"],
            text_color=TEXT_SUB,
        ).pack(padx=4, pady=(0, 2))

        # Duration chip
        ctk.CTkLabel(
            card,
            text=rec.duration_str,
            font=FONTS["xs"],
            text_color=ACCENT2,
            fg_color=CARD,
            corner_radius=RADIUS["full"],
        ).pack(pady=(0, 6))

        # Click to load
        for widget in [card, thumb_label]:
            widget.bind("<Button-1>", lambda e, r=rec: self._load_record(r))
            widget.configure(cursor="hand2")

    def _load_record(self, rec: GenerationRecord):
        """Make a historical record the active display item."""
        if self._playing:
            self._stop_playback()
        self._current = rec
        self._build_main_card_content()
        self._rebuild_recent_strip()

    def clear_history(self):
        """Remove all history records from the panel."""
        self._current = None
        self._history.clear()
        self._build_main_card_content()
        self._rebuild_recent_strip()

    def get_history(self) -> List[GenerationRecord]:
        return list(self._history)

    def show_generating_state(self, message: str = "Generating…"):
        """Show a loading indicator in the main card."""
        for w in self._main_card.winfo_children():
            w.destroy()

        frame = ctk.CTkFrame(self._main_card, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=PAD["card"], pady=56)

        ctk.CTkLabel(
            frame,
            text="◈",
            font=(FONTS["3xl"][0], 56),
            text_color=ACCENT,
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            frame,
            text=message,
            font=FONTS["lg"],
            text_color=TEXT_SUB,
        ).pack()

        self._gen_progress = ctk.CTkProgressBar(
            frame,
            height=6,
            fg_color=PANEL,
            progress_color=ACCENT,
            corner_radius=3,
            mode="indeterminate",
        )
        self._gen_progress.pack(fill="x", padx=40, pady=12)
        self._gen_progress.start()

    def stop_generating_state(self):
        """Remove the loading indicator."""
        if hasattr(self, "_gen_progress"):
            try:
                self._gen_progress.stop()
            except Exception:
                pass
