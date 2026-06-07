"""
Whisper STT wrapper — Phase 3.

Loads the Whisper 'base' model once at module level (singleton),
then exposes a simple transcribe(audio_path) → str function.
"""

from __future__ import annotations

import whisper

# ─── Singleton model loader ────────────────────────────────────────────────────

_model = None


def _get_model():
    """Load the Whisper model once and cache it."""
    global _model
    if _model is None:
        print("🎙️  Loading Whisper 'base' model (first load may download ~140 MB)...")
        _model = whisper.load_model("base")
        print("✅  Whisper model loaded.")
    return _model


def preload_model() -> None:
    """Pre-warm the model at server startup so the first request is fast."""
    _get_model()


# ─── Public API ─────────────────────────────────────────────────────────────────

def transcribe(audio_path: str) -> str:
    """
    Transcribe an audio file to text using Whisper.

    Args:
        audio_path: Path to the audio file (webm, wav, mp3, etc.)

    Returns:
        Raw transcript text.
    """
    model = _get_model()
    result = model.transcribe(audio_path)
    return result["text"]
