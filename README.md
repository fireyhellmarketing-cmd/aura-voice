# AURA VOICE — AI Text to Speech Studio

> *Your words. Your voice. Locally yours.*

AURA VOICE is a fully offline, production-quality Text-to-Speech desktop application for macOS (Apple Silicon). It converts any length of text — from a single sentence to a 20-hour audiobook — into natural-sounding speech, entirely on your machine. No API keys. No subscriptions. No data leaves your computer.

---

## 1. What is AURA VOICE?

AURA VOICE wraps the state-of-the-art [Coqui XTTS v2](https://github.com/coqui-ai/TTS) model inside a polished, dark-themed desktop GUI. XTTS v2 is a multilingual, multi-speaker neural TTS model with expressive voice cloning — and it runs natively on Apple Silicon via Metal Performance Shaders (MPS).

Key features:
- **Long-form synthesis** — split any text into sentence-aligned chunks, synthesise each one, then stitch the results into a single WAV/MP3 file
- **6 voice profiles** — built-in XTTS v2 speakers covering female, male, warm, professional, energetic, and calm personas
- **Voice cloning** — upload 6–30 seconds of any speaker's voice and clone it
- **6 emotion/delivery styles** — neutral, happy, serious, sad, excited, and meditative
- **8 languages** — English, Spanish, French, German, Hindi, Portuguese, Italian, Dutch
- **Variable speed** — 0.5× to 2.0× speaking rate
- **WAV + MP3 export** (requires ffmpeg for MP3)
- **`.auravoice` project files** — save and reload your script + settings as a portable project
- **Live progress** — chunk counter, percentage bar, and real-time ETA
- **100% Apple MPS acceleration** — dramatically faster than CPU on M-series chips

---

## 2. System Requirements

| Requirement | Minimum |
|---|---|
| Mac | Apple Silicon (M1/M2/M3/M4 or later) |
| macOS | Ventura 13.0 or later |
| Python | 3.11 (via Homebrew: `brew install python@3.11`) |
| RAM | 8 GB (16 GB recommended for very long texts) |
| Disk | ~3 GB free (1.8 GB model + app) |
| ffmpeg | Required for MP3 export (`brew install ffmpeg`) |

---

## 3. Quick Start

```bash
# 1 — Clone or download this repository
git clone <repo-url>
cd aura_voice

# 2 — Run the one-command setup script
bash setup.sh

# 3 — Launch the app
source venv/bin/activate && python3 main.py
```

That's it. The first time you click **Generate Audio**, the app will prompt you to download the XTTS v2 model (~1.8 GB). This happens once and is cached locally.

---

## 4. First Run

On first launch, AURA VOICE detects that the voice model is not yet cached and shows a modal:

> *"The AI voice model needs to be downloaded once. File size: ~1.8 GB — stored locally, never sent online."*

Click **Download Now** to pull the model from Coqui's model hub. The download progress is shown in the modal. Once complete, the model is cached at:

```
~/.local/share/tts/tts_models--multilingual--multi-dataset--xtts_v2/
```

All subsequent launches load the model from disk in a few seconds.

---

## 5. How to Generate Audio

1. **Paste or load your script** — use the left panel. You can paste directly, or click *Load .txt File* to import from disk.
2. **Choose a Voice Profile** — from the right panel dropdown.
3. **Choose an Emotion** — pick the delivery style that matches your content.
4. **Set the speed** — drag the slider (default 1.0×).
5. **Select a language** — English is default.
6. **Choose output format** — WAV or MP3.
7. **Set your output folder** — defaults to Desktop.
8. **Click ✦ Generate Audio** — the bottom bar shows live progress with a chunk counter and ETA.
9. **When done**, click *✓ Open Output Folder* to reveal the file in Finder.

---

## 6. Voice Types and Emotions Explained

### Voice Profiles

| Profile | Character |
|---|---|
| Natural Female | Claribel Dervla — clear, natural female voice |
| Natural Male | Craig Gutsy — confident, natural male voice |
| Warm & Friendly | Daisy Studious — warm and approachable |
| Professional Narrator | Andrew Chipper — clean, broadcast-quality narration |
| Energetic & Upbeat | Sofia Hellen — bright and expressive |
| Calm & Soothing | Gracie Wise — smooth and relaxing |
| Custom Voice Clone | Upload your own reference WAV |

### Emotion Styles

XTTS v2 is responsive to natural-language conditioning. AURA VOICE prepends a short style prompt to each chunk before synthesis:

| Emotion | Effect |
|---|---|
| Neutral | No modification — raw voice |
| Happy & Upbeat | Warm, enthusiastic delivery |
| Serious & Authoritative | Clear, firm, newsreader-like |
| Sad & Reflective | Soft, slower, introspective |
| Excited & Enthusiastic | High-energy, expressive |
| Calm & Meditative | Very slow, soothing, ambient |

---

## 7. Voice Cloning

1. Select **Custom Voice Clone** from the Voice Profile dropdown.
2. A card appears asking for a reference audio file.
3. Click **Browse…** and select a `.wav` file containing 6–30 seconds of clean speech from the voice you want to clone.
4. Proceed with generation as normal.

**Tips for good cloning:**
- Use a clean recording with no background noise or music
- 15–20 seconds gives better results than the minimum 6 seconds
- The voice should be the only speaker in the recording
- 22 kHz mono WAV works best

---

## 8. The .auravoice Project Format

AURA VOICE uses a custom `.auravoice` file extension for saving projects. Under the hood it is a ZIP archive containing:

- `manifest.json` — identifies the file as an AURA VOICE project
- `project.json` — all your settings (voice, emotion, speed, language, etc.)
- `script.txt` — your full input text

### Saving a project
- **File → Save Project** (`⌘S`) — save to the current file
- **File → Save Project As…** — choose a new location

### Loading a project
- **File → Open Project…** (`⌘O`) — open a file picker
- Or click **Load .auravoice** in the left panel
- Or drag a `.auravoice` file onto the left panel text area

### File association (optional)
To always open `.auravoice` files with AURA VOICE:
1. Right-click any `.auravoice` file in Finder
2. **Get Info → Open With → Other…**
3. Navigate to `python3` or your launcher script
4. Check *Always Open With*

See [docs/AURAVOICE_FORMAT.md](docs/AURAVOICE_FORMAT.md) for the full technical specification.

---

## 9. Generating Very Long Audio

AURA VOICE is designed for long-form content. A 20-hour audiobook is ~180,000 words. Here are tips:

**Performance on Apple Silicon:**
- M1 Pro: ~1.5–2.5 real-time factor (a 1-minute audio chunk takes 24–40 seconds)
- M2 Max: ~0.8–1.2 real-time factor (near real-time)
- M3 Ultra: even faster

**For very long scripts (10,000+ words):**
1. Check that your Mac is plugged in (prevents thermal throttling)
2. Close other memory-heavy applications
3. Set your output folder to a fast NVMe drive (the internal SSD is fine)
4. Chunk size is ~175 words — a 100,000-word book creates ~570 chunks
5. Each chunk is saved as a temp WAV, then all are stitched at the end
6. If generation is interrupted, you will need to restart (partial generation is not resumable in v1.0)

**ETA calculation:**
The bottom bar shows a live ETA based on the rolling average time per chunk. This becomes accurate after the first ~10 chunks.

---

## 10. Troubleshooting

### "Model not found" / download fails
- Check your internet connection — the model downloads from Hugging Face
- Ensure `~/.local/share/tts/` is writable
- Try: `python3 -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"`

### App is slow / using CPU not GPU
- Verify MPS is available: `python3 -c "import torch; print(torch.backends.mps.is_available())"`
- Should print `True` on Apple Silicon
- If `False`, your PyTorch install may not have MPS support — reinstall with `pip install torch torchaudio`

### "ffmpeg not found" when exporting MP3
- Run: `brew install ffmpeg`
- Verify: `which ffmpeg` — should print a path

### Audio sounds robotic / unnatural
- Try a different voice profile
- Reduce speed to 0.85–0.95× for more natural pacing
- Try "Neutral" emotion for the cleanest output
- Ensure input text has proper punctuation (periods, commas) for natural pausing

### App crashes on launch
- Ensure you are running from inside the venv: `source venv/bin/activate`
- Verify all dependencies: `pip list | grep -E 'customtkinter|TTS|pydub|torch'`
- Check Python version: `python3 --version` (should be 3.11.x)

### NLTK errors on first run
```bash
python3 -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

---

## 11. Credits

| Component | Credit |
|---|---|
| **TTS Engine** | [Coqui TTS](https://github.com/coqui-ai/TTS) — XTTS v2 model |
| **GUI Framework** | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) by Tom Schimansky |
| **Audio Processing** | [pydub](https://github.com/jiaaro/pydub) by Jiaaro |
| **Audio Backend** | [ffmpeg](https://ffmpeg.org) |
| **Acceleration** | Apple Metal Performance Shaders via PyTorch |
| **Tokenisation** | [NLTK](https://www.nltk.org) |

---

*AURA VOICE — 100% offline · Apple Silicon optimised · Open source*
