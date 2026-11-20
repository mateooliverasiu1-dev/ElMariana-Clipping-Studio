"""Voz sintética local y gratuita (CPU, sin servicios de pago). Dos motores:

* Piper  (voces como "es_MX-claude-high"): ligero, acento mexicano.
* Kokoro (voces como "kokoro:em_alex", "kokoro:ef_dora", "kokoro:em_santa"):
  más natural. Modelo Apache 2.0 vía kokoro-onnx (sin PyTorch).

La primera vez se descargan los modelos a data/voices/; después funciona sin internet.

Uso rápido desde la terminal:
    python -m app.services.voice "Hola, esto es una prueba"                 -> voz por defecto
    python -m app.services.voice --voz kokoro:em_alex "Hola, esto es una prueba"
    python -m app.services.voice --comparar "Hola, esto es una prueba"      -> un WAV por voz
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

# Kokoro v1.0 en ONNX (thewh1teagle/kokoro-onnx). Voces en español: ef_dora, em_alex, em_santa.
KOKORO_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
KOKORO_SPANISH = ("em_alex", "ef_dora", "em_santa")
# "es-419" = español latinoamericano en espeak-ng (seseo: "cielo" sin la z española).
KOKORO_LANGS = ("es-419", "es")
COMPARE_VOICES = ("es_MX-claude-high", "kokoro:em_alex", "kokoro:ef_dora", "kokoro:em_santa")

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


def _download(url: str, dst: Path) -> None:
    if dst.exists() and dst.stat().st_size > 0:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"Descargando {dst.name} (solo la primera vez)…", flush=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, tmp.open("wb") as fh:
            while chunk := resp.read(1024 * 1024):
                fh.write(chunk)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise VoiceUnavailable(f"No se pudo descargar {dst.name}: {exc}") from exc
    tmp.replace(dst)


def is_kokoro(voice: str) -> bool:
    return voice.startswith("kokoro:")


def kokoro_available() -> bool:
    try:
        import kokoro_onnx  # noqa: F401
        return True
    except Exception:
        return False


def ensure_kokoro() -> tuple[Path, Path]:
    d = VOICES_DIR / "kokoro"
    for name in KOKORO_FILES:
        _download(f"{KOKORO_RELEASE}/{name}", d / name)
    return d / KOKORO_FILES[0], d / KOKORO_FILES[1]


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
    if is_kokoro(voice):
        return _synthesize_kokoro(text, out_wav, voice.split(":", 1)[1], speed)
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


def _load_kokoro():
    try:
        from kokoro_onnx import Kokoro
    except Exception as exc:
        raise VoiceUnavailable("Kokoro no está instalado. Ejecuta: pip install kokoro-onnx") from exc
    with _lock:
        if "kokoro" not in _loaded:
            model, voices = ensure_kokoro()
            _loaded.clear()
            _loaded["kokoro"] = Kokoro(str(model), str(voices))
        return _loaded["kokoro"]


def _synthesize_kokoro(text: str, out_wav: Path, name: str, speed: float) -> Path:
    import numpy as np
    k = _load_kokoro()
    last_exc: Exception | None = None
    for lang in KOKORO_LANGS:  # primero acento latinoamericano; si no se admite, español general
        try:
            samples, rate = k.create(text, voice=name, speed=speed, lang=lang)
            break
        except Exception as exc:  # idioma o voz no admitidos
            last_exc = exc
    else:
        raise VoiceUnavailable(f"Kokoro no pudo generar la voz '{name}': {last_exc}")
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
    tmp = out_wav.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(rate))
        wf.writeframes(pcm.tobytes())
    tmp.replace(out_wav)
    return out_wav


def engine_available(voice: str) -> bool:
    return kokoro_available() if is_kokoro(voice) else piper_available()


def wav_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Prueba de voces (Piper y Kokoro)")
    ap.add_argument("texto", nargs="*")
    ap.add_argument("--voz", default=DEFAULT_VOICE)
    ap.add_argument("--comparar", action="store_true", help="genera un WAV con cada voz disponible")
    a = ap.parse_args()
    texto = " ".join(a.texto) or "Hola, soy la voz de ElMariana Clipping Studio. ¿Por qué el cielo es azul?"
    voces = COMPARE_VOICES if a.comparar else (a.voz,)
    for v in voces:
        if not engine_available(v):
            print(f"- {v}: motor no instalado ({'pip install kokoro-onnx' if is_kokoro(v) else 'pip install piper-tts'})")
            continue
        out = VOICES_DIR / f"prueba_{v.replace(':', '_')}.wav"
        try:
            synthesize(texto, out, voice=v)
            print(f"- {v}: {out} ({wav_duration(out):.1f} s)")
        except VoiceUnavailable as exc:
            print(f"- {v}: {exc}")
