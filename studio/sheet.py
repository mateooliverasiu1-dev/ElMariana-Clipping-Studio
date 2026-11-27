"""Hoja de contacto: captura fotogramas del video final para revisar la edición.

Uso:
    python -m studio.sheet output/video.mp4 [--every 1.0] [--times 1.2,3.4] [--cols 6]
Guarda output/<nombre>_sheet.jpg
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .transcribe import probe


def grab(video: Path, t: float, w: int) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-vf", f"scale={w}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def sheet(video: Path, every=1.0, times=None, cols=6, w=270) -> Path:
    dur = probe(video)["duration"]
    ts = times or list(np.arange(0.2, dur, every))
    tiles = []
    for t in ts:
        img = grab(video, t, w)
        if img is None:
            continue
        cv2.putText(img, f"{t:.1f}s", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(img, f"{t:.1f}s", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        tiles.append(img)
    h = tiles[0].shape[0]
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    out = video.with_name(video.stem + "_sheet.jpg")
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--every", type=float, default=1.0)
    ap.add_argument("--times", type=str)
    ap.add_argument("--cols", type=int, default=6)
    a = ap.parse_args()
    sheet(a.video, a.every, [float(x) for x in a.times.split(",")] if a.times else None, a.cols)
