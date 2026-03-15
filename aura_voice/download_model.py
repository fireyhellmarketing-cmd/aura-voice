"""
AURA VOICE — Standalone model downloader.
Run this once before launching the app:
    venv/bin/python3 download_model.py
"""

import os
import sys
import re
from pathlib import Path

os.environ["COQUI_TOS_AGREED"] = "1"

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
MODEL_SIZE_GB = 1.87


def _bar(pct: float, width: int = 40) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def check_cached() -> bool:
    slug = MODEL_NAME.replace("/", "--")
    candidates = [
        Path.home() / "Library" / "Application Support" / "tts" / slug,
        Path.home() / ".local" / "share" / "tts" / slug,
    ]
    for d in candidates:
        if d.exists():
            try:
                files = list(d.iterdir())
                total = sum(f.stat().st_size for f in files if f.is_file())
                # Full model is ~1.87 GB — consider cached if > 1.8 GB on disk
                if total > 1_800_000_000:
                    return True
            except Exception:
                pass
    return False


def main():
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║       AURA VOICE — Model Downloader      ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

    if check_cached():
        print("  ✅  Model already downloaded and ready!")
        print("  Run:  venv/bin/python3 main.py")
        print()
        return

    print(f"  Downloading: {MODEL_NAME}")
    print(f"  Size: ~{MODEL_SIZE_GB} GB  (downloads once, stored locally)")
    print()

    # Intercept tqdm to show a clean progress bar
    import io
    import sys as _sys

    class _TqdmCapture:
        _SIZE_RE = re.compile(r'([\d.]+)([KMGT]?)iB/([\d.]+)([KMGT]?)iB')
        _UNITS = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
        _real = _sys.stderr

        def write(self, text):
            self._real.write(text)          # keep normal stderr
            m = self._SIZE_RE.search(text)
            if m:
                done  = float(m.group(1)) * self._UNITS.get(m.group(2), 1)
                total = float(m.group(3)) * self._UNITS.get(m.group(4), 1)
                if total > 0:
                    pct      = done / total * 100
                    done_mb  = done  / 1024**2
                    total_mb = total / 1024**2
                    bar      = _bar(pct)
                    line = (
                        f"\r  [{bar}]  "
                        f"{pct:5.1f}%  "
                        f"{done_mb:.0f} / {total_mb:.0f} MB   "
                    )
                    print(line, end="", flush=True)

        def flush(self):
            self._real.flush()

    _sys.stderr = _TqdmCapture()

    try:
        from TTS.api import TTS
        print("  Starting download…\n")
        TTS(MODEL_NAME)
        _sys.stderr = _sys.__stderr__
        print()
        print()
        print("  ✅  Download complete!")
        print("  Run:  venv/bin/python3 main.py")
        print()
    except KeyboardInterrupt:
        _sys.stderr = _sys.__stderr__
        print()
        print("\n  ⚠️   Download interrupted. Run this script again to resume.")
        print()
    except Exception as e:
        _sys.stderr = _sys.__stderr__
        print()
        print(f"\n  ❌  Error: {e}")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
