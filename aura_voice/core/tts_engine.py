"""
AURA VOICE — TTS engine: Coqui XTTS v2 wrapper, text chunking, and synthesis pipeline.
"""

from __future__ import annotations

import re
import threading
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

CHUNK_TARGET_WORDS  = 175   # aim for this many words per chunk
CHUNK_MAX_WORDS     = 220   # hard upper limit before forcing a split

# XTTS v2 is a voice-cloning model — it does NOT support style/emotion
# conditioning via text prefixes.  All prefixes are empty; the "delivery
# style" setting is stored for metadata only and does not alter synthesis.
EMOTION_PREFIXES: Dict[str, str] = {
    "Neutral":                "",
    "Happy & Upbeat":         "",
    "Serious & Authoritative":"",
    "Sad & Reflective":       "",
    "Excited & Enthusiastic": "",
    "Calm & Meditative":      "",
}

# Maps our friendly voice-profile names to XTTS v2 speaker IDs.
# The model ships with a set of built-in speaker embeddings; these are the
# most natural-sounding ones for each persona.
VOICE_PROFILES: Dict[str, str] = {
    "Natural Female":        "Claribel Dervla",
    "Natural Male":          "Craig Gutsy",
    "Warm & Friendly":       "Daisy Studious",
    "Professional Narrator": "Andrew Chipper",
    "Energetic & Upbeat":    "Sofia Hellen",
    "Calm & Soothing":       "Gracie Wise",
    "Custom Voice Clone":    "__custom__",
}

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
    """
    Split text into sentences.  Tries NLTK first; falls back to a robust regex.
    """
    try:
        import nltk
        try:
            return nltk.sent_tokenize(text)
        except LookupError:
            nltk.download("punkt", quiet=True)
            nltk.download("punkt_tab", quiet=True)
            return nltk.sent_tokenize(text)
    except Exception:
        # Fallback: split on sentence-ending punctuation followed by whitespace
        raw = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in raw if s.strip()]


def chunk_text(text: str, target_words: int = CHUNK_TARGET_WORDS) -> List[str]:
    """
    Split *text* into chunks of approximately *target_words* words, never
    cutting mid-sentence.

    Returns:
        A list of text strings, each roughly target_words words long.
    """
    sentences = _split_into_sentences(text)
    chunks: List[str] = []
    current_sentences: List[str] = []
    current_word_count = 0

    for sentence in sentences:
        word_count = len(sentence.split())

        # If a single sentence is enormous, break it at commas / semicolons
        if word_count > CHUNK_MAX_WORDS:
            sub_parts = re.split(r'(?<=[,;:])\s+', sentence)
            for part in sub_parts:
                part_wc = len(part.split())
                if current_word_count + part_wc >= target_words and current_sentences:
                    chunks.append(" ".join(current_sentences))
                    current_sentences = [part]
                    current_word_count = part_wc
                else:
                    current_sentences.append(part)
                    current_word_count += part_wc
            continue

        if current_word_count + word_count >= target_words and current_sentences:
            chunks.append(" ".join(current_sentences))
            current_sentences = [sentence]
            current_word_count = word_count
        else:
            current_sentences.append(sentence)
            current_word_count += word_count

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return [c.strip() for c in chunks if c.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# TTS Engine
# ─────────────────────────────────────────────────────────────────────────────

class TTSEngine:
    """
    Wrapper around Coqui TTS / XTTS v2.

    Lifecycle
    ---------
    1.  Call ``is_model_cached()`` to check if the model is already on disk.
    2.  Call ``load_model()`` (blocks; run in a thread) to initialise the model.
    3.  Call ``synthesise()`` to run the full pipeline asynchronously.
    """

    def __init__(self) -> None:
        self._tts = None
        self._model_loaded = False
        self._lock = threading.Lock()

    # ── Model helpers ────────────────────────────────────────────────────────

    @staticmethod
    def is_model_cached() -> bool:
        """Return True if the XTTS v2 model is fully downloaded on disk (>1.8 GB)."""
        slug = MODEL_NAME.replace("/", "--")
        candidates = [
            Path.home() / "Library" / "Application Support" / "tts" / slug,
            Path.home() / ".local" / "share" / "tts" / slug,
            Path.home() / "AppData" / "Local" / "tts" / slug,
        ]
        for d in candidates:
            if d.exists():
                try:
                    total_bytes = sum(
                        f.stat().st_size for f in d.rglob("*") if f.is_file()
                    )
                    # Full model is ~1.87 GB — treat as cached if >1.8 GB present
                    if total_bytes > 1_800_000_000:
                        return True
                except Exception:
                    pass
        return False

    def load_model(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Initialise the TTS model.  Downloads it if not cached.
        This is a blocking call — run it in a background thread.
        """
        try:
            import torch
            import os
            os.environ.setdefault("COQUI_TOS_AGREED", "1")
            from TTS.api import TTS

            device = "mps" if torch.backends.mps.is_available() else "cpu"

            if progress_callback:
                progress_callback(f"Loading model on device: {device} …")

            tts_instance = TTS(MODEL_NAME, gpu=False).to(device)

            with self._lock:
                self._tts = tts_instance
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
        """Return the list of built-in speaker IDs from the loaded model."""
        with self._lock:
            if self._tts is None:
                return []
            try:
                return self._tts.speakers or []
            except Exception:
                return []

    # ── Single-chunk synthesis ───────────────────────────────────────────────

    def synthesise_chunk(
        self,
        text: str,
        output_path: Path,
        speaker: str,
        language: str = "en",
        speed: float = 1.0,
        reference_wav: Optional[Path] = None,
    ) -> None:
        """
        Synthesise a single text chunk and write it to *output_path* as WAV.

        Args:
            text:          The text to synthesise.
            output_path:   Where to save the WAV file.
            speaker:       Speaker ID (or "__custom__" for voice cloning).
            language:      ISO 639-1 language code, e.g. "en".
            speed:         Speaking rate multiplier (0.5 – 2.0).
            reference_wav: Path to reference WAV for voice cloning (required when
                           speaker == "__custom__").
        """
        with self._lock:
            tts = self._tts

        if tts is None:
            raise RuntimeError("TTS model is not loaded. Call load_model() first.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if speaker == "__custom__":
                if reference_wav is None or not reference_wav.exists():
                    raise ValueError("A reference WAV file is required for voice cloning.")
                tts.tts_to_file(
                    text=text,
                    speaker_wav=str(reference_wav),
                    language=language,
                    file_path=str(output_path),
                    speed=speed,
                )
            else:
                tts.tts_to_file(
                    text=text,
                    speaker=speaker,
                    language=language,
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
        on_chunk_start: Optional[Callable[[int, int], None]] = None,
        on_chunk_done: Optional[Callable[[int, int, float], None]] = None,
        on_stitch_start: Optional[Callable[[], None]] = None,
        on_stitch_progress: Optional[Callable[[int, int], None]] = None,
        on_export_start: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[Path], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> Optional[Path]:
        """
        Full synthesis pipeline:

        1. Chunk the input text.
        2. Synthesise each chunk to a temp WAV.
        3. Stitch all chunks together (with 300 ms silence between them).
        4. Export the final file as WAV or MP3.

        All *on_*  callbacks are invoked from this thread (caller is responsible
        for routing them to the UI thread via queue if needed).

        Returns the final output path on success, or None on failure/cancel.
        """
        from core.audio_utils import (
            stitch_chunks, export_wav, export_mp3, cleanup_temp_directory
        )

        # ── Prepare ──────────────────────────────────────────────────────────
        speaker_id = VOICE_PROFILES.get(voice_profile, "Claribel Dervla")
        emotion_prefix = EMOTION_PREFIXES.get(emotion, "")
        lang_code = LANGUAGE_CODES.get(language, "en")

        chunks = chunk_text(text)
        total_chunks = len(chunks)

        if total_chunks == 0:
            if on_error:
                on_error("No text to synthesise.")
            return None

        # ── Temp directory ────────────────────────────────────────────────────
        owns_temp_dir = temp_dir is None
        if owns_temp_dir:
            temp_dir = Path(tempfile.mkdtemp(prefix="aura_voice_"))

        chunk_paths: List[Path] = []

        try:
            # ── Synthesise chunks ─────────────────────────────────────────────
            chunk_times: List[float] = []
            for idx, chunk in enumerate(chunks):
                if cancel_event and cancel_event.is_set():
                    return None

                if on_chunk_start:
                    on_chunk_start(idx + 1, total_chunks)

                conditioned_text = emotion_prefix + chunk
                chunk_path = temp_dir / f"chunk_{idx + 1:04d}.wav"
                t0 = time.perf_counter()

                self.synthesise_chunk(
                    text=conditioned_text,
                    output_path=chunk_path,
                    speaker=speaker_id,
                    language=lang_code,
                    speed=speed,
                    reference_wav=reference_wav,
                )

                elapsed = time.perf_counter() - t0
                chunk_times.append(elapsed)
                chunk_paths.append(chunk_path)

                avg_time = sum(chunk_times) / len(chunk_times)
                eta_seconds = avg_time * (total_chunks - (idx + 1))

                if on_chunk_done:
                    on_chunk_done(idx + 1, total_chunks, eta_seconds)

            if cancel_event and cancel_event.is_set():
                return None

            # ── Stitch ────────────────────────────────────────────────────────
            if on_stitch_start:
                on_stitch_start()

            combined = stitch_chunks(
                chunk_paths,
                progress_callback=on_stitch_progress,
            )

            if cancel_event and cancel_event.is_set():
                return None

            # ── Export ────────────────────────────────────────────────────────
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_format.lower() == "mp3":
                final_path = output_path.with_suffix(".mp3")
                if on_export_start:
                    on_export_start("mp3")
                export_mp3(combined, final_path)
            else:
                final_path = output_path.with_suffix(".wav")
                if on_export_start:
                    on_export_start("wav")
                export_wav(combined, final_path)

            if on_complete:
                on_complete(final_path)

            return final_path

        except Exception as exc:
            if on_error:
                on_error(str(exc))
            return None

        finally:
            if owns_temp_dir:
                cleanup_temp_directory(temp_dir)
