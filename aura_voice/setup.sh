#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# AURA VOICE — One-command setup for macOS (Apple Silicon / M-series)
# ─────────────────────────────────────────────────────────────────────────────

set -e

echo ""
echo "🎙  Setting up AURA VOICE…"
echo "────────────────────────────────────────────────────────────"

# ── 1. ffmpeg ────────────────────────────────────────────────────────────────
if command -v ffmpeg &>/dev/null; then
    echo "✓  ffmpeg already installed ($(ffmpeg -version 2>&1 | head -1))"
else
    echo "⬇  Installing ffmpeg via Homebrew…"
    if ! command -v brew &>/dev/null; then
        echo "❌  Homebrew is required but not found."
        echo "    Install it from https://brew.sh and re-run this script."
        exit 1
    fi
    brew install ffmpeg
    echo "✓  ffmpeg installed."
fi

# ── 2. Python venv ───────────────────────────────────────────────────────────
echo ""
echo "🐍  Creating Python virtual environment…"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet

# ── 3. PyTorch for Apple Silicon (MPS) ──────────────────────────────────────
echo ""
echo "⬇  Installing PyTorch (MPS-enabled for Apple Silicon)…"
pip install torch torchaudio --quiet

# ── 4. Remaining dependencies ────────────────────────────────────────────────
echo ""
echo "⬇  Installing remaining dependencies…"
pip install -r requirements.txt --quiet

# ── 5. NLTK punkt tokeniser ──────────────────────────────────────────────────
echo ""
echo "⬇  Downloading NLTK punkt tokeniser…"
python3 -c "
import nltk
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
print('✓  NLTK data downloaded.')
"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────────────────────"
echo "✅  Setup complete!"
echo ""
echo "   To launch AURA VOICE:"
echo "   source venv/bin/activate && python3 main.py"
echo ""
