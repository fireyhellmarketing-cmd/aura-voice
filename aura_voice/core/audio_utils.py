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
    Concatenate WAV chunks into a single AudioSegment (pydub path).
    Kept for callers that need an AudioSegment object.
    For large jobs, prefer stitch_chunks_to_file() which is much lighter.
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


def stitch_chunks_to_file(
    chunk_paths: List[Path],
    output_path: Path,
    silence_ms: int = SILENCE_BETWEEN_CHUNKS_MS,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> None:
    """
    Concatenate WAV chunks directly into a WAV file using the built-in
    ``wave`` module — no pydub decoding, no large AudioSegment in memory.

    This is significantly lighter on CPU and RAM than the pydub approach
    because it copies raw PCM bytes without decoding/re-encoding.
    All chunks must share the same sample-rate, bit-depth, and channel count
    (guaranteed when they come from the same TTS model).

    Args:
        chunk_paths:       Ordered list of WAV chunk file paths.
        output_path:       Destination WAV path (created/overwritten).
        silence_ms:        Milliseconds of silence inserted between chunks.
        progress_callback: Optional callback(current_index, total).
    """
    import wave as _wave

    if not chunk_paths:
        raise ValueError("No audio chunks provided for stitching.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total  = len(chunk_paths)
    params = None   # wave.params namedtuple (set from first chunk)

    with _wave.open(str(output_path), "wb") as out_wav:
        for idx, path in enumerate(chunk_paths):
            with _wave.open(str(path), "rb") as in_wav:
                if params is None:
                    params = in_wav.getparams()
                    out_wav.setparams(params)
                out_wav.writeframes(in_wav.readframes(in_wav.getnframes()))

            # Silence gap between chunks (not after the last one)
            if idx < total - 1 and silence_ms > 0 and params is not None:
                n_silence = int(params.framerate * silence_ms / 1000)
                silence_bytes = b"\x00" * (n_silence * params.nchannels * params.sampwidth)
                out_wav.writeframes(silence_bytes)

            if progress_callback:
                progress_callback(idx + 1, total)


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
