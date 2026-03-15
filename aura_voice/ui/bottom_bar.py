"""AURA VOICE v2 — Bottom status / progress bar."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import customtkinter as ctk

from assets.styles import (
    COLORS, FONTS, PAD,
    PANEL, CARD, CARD_HOVER,
    ACCENT, ACCENT_DIM,
    TEXT, TEXT_SUB, TEXT_MUTED,
    BORDER, BORDER_LIGHT,
    SUCCESS, SUCCESS_BG,
    WARNING, ERROR,
    BOTTOM_BAR_HEIGHT,
)


class BottomBar(ctk.CTkFrame):
    """
    Slim (40 px) bottom status bar:

    [ ████████████████░░░░  status text… ]  ETA  %  [✕ Cancel] [✓ Open Folder]

    - Progress bar fills the full width behind the content.
    - Status text is left-aligned.
    - ETA + % are right-aligned.
    - Cancel button (✕) far right while generating.
    - On complete: green "✓ Complete" text + "Open Folder" button replaces cancel.
    """

    def __init__(
        self,
        master,
        on_cancel:    Optional[Callable[[], None]] = None,
        on_open_file: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=PANEL,
            corner_radius=0,
            height=BOTTOM_BAR_HEIGHT,
            **kwargs,
        )
        self.pack_propagate(False)
        self._on_cancel    = on_cancel
        self._on_open_file = on_open_file
        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Top border line
        ctk.CTkFrame(
            self, height=1, fg_color=BORDER, corner_radius=0,
        ).pack(fill="x", side="top")

        # Main inner row (fills remaining height)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True)

        # ── Progress bar (sits below everything as a background layer) ──
        # We use a ttk.Progressbar styled to look sleek
        style = ttk.Style()
        try:
            style.theme_use("default")
        except Exception:
            pass
        style.configure(
            "AuraV2.Horizontal.TProgressbar",
            troughcolor=PANEL,
            background=ACCENT,
            borderwidth=0,
            thickness=BOTTOM_BAR_HEIGHT - 1,
        )

        self._pct_var = tk.DoubleVar(value=0.0)
        self._bar = ttk.Progressbar(
            inner,
            variable=self._pct_var,
            maximum=100.0,
            mode="determinate",
            style="AuraV2.Horizontal.TProgressbar",
        )
        self._bar.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        # ── Content overlay ──
        content = ctk.CTkFrame(inner, fg_color="transparent")
        content.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        # Status label (left)
        self._status = ctk.CTkLabel(
            content,
            text="Ready  —  enter a script and click Generate.",
            font=FONTS["status"],
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self._status.pack(side="left", padx=(PAD["xl"], 0))

        # Cancel button (far right, hidden by default)
        self._cancel_btn = ctk.CTkButton(
            content,
            text="✕",
            width=28, height=26,
            fg_color=CARD,
            hover_color=COLORS["error_bg"],
            text_color=TEXT_MUTED,
            border_color=BORDER,
            border_width=1,
            corner_radius=RADIUS_SM,
            font=FONTS["sm_bold"],
            command=self._do_cancel,
        )
        self._cancel_btn.pack(side="right", padx=(0, PAD["xl"]))
        self._cancel_btn.pack_forget()

        # Open Folder button (far right, hidden by default)
        self._done_btn = ctk.CTkButton(
            content,
            text="Open Folder",
            width=110, height=26,
            fg_color=SUCCESS_BG,
            hover_color=SUCCESS,
            text_color=SUCCESS,
            border_color=SUCCESS,
            border_width=1,
            corner_radius=RADIUS_SM,
            font=FONTS["xs_bold"],
            command=self._do_open,
        )
        self._done_btn.pack(side="right", padx=(0, PAD["sm"]))
        self._done_btn.pack_forget()

        # Percent label (right, before cancel)
        self._pct_label = ctk.CTkLabel(
            content,
            text="",
            font=FONTS["mono_xs"],
            text_color=TEXT_MUTED,
            width=50,
            anchor="e",
        )
        self._pct_label.pack(side="right", padx=(0, PAD["sm"]))

        # ETA label (right, before %)
        self._eta = ctk.CTkLabel(
            content,
            text="",
            font=FONTS["xs"],
            text_color=TEXT_MUTED,
            width=64,
            anchor="e",
        )
        self._eta.pack(side="right", padx=(0, PAD["sm"]))

    # ── Public API ─────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Return bar to idle state."""
        self._pct_var.set(0)
        self._pct_label.configure(text="")
        self._eta.configure(text="")
        self._cancel_btn.pack_forget()
        self._done_btn.pack_forget()
        self._set_status("Ready  —  enter a script and click Generate.", TEXT_MUTED)

    def start_generation(self, total: int = 1) -> None:
        """Called when synthesis begins."""
        self._pct_var.set(0)
        self._done_btn.pack_forget()
        self._cancel_btn.pack(side="right", padx=(0, PAD["xl"]))
        self._set_status("Starting synthesis…", TEXT_SUB)

    def update_chunk(self, current: int, total: int, eta_sec: float = 0) -> None:
        """Update progress mid-generation."""
        pct = (current / total * 100) if total else 0
        self._pct_var.set(pct)
        self._pct_label.configure(text=f"{pct:.0f}%")
        self._set_status(f"Synthesising chunk {current} / {total}", TEXT_SUB)
        if eta_sec > 0:
            mins, secs = divmod(int(eta_sec), 60)
            eta_str = f"{mins}m {secs}s" if mins else f"{secs}s"
            self._eta.configure(text=f"ETA {eta_str}")
        else:
            self._eta.configure(text="")

    def set_progress(self, pct: float, message: str = "") -> None:
        """Generic progress update (0–100)."""
        self._pct_var.set(max(0.0, min(100.0, pct)))
        self._pct_label.configure(text=f"{pct:.0f}%")
        if message:
            self._set_status(message, TEXT_SUB)

    def set_stitching(self) -> None:
        self._set_status("Stitching audio segments…", TEXT_SUB)
        self._eta.configure(text="")

    def set_stitch_progress(self, current: int, total: int) -> None:
        pct = (current / total * 100) if total else 0
        self._pct_var.set(pct)
        self._pct_label.configure(text=f"{pct:.0f}%")

    def set_exporting(self, fmt: str = "WAV") -> None:
        self._set_status(f"Saving {fmt.upper()} file…", TEXT_SUB)
        self._pct_var.set(99)

    def set_complete(self, path: str = "") -> None:
        """Called when synthesis finishes successfully."""
        self._pct_var.set(100)
        self._pct_label.configure(text="")
        self._eta.configure(text="")
        self._cancel_btn.pack_forget()
        self._done_btn.pack(side="right", padx=(0, PAD["sm"]))
        msg = f"✓  Complete" + (f"  —  {path}" if path else "")
        self._set_status(msg, SUCCESS)

    def set_cancelled(self) -> None:
        self._cancel_btn.pack_forget()
        self._eta.configure(text="")
        self._pct_label.configure(text="")
        self._set_status("Cancelled.", WARNING)

    def set_error(self, msg: str) -> None:
        self._cancel_btn.pack_forget()
        self._eta.configure(text="")
        self._pct_label.configure(text="")
        self._set_status(f"Error: {msg}", COLORS["error"])

    # ── Internals ──────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str = TEXT_MUTED) -> None:
        self._status.configure(text=text, text_color=color)

    def _do_cancel(self) -> None:
        if self._on_cancel:
            self._on_cancel()

    def _do_open(self) -> None:
        if self._on_open_file:
            self._on_open_file()


# Module-level constant needed by _build
RADIUS_SM = 4
