# AURA VOICE — Setup Guide (macOS Apple Silicon)

## Prerequisites

### 1. Python 3.11

Check your version:
```bash
python3 --version
```

If you need 3.11:
```bash
brew install python@3.11
# Then use python3.11 instead of python3 below
```

### 2. Homebrew

If not installed:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 3. ffmpeg (required for MP3 export)

```bash
brew install ffmpeg
ffmpeg -version   # verify
```

---

## Installation

### Option A — Automated (recommended)

```bash
cd aura_voice
bash setup.sh
```

This script:
1. Installs ffmpeg (if missing)
2. Creates a Python venv
3. Installs all pip packages
4. Downloads the NLTK punkt tokeniser

### Option B — Manual step-by-step

```bash
cd aura_voice

# Create venv
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install PyTorch with MPS support
pip install torch torchaudio

# Install the rest
pip install -r requirements.txt

# NLTK data
python3 -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

---

## Launching the App

```bash
source venv/bin/activate
python3 main.py
```

---

## First-Run Model Download

AURA VOICE uses the Coqui XTTS v2 model (~1.8 GB). On first launch, a dialog will prompt you to download it. The model is cached at:

```
~/.local/share/tts/tts_models--multilingual--multi-dataset--xtts_v2/
```

You can also pre-download it from the command line:
```bash
source venv/bin/activate
python3 -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

---

## Verifying MPS Acceleration

Run this to confirm GPU acceleration is active:
```bash
source venv/bin/activate
python3 -c "
import torch
print('MPS available:', torch.backends.mps.is_available())
print('MPS built:',     torch.backends.mps.is_built())
"
```

Both should print `True` on Apple Silicon.

---

## Uninstalling

To remove AURA VOICE completely:
```bash
# Delete the app
rm -rf /path/to/aura_voice

# Delete the model cache
rm -rf ~/.local/share/tts/
```
