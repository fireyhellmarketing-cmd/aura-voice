"""AURA VOICE — Procedural thumbnail generator using Pillow only."""

import math
import random
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ─── Color helpers ─────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _lerp_color(
    c1: Tuple[int, int, int],
    c2: Tuple[int, int, int],
    t: float,
) -> Tuple[int, int, int]:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _with_alpha(rgb: Tuple[int, int, int], alpha: int) -> Tuple[int, int, int, int]:
    return (rgb[0], rgb[1], rgb[2], alpha)


# ─── Emotion color map ─────────────────────────────────────────────────────────

COLOR_EMOTIONS = {
    "Neutral":                  ("#4a5568", "#2d3748"),
    "Happy & Upbeat":           ("#f59e0b", "#d97706"),
    "Serious & Authoritative":  ("#3b82f6", "#1d4ed8"),
    "Sad & Reflective":         ("#8b5cf6", "#6d28d9"),
    "Excited & Enthusiastic":   ("#ef4444", "#dc2626"),
    "Calm & Meditative":        ("#10b981", "#059669"),
    "Warm & Friendly":          ("#f97316", "#ea580c"),
    "Professional":             ("#64748b", "#475569"),
}

_ACCENT_VIOLET = "#7c3aed"
_BG_DARK       = "#0d0d12"


# ─── Layer drawing helpers ─────────────────────────────────────────────────────

def _draw_radial_gradient(
    draw: ImageDraw.ImageDraw,
    cx: int, cy: int,
    radius: int,
    color_inner: Tuple[int, int, int],
    color_outer: Tuple[int, int, int],
    alpha_inner: int = 220,
    alpha_outer: int = 0,
    steps: int = 80,
):
    """Draw a radial gradient circle by painting concentric rings."""
    for i in range(steps, 0, -1):
        t = i / steps
        r = int(radius * t)
        color = _lerp_color(color_inner, color_outer, 1.0 - t)
        alpha = int(alpha_inner + (alpha_outer - alpha_inner) * (1.0 - t))
        alpha = max(0, min(255, alpha))
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(color[0], color[1], color[2], alpha),
        )


def _draw_background_gradient(img: Image.Image) -> Image.Image:
    """Fill the image with a top-to-bottom dark gradient."""
    W, H = img.size
    draw = ImageDraw.Draw(img)
    top_color    = _hex_to_rgb("#0d0d12")
    bottom_color = _hex_to_rgb("#09090f")
    for y in range(H):
        t = y / H
        c = _lerp_color(top_color, bottom_color, t)
        draw.line([(0, y), (W, y)], fill=c)
    return img


def _draw_floating_orbs(
    canvas: Image.Image,
    rng: random.Random,
    emotion_color1: Tuple[int, int, int],
    emotion_color2: Tuple[int, int, int],
    count: int = 7,
):
    """Draw blurred floating orbs for a dreamy depth effect."""
    W, H = canvas.size
    for i in range(count):
        orb_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d         = ImageDraw.Draw(orb_layer)

        # Alternate between emotion colors and a dim violet
        if i % 3 == 0:
            color = emotion_color1
        elif i % 3 == 1:
            color = emotion_color2
        else:
            color = _hex_to_rgb(_ACCENT_VIOLET)

        size  = rng.randint(W // 8, W // 3)
        x     = rng.randint(-size // 2, W + size // 2)
        y     = rng.randint(-size // 2, H + size // 2)
        alpha = rng.randint(18, 55)

        _draw_radial_gradient(
            d, x, y, size // 2,
            color_inner=color,
            color_outer=_hex_to_rgb(_BG_DARK),
            alpha_inner=alpha,
            alpha_outer=0,
            steps=60,
        )

        blur_r = rng.randint(size // 6, size // 3)
        orb_layer = orb_layer.filter(ImageFilter.GaussianBlur(radius=blur_r))
        canvas = Image.alpha_composite(canvas, orb_layer)

    return canvas


def _draw_concentric_arcs(
    canvas: Image.Image,
    cx: int, cy: int,
    accent_color: Tuple[int, int, int],
    count: int = 14,
    start_radius: int = 90,
    spacing: int = 22,
    rng: Optional[random.Random] = None,
):
    """Draw thin concentric arc rings — like a circular waveform."""
    if rng is None:
        rng = random.Random(42)

    arc_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(arc_layer)

    for i in range(count):
        radius  = start_radius + i * spacing
        alpha   = max(8, 50 - i * 3)
        width_px = 1 if i % 2 == 0 else 2

        # Randomly break each arc into segments for a waveform look
        n_segments = rng.randint(3, 8)
        arc_start  = rng.randint(0, 60)
        total_span = rng.randint(200, 340)
        seg_span   = total_span / n_segments

        for s in range(n_segments):
            if rng.random() < 0.25:
                continue  # leave some gaps
            seg_start = arc_start + s * seg_span + rng.uniform(-5, 5)
            seg_end   = seg_start + seg_span * rng.uniform(0.5, 0.95)

            box = [
                cx - radius, cy - radius,
                cx + radius, cy + radius,
            ]
            try:
                d.arc(
                    box,
                    start=seg_start,
                    end=seg_end,
                    fill=(*accent_color, alpha),
                    width=width_px,
                )
            except Exception:
                pass

    arc_layer = arc_layer.filter(ImageFilter.GaussianBlur(radius=0.8))
    return Image.alpha_composite(canvas, arc_layer)


def _draw_center_orb(
    canvas: Image.Image,
    cx: int, cy: int,
    accent_color: Tuple[int, int, int],
    radius: int = 70,
):
    """Draw the glowing central orb — the focal point of the thumbnail."""
    # Outer glow (large, very soft)
    glow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    _draw_radial_gradient(
        gd, cx, cy, radius * 3,
        color_inner=accent_color,
        color_outer=_hex_to_rgb(_BG_DARK),
        alpha_inner=90,
        alpha_outer=0,
        steps=100,
    )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=radius // 2))

    # Inner orb (solid, crisp with small blur)
    orb_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(orb_layer)
    _draw_radial_gradient(
        od, cx, cy, radius,
        color_inner=(255, 255, 255),
        color_outer=accent_color,
        alpha_inner=240,
        alpha_outer=180,
        steps=80,
    )
    orb_layer = orb_layer.filter(ImageFilter.GaussianBlur(radius=4))

    # Highlight sparkle (tiny bright spot offset up-left)
    hl_x = cx - radius // 4
    hl_y = cy - radius // 4
    od.ellipse(
        [hl_x - 8, hl_y - 8, hl_x + 8, hl_y + 8],
        fill=(255, 255, 255, 180),
    )

    canvas = Image.alpha_composite(canvas, glow_layer)
    canvas = Image.alpha_composite(canvas, orb_layer)
    return canvas


def _draw_noise_texture(canvas: Image.Image, strength: int = 6) -> Image.Image:
    """Add a very subtle film-grain noise texture for richness."""
    import os
    W, H = canvas.size
    noise = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pixels = noise.load()
    rng = random.Random(12345)
    for y in range(H):
        for x in range(W):
            v = rng.randint(-strength, strength)
            pixels[x, y] = (
                max(0, min(255, 128 + v)),
                max(0, min(255, 128 + v)),
                max(0, min(255, 128 + v)),
                12,
            )
    return Image.alpha_composite(canvas, noise)


def _draw_bottom_text_strip(
    canvas: Image.Image,
    title: str,
    voice_profile: str,
    accent_color: Tuple[int, int, int],
) -> Image.Image:
    """Draw a bottom frosted-glass strip with app name and voice profile."""
    W, H = canvas.size
    strip_h = int(H * 0.22)

    # Frosted glass overlay
    strip_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip_layer)

    # Gradient from transparent top to semi-opaque bottom
    for y in range(strip_h):
        t = y / strip_h
        alpha = int(200 * t)
        sd.line([(0, H - strip_h + y), (W, H - strip_h + y)],
                fill=(10, 10, 18, alpha))

    canvas = Image.alpha_composite(canvas, strip_layer)
    d = ImageDraw.Draw(canvas)

    # ── Try to load a font, fall back to default ──
    font_large  = None
    font_small  = None
    font_badge  = None

    for attempt in [
        lambda: ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", int(H * 0.065)),
        lambda: ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(H * 0.065)),
        lambda: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(H * 0.065)),
        lambda: ImageFont.load_default(),
    ]:
        try:
            font_large = attempt()
            break
        except Exception:
            continue

    for attempt in [
        lambda: ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", int(H * 0.045)),
        lambda: ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(H * 0.045)),
        lambda: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(H * 0.045)),
        lambda: ImageFont.load_default(),
    ]:
        try:
            font_small = attempt()
            break
        except Exception:
            continue

    for attempt in [
        lambda: ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", int(H * 0.036)),
        lambda: ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(H * 0.036)),
        lambda: ImageFont.load_default(),
    ]:
        try:
            font_badge = attempt()
            break
        except Exception:
            continue

    pad = int(W * 0.06)
    text_y_app   = H - strip_h + int(strip_h * 0.22)
    text_y_voice = H - strip_h + int(strip_h * 0.55)

    # App name in white
    d.text(
        (pad, text_y_app),
        "AURA VOICE",
        fill=(255, 255, 255, 240),
        font=font_large,
    )

    # Accent line separator
    accent_rgba = (*accent_color, 200)
    line_y = text_y_app + int(H * 0.072)
    d.line([(pad, line_y), (W - pad, line_y)], fill=accent_rgba, width=1)

    # Voice profile subtitle
    profile_text = voice_profile[:38] + ("…" if len(voice_profile) > 38 else "")
    d.text(
        (pad, text_y_voice),
        profile_text,
        fill=(*accent_color, 210),
        font=font_small,
    )

    return canvas


def _draw_v2_badge(canvas: Image.Image, accent_color: Tuple[int, int, int]) -> Image.Image:
    """Draw a small rounded 'v2' badge in the top-right corner."""
    W, H = canvas.size
    badge_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge_layer)

    bw, bh = int(W * 0.115), int(H * 0.065)
    margin  = int(W * 0.04)
    x0 = W - margin - bw
    y0 = margin
    x1 = W - margin
    y1 = margin + bh
    radius = bh // 2

    # Rounded rectangle background
    bd.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=radius,
        fill=(*accent_color, 200),
    )

    # Badge text
    badge_font = None
    for attempt in [
        lambda: ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", int(bh * 0.62)),
        lambda: ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(bh * 0.62)),
        lambda: ImageFont.load_default(),
    ]:
        try:
            badge_font = attempt()
            break
        except Exception:
            continue

    try:
        bbox = bd.textbbox((0, 0), "v2", font=badge_font)
        tw   = bbox[2] - bbox[0]
        th   = bbox[3] - bbox[1]
    except Exception:
        tw, th = 20, 14

    tx = x0 + (bw - tw) // 2
    ty = y0 + (bh - th) // 2
    bd.text((tx, ty), "v2", fill=(255, 255, 255, 255), font=badge_font)

    return Image.alpha_composite(canvas, badge_layer)


# ─── Public API ────────────────────────────────────────────────────────────────

def generate_thumbnail(
    output_path: Path,
    title: str = "AURA VOICE",
    emotion: str = "Neutral",
    voice_profile: str = "Natural Female",
    seed: Optional[int] = None,
    size: Tuple[int, int] = (512, 512),
) -> Path:
    """
    Generate a beautiful procedural album-art thumbnail and save it as PNG.

    Layers (bottom to top):
      1. Dark radial gradient background
      2. Abstract floating orbs (emotion-colored, blurred)
      3. Concentric arc rings (waveform-style)
      4. Central glowing orb (accent violet)
      5. Subtle film-grain noise texture
      6. Bottom frosted-glass text strip
      7. Top-right v2 badge

    Returns the path to the saved PNG.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    W, H = size
    rng  = random.Random(seed if seed is not None else random.randint(0, 999999))

    # Resolve emotion colors
    emotion_pair = COLOR_EMOTIONS.get(emotion, COLOR_EMOTIONS["Neutral"])
    emotion_c1   = _hex_to_rgb(emotion_pair[0])
    emotion_c2   = _hex_to_rgb(emotion_pair[1])
    accent_color = _hex_to_rgb(_ACCENT_VIOLET)

    # ── Layer 1: Background ──
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    _draw_background_gradient(bg)

    canvas = bg.convert("RGBA")

    # ── Layer 2: Floating orbs ──
    canvas = _draw_floating_orbs(canvas, rng, emotion_c1, emotion_c2, count=8)

    # ── Layer 3: Secondary accent-colored orb cluster ──
    for _ in range(3):
        orb_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(orb_layer)
        sz = rng.randint(W // 10, W // 5)
        ox = rng.randint(W // 4, 3 * W // 4)
        oy = rng.randint(H // 4, 3 * H // 4)
        _draw_radial_gradient(
            od, ox, oy, sz,
            color_inner=emotion_c1,
            color_outer=_hex_to_rgb(_BG_DARK),
            alpha_inner=rng.randint(20, 45),
            alpha_outer=0,
            steps=50,
        )
        orb_layer = orb_layer.filter(ImageFilter.GaussianBlur(radius=sz // 3))
        canvas = Image.alpha_composite(canvas, orb_layer)

    # ── Layer 4: Concentric arcs ──
    cx, cy = W // 2, H // 2
    canvas = _draw_concentric_arcs(
        canvas, cx, cy,
        accent_color=emotion_c1,
        count=16,
        start_radius=int(W * 0.17),
        spacing=int(W * 0.043),
        rng=rng,
    )

    # A second set of arcs in violet at slightly different scale
    canvas = _draw_concentric_arcs(
        canvas, cx, cy,
        accent_color=accent_color,
        count=10,
        start_radius=int(W * 0.20),
        spacing=int(W * 0.038),
        rng=rng,
    )

    # ── Layer 5: Central glowing orb ──
    canvas = _draw_center_orb(
        canvas, cx, cy,
        accent_color=accent_color,
        radius=int(W * 0.13),
    )

    # ── Layer 6: Noise texture ──
    canvas = _draw_noise_texture(canvas, strength=5)

    # ── Layer 7: Bottom text strip ──
    canvas = _draw_bottom_text_strip(canvas, title, voice_profile, accent_color)

    # ── Layer 8: v2 badge ──
    canvas = _draw_v2_badge(canvas, accent_color)

    # Save
    final = canvas.convert("RGB")
    final.save(str(output_path), "PNG", quality=95)
    return output_path


# ─── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    out = Path("/tmp/aura_thumb_test.png")
    emotion = sys.argv[1] if len(sys.argv) > 1 else "Calm & Meditative"
    result = generate_thumbnail(
        out,
        title="Test Generation",
        emotion=emotion,
        voice_profile="Calm Female — British",
        seed=42,
    )
    print(f"Saved: {result}")
