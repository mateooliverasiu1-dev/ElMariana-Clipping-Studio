"""Fixtures comunes: video sintético generado con FFmpeg y transcripción simulada."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

LINES = [
    "Hola chat, bienvenidos al stream de hoy.", "Hoy vamos a probar el nuevo mapa.",
    "Miren esto, está muy raro.", "Creo que por aquí hay algo escondido.",
    "Espera, espera, ¿qué fue eso?", "¡No manches, jajaja, qué susto!",
    "No puede ser, me muero de risa.", "Bueno, sigamos con la partida.",
    "Vamos a revisar el inventario.", "Aquí tengo unas pociones y una espada.",
    "¿Ustedes qué harían en mi lugar?", "Escriban en el chat.",
]


def fake_transcript(duration: float = 60.0) -> dict:
    """Transcripción determinista con marcas por palabra (sustituye a Whisper en pruebas)."""
    segs, t, k = [], 1.0, 0
    while t < duration - 4:
        text = LINES[k % len(LINES)]
        words, tt = [], t
        for w in text.split():
            words.append({"w": w, "start": round(tt, 2), "end": round(tt + 0.32, 2), "p": 0.9})
            tt += 0.42
        segs.append({"start": t, "end": round(tt, 2), "text": text, "words": words})
        t = tt + (1.6 if k % 4 == 3 else 0.35)
        k += 1
    return {"language": "es", "language_probability": 0.99, "model": "fake", "segments": segs}


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory) -> Path:
    """Video 1280x720 de 60 s con un pico de audio a los 28–30 s."""
    out = tmp_path_factory.mktemp("media") / "sample.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=60",
        "-f", "lavfi", "-i", "sine=f=200:d=60",
        "-af", "volume='if(between(t,28,30),3.0,0.2)':eval=frame",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(out),
    ], check=True)
    return out


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    config.ensure_dirs()
    return tmp_path


APPROVED_RIGHTS = {
    "source_description": "Stream propio de prueba", "rights_holder": "ElMariana", "creator_name": "ElMariana",
    "permission_type": "own", "evidence": "Contenido propio", "third_party_music": "no",
    "third_party_footage": "no", "confirmed": True,
}
