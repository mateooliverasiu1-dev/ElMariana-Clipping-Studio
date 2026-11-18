"""Portadas verticales 1080x1920 para cada clip (miniatura del Short).

1. Elige el fotograma: candidatos en reacciones del diálogo, picos de audio y puntos
   repartidos del clip; con OpenCV se prefiere el más nítido y con cara visible.
2. Lo encuadra igual que el Short (recorte al hablante o fondo desenfocado).
3. Añade el título en grande con una palabra clave resaltada, en la zona segura central.

Salida: JPG < 2 MB (límite de YouTube para miniaturas).
"""
from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

from .. import config
from . import framing
from .media import run
from .text import is_important_word, keywords, reaction_hits

log = logging.getLogger("elmariana.cover")

COVER_W, COVER_H = config.OUT_WIDTH, config.OUT_HEIGHT
MAX_BYTES = 2 * 1024 * 1024
YELLOW = "&H0000E5FF"
MAX_LINE_CHARS = 15
MAX_LINES = 4


def clean_text(text: str) -> str:
    """Quita emojis y símbolos que la fuente no puede dibujar."""
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if ord(ch) > 0xFFFF or cat in ("So", "Sk", "Cs", "Co") or ch in "️‍":
            continue
        out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def default_cover_text(title: str) -> str:
    """Para la portada basta la frase: si el título trae una cita “…”, se usa solo la cita."""
    m = re.search(r"[“\"]([^”\"]{4,})[”\"]", title)
    return clean_text(m.group(1) if m else title)


def wrap_lines(text: str, width: int = MAX_LINE_CHARS, max_lines: int = MAX_LINES) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    return lines


def _font_size(lines: list[str]) -> int:
    longest = max((len(l) for l in lines), default=1)
    return int(max(84, min(132, 1500 / max(longest, 8) * 1.0)))


def build_cover_ass(text: str, font: str = config.SUBTITLE_FONT) -> str:
    """Un evento ASS con el título centrado; la palabra más importante va en amarillo."""
    original = clean_text(text)
    # La palabra a resaltar se decide con el texto original (en mayúsculas todo parecería importante).
    orig_words = original.split()
    kw = set(keywords([original], top=3))
    hl_idx = next((i for i, w in enumerate(orig_words) if reaction_hits(w) > 0), None)
    if hl_idx is None:
        important = [i for i, w in enumerate(orig_words) if is_important_word(w, kw)]
        hl_idx = max(important, key=lambda i: len(orig_words[i].strip(".,;:¡!¿?\"'…"))) if important else None
    lines = wrap_lines(original.upper()) or [""]

    rendered, idx = [], 0
    for line in lines:
        parts = []
        for w in line.split():
            safe = w.replace("{", "(").replace("}", ")").replace("\\", "")
            parts.append("{\\c" + YELLOW + "&}" + safe + "{\\c&H00FFFFFF&}" if idx == hl_idx else safe)
            idx += 1
        rendered.append(" ".join(parts))
    size = _font_size(lines)
    # Centro algo por encima de la mitad: visible en el feed y lejos de la interfaz inferior.
    y = int(COVER_H * 0.40)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {COVER_W}
PlayResY: {COVER_H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cover,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,11,6,5,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Cover,,0,0,0,,{{\\pos({COVER_W // 2},{y})}}{"\\N".join(rendered)}
"""


def candidate_times(clip: dict[str, Any], words: list[dict[str, Any]], energy: dict[str, Any] | None) -> list[tuple[float, float]]:
    """(tiempo, prioridad) dentro del clip, evitando el primer y último medio segundo."""
    start, end = float(clip["start"]), float(clip["end"])
    lo, hi = start + 0.5, end - 0.5
    cands: list[tuple[float, float]] = []
    for w in words:
        if lo <= w["start"] <= hi and reaction_hits(w["w"]) > 0:
            cands.append((min(w["start"] + 0.25, hi), 1.0))  # cara durante la reacción
    if energy and energy.get("db"):
        hop = energy["hop"]
        idx = [i for i in range(int(lo / hop), int(hi / hop)) if i < len(energy["db"])]
        idx.sort(key=lambda i: energy["db"][i], reverse=True)
        cands += [(i * hop + hop / 2, 0.8) for i in idx[:2]]
    span = max(hi - lo, 0.1)
    cands += [(lo + span * f, 0.3) for f in (0.2, 0.4, 0.6, 0.8)]
    seen: list[tuple[float, float]] = []
    for t, p in sorted(cands, key=lambda c: -c[1]):
        if all(abs(t - s) > 0.8 for s, _ in seen):
            seen.append((round(t, 2), p))
    return seen[:8]


def pick_frame_time(src: str | Path, cands: list[tuple[float, float]]) -> tuple[float, str]:
    """Con OpenCV: nitidez (varianza del Laplaciano) + cara + prioridad. Sin OpenCV: mayor prioridad."""
    if not cands:
        return 0.0, "inicio"
    best_t, best_reason = cands[0][0], "momento de reacción" if cands[0][1] >= 1 else "momento destacado"
    try:
        import cv2
        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            return best_t, best_reason
        cascade = None
        if framing.opencv_status() == "ok":
            cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
        scored = []
        try:
            for t, prio in cands:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                h, w = frame.shape[:2]
                small = cv2.resize(frame, (480, int(h * 480 / w))) if w > 480 else frame
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                bright = float(gray.mean())
                face = 0
                if cascade is not None and not cascade.empty():
                    face = len(cascade.detectMultiScale(gray, 1.1, 5, minSize=(max(24, small.shape[1] // 20),) * 2))
                scored.append((t, prio, sharp, bright, face))
        finally:
            cap.release()
        if not scored:
            return best_t, best_reason
        max_sharp = max(s[2] for s in scored) or 1.0
        def total(s):
            t, prio, sharp, bright, face = s
            dark_penalty = 0.6 if bright < 35 else 0.0  # evita fotogramas negros
            return 0.45 * (sharp / max_sharp) + 0.35 * prio + (0.35 if face else 0) - dark_penalty
        t, prio, _, _, face = max(scored, key=total)
        reason = ("reacción" if prio >= 1 else "pico de audio" if prio >= 0.8 else "fotograma nítido")
        return t, reason + (" con cara visible" if face else "")
    except Exception as exc:  # OpenCV incompleto: se usa la prioridad
        log.info("Selección de fotograma sin OpenCV (%s)", exc)
        return best_t, best_reason


def _ass_path(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def generate_cover(src: Path, info: dict[str, Any], clip: dict[str, Any], words: list[dict[str, Any]],
                   energy: dict[str, Any] | None, out_dir: Path, text: str | None = None,
                   at: float | None = None, layout: str = "auto") -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if at is None:
        at, reason = pick_frame_time(src, candidate_times(clip, words, energy))
    else:
        at = min(max(float(at), 0.0), max(info.get("duration", at) - 0.1, 0.0))
        reason = "elegido a mano"
    subject = framing.detect_subject(src, max(at - 2, 0), at + 2, samples=4)
    resolved = framing.resolve_layout(layout, info, subject)
    title = text if text is not None else default_cover_text(clip.get("title", ""))
    ass_file = out_dir / f"{clip['id']}.cover.ass"
    ass_file.write_text(build_cover_ass(title), encoding="utf-8")
    out = out_dir / f"{clip['id']}.cover.jpg"

    graph = (framing.layout_filter(resolved, info, subject["center_x"], COVER_W, COVER_H, "0:v", "base")
             + ";[base]eq=contrast=1.08:saturation=1.18:brightness=0.02,"
             # Banda oscura suave detrás del título para que se lea sobre cualquier fondo.
             + f"drawbox=x=0:y={int(COVER_H * 0.25)}:w={COVER_W}:h={int(COVER_H * 0.30)}:color=black@0.30:t=fill,"
             + f"ass='{_ass_path(ass_file)}',format=yuvj420p[out]")
    for q in (2, 4, 6, 9):
        run([config.FFMPEG, "-y", "-v", "error", "-ss", f"{at:.3f}", "-i", str(src), "-frames:v", "1",
             "-filter_complex", graph, "-map", "[out]", "-q:v", str(q), str(out)])
        if out.stat().st_size <= MAX_BYTES:
            break
    return {"file": out.name, "at": round(at, 2), "reason": reason, "text": title, "layout": resolved,
            "width": COVER_W, "height": COVER_H, "size_bytes": out.stat().st_size}
