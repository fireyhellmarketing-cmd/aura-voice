"""AURA VOICE — SYNAPTIC FLOWDENSITY animated wave + particle canvas."""

from __future__ import annotations

import math
import random
import tkinter as tk
from typing import List

import customtkinter as ctk

# ── Color palette (matches reference screenshot) ──────────────────────────────
_BG      = "#0A0A0A"
_WAVES = [
    # (color, freq, amplitude, y_base, phase_off, line_width, secondary)
    ("#00E5FF", 1.4, 0.11, 0.30, 0.00, 2, False),   # bright cyan
    ("#00BCD4", 1.4, 0.09, 0.30, 0.35, 1, True),    # teal shadow
    ("#F59E0B", 1.1, 0.13, 0.52, 1.00, 2, False),   # gold
    ("#FFD54F", 1.1, 0.10, 0.52, 1.45, 1, True),    # gold lighter
    ("#10B981", 0.85, 0.10, 0.70, 2.00, 2, False),  # emerald
    ("#4ADE80", 0.85, 0.08, 0.70, 2.55, 1, True),   # light green
    ("#A855F7", 1.9,  0.07, 0.18, -0.5, 1, False),  # violet (deep)
    ("#EC4899", 1.7,  0.06, 0.82, -1.0, 1, False),  # magenta (base)
]
_PARTICLE_COLORS = [
    "#00E5FF", "#00BCD4", "#F59E0B", "#10B981", "#A855F7", "#EC4899",
    "#4ADE80", "#FFD54F",
]
_PARTICLE_COUNT = 55
_FRAME_MS       = 40    # ~25 fps — light on CPU
_PHASE_STEP     = 0.025
_WAVE_STEPS     = 180   # points per wave line


class WaveCanvas(ctk.CTkFrame):
    """
    Animated SYNAPTIC FLOWDENSITY panel — multiple sine waves in gold/cyan/
    green/violet float across a dark canvas with drifting glow particles.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=_BG, corner_radius=0, **kwargs)

        self._phase:     float = 0.0
        self._particles: List[dict] = []
        self._running:   bool = False
        self._canvas:    tk.Canvas | None = None
        self._w = self._h = 0

        self._build()
        self.bind("<Configure>", self._on_configure)

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # Panel header
        hdr = ctk.CTkFrame(self, fg_color="#0D0D0D", corner_radius=0, height=26)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr, text="SYNAPTIC FLOWDENSITY",
            font=("SF Mono", 9),
            text_color="#2E2E2E",
        ).pack(side="left", padx=10)

        self._canvas = tk.Canvas(
            self, bg=_BG, highlightthickness=0, bd=0,
        )
        self._canvas.pack(fill="both", expand=True)

    # ── Resize / start ─────────────────────────────────────────────────────────

    def _on_configure(self, _event=None):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 20 or h < 20:
            return
        self._w, self._h = w, h
        if not self._running:
            self._running = True
            self._init_particles()
            self._animate()

    def _init_particles(self):
        self._particles = []
        for _ in range(_PARTICLE_COUNT):
            self._particles.append({
                "x":  random.uniform(0, self._w),
                "y":  random.uniform(0, self._h),
                "vx": random.uniform(-0.25, 0.25),
                "vy": random.uniform(-0.18, 0.18),
                "r":  random.uniform(0.8, 2.2),
                "col": random.choice(_PARTICLE_COLORS),
            })

    # ── Animation loop ─────────────────────────────────────────────────────────

    def _animate(self):
        if not self._running or self._canvas is None:
            return
        c = self._canvas
        w, h = self._w, self._h
        if w < 20 or h < 20:
            self.after(_FRAME_MS, self._animate)
            return

        c.delete("all")

        self._draw_waves(c, w, h)
        self._tick_particles(w, h)
        self._draw_particles(c)

        self._phase += _PHASE_STEP
        self.after(_FRAME_MS, self._animate)

    # ── Wave drawing ───────────────────────────────────────────────────────────

    def _draw_waves(self, c: tk.Canvas, w: int, h: int):
        for color, freq, amp, y_base, ph_off, lw, secondary in _WAVES:
            pts: list[int] = []
            for i in range(_WAVE_STEPS + 1):
                x = int(i * w / _WAVE_STEPS)
                angle = (i / _WAVE_STEPS) * math.pi * 2 * freq + self._phase + ph_off
                y = int(h * y_base + math.sin(angle) * h * amp)
                pts += [x, y]
            if len(pts) >= 4:
                c.create_line(pts, fill=color, width=lw, smooth=True)

    # ── Particles ──────────────────────────────────────────────────────────────

    def _tick_particles(self, w: int, h: int):
        for p in self._particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["x"] < 0:  p["x"] = w
            if p["x"] > w:  p["x"] = 0
            if p["y"] < 0:  p["y"] = h
            if p["y"] > h:  p["y"] = 0

    def _draw_particles(self, c: tk.Canvas):
        for p in self._particles:
            x, y, r = p["x"], p["y"], p["r"]
            c.create_oval(x - r, y - r, x + r, y + r,
                          fill=p["col"], outline="")

    def stop(self):
        self._running = False
