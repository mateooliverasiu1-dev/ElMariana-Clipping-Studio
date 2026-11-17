"""Análisis y conversión de medios con FFmpeg/FFprobe."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .. import config


class MediaError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which(config.FFMPEG) is not None and shutil.which(config.FFPROBE) is not None


def run(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    """Ejecuta un comando y lanza MediaError con el final de stderr si falla."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise MediaError(f"No se encontró el ejecutable: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"Tiempo agotado ejecutando {cmd[0]}") from exc
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise MediaError(f"{Path(cmd[0]).name} falló (código {proc.returncode}): {tail}")
    return proc


def _ratio(value: str | None) -> float:
    if not value or value in ("0/0", "N/A"):
        return 0.0
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            return float(num) / float(den) if float(den) else 0.0
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def probe(path: str | Path) -> dict[str, Any]:
    """Devuelve duración, resolución, fps, códecs y datos de audio del archivo."""
    proc = run([
        config.FFPROBE, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ], timeout=120)
    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError("FFprobe devolvió una respuesta ilegible") from exc

    streams = info.get("streams", [])
    fmt = info.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width = int(video.get("width", 0)) if video else 0
    height = int(video.get("height", 0)) if video else 0
    rotation = 0
    if video:
        for sd in video.get("side_data_list", []) or []:
            if "rotation" in sd:
                rotation = int(sd["rotation"])
        rotation = int(video.get("tags", {}).get("rotate", rotation) or rotation)
    if abs(rotation) in (90, 270):
        width, height = height, width

    duration = _ratio(fmt.get("duration")) or (_ratio(video.get("duration")) if video else 0.0)
    result = {
        "duration": round(duration, 3),
        "format_name": fmt.get("format_name", ""),
        "size_bytes": int(fmt.get("size", 0) or 0),
        "bit_rate": int(fmt.get("bit_rate", 0) or 0),
        "has_video": video is not None,
        "has_audio": audio is not None,
        "width": width,
        "height": height,
        "rotation": rotation,
        "fps": round(_ratio(video.get("avg_frame_rate") or video.get("r_frame_rate")) if video else 0.0, 3),
        "video_codec": video.get("codec_name", "") if video else "",
        "pix_fmt": video.get("pix_fmt", "") if video else "",
        "audio_codec": audio.get("codec_name", "") if audio else "",
        "audio_channels": int(audio.get("channels", 0)) if audio else 0,
        "audio_sample_rate": int(audio.get("sample_rate", 0) or 0) if audio else 0,
    }
    result["aspect"] = round(width / height, 4) if height else 0.0
    result["orientation"] = (
        "vertical" if height > width else "horizontal" if width > height else "cuadrado"
    )
    return result


def validate_source(info: dict[str, Any]) -> list[str]:
    """Errores que impiden procesar el video."""
    errors = []
    if not info.get("has_video"):
        errors.append("El archivo no contiene pista de video.")
    if not info.get("has_audio"):
        errors.append("El archivo no contiene pista de audio (necesaria para transcribir).")
    if info.get("duration", 0) < 5:
        errors.append("El video dura menos de 5 segundos.")
    return errors


def extract_audio(src: str | Path, dst: str | Path) -> Path:
    """Audio WAV 16 kHz mono (formato que espera Whisper)."""
    dst = Path(dst)
    run([config.FFMPEG, "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(dst)])
    return dst


def browser_playable(info: dict[str, Any], src: str | Path) -> bool:
    ext = Path(src).suffix.lower()
    return (ext in (".mp4", ".mov") and info.get("video_codec") == "h264"
            and info.get("audio_codec") in ("aac", "mp3") and info.get("pix_fmt") in ("yuv420p", "yuvj420p"))


def make_preview(src: str | Path, dst: str | Path) -> Path:
    """Proxy ligero (540p, H.264 ultrafast) para vista previa en el navegador."""
    dst = Path(dst)
    run([config.FFMPEG, "-y", "-v", "error", "-i", str(src),
         "-vf", "scale=-2:'min(540,ih)'", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst)])
    return dst


def thumbnail(src: str | Path, dst: str | Path, at: float) -> Path:
    dst = Path(dst)
    run([config.FFMPEG, "-y", "-v", "error", "-ss", f"{max(at, 0):.3f}", "-i", str(src),
         "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "4", str(dst)])
    return dst
