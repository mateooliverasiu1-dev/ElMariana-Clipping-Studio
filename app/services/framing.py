"""Encuadre vertical: detecta caras con OpenCV (Haar, ligero en CPU) para centrar el recorte 9:16.

Modos de composición:
  * crop: recorta 9:16 centrado en el hablante (o en el centro si no hay cara).
  * fit:  video completo centrado sobre un fondo desenfocado (útil para gameplay).
  * auto: crop si se detecta una cara de forma consistente, si no fit.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("elmariana.framing")

LAYOUTS = ("auto", "crop", "fit")


def detect_subject(src: str | Path, start: float, end: float, samples: int = 8) -> dict[str, Any]:
    """Devuelve {'face_found', 'center_x' (0–1), 'hits', 'samples', 'detector'}; nunca lanza excepción.

    Si OpenCV falta o está incompleto, se usa encuadre centrado y el render continúa.
    """
    result: dict[str, Any] = {"face_found": False, "center_x": 0.5, "hits": 0, "samples": 0, "detector": "opencv"}
    try:
        return _detect(src, start, end, samples, result)
    except Exception as exc:  # OpenCV roto, video ilegible, etc.
        log.warning("Detección de caras no disponible (%s); se usa encuadre centrado", exc)
        return {"face_found": False, "center_x": 0.5, "hits": 0, "samples": 0,
                "detector": f"no disponible: {exc}"}


def _detect(src: str | Path, start: float, end: float, samples: int, result: dict[str, Any]) -> dict[str, Any]:
    import cv2
    if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data"):
        raise RuntimeError("la instalación de OpenCV está incompleta (instala opencv-python-headless<5: OpenCV 5 quitó CascadeClassifier)")
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    if not cascade_path.exists():
        raise RuntimeError("falta el modelo haarcascade de OpenCV")
    cascade = cv2.CascadeClassifier(str(cascade_path))
    if cascade.empty():
        return result
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        return result
    centers: list[float] = []
    try:
        span = max(end - start, 0.1)
        for k in range(samples):
            t = start + span * (k + 0.5) / samples
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            result["samples"] += 1
            h, w = frame.shape[:2]
            scale = 480 / w if w > 480 else 1.0
            small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale != 1.0 else frame
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                             minSize=(max(24, small.shape[1] // 20),) * 2)
            if len(faces):
                x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])  # la cara más grande
                centers.append((x + fw / 2) / small.shape[1])
    finally:
        cap.release()
    result["hits"] = len(centers)
    if centers and len(centers) >= max(2, result["samples"] // 3):
        result["face_found"] = True
        # Mediana: encuadre estable, sin saltos.
        centers.sort()
        result["center_x"] = round(centers[len(centers) // 2], 3)
    return result


def opencv_status() -> str:
    """'ok' o el motivo por el que la detección de caras no está disponible."""
    try:
        import cv2
        if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data"):
            return "instalación incompleta"
        if not (Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml").exists():
            return "falta el modelo de caras"
        return "ok"
    except Exception as exc:
        return f"no disponible ({exc.__class__.__name__})"


def resolve_layout(requested: str, info: dict[str, Any], subject: dict[str, Any]) -> str:
    if requested not in LAYOUTS:
        requested = "auto"
    if info.get("aspect", 1) <= 0.6:  # ya es vertical
        return "fit"
    if requested == "auto":
        return "crop" if subject.get("face_found") else "fit"
    return requested


def layout_filter(layout: str, info: dict[str, Any], center_x: float, out_w: int, out_h: int,
                  inp: str, out: str) -> str:
    """Cadena de filtros FFmpeg que convierte `inp` en un lienzo out_w x out_h etiquetado `out`."""
    if layout == "crop":
        # Ancho de recorte 9:16 a partir de la altura; x centrada en el sujeto y limitada al cuadro.
        cw = f"trunc(ih*{out_w}/{out_h}/2)*2"
        x = f"min(max(iw*{center_x:.4f}-({cw})/2\\,0)\\,iw-({cw}))"
        return (f"[{inp}]crop=w={cw}:h=ih:x={x}:y=0,scale={out_w}:{out_h}:flags=lanczos,"
                f"setsar=1[{out}]")
    # fit: fondo desenfocado + video completo encima.
    return (f"[{inp}]split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={out_w // 4}:{out_h // 4}:force_original_aspect_ratio=increase,"
            f"crop={out_w // 4}:{out_h // 4},boxblur=10:2,scale={out_w}:{out_h},eq=brightness=-0.08[bg];"
            f"[fgsrc]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:flags=lanczos,setsar=1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[{out}]")
