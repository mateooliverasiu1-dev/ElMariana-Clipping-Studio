"""Voz sintética local con Piper (gratis, sin servicios de pago, corre en CPU).

La primera vez descarga el modelo de voz desde Hugging Face (rhasspy/piper-voices)
a data/voices/. Después funciona sin internet.

Uso rápido desde la terminal:
    python -m app.services.voice "Hola, esto es una prueba"      -> data/voices/prueba.wav
"""
from __future__ import annotations

import logging
import sys
import threading
import urllib.request
import wave
from pathlib import Path

from .. import config

log = logging.getLogger("elmariana.voice")

VOICES_DIR = config.DATA_DIR / "voices"
DEFAULT_VOICE = "es_MX-claude-high"   # alternativa más ligera: "es_MX-ald-medium"
HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

_lock = threading.Lock()
_loaded: dict[str, object] = {}


class VoiceUnavailable(RuntimeError):
    pass


def piper_available() -> bool:
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def voice_url(voice: str, suffix: str) -> str:
    """es_MX-claude-high -> es/es_MX/claude/high/es_MX-claude-high.onnx"""
    try:
        locale, name, quality = voice.split("-", 2)
    except ValueError:
        raise ValueError(f"Nombre de voz no válido: {voice}") from None
    family = locale.split("_")[0]
    return f"{HF_BASE}/{family}/{locale}/{name}/{quality}/{voice}{suffix}"


def ensure_voice(voice: str = DEFAULT_VOICE) -> Path:
    """Descarga el modelo si no está (modelo .onnx + configuración .onnx.json)."""
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    model = VOICES_DIR / f"{voice}.onnx"
    for suffix in (".onnx.json", ".onnx"):
        dst = VOICES_DIR / f"{voice}{suffix}"
        if dst.exists() and dst.stat().st_size > 0:
            continue
        url = voice_url(voice, suffix)
        log.info("Descargando voz %s …", dst.name)
        print(f"Descargando {dst.name} (solo la primera vez)…", flush=True)
        tmp = dst.with_suffix(dst.suffix + ".part")
        try:
            with urllib.request.urlopen(url, timeout=60) as resp, tmp.open("wb") as fh:
                while chunk := resp.read(1024 * 1024):
                    fh.write(chunk)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            raise VoiceUnavailable(f"No se pudo descargar la voz {voice}: {exc}") from exc
        tmp.replace(dst)
    return model


def _load(voice: str):
    try:
        from piper import PiperVoice
    except Exception as exc:
        raise VoiceUnavailable("Piper no está instalado. Ejecuta: pip install piper-tts") from exc
    with _lock:
        if voice not in _loaded:
            model = ensure_voice(voice)
            _loaded.clear()
            _loaded[voice] = PiperVoice.load(str(model))
        return _loaded[voice]


def synthesize(text: str, out_wav: str | Path, voice: str = DEFAULT_VOICE, speed: float = 1.1) -> Path:
    """Convierte `text` en un WAV. `speed` > 1 habla más rápido (ritmo de Shorts ≈ 1.1)."""
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    pv = _load(voice)
    length_scale = 1.0 / max(speed, 0.5)
    tmp = out_wav.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as wf:
        if hasattr(pv, "synthesize_wav"):          # piper-tts >= 1.3
            try:
                from piper import SynthesisConfig
                pv.synthesize_wav(text, wf, syn_config=SynthesisConfig(length_scale=length_scale))
            except ImportError:
                pv.synthesize_wav(text, wf)
        else:                                        # piper-tts 1.2
            pv.synthesize(text, wf, length_scale=length_scale)
    tmp.replace(out_wav)
    return out_wav


def wav_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


if __name__ == "__main__":
    texto = " ".join(sys.argv[1:]) or "Hola, soy la voz de ElMariana Clipping Studio."
    out = synthesize(texto, VOICES_DIR / "prueba.wav")
    print(f"Listo: {out} ({wav_duration(out):.1f} s)")
