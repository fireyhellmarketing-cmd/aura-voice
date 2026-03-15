# AURA VOICE — User Guide

## Interface Overview

The window is split into two panels:

```
┌─────────────────────────────────────────────────────────────────┐
│  AURA VOICE — AI Text to Speech Studio               ⬤ Ready   │
├──────────────────────────┬──────────────────────────────────────┤
│                          │                                      │
│   LEFT PANEL             │   RIGHT PANEL                        │
│   Your Script            │   Voice & Controls                   │
│                          │                                      │
│   [large text area]      │   Voice Profile ▾                    │
│                          │   Emotion       ▾                    │
│   1,234 words · ~8m 14s  │   Speed ────●── 1.0×                │
│                          │   Language  ▾                        │
│   [Load .txt] [Load .av] │   ○ WAV  ● MP3                      │
│                          │   Output: ~/Desktop  [Change…]       │
│                          │                                      │
│                          │   ╔══════════════════════╗          │
│                          │   ║  ✦  Generate Audio   ║          │
│                          │   ╚══════════════════════╝          │
├─────────────────────────────────────────────────────────────────┤
│  Synthesising chunk 12 of 340 — 3.5%  ████░░░  ETA: 14m 32s   │
│                                           [Cancel]              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Left Panel — Your Script

### Entering text

Paste any text directly into the large text box. There is no practical length limit — the app has been tested with scripts exceeding 500,000 words.

The **word count** and **estimated duration** update live as you type or paste. Duration is estimated at 150 words per minute (close to a neutral narration pace).

### Loading a .txt file

Click **↑ Load .txt File** to open a file picker and import any plain-text file. The entire file contents replace the current text box content.

### Loading an .auravoice project

Click **⬡ Load .auravoice** to restore a previously saved project. This restores both the script and all your voice/emotion/speed settings.

---

## Right Panel — Voice & Controls

### Voice Profile

Choose the speaker personality:

| Option | Description |
|---|---|
| Natural Female | Clear, natural female voice (default) |
| Natural Male | Confident, natural male voice |
| Warm & Friendly | Approachable, conversational |
| Professional Narrator | Broadcast-quality narration |
| Energetic & Upbeat | Expressive, bright |
| Calm & Soothing | Smooth, relaxing |
| Custom Voice Clone | Clone any voice from a WAV file |

### Emotion / Delivery Style

Controls the emotional character of the delivery. This works by prepending a short style prompt to each text chunk before synthesis — XTTS v2 responds well to this kind of natural language conditioning.

| Emotion | Best for |
|---|---|
| Neutral | Audiobooks, documentation, anything clean |
| Happy & Upbeat | Explainer videos, marketing, friendly content |
| Serious & Authoritative | News, legal, instructional |
| Sad & Reflective | Memoirs, poetry, introspective content |
| Excited & Enthusiastic | Trailers, promos, sports |
| Calm & Meditative | Meditation guides, sleep audio, ambient |

### Speaking Speed

- Default: **1.0×** (natural pace, ~150 wpm)
- Slow: **0.75×** — very clear, good for technical content
- Fast: **1.3–1.5×** — efficient listening
- Note: extreme speeds (below 0.6× or above 1.8×) can degrade audio quality

### Language

XTTS v2 supports multilingual synthesis natively. The selected language affects pronunciation and intonation. Choose the language that matches your input text.

Supported: English, Spanish, French, German, Hindi, Portuguese, Italian, Dutch.

### Output Format

- **WAV** — lossless, larger file (~10 MB/minute at 22 kHz)
- **MP3** — compressed, smaller (~2.5 MB/minute at 192 kbps). Requires ffmpeg.

### Custom Voice Clone

When you select **Custom Voice Clone**, a card appears:

1. Click **Browse…** to select a `.wav` reference file (6–30 seconds)
2. The file name appears to confirm selection
3. Generate as normal — XTTS v2 will match the voice characteristics

**Reference audio requirements:**
- Format: WAV (PCM, any sample rate — will be resampled internally)
- Length: 6–30 seconds (15–20 seconds is optimal)
- Content: a single speaker reading clearly, no background noise
- Language: should match the synthesis language for best results

### Output Folder

Shows the current destination folder. Click **Change…** to pick a different location. The output file is named `aura_voice_YYYYMMDD_HHMMSS.wav` (or `.mp3`).

---

## Bottom Bar — Progress

During generation, the bottom bar shows:

- **Progress bar** — fills left to right as chunks are synthesised
- **Status text** — current action (e.g. "Synthesising chunk 47 of 320…")
- **Chunk counter** — `Chunk 47 of 320 — 14.7%`
- **ETA** — estimated time remaining based on rolling average chunk time
- **Cancel button** — safely stops synthesis after the current chunk completes

When generation finishes:
- Bar fills to 100%
- Status turns green: "✓ Complete!"
- **Open Output Folder** button appears — click to reveal the file in Finder

---

## Menu Bar

### File menu

| Command | Shortcut | Action |
|---|---|---|
| New Project | ⌘N | Clear script and reset settings |
| Open Project… | ⌘O | Open an .auravoice file |
| Save Project | ⌘S | Save to current file (or prompt if new) |
| Save Project As… | — | Save to a new location |
| Import Script (.txt)… | — | Load text from a .txt file |
| Export as WAV… | — | Copy the last generated WAV to a chosen path |
| Export as MP3… | — | Convert and export the last generation as MP3 |
| Quit | ⌘Q | Exit the application |

### View menu

- **Toggle Dark / Light Mode** — switches between dark (default) and light themes

### Help menu

- **About AURA VOICE** — version, credits, and offline badge
- **Check Model Cache** — shows whether the model is cached and loaded

---

## Tips & Tricks

**For natural audiobook narration:**
- Use "Professional Narrator" voice + "Neutral" emotion + 0.95× speed
- Ensure your text has proper punctuation for natural pauses

**For YouTube voiceovers:**
- Try "Energetic & Upbeat" emotion + 1.1× speed
- Export as MP3 for smaller file sizes

**For meditation / relaxation content:**
- "Calm & Soothing" voice + "Calm & Meditative" emotion + 0.8× speed

**Batch workflow for very long content:**
- Split your script into chapters, save each as a separate .auravoice project
- Generate each chapter individually; stitch in your DAW or with ffmpeg afterwards
