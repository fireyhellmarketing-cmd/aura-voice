"""AURA VOICE — SYNAPTIC FLOWDENSITY audio visualizer.

Circular radial frequency-bar spectrum (audioMotion-style) with:
  • 128 bars radiating outward from a center ring
  • Inward reflection (bars also grow toward center)
  • Smooth glow simulation (thick-dim + thin-bright per bar)
  • Rotating color gradient: cyan → teal → gold → green → violet → magenta
  • Reactive center orb that pulses with amplitude
  • 60 drifting depth particles
  • Three modes: idle / generating / playing
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from typing import List

import customtkinter as ctk

# ── Constants ─────────────────────────────────────────────────────────────────
_BG           = "#0A0A0A"
_N_BARS       = 128        # frequency bars in the ring
_FRAME_MS     = 33         # ~30 fps
_PART_COUNT   = 65

# Color palette — bar colors cycle through this gradient around the ring
_PALETTE = [
    "#00E5FF",   # bright cyan
    "#00BCD4",   # teal
    "#4ADE80",   # green
    "#10B981",   # emerald
    "#F59E0B",   # amber
    "#FFD54F",   # gold
    "#A855F7",   # violet
    "#EC4899",   # magenta
    "#00E5FF",   # back to cyan (smooth wrap)
]


def _lerp_color(palette: list, frac: float, brightness: float = 1.0) -> str:
    """Interpolate through palette. frac ∈ [0,1). brightness ∈ [0,1]."""
    frac = frac % 1.0
    n    = len(palette) - 1          # last entry = first (wrap handled above)
    idx  = frac * n
    i0   = int(idx)
    t    = idx - i0
    i1   = min(i0 + 1, n)

    def _p(h):
        return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)

    r0, g0, b0 = _p(palette[i0])
    r1, g1, b1 = _p(palette[i1])
    r = r0 + (r1 - r0) * t
    g = g0 + (g1 - g0) * t
    b = b0 + (b1 - b0) * t
    # apply brightness (blend toward near-black)
    r = max(0, min(255, int(r * brightness + 10 * (1 - brightness))))
    g = max(0, min(255, int(g * brightness + 10 * (1 - brightness))))
    b = max(0, min(255, int(b * brightness + 10 * (1 - brightness))))
    return f"#{r:02x}{g:02x}{b:02x}"


class WaveCanvas(ctk.CTkFrame):
    """
    SYNAPTIC FLOWDENSITY — circular radial spectrum analyzer.

    set_mode("idle")       → gentle idle pulse
    set_mode("generating") → fast high-energy bars + center orb burst
    set_mode("playing")    → voice-profile reactive bars
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=_BG, corner_radius=0, **kwargs)

        self._phase       = 0.0
        self._pulse_t     = 0.0
        self._running     = False
        self._canvas: tk.Canvas | None = None
        self._width       = 0
        self._height      = 0

        self._mode        = "idle"
        self._amp_mult    = 1.0

        # Smoothed bar heights (0..1) and their targets
        self._heights: List[float] = [0.0] * _N_BARS
        self._targets: List[float] = [0.05] * _N_BARS

        self._particles:  List[dict] = []

        self._build()
        self.bind("<Configure>", self._on_configure)

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="#0D0D0D", corner_radius=0, height=26)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr, text="SYNAPTIC FLOWDENSITY",
            font=("SF Mono", 9), text_color="#2E2E2E",
        ).pack(side="left", padx=10)

        self._canvas = tk.Canvas(self, bg=_BG, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def _on_configure(self, _event=None):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 20 or h < 20:
            return
        self._width, self._height = w, h
        if not self._running:
            self._running = True
            self._init_particles()
            self._animate()

    def _init_particles(self):
        self._particles = []
        for _ in range(_PART_COUNT):
            self._particles.append({
                "x":   random.uniform(0, self._width),
                "y":   random.uniform(0, self._height),
                "vx":  random.uniform(-0.40, 0.40),
                "vy":  random.uniform(-0.28, 0.28),
                "r":   random.uniform(0.7, 2.2),
                "z":   random.uniform(0.15, 1.0),
                "col": random.choice(_PALETTE[:-1]),
            })

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_mode(self, mode: str):
        """Switch reactive mode: 'idle' | 'generating' | 'playing'"""
        self._mode = mode
        if mode == "idle":
            self._amp_mult = 1.0
            self._pulse_t  = 0.0

    # ── Animation loop ─────────────────────────────────────────────────────────

    def _update_bars(self):
        self._pulse_t += 0.07

        if self._mode == "generating":
            # Random high-energy targets, fast refresh
            for i in range(_N_BARS):
                if random.random() < 0.35:
                    self._targets[i] = 0.25 + random.random() * 0.75
            # Pulsing amp multiplier
            self._amp_mult = 1.0 + 0.7 * (1.0 + math.sin(self._pulse_t * 3.2))

        elif self._mode == "playing":
            # Voice-like: lower "frequencies" carry more energy
            for i in range(_N_BARS):
                if random.random() < 0.45:
                    # Map bar index to a frequency-like profile
                    f = i / _N_BARS              # 0 .. 1
                    # Voice: peak around 0.1-0.4 (low-mid), roll off at high
                    energy_profile = (
                        0.15 +
                        0.75 * max(0.0, math.exp(-((f - 0.25) ** 2) / 0.06)) +
                        0.35 * max(0.0, math.exp(-((f - 0.75) ** 2) / 0.04)) * random.random()
                    )
                    self._targets[i] = energy_profile * (0.5 + random.random() * 0.5)
            self._amp_mult = 0.9 + random.random() * 0.7

        else:
            # Idle: slow sine ripple — very subtle
            for i in range(_N_BARS):
                ang = (i / _N_BARS) * math.pi * 4 + self._pulse_t * 0.6
                self._targets[i] = 0.04 + 0.10 * abs(math.sin(ang))
            self._amp_mult += (1.0 - self._amp_mult) * 0.06

        # Smooth interpolation toward targets
        alpha = 0.22 if self._mode != "idle" else 0.08
        for i in range(_N_BARS):
            self._heights[i] += (self._targets[i] - self._heights[i]) * alpha

    def _animate(self):
        if not self._running or self._canvas is None:
            return
        c  = self._canvas
        w, h = self._width, self._height
        if w < 20 or h < 20:
            self.after(_FRAME_MS, self._animate)
            return

        c.delete("all")
        self._update_bars()
        self._draw_background_rings(c, w, h)
        self._draw_radial_spectrum(c, w, h)
        self._tick_particles(w, h)
        self._draw_particles(c)

        step = (0.055 if self._mode == "generating" else
                0.040 if self._mode == "playing"    else 0.018)
        self._phase += step
        self.after(_FRAME_MS, self._animate)

    # ── Background rings (subtle depth) ────────────────────────────────────────

    def _draw_background_rings(self, c: tk.Canvas, w: int, h: int):
        cx, cy   = w / 2, h / 2
        min_dim  = min(w, h)
        # Two faint concentric circles for depth context
        for frac, opacity in ((0.55, 0.12), (0.75, 0.07)):
            r = min_dim * frac / 2
            col = _lerp_color(_PALETTE, (self._phase * 0.15) % 1.0, opacity)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=1)

    # ── Main radial spectrum ────────────────────────────────────────────────────

    def _draw_radial_spectrum(self, c: tk.Canvas, w: int, h: int):
        cx, cy   = w / 2, h / 2
        min_dim  = min(w, h)
        inner_r  = min_dim * 0.13
        max_bar  = min_dim * 0.33      # max outward bar length

        # Color phase offset rotates the palette around the ring over time
        color_phase_off = self._phase * 0.12

        for i in range(_N_BARS):
            bar_frac   = self._heights[i] * self._amp_mult
            bar_frac   = max(bar_frac, 0.01)
            bar_outlen = bar_frac * max_bar      # outward bar length
            bar_inlen  = bar_frac * inner_r * 0.55  # inward reflection

            angle = (i / _N_BARS) * math.pi * 2 - math.pi / 2
            ca, sa = math.cos(angle), math.sin(angle)

            # Color: fraction cycles around ring + slowly rotates
            col_frac = ((i / _N_BARS) + color_phase_off) % 1.0
            bright_col = _lerp_color(_PALETTE, col_frac, 1.0)
            glow_col   = _lerp_color(_PALETTE, col_frac, 0.28)
            inner_col  = _lerp_color(_PALETTE, col_frac, 0.55)

            # ── Outward bar (glow + core) ────────────────────────────────
            x1 = cx + ca * inner_r
            y1 = cy + sa * inner_r
            x2 = cx + ca * (inner_r + bar_outlen)
            y2 = cy + sa * (inner_r + bar_outlen)

            c.create_line(x1, y1, x2, y2, fill=glow_col,   width=3.5, capstyle="round")
            c.create_line(x1, y1, x2, y2, fill=bright_col, width=1.0, capstyle="round")

            # ── Inward reflection bar ────────────────────────────────────
            xi = cx + ca * (inner_r - bar_inlen)
            yi = cy + sa * (inner_r - bar_inlen)

            c.create_line(x1, y1, xi, yi, fill=glow_col,  width=2.5, capstyle="round")
            c.create_line(x1, y1, xi, yi, fill=inner_col, width=0.8, capstyle="round")

        # ── Spinning inner ring ──────────────────────────────────────────
        ring_col = _lerp_color(_PALETTE, (self._phase * 0.08) % 1.0, 0.7)
        c.create_oval(
            cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r,
            outline=ring_col, width=1.5, fill=_BG,
        )

        # ── Center orb ──────────────────────────────────────────────────
        orb_r = inner_r * (0.25 + 0.12 * math.sin(self._pulse_t * 2.5)) * self._amp_mult
        orb_col = _lerp_color(_PALETTE, (self._phase * 0.20) % 1.0, 0.85)
        # Outer glow
        og = orb_r * 2.0
        c.create_oval(cx - og, cy - og, cx + og, cy + og,
                      fill=_lerp_color(_PALETTE, (self._phase * 0.20) % 1.0, 0.12),
                      outline="")
        # Core
        c.create_oval(cx - orb_r, cy - orb_r, cx + orb_r, cy + orb_r,
                      fill=orb_col, outline="")

    # ── Particles ──────────────────────────────────────────────────────────────

    def _tick_particles(self, w: int, h: int):
        spd = (2.2 if self._mode == "generating" else
               1.6 if self._mode == "playing"    else 1.0)
        for p in self._particles:
            p["x"] += p["vx"] * spd
            p["y"] += p["vy"] * spd
            if p["x"] < 0: p["x"] = w
            if p["x"] > w: p["x"] = 0
            if p["y"] < 0: p["y"] = h
            if p["y"] > h: p["y"] = 0

    def _draw_particles(self, c: tk.Canvas):
        for p in self._particles:
            z   = p["z"]
            r   = p["r"] * z * max(0.5, self._amp_mult * 0.45)
            x, y = p["x"], p["y"]
            col = p["col"] if z >= 0.65 else _lerp_color(_PALETTE, 0, z * 0.6)
            c.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="")

    def stop(self):
        self._running = False
