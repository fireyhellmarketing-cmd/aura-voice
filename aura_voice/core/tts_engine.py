"""
AURA VOICE — TTS engine: Coqui VITS (VCTK) wrapper, text chunking, and synthesis pipeline.

Primary model : tts_models/en/vctk/vits
 - 109 English speakers, fast VITS architecture
 - Real-time factor ~0.13 (very fast, even on CPU)
 - Requires espeak-ng:  brew install espeak-ng  (macOS)
"""

from __future__ import annotations

import re
import threading
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

MODEL_NAME       = "tts_models/en/vctk/vits"
XTTS_MODEL_NAME  = "tts_models/multilingual/multi-dataset/xtts_v2"

CHUNK_TARGET_WORDS = 100   # VITS handles shorter chunks best
CHUNK_MAX_WORDS    = 150

# Friendly voice profile name → VCTK speaker ID
# Names must exactly match controls_panel.py VOICE_PROFILES list.
VOICE_PROFILES: Dict[str, str] = {
    "Natural Female":            "p225",   # clear, neutral British female
    "Natural Male":              "p226",   # clear, neutral British male
    "Warm Female":               "p270",   # warm, expressive female
    "Deep Male":                 "p260",   # deep male voice
    "Youthful Female":           "p330",   # young, bright female
    "Authoritative Male":        "p247",   # authoritative male
    "Calm Female — British":     "p236",   # calm, clear British female
    "Energetic Male — American": "p374",   # energetic male
    "Soft Whispery Female":      "p228",   # soft, gentle female
    "Professional Narrator":     "p245",   # clear narrator male
    "Custom (Clone)":            "p225",   # fallback — VCTK doesn't support cloning
}

# Kept for UI compatibility — VITS doesn't use emotion conditioning
EMOTION_PREFIXES: Dict[str, str] = {k: "" for k in [
    "Neutral", "Happy & Upbeat", "Serious & Authoritative",
    "Sad & Reflective", "Excited & Enthusiastic", "Calm & Meditative",
]}

# Delivery style → speed multiplier applied on top of user speed setting
EMOTION_SPEEDS: Dict[str, float] = {
    "Neutral":                  1.00,
    "Happy & Upbeat":           1.10,
    "Serious & Authoritative":  0.93,
    "Sad & Reflective":         0.82,
    "Excited & Enthusiastic":   1.20,
    "Calm & Meditative":        0.80,
    "Warm & Friendly":          1.02,
    "Professional":             0.95,
}

# Language codes (kept for UI; VITS model is English-only)
LANGUAGE_CODES: Dict[str, str] = {
    "English":    "en",
    "Spanish":    "es",
    "French":     "fr",
    "German":     "de",
    "Hindi":      "hi",
    "Portuguese": "pt",
    "Italian":    "it",
    "Dutch":      "nl",
}


# ─────────────────────────────────────────────────────────────────────────────
# Text Chunking
# ─────────────────────────────────────────────────────────────────────────────

def _split_into_sentences(text: str) -> List[str]:
    try:
        import nltk
        try:
            return nltk.sent_tokenize(text)
        except LookupError:
            nltk.download("punkt", quiet=True)
            nltk.download("punkt_tab", quiet=True)
            return nltk.sent_tokenize(text)
    except Exception:
        raw = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in raw if s.strip()]


def chunk_text(text: str, target_words: int = CHUNK_TARGET_WORDS) -> List[str]:
    sentences = _split_into_sentences(text)
    chunks: List[str] = []
    current: List[str] = []
    current_wc = 0

    for sentence in sentences:
        wc = len(sentence.split())
        if wc > CHUNK_MAX_WORDS:
            sub = re.split(r'(?<=[,;:])\s+', sentence)
            for part in sub:
                pwc = len(part.split())
                if current_wc + pwc >= target_words and current:
                    chunks.append(" ".join(current))
                    current = [part]; current_wc = pwc
                else:
                    current.append(part); current_wc += pwc
            continue
        if current_wc + wc >= target_words and current:
            chunks.append(" ".join(current))
            current = [sentence]; current_wc = wc
        else:
            current.append(sentence); current_wc += wc

    if current:
        chunks.append(" ".join(current))
    return [c.strip() for c in chunks if c.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# TTS Engine
# ─────────────────────────────────────────────────────────────────────────────

class TTSEngine:
    """
    Wrapper around Coqui TTS / VCTK VITS.

    Lifecycle
    ---------
    1. is_model_cached() — check if already downloaded
    2. load_model()      — blocking; run in a thread
    3. synthesise()      — full pipeline
    """

    def __init__(self) -> None:
        self._tts          = None
        self._model_loaded = False
        self._lock         = threading.Lock()
        # XTTS v2 — lazily loaded only when voice cloning is requested
        self._xtts_tts     = None
        self._xtts_loaded  = False
        self._xtts_lock    = threading.Lock()

    # ── Model helpers ────────────────────────────────────────────────────────

    @staticmethod
    def is_model_cached() -> bool:
        """Return True if the VCTK VITS model is downloaded (>100 MB)."""
        slug = MODEL_NAME.replace("/", "--")
        candidates = [
            Path.home() / "Library" / "Application Support" / "tts" / slug,
            Path.home() / ".local" / "share" / "tts" / slug,
            Path.home() / "AppData" / "Local" / "tts" / slug,
        ]
        for d in candidates:
            if d.exists():
                try:
                    total = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                    if total > 100_000_000:   # >100 MB
                        return True
                except Exception:
                    pass
        return False

    def load_model(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialise the TTS model (blocking — run in a background thread)."""
        try:
            import os
            os.environ.setdefault("COQUI_TOS_AGREED", "1")
            from TTS.api import TTS

            if progress_callback:
                progress_callback("Loading VITS model…")

            tts_instance = TTS(MODEL_NAME, gpu=False)

            with self._lock:
                self._tts          = tts_instance
                self._model_loaded = True

            if progress_callback:
                progress_callback("Model loaded successfully.")

        except Exception as exc:
            with self._lock:
                self._model_loaded = False
            raise RuntimeError(f"Failed to load TTS model: {exc}") from exc

    @property
    def is_loaded(self) -> bool:
        with self._lock:
            return self._model_loaded

    def get_available_speakers(self) -> List[str]:
        with self._lock:
            if self._tts is None:
                return []
            try:
                return self._tts.speakers or []
            except Exception:
                return []

    # ── XTTS v2 (voice cloning) ──────────────────────────────────────────────

    def _load_xtts_if_needed(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Lazily load XTTS v2 the first time voice cloning is requested."""
        with self._xtts_lock:
            if self._xtts_loaded:
                return
        if progress_callback:
            progress_callback("Loading XTTS v2 for voice cloning…")
        import os
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        from TTS.api import TTS
        xtts = TTS(XTTS_MODEL_NAME, gpu=False)
        with self._xtts_lock:
            self._xtts_tts    = xtts
            self._xtts_loaded = True
        if progress_callback:
            progress_callback("XTTS v2 ready.")

    def _synthesise_chunk_xtts(
        self,
        text: str,
        output_path: Path,
        reference_wav: Path,
        language: str = "en",
    ) -> None:
        """Synthesise one chunk using XTTS v2 (voice cloning)."""
        with self._xtts_lock:
            tts = self._xtts_tts
        if tts is None:
            raise RuntimeError("XTTS model not loaded.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            tts.tts_to_file(
                text=text,
                speaker_wav=str(reference_wav),
                language=language,
                file_path=str(output_path),
            )
        except Exception as exc:
            raise RuntimeError(f"XTTS synthesis failed: {exc}") from exc

    # ── Single-chunk synthesis ───────────────────────────────────────────────

    def synthesise_chunk(
        self,
        text: str,
        output_path: Path,
        speaker: str,
        speed: float = 1.0,
    ) -> None:
        """Synthesise one text chunk → WAV file."""
        with self._lock:
            tts = self._tts
        if tts is None:
            raise RuntimeError("Model not loaded.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Clamp speed: VITS supports via length_scale (inverse of speed)
            tts.tts_to_file(
                text=text,
                speaker=speaker,
                file_path=str(output_path),
                speed=speed,
            )
        except Exception as exc:
            raise RuntimeError(f"Synthesis failed for chunk: {exc}") from exc

    # ── Full pipeline ────────────────────────────────────────────────────────

    def synthesise(
        self,
        text: str,
        output_path: Path,
        voice_profile: str = "Natural Female",
        emotion: str = "Neutral",
        speed: float = 1.0,
        language: str = "en",
        output_format: str = "wav",
        reference_wav: Optional[Path] = None,
        temp_dir: Optional[Path] = None,
        cancel_event: Optional[threading.Event] = None,
        on_chunk_start:    Optional[Callable[[int, int], None]]       = None,
        on_chunk_done:     Optional[Callable[[int, int, float], None]] = None,
        on_stitch_start:   Optional[Callable[[], None]]               = None,
        on_stitch_progress:Optional[Callable[[int, int], None]]       = None,
        on_export_start:   Optional[Callable[[str], None]]            = None,
        on_complete:       Optional[Callable[[Path], None]]           = None,
        on_error:          Optional[Callable[[str], None]]            = None,
    ) -> Optional[Path]:
        from core.audio_utils import (
            stitch_chunks_to_file, export_mp3, cleanup_temp_directory
        )

        # Determine if we're cloning
        use_clone = voice_profile == "Custom (Clone)" and reference_wav is not None

        if use_clone:
            try:
                self._load_xtts_if_needed()
            except Exception as exc:
                if on_error:
                    on_error(f"Failed to load XTTS v2: {exc}")
                return None
        else:
            speaker_id = VOICE_PROFILES.get(voice_profile, "p225")

        # Apply delivery-style speed multiplier on top of user speed
        emotion_mult    = EMOTION_SPEEDS.get(emotion, 1.0)
        effective_speed = round(speed * emotion_mult, 3)

        chunks = chunk_text(text)
        total  = len(chunks)

        if total == 0:
            if on_error:
                on_error("No text to synthesise.")
            return None

        # ── Persistent chunk folder ──────────────────────────────────────────
        # Chunks are saved next to the output file (not in a system temp dir).
        # If the app crashes mid-synthesis the folder survives so the user can
        # manually stitch the completed chunks later.
        #   e.g.  ~/Documents/AuraVoice/aura_voice_20260316_012345_chunks/
        owns_chunk_dir = temp_dir is None
        if owns_chunk_dir:
            output_path = Path(output_path)
            chunk_dir   = output_path.parent / (output_path.name + "_chunks")
            chunk_dir.mkdir(parents=True, exist_ok=True)
            temp_dir    = chunk_dir
        else:
            chunk_dir   = Path(temp_dir)

        chunk_paths: List[Path] = []
        succeeded = False
        try:
            chunk_times: List[float] = []
            for idx, chunk in enumerate(chunks):
                if cancel_event and cancel_event.is_set():
                    return None
                if on_chunk_start:
                    on_chunk_start(idx + 1, total)

                chunk_path = temp_dir / f"chunk_{idx + 1:04d}.wav"
                t0 = time.perf_counter()
                if use_clone:
                    self._synthesise_chunk_xtts(
                        text=chunk,
                        output_path=chunk_path,
                        reference_wav=reference_wav,
                        language=language,
                    )
                else:
                    self.synthesise_chunk(
                        text=chunk,
                        output_path=chunk_path,
                        speaker=speaker_id,
                        speed=effective_speed,
                    )
                elapsed = time.perf_counter() - t0
                chunk_times.append(elapsed)
                chunk_paths.append(chunk_path)

                avg = sum(chunk_times) / len(chunk_times)
                eta = avg * (total - (idx + 1))
                if on_chunk_done:
                    on_chunk_done(idx + 1, total, eta)

            if cancel_event and cancel_event.is_set():
                return None

            if on_stitch_start:
                on_stitch_start()

            # ── Light stitching via wave module (no pydub decoding) ──────────
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_format.lower() == "mp3":
                # Stitch to a temporary WAV first, then convert
                wav_tmp = output_path.with_suffix(".wav")
                stitch_chunks_to_file(
                    chunk_paths, wav_tmp,
                    progress_callback=on_stitch_progress,
                )
                if cancel_event and cancel_event.is_set():
                    return None
                final_path = output_path.with_suffix(".mp3")
                if on_export_start:
                    on_export_start("mp3")
                try:
                    from pydub import AudioSegment as _AS
                    export_mp3(_AS.from_wav(str(wav_tmp)), final_path)
                finally:
                    if wav_tmp.exists():
                        wav_tmp.unlink(missing_ok=True)
            else:
                final_path = output_path.with_suffix(".wav")
                if on_export_start:
                    on_export_start("wav")
                stitch_chunks_to_file(
                    chunk_paths, final_path,
                    progress_callback=on_stitch_progress,
                )

            succeeded = True
            if on_complete:
                on_complete(final_path)
            return final_path

        except Exception as exc:
            if on_error:
                on_error(
                    f"{exc}\n\n"
                    f"Chunks saved at:\n{chunk_dir}\n"
                    "(You can stitch them manually using ffmpeg or Audacity.)"
                )
            return None
        finally:
            # Clean up chunk folder only on success; keep it on failure/cancel
            if owns_chunk_dir and succeeded:
                cleanup_temp_directory(temp_dir)
