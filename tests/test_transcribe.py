"""Prueba real de Faster-Whisper (descarga el modelo 'tiny', ~75 MB, gratis desde Hugging Face).

Solo se ejecuta con RUN_WHISPER_TEST=1 para no descargar modelos sin querer.
Si existe `espeak-ng`, genera una voz sintética en español y verifica que se transcriba.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("RUN_WHISPER_TEST") != "1",
                                reason="Activa con RUN_WHISPER_TEST=1")


def test_whisper_word_timestamps(tmp_path):
    pytest.importorskip("faster_whisper")
    from app.services import media, transcribe

    wav = tmp_path / "voz.wav"
    if shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-v", "es", "-w", str(tmp_path / "raw.wav"),
                        "Hola chat, bienvenidos al stream. No puede ser, qué susto."], check=True)
        media.extract_audio(tmp_path / "raw.wav", wav)
        expect_words = True
    else:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=300:d=5",
                        "-ac", "1", "-ar", "16000", str(wav)], check=True)
        expect_words = False

    tr = transcribe.transcribe(wav, language="es", model_size="tiny")
    assert "segments" in tr and tr["model"] == "tiny"
    words = transcribe.all_words(tr)
    if expect_words:
        assert words, "debería reconocer palabras"
        assert all(w["end"] >= w["start"] for w in words)
