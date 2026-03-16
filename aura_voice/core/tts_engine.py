"""
AURA VOICE — TTS engine.

Supported engines:
  • Kokoro TTS  (default) — 82M params, human-quality US/UK English voices, very fast on CPU
  • Chatterbox  (cloning) — Resemble AI open-source ElevenLabs alternative, emotion control
  • XTTS v2     (legacy)  — multilingual voice cloning fallback
  • VCTK VITS   (legacy)  — fast 109-speaker English fallback
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

CHUNK_TARGET_WORDS = 80    # shorter chunks → more natural prosody
CHUNK_MAX_WORDS    = 120

# ── Kokoro voices ─────────────────────────────────────────────────────────────
# pip install kokoro soundfile
KOKORO_VOICES: Dict[str, str] = {
    "Warm Female (US)":          "af_heart",     # warm, expressive — best overall
    "Bright Female (US)":        "af_nova",       # bright, energetic
    "Professional Female (US)":  "af_alloy",      # neutral, clear
    "Soft Female (US)":          "af_shimmer",    # gentle, soothing
    "Clear Male (US)":           "am_echo",       # clear, articulate
    "Deep Male (US)":            "am_onyx",       # deep, authoritative
    "Natural Female (UK)":       "bf_emma",       # natural British female
    "Expressive Female (UK)":    "bf_isabella",   # expressive British female
    "Natural Male (UK)":         "bm_george",     # natural British male
    "Warm Male (UK)":            "bm_lewis",      # warm British male
    "Custom (Clone)":            "af_heart",      # placeholder — routes to Chatterbox
}

# ── VCTK VITS voices (legacy fallback) ───────────────────────────────────────
VOICE_PROFILES: Dict[str, str] = {
    "Natural Female":            "p225",
    "Natural Male":              "p226",
    "Warm Female":               "p270",
    "Deep Male":                 "p260",
    "Youthful Female":           "p330",
    "Authoritative Male":        "p247",
    "Calm Female — British":     "p236",
    "Energetic Male — American": "p374",
    "Soft Whispery Female":      "p228",
    "Professional Narrator":     "p245",
    "Custom (Clone)":            "p225",
}

# Kept for UI compatibility
EMOTION_PREFIXES: Dict[str, str] = {k: "" for k in [
    "Neutral", "Happy & Upbeat", "Serious & Authoritative",
    "Sad & Reflective", "Excited & Enthusiastic", "Calm & Meditative",
]}

# Delivery style → speed multiplier
EMOTION_SPEEDS: Dict[str, float] = {
    "Neutral":                  1.00,
    "Happy & Upbeat":           1.10,
    "Serious & Authoritative":  0.93,
    "Sad & Reflective":         0.88,
    "Excited & Enthusiastic":   1.15,
    "Calm & Meditative":        0.85,
    "Warm & Friendly":          1.02,
    "Professional":             0.95,
}

# Delivery style → Chatterbox exaggeration override (None = use slider value)
EMOTION_EXAGGERATION: Dict[str, Optional[float]] = {
    "Neutral":                  0.50,
    "Happy & Upbeat":           0.70,
    "Serious & Authoritative":  0.40,
    "Sad & Reflective":         0.35,
    "Excited & Enthusiastic":   0.85,
    "Calm & Meditative":        0.25,
    "Warm & Friendly":          0.60,
    "Professional":             0.45,
}

# Language codes
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


def _get_torch_device(allow_mps: bool = True) -> str:
    """Return 'mps' on Apple Silicon (if allowed), else 'cpu'."""
    if allow_mps:
        try:
            import torch
            if torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
    return "cpu"


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
    Multi-engine TTS wrapper.

    Engines:
      kokoro     — primary (human-quality, fast CPU)
      chatterbox — voice cloning (ElevenLabs-grade quality)
      vctk       — legacy VCTK VITS fallback
      xtts       — legacy XTTS v2 cloning fallback
    """

    def __init__(self) -> None:
        # Engine type currently loaded for standard synthesis
        self._engine_type  = "vctk"    # "kokoro" | "chatterbox" | "vctk"
        self._model_loaded = False
        self._lock         = threading.Lock()

        # VCTK VITS (legacy)
        self._tts      = None

        # Kokoro TTS
        self._kokoro_pipeline = None
        self._kokoro_loaded   = False
        self._kokoro_lock     = threading.Lock()

        # Chatterbox TTS (voice cloning + standard)
        self._chatterbox_model  = None
        self._chatterbox_loaded = False
        self._chatterbox_lock   = threading.Lock()

        # XTTS v2 (legacy cloning fallback)
        self._xtts_tts    = None
        self._xtts_loaded = False
        self._xtts_lock   = threading.Lock()

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
        model_name: str = "",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialise the TTS model (blocking — run in a background thread)."""
        name_lower = model_name.lower()
        if "kokoro" in name_lower:
            self._load_kokoro(progress_callback)
        elif "chatterbox" in name_lower:
            self._load_chatterbox_primary(progress_callback)
        else:
            self._load_vctk(progress_callback)

    def _load_vctk(self, progress_callback=None):
        """Load legacy VCTK VITS model."""
        try:
            import os
            os.environ.setdefault("COQUI_TOS_AGREED", "1")
            from TTS.api import TTS
            if progress_callback:
                progress_callback("Loading VITS model…")
            tts_instance = TTS(MODEL_NAME, gpu=False)
            with self._lock:
                self._tts          = tts_instance
                self._engine_type  = "vctk"
                self._model_loaded = True
            if progress_callback:
                progress_callback("VCTK VITS loaded.")
        except Exception as exc:
            with self._lock:
                self._model_loaded = False
            raise RuntimeError(f"Failed to load VCTK VITS: {exc}") from exc

    def _load_kokoro(self, progress_callback=None):
        """Load Kokoro TTS pipeline (pip install kokoro soundfile)."""
        try:
            if progress_callback:
                progress_callback("Loading Kokoro TTS…")
            from kokoro import KPipeline
            # American English pipeline ('a'); British = 'b'
            pipeline = KPipeline(lang_code="a")
            with self._kokoro_lock:
                self._kokoro_pipeline = pipeline
                self._kokoro_loaded   = True
            with self._lock:
                self._engine_type  = "kokoro"
                self._model_loaded = True
            if progress_callback:
                progress_callback("Kokoro TTS loaded — human-quality voices ready.")
        except ImportError:
            raise RuntimeError(
                "Kokoro package not installed.\n"
                "Run:  pip install kokoro soundfile"
            )
        except Exception as exc:
            with self._lock:
                self._model_loaded = False
            raise RuntimeError(f"Failed to load Kokoro: {exc}") from exc

    def _load_chatterbox_primary(self, progress_callback=None):
        """Load Chatterbox as the primary engine (pip install chatterbox-tts)."""
        try:
            if progress_callback:
                progress_callback("Loading Chatterbox TTS…")
            import warnings
            from chatterbox.tts import ChatterboxTTS
            # Chatterbox vocoder/flow-matching pipeline is not fully MPS-compatible;
            # use CPU to avoid 'NoneType not callable' errors on Apple Silicon
            device = "cpu"
            print(f"[Chatterbox] Loading on device: {device}")
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                model = ChatterboxTTS.from_pretrained(device=device)
            with self._chatterbox_lock:
                self._chatterbox_model  = model
                self._chatterbox_loaded = True
            with self._lock:
                self._engine_type  = "chatterbox"
                self._model_loaded = True
            if progress_callback:
                progress_callback("Chatterbox TTS loaded — voice cloning ready.")
        except ImportError:
            raise RuntimeError(
                "Chatterbox package not installed.\n"
                "Run:  pip install chatterbox-tts"
            )
        except Exception as exc:
            with self._lock:
                self._model_loaded = False
            raise RuntimeError(f"Failed to load Chatterbox: {exc}") from exc

    @property
    def is_loaded(self) -> bool:
        with self._lock:
            return self._model_loaded

    @property
    def engine_type(self) -> str:
        with self._lock:
            return self._engine_type

    def get_available_speakers(self) -> List[str]:
        with self._lock:
            if self._tts is None:
                return []
            try:
                return self._tts.speakers or []
            except Exception:
                return []

    # ── Kokoro synthesis ─────────────────────────────────────────────────────

    def _synthesise_chunk_kokoro(
        self,
        text: str,
        output_path: Path,
        voice: str = "af_heart",
        speed: float = 1.0,
    ) -> None:
        """Synthesise one chunk with Kokoro TTS. Output: 24 kHz mono WAV."""
        with self._kokoro_lock:
            pipeline = self._kokoro_pipeline
        if pipeline is None:
            raise RuntimeError("Kokoro pipeline not loaded.")

        import numpy as np
        import soundfile as sf

        audio_parts: List[np.ndarray] = []
        # split_pattern=None lets Kokoro handle its own sentence splitting
        for _gs, _ps, audio in pipeline(text, voice=voice, speed=speed, split_pattern=None):
            if audio is not None and len(audio) > 0:
                audio_parts.append(audio)

        if not audio_parts:
            raise RuntimeError("Kokoro produced no audio output.")

        combined = np.concatenate(audio_parts).astype(np.float32)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), combined, 24000)

    # ── Chatterbox synthesis ─────────────────────────────────────────────────

    def _load_chatterbox_if_needed(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Lazily load Chatterbox for voice cloning."""
        with self._chatterbox_lock:
            if self._chatterbox_loaded:
                return
        if progress_callback:
            progress_callback("Loading Chatterbox for voice cloning…")
        try:
            import warnings
            from chatterbox.tts import ChatterboxTTS
            # Force CPU — MPS vocoder path raises 'NoneType not callable' on macOS
            device = "cpu"
            print(f"[Chatterbox] Loading cloning engine on {device}…")
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                model = ChatterboxTTS.from_pretrained(device=device)
            with self._chatterbox_lock:
                self._chatterbox_model  = model
                self._chatterbox_loaded = True
            if progress_callback:
                progress_callback("Chatterbox loaded — voice cloning ready.")
        except ImportError:
            raise RuntimeError(
                "Chatterbox not installed. Run:  pip install chatterbox-tts"
            )
        except Exception as exc:
            raise RuntimeError(f"Chatterbox load failed: {exc}") from exc

    def _synthesise_chunk_chatterbox(
        self,
        text: str,
        output_path: Path,
        reference_wav: Optional[Path] = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 3.0,
    ) -> None:
        """Synthesise one chunk with Chatterbox. Supports voice cloning + emotion."""
        with self._chatterbox_lock:
            model = self._chatterbox_model
        if model is None:
            raise RuntimeError("Chatterbox model not loaded.")

        import torchaudio

        kwargs: dict = {
            "exaggeration": max(0.1, min(1.0, exaggeration)),
            "cfg_weight":   cfg_weight,
        }
        if reference_wav and reference_wav.exists():
            kwargs["audio_prompt_path"] = str(reference_wav)

        # Suppress the attention-mask warning from HuggingFace tokenizer
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*attention mask.*")
            wav = model.generate(text, **kwargs)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        torchaudio.save(str(output_path), wav, model.sr)

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

    # ── XTTS helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _patch_torchaudio_load():
        """
        torchaudio >= 2.9 routes torchaudio.load() through TorchCodec which
        requires torchcodec (not installed). Monkey-patch to use soundfile.
        Returns the original so caller can restore it.
        """
        import torchaudio
        import torch
        import soundfile as _sf

        original = torchaudio.load

        def _sf_load(path, frame_offset=0, num_frames=-1,
                     normalize=True, channels_first=True, format=None, **_kw):
            data, sr = _sf.read(str(path), dtype="float32", always_2d=True)
            tensor = torch.from_numpy(data.T)   # [channel, time]
            if frame_offset:
                tensor = tensor[:, frame_offset:]
            if num_frames > 0:
                tensor = tensor[:, :num_frames]
            if not channels_first:
                tensor = tensor.T
            return tensor, sr

        torchaudio.load = _sf_load
        return original

    @staticmethod
    def _prepare_ref_wav(reference_wav: Path) -> Path:
        """Convert any audio to 22050 Hz mono PCM WAV for XTTS compatibility."""
        import tempfile
        tmp = Path(tempfile.mktemp(suffix="_ref.wav"))
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(str(reference_wav))
            seg = seg.set_frame_rate(22050).set_channels(1).set_sample_width(2)
            seg.export(str(tmp), format="wav")
            return tmp
        except Exception:
            try:
                import soundfile as sf
                import numpy as np
                data, sr = sf.read(str(reference_wav), always_2d=False)
                if data.ndim > 1:
                    data = data.mean(axis=1)
                sf.write(str(tmp), data, sr, subtype="PCM_16")
                return tmp
            except Exception:
                return reference_wav

    @staticmethod
    def _load_npz_embeddings(path: Path):
        """Load cached (gpt_cond_latent, speaker_embedding) from .npz file."""
        import numpy as np
        import torch
        d = np.load(str(path))
        return (
            torch.from_numpy(d["gpt_cond_latent"]),
            torch.from_numpy(d["speaker_embedding"]),
        )

    @staticmethod
    def _save_npz_embeddings(path: Path, gpt_cond, spk_emb) -> None:
        """Save (gpt_cond_latent, speaker_embedding) tensors to .npz file."""
        import numpy as np
        np.savez(
            str(path),
            gpt_cond_latent=gpt_cond.cpu().numpy(),
            speaker_embedding=spk_emb.cpu().numpy(),
        )

    def _get_speaker_embeddings(
        self,
        model,
        reference_wav: Path,
        profile_npz: Optional[Path] = None,
    ):
        """
        Return (gpt_cond_latent, speaker_embedding) for a reference audio.

        Priority:
          1. profile_npz     — pre-saved named profile (.npz)
          2. auto-cache npz  — cached next to the reference file
          3. live encode     — compute from reference_wav and cache it
        """
        # 1. Named saved profile
        if profile_npz and profile_npz.exists():
            return self._load_npz_embeddings(profile_npz)

        # 2. Auto-cache
        cache_path = reference_wav.with_suffix("").with_suffix(".xtts_emb.npz")
        # ^ e.g. /path/voice.wav  →  /path/voice.xtts_emb.npz
        if cache_path.exists():
            return self._load_npz_embeddings(cache_path)

        # 3. Encode from reference (slow, done once)
        ref_path = self._prepare_ref_wav(reference_wav)
        try:
            gpt_cond, spk_emb = model.get_conditioning_latents(
                audio_path=[str(ref_path)],
                gpt_cond_len=30,
                max_ref_length=60,
                sound_norm_refs=False,
            )
        finally:
            if ref_path != reference_wav:
                try:
                    ref_path.unlink(missing_ok=True)
                except Exception:
                    pass

        # Cache result
        try:
            self._save_npz_embeddings(cache_path, gpt_cond, spk_emb)
        except Exception:
            pass  # cache failure is non-fatal

        return gpt_cond, spk_emb

    def _synthesise_chunk_xtts(
        self,
        text: str,
        output_path: Path,
        reference_wav: Optional[Path] = None,
        language: str = "en",
        profile_npz: Optional[Path] = None,
    ) -> None:
        """
        Synthesise one chunk using XTTS v2.

        Uses pre-computed speaker embeddings when available (fast path).
        Falls back to encoding the reference on first use, then caches.
        """
        with self._xtts_lock:
            tts = self._xtts_tts
        if tts is None:
            raise RuntimeError("XTTS model not loaded.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # XTTS needs at least ~15 chars for stable output
        if len(text.strip()) < 15:
            text = (text.strip() + " ") * 3

        model = tts.synthesizer.tts_model

        orig_load = self._patch_torchaudio_load()
        try:
            gpt_cond, spk_emb = self._get_speaker_embeddings(
                model, reference_wav, profile_npz
            )

            out = model.inference(
                text=text,
                language=language,
                gpt_cond_latent=gpt_cond,
                speaker_embedding=spk_emb,
                temperature=0.65,
                repetition_penalty=10.0,
                top_k=50,
                top_p=0.85,
                enable_text_splitting=True,
            )
        except Exception as exc:
            raise RuntimeError(f"XTTS synthesis failed: {exc}") from exc
        finally:
            import torchaudio as _ta
            _ta.load = orig_load

        # Write 24000 Hz mono PCM WAV (XTTS native sample rate)
        import numpy as np
        import wave as _wave
        wav = np.array(out["wav"])
        wav_i16 = (wav * 32767).clip(-32768, 32767).astype(np.int16)
        with _wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(wav_i16.tobytes())

    def encode_speaker_profile(
        self,
        reference_wav: Path,
        profile_name: str,
        profiles_dir: Path,
    ) -> Path:
        """
        Encode a reference audio file into a named reusable speaker profile.
        Saves a .npz and updates profiles.json in profiles_dir.
        Returns the path to the .npz file.
        """
        with self._xtts_lock:
            tts = self._xtts_tts
        if tts is None:
            raise RuntimeError("XTTS model not loaded. Generate one clone first.")

        profiles_dir.mkdir(parents=True, exist_ok=True)
        ref_path = self._prepare_ref_wav(reference_wav)

        model = tts.synthesizer.tts_model
        orig = self._patch_torchaudio_load()
        try:
            gpt_cond, spk_emb = model.get_conditioning_latents(
                audio_path=[str(ref_path)],
                gpt_cond_len=30,
                max_ref_length=60,
                sound_norm_refs=False,
            )
        finally:
            import torchaudio as _ta
            _ta.load = orig
            if ref_path != reference_wav:
                try:
                    ref_path.unlink(missing_ok=True)
                except Exception:
                    pass

        # Sanitise profile name for filename
        safe = "".join(
            c if (c.isalnum() or c in " _-") else "_"
            for c in profile_name
        ).strip() or "profile"
        npz_path = profiles_dir / f"{safe}.npz"
        self._save_npz_embeddings(npz_path, gpt_cond, spk_emb)

        # Update registry
        import json
        reg_path = profiles_dir / "profiles.json"
        registry: dict = {}
        if reg_path.exists():
            try:
                registry = json.loads(reg_path.read_text())
            except Exception:
                pass
        registry[profile_name] = str(npz_path)
        reg_path.write_text(json.dumps(registry, indent=2))

        return npz_path

    @staticmethod
    def list_speaker_profiles(profiles_dir: Path) -> dict:
        """Return {name: npz_path_str} for all saved profiles."""
        import json
        reg = profiles_dir / "profiles.json"
        if not reg.exists():
            return {}
        try:
            data = json.loads(reg.read_text())
            # Filter out entries whose .npz files no longer exist
            return {k: v for k, v in data.items() if Path(v).exists()}
        except Exception:
            return {}

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
        voice_profile: str = "Warm Female (US)",
        emotion: str = "Neutral",
        speed: float = 1.0,
        exaggeration: float = 0.5,      # Chatterbox emotion expressiveness
        language: str = "en",
        output_format: str = "wav",
        reference_wav: Optional[Path] = None,
        profile_npz: Optional[Path] = None,
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

        with self._lock:
            engine = self._engine_type

        # ── Determine synthesis route ────────────────────────────────────────
        use_clone = (
            (voice_profile == "Custom (Clone)" and reference_wav is not None)
            or profile_npz is not None
        )

        # Cloning: always prefer Chatterbox, fall back to XTTS
        use_chatterbox_clone = False
        if use_clone:
            try:
                self._load_chatterbox_if_needed()
                use_chatterbox_clone = True
                print("[Engine] Cloning via Chatterbox TTS")
            except Exception as exc:
                print(f"[Engine] Chatterbox unavailable ({exc}), falling back to XTTS v2")
                try:
                    self._load_xtts_if_needed()
                except Exception as exc2:
                    if on_error:
                        on_error(f"Failed to load cloning engine: {exc2}")
                    return None

        # Map emotion to exaggeration override for Chatterbox
        emo_exag = EMOTION_EXAGGERATION.get(emotion)
        effective_exag = emo_exag if emo_exag is not None else exaggeration

        # Apply speed multiplier for all engines
        emotion_mult    = EMOTION_SPEEDS.get(emotion, 1.0)
        effective_speed = round(speed * emotion_mult, 3)

        # Voice IDs
        if engine == "kokoro" and not use_clone:
            kokoro_voice = KOKORO_VOICES.get(voice_profile, "af_heart")
        elif engine == "vctk" and not use_clone:
            speaker_id = VOICE_PROFILES.get(voice_profile, "p225")

        chunks = chunk_text(text)
        total  = len(chunks)

        if total == 0:
            if on_error:
                on_error("No text to synthesise.")
            return None

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

                if use_clone and use_chatterbox_clone:
                    self._synthesise_chunk_chatterbox(
                        text=chunk,
                        output_path=chunk_path,
                        reference_wav=reference_wav,
                        exaggeration=effective_exag,
                    )
                elif use_clone:
                    # XTTS v2 fallback
                    self._synthesise_chunk_xtts(
                        text=chunk,
                        output_path=chunk_path,
                        reference_wav=reference_wav,
                        language=language,
                        profile_npz=profile_npz,
                    )
                elif engine == "kokoro":
                    self._synthesise_chunk_kokoro(
                        text=chunk,
                        output_path=chunk_path,
                        voice=kokoro_voice,
                        speed=effective_speed,
                    )
                elif engine == "chatterbox":
                    # Chatterbox as primary (no reference = default voice)
                    self._synthesise_chunk_chatterbox(
                        text=chunk,
                        output_path=chunk_path,
                        reference_wav=None,
                        exaggeration=effective_exag,
                    )
                else:
                    # VCTK VITS fallback
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
