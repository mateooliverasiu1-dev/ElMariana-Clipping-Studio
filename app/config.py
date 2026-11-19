"""Configuración central. Todo se puede sobrescribir con variables de entorno.

Valores por defecto pensados para GitHub Codespaces (2-4 CPU, 8 GB RAM, sin GPU).
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("ELMARIANA_DATA_DIR", BASE_DIR / "data")).resolve()
PROJECTS_DIR = DATA_DIR / "projects"
# Carpeta para importar videos copiados directamente al servidor (sin subirlos por el navegador).
INBOX_DIR = DATA_DIR / "entrada"
STATIC_DIR = BASE_DIR / "static"

# Formatos de entrada aceptados.
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv"}
MAX_UPLOAD_BYTES = int(os.environ.get("ELMARIANA_MAX_UPLOAD_MB", "4096")) * 1024 * 1024

# Faster-Whisper: modelos ligeros para CPU. "small" es el máximo recomendado con 8 GB.
WHISPER_MODELS = ("tiny", "base", "small")
WHISPER_DEFAULT_MODEL = os.environ.get("ELMARIANA_WHISPER_MODEL", "base")
WHISPER_COMPUTE_TYPE = os.environ.get("ELMARIANA_WHISPER_COMPUTE", "int8")
WHISPER_CPU_THREADS = int(os.environ.get("ELMARIANA_WHISPER_THREADS", str(os.cpu_count() or 2)))
LANGUAGES = ("auto", "es", "en")

# Detección de clips (recomendación de la skill shorts-video-editor: 20–60 s).
CLIP_MIN_SECONDS = float(os.environ.get("ELMARIANA_CLIP_MIN", "20"))
CLIP_MAX_SECONDS = float(os.environ.get("ELMARIANA_CLIP_MAX", "60"))
MAX_CANDIDATES = int(os.environ.get("ELMARIANA_MAX_CANDIDATES", "12"))

# Salida para YouTube Shorts.
OUT_WIDTH = 1080
OUT_HEIGHT = 1920
OUT_FPS = 30
OUT_CRF = int(os.environ.get("ELMARIANA_CRF", "20"))
OUT_PRESET = os.environ.get("ELMARIANA_X264_PRESET", "veryfast")
OUT_AUDIO_BITRATE = "192k"

# Fuente de subtítulos (DejaVu Sans viene con fonts-dejavu-core).
SUBTITLE_FONT = os.environ.get("ELMARIANA_SUB_FONT", "DejaVu Sans")

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE_BIN", "ffprobe")


def ensure_dirs() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
