"""Señales no textuales: energía de audio (reacciones, gritos, risas) y cambios de escena."""
from __future__ import annotations

import re
import wave
from pathlib import Path
from typing import Any

import numpy as np

from .. import config
from .media import run

HOP_SECONDS = 0.5


def audio_energy(wav_path: str | Path, hop: float = HOP_SECONDS) -> dict[str, Any]:
    """RMS en dBFS por ventana de `hop` segundos, leyendo el WAV por bloques (poca RAM)."""
    with wave.open(str(wav_path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise ValueError("Se esperaba audio PCM de 16 bits")
        sr = wf.getframerate()
        ch = wf.getnchannels()
        hop_frames = max(int(sr * hop), 1)
        values: list[float] = []
        while True:
            raw = wf.readframes(hop_frames)
            if not raw:
                break
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            if ch > 1:
                x = x.reshape(-1, ch).mean(axis=1)
            rms = float(np.sqrt(np.mean(np.square(x / 32768.0)))) if x.size else 0.0
            values.append(20 * np.log10(max(rms, 1e-5)))
    db = np.array(values, dtype=np.float32)
    return {"hop": hop, "db": [round(float(v), 2) for v in db],
            "median": round(float(np.median(db)) if db.size else -60.0, 2),
            "p90": round(float(np.percentile(db, 90)) if db.size else -60.0, 2)}


_PTS_RE = re.compile(r"pts_time:([0-9.]+)")


def scene_changes(src: str | Path, threshold: float = 0.32, analysis_fps: int = 4) -> list[float]:
    """Instantes con cambio de escena. Se analiza a baja resolución y pocos fps para ahorrar CPU."""
    proc = run([
        config.FFMPEG, "-hide_banner", "-nostats", "-i", str(src), "-an", "-sn",
        "-vf", f"fps={analysis_fps},scale=160:-2,select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ])
    times = sorted({round(float(m), 2) for m in _PTS_RE.findall(proc.stderr)})
    return times


def window_energy(energy: dict[str, Any], start: float, end: float) -> np.ndarray:
    hop = energy["hop"]
    db = energy["db"]
    i0, i1 = int(start / hop), max(int(end / hop), int(start / hop) + 1)
    return np.array(db[i0:i1] or [energy.get("median", -60.0)], dtype=np.float32)
