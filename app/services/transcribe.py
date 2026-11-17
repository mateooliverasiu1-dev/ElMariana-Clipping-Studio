"""Transcripción con Faster-Whisper en CPU (int8), con marcas de tiempo por palabra.

El modelo se carga de forma perezosa y se reutiliza. Solo modelos ligeros
(tiny/base/small) para no superar 8 GB de RAM.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable

from .. import config

log = logging.getLogger("elmariana.transcribe")

_model_lock = threading.Lock()
_model_cache: dict[str, Any] = {}


class TranscriptionUnavailable(RuntimeError):
    pass


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def _get_model(size: str):
    if size not in config.WHISPER_MODELS:
        raise ValueError(f"Modelo no permitido: {size}. Usa uno de {config.WHISPER_MODELS}")
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise TranscriptionUnavailable(
            "Faster-Whisper no está instalado. Ejecuta: pip install -r requirements.txt") from exc
    with _model_lock:
        if size not in _model_cache:
            _model_cache.clear()  # solo un modelo en memoria a la vez
            log.info("Cargando modelo Whisper '%s' (%s)…", size, config.WHISPER_COMPUTE_TYPE)
            _model_cache[size] = WhisperModel(
                size, device="cpu", compute_type=config.WHISPER_COMPUTE_TYPE,
                cpu_threads=config.WHISPER_CPU_THREADS)
        return _model_cache[size]


def transcribe(audio_path: str | Path, language: str = "auto", model_size: str | None = None,
               duration: float | None = None,
               on_progress: Callable[[float], None] | None = None) -> dict[str, Any]:
    """Transcribe y devuelve {language, language_probability, segments:[{start,end,text,words}]}."""
    model = _get_model(model_size or config.WHISPER_DEFAULT_MODEL)
    lang = None if language in (None, "", "auto") else language
    segments_iter, info = model.transcribe(
        str(audio_path), language=lang, word_timestamps=True, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500}, beam_size=1, condition_on_previous_text=False)
    total = duration or getattr(info, "duration", None) or 0.0
    segments = []
    for seg in segments_iter:
        words = [
            {"w": w.word.strip(), "start": round(float(w.start), 3), "end": round(float(w.end), 3),
             "p": round(float(w.probability), 3)}
            for w in (seg.words or []) if w.word.strip()
        ]
        segments.append({"start": round(float(seg.start), 3), "end": round(float(seg.end), 3),
                         "text": seg.text.strip(), "words": words})
        if on_progress and total:
            on_progress(min(seg.end / total, 1.0))
    return {"language": info.language, "language_probability": round(float(info.language_probability), 3),
            "model": model_size or config.WHISPER_DEFAULT_MODEL, "segments": segments}


def all_words(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    return [w for s in transcript.get("segments", []) for w in s.get("words", [])]
