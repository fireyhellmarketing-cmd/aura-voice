"""AURA VOICE — Model catalog and compatibility layer."""

import os
import json
from pathlib import Path
from typing import Dict, Any

# Import only when needed to avoid hard dependency at import time
from .hardware_detect import HardwareInfo


# ─── Model Catalog ─────────────────────────────────────────────────────────────

MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    "XTTS v2 — Multilingual Pro": {
        "model_id":             "tts_models/multilingual/multi-dataset/xtts_v2",
        "size_gb":              1.87,
        "quality":              5,
        "quality_label":        "★★★★★",
        "supports_cloning":     True,
        "supports_emotions":    True,
        "hardware":             ["cuda", "mps", "cpu"],
        "min_ram_gb":           8,
        "recommended_vram_gb":  4,
        "languages": [
            "English", "Spanish", "French", "German", "Hindi",
            "Portuguese", "Italian", "Dutch", "Polish", "Russian",
            "Turkish", "Korean", "Japanese", "Chinese",
        ],
        "description": (
            "Best quality. Multilingual with 14 languages. "
            "Voice cloning from a short audio sample. "
            "Slow on CPU — GPU/MPS strongly recommended."
        ),
        "recommended": True,
        "tag": "BEST",
    },

    "YourTTS — Fast Multilingual": {
        "model_id":             "tts_models/multilingual/multi-dataset/your_tts",
        "size_gb":              0.39,
        "quality":              3,
        "quality_label":        "★★★☆☆",
        "supports_cloning":     True,
        "supports_emotions":    False,
        "hardware":             ["cuda", "mps", "cpu"],
        "min_ram_gb":           4,
        "recommended_vram_gb":  2,
        "languages": ["English", "French", "Portuguese"],
        "description": (
            "Fast multilingual model. "
            "Supports voice cloning. "
            "Good quality, moderate speed on CPU."
        ),
        "recommended": False,
        "tag": "FAST",
    },

    "Glow-TTS — Fast English": {
        "model_id":             "tts_models/en/ljspeech/glow-tts",
        "size_gb":              0.08,
        "quality":              3,
        "quality_label":        "★★★☆☆",
        "supports_cloning":     False,
        "supports_emotions":    False,
        "hardware":             ["cuda", "mps", "cpu"],
        "min_ram_gb":           2,
        "recommended_vram_gb":  1,
        "languages": ["English"],
        "description": (
            "Very fast English-only synthesis. "
            "Small footprint. "
            "Good for prototyping or low-resource machines."
        ),
        "recommended": False,
        "tag": "LIGHT",
    },

    "FastPitch — English Pro": {
        "model_id":             "tts_models/en/ljspeech/fast_pitch",
        "size_gb":              0.35,
        "quality":              4,
        "quality_label":        "★★★★☆",
        "supports_cloning":     False,
        "supports_emotions":    False,
        "hardware":             ["cuda", "mps", "cpu"],
        "min_ram_gb":           4,
        "recommended_vram_gb":  2,
        "languages": ["English"],
        "description": (
            "High-quality English synthesis. "
            "Fast inference with good prosody. "
            "Great balance of quality and speed."
        ),
        "recommended": False,
        "tag": "QUALITY",
    },

    "VITS — Lightweight English": {
        "model_id":             "tts_models/en/ljspeech/vits",
        "size_gb":              0.12,
        "quality":              3,
        "quality_label":        "★★★☆☆",
        "supports_cloning":     False,
        "supports_emotions":    False,
        "hardware":             ["cuda", "mps", "cpu"],
        "min_ram_gb":           2,
        "recommended_vram_gb":  1,
        "languages": ["English"],
        "description": (
            "End-to-end English TTS. "
            "Tiny model, fast on CPU. "
            "Ideal for offline / low-RAM environments."
        ),
        "recommended": False,
        "tag": "MINIMAL",
    },
}


# ─── Cache Path Utilities ──────────────────────────────────────────────────────

def get_model_cache_root() -> Path:
    """Return the root directory where Coqui/TTS caches models."""
    # Coqui TTS stores models in ~/.local/share/tts on Linux/Mac and
    # %APPDATA%/tts on Windows by default.
    env_override = os.environ.get("TTS_HOME")
    if env_override:
        return Path(env_override)
    return Path.home() / ".local" / "share" / "tts"


def get_model_cache_path(model_id: str) -> Path:
    """
    Return the local cache directory for a given model_id.

    model_id format: "tts_models/multilingual/multi-dataset/xtts_v2"
    Coqui maps this to:  ~/.local/share/tts/tts_models--multilingual--multi-dataset--xtts_v2
    """
    slug = model_id.replace("/", "--")
    return get_model_cache_root() / slug


def is_model_downloaded(model_id: str) -> bool:
    """Return True if the model directory exists and appears non-empty."""
    path = get_model_cache_path(model_id)
    if not path.exists():
        return False
    # Check for at least one file inside
    try:
        return any(path.iterdir())
    except Exception:
        return False


def get_downloaded_size_gb(model_id: str) -> float:
    """Return the total size in GB of a downloaded model directory."""
    path = get_model_cache_path(model_id)
    if not path.exists():
        return 0.0
    total_bytes = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total_bytes += entry.stat().st_size
    except Exception:
        return 0.0
    return round(total_bytes / (1024 ** 3), 2)


# ─── Compatibility Filtering ───────────────────────────────────────────────────

def get_compatible_models(hardware: HardwareInfo) -> Dict[str, Dict[str, Any]]:
    """
    Return a filtered subset of MODEL_CATALOG compatible with the given hardware.

    Compatibility rules:
    - Model's hardware list must include the recommended device, OR include "cpu"
      (every model that supports cpu is usable, just potentially slow).
    - Model's min_ram_gb must be <= hardware.ram_gb.
    - If hardware has no GPU (cuda/mps), models requiring > 6 GB VRAM are still
      included but flagged with a warning note.
    """
    compatible: Dict[str, Dict[str, Any]] = {}

    for name, spec in MODEL_CATALOG.items():
        # RAM check
        if hardware.ram_gb < spec.get("min_ram_gb", 0):
            continue

        # Device check — all models support CPU, so they're all usable
        # We just annotate whether the recommended device applies
        entry = dict(spec)
        device = hardware.recommended_device

        if device == "cuda" and "cuda" in spec["hardware"]:
            entry["_device_note"] = "GPU accelerated"
            entry["_device_ok"] = True
        elif device == "mps" and "mps" in spec["hardware"]:
            entry["_device_note"] = "Apple MPS accelerated"
            entry["_device_ok"] = True
        else:
            entry["_device_note"] = "CPU mode (slower)"
            entry["_device_ok"] = False

        # Mark download status
        entry["_downloaded"] = is_model_downloaded(spec["model_id"])
        entry["_downloaded_size_gb"] = (
            get_downloaded_size_gb(spec["model_id"])
            if entry["_downloaded"]
            else 0.0
        )

        compatible[name] = entry

    return compatible


# ─── Config Persistence ────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".aura_voice_config.json"


def load_config() -> dict:
    """Load config from ~/.aura_voice_config.json, return defaults if missing."""
    defaults = {
        "first_run": True,
        "selected_model": "XTTS v2 — Multilingual Pro",
        "device": "cpu",
        "output_dir": str(Path.home() / "Documents" / "AuraVoice"),
        "filename_pattern": "aura_voice_{date}_{time}",
        "auto_open_folder": False,
        "sample_rate": 22050,
        "mp3_bitrate": "192k",
        "fade_in_ms": 0,
        "fade_out_ms": 0,
        "accent_color": "#7c3aed",
        "theme": "dark",
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_config(config: dict) -> None:
    """Persist config dict to ~/.aura_voice_config.json."""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as exc:
        print(f"[AURA VOICE] Warning: could not save config: {exc}")


# ─── Model Name Lookup ─────────────────────────────────────────────────────────

def model_id_to_name(model_id: str) -> str:
    """Reverse-lookup model display name from model_id."""
    for name, spec in MODEL_CATALOG.items():
        if spec["model_id"] == model_id:
            return name
    return model_id


def get_model_spec(display_name: str) -> Dict[str, Any]:
    """Return the catalog spec for a display name, or empty dict."""
    return MODEL_CATALOG.get(display_name, {})
