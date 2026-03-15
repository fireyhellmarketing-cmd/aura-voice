"""
AURA VOICE — Audio utilities: pydub helpers, format conversion, silence gaps.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Optional, Callable

try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

SILENCE_BETWEEN_CHUNKS_MS = 300   # 300 ms gap between chunks
SAMPLE_RATE               = 22050
CHANNELS                  = 1


# ─────────────────────────────────────────────────────────────────────────────
# Core helpers
# ─────────────────────────────────────────────────────────────────────────────

def silence_segment(duration_ms: int = SILENCE_BETWEEN_CHUNKS_MS) -> "AudioSegment":
    """Return a silent AudioSegment of the given duration."""
    return AudioSegment.silent(duration=duration_ms, frame_rate=SAMPLE_RATE)


def load_wav(path: Path) -> "AudioSegment":
    """Load a WAV file and return an AudioSegment."""
    try:
        return AudioSegment.from_wav(str(path))
    except CouldntDecodeError as exc:
        raise RuntimeError(f"Could not decode audio file: {path}") from exc


def stitch_chunks(
    chunk_paths: List[Path],
    silence_ms: int = SILENCE_BETWEEN_CHUNKS_MS,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> "AudioSegment":
    """
    Concatenate a list of WAV chunk files into a single AudioSegment,
    inserting a silence gap between each chunk.

    Args:
        chunk_paths:       Ordered list of chunk WAV file paths.
        silence_ms:        Milliseconds of silence between chunks.
        progress_callback: Optional callback(current_index, total) called per chunk.

    Returns:
        A single concatenated AudioSegment.
    """
    if not chunk_paths:
        raise ValueError("No audio chunks provided for stitching.")

    gap = silence_segment(silence_ms)
    total = len(chunk_paths)
    combined: Optional[AudioSegment] = None

    for idx, path in enumerate(chunk_paths):
        segment = load_wav(path)
        if combined is None:
            combined = segment
        else:
            combined = combined + gap + segment

        if progress_callback:
            progress_callback(idx + 1, total)

    return combined  # type: ignore[return-value]


def export_wav(audio: "AudioSegment", output_path: Path) -> None:
    """Export an AudioSegment as a WAV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(str(output_path), format="wav")


def export_mp3(
    audio: "AudioSegment",
    output_path: Path,
    bitrate: str = "192k",
) -> None:
    """Export an AudioSegment as an MP3 file (requires ffmpeg)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(str(output_path), format="mp3", bitrate=bitrate)


def wav_to_mp3(
    wav_path: Path,
    mp3_path: Path,
    bitrate: str = "192k",
) -> None:
    """Convert an existing WAV file to MP3."""
    audio = load_wav(wav_path)
    export_mp3(audio, mp3_path, bitrate=bitrate)


def get_audio_duration_seconds(path: Path) -> float:
    """Return the duration of an audio file in seconds."""
    try:
        audio = AudioSegment.from_file(str(path))
        return len(audio) / 1000.0
    except Exception:
        return 0.0


def cleanup_temp_directory(temp_dir: Path) -> None:
    """Safely remove a temporary directory and all its contents."""
    if temp_dir.exists() and temp_dir.is_dir():
        shutil.rmtree(temp_dir, ignore_errors=True)


def ffmpeg_available() -> bool:
    """Return True if ffmpeg is on the system PATH."""
    return shutil.which("ffmpeg") is not None


def estimate_duration_minutes(word_count: int, wpm: int = 150) -> float:
    """Estimate audio duration in minutes based on word count."""
    if wpm <= 0:
        return 0.0
    return word_count / wpm


def format_duration(minutes: float) -> str:
    """Format a duration in minutes to a human-readable string."""
    total_seconds = int(minutes * 60)
    hours   = total_seconds // 3600
    mins    = (total_seconds % 3600) // 60
    secs    = total_seconds % 60

    if hours > 0:
        return f"{hours}h {mins}m {secs}s"
    elif mins > 0:
        return f"{mins}m {secs}s"
    else:
        return f"{secs}s"


def format_eta(seconds_remaining: float) -> str:
    """Format remaining seconds into a readable ETA string."""
    if seconds_remaining <= 0:
        return "—"
    total = int(seconds_remaining)
    hours = total // 3600
    mins  = (total % 3600) // 60
    secs  = total % 60
    if hours > 0:
        return f"{hours}h {mins}m {secs}s"
    elif mins > 0:
        return f"{mins}m {secs}s"
    else:
        return f"{secs}s"
