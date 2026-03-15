"""
Run this script once (after Pillow is installed) to generate the app icon.
    python3 assets/generate_icon.py
"""

from PIL import Image, ImageDraw
from pathlib import Path

def generate_icon(out_path: Path = Path(__file__).parent / "icon.png") -> None:
    size = 512
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark background circle
    draw.ellipse([20, 20, 492, 492], fill="#13131f")

    # Stylised waveform bars
    cx, cy = 256, 256
    amplitudes = [0.30, 0.55, 0.75, 0.95, 1.00, 0.85, 0.70, 0.50,
                  0.35, 0.60, 0.90, 0.80, 0.40, 0.65, 0.30]
    bar_w = 18
    gap   = 8
    total_w = len(amplitudes) * (bar_w + gap) - gap
    x_start = cx - total_w // 2

    for i, amp in enumerate(amplitudes):
        h     = int(amp * 200)
        x     = x_start + i * (bar_w + gap)
        color = "#c084fc" if amp > 0.8 else "#7b5ea7"
        draw.rounded_rectangle(
            [x, cy - h // 2, x + bar_w, cy + h // 2],
            radius=bar_w // 2,
            fill=color,
        )

    img.save(str(out_path))
    print(f"Icon saved to: {out_path}")


if __name__ == "__main__":
    generate_icon()
