"""Subtítulos dinámicos palabra por palabra en formato ASS (libass, vía FFmpeg).

* Se agrupan 1–3 palabras por "golpe" de pantalla (ritmo de Shorts).
* La palabra que se está diciendo se muestra en amarillo con un pequeño "pop".
* Las palabras importantes se pintan en verde de forma consistente.
* Márgenes seguros: el texto queda por encima de la zona de la interfaz de Shorts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import config
from .text import is_important_word, keywords

# Colores ASS en formato &HAABBGGRR
COLOR_TEXT = "&H00FFFFFF"
COLOR_CURRENT = "&H0000E5FF"    # amarillo cálido
COLOR_IMPORTANT = "&H007AF03C"  # verde
COLOR_OUTLINE = "&H00000000"

SAFE_MARGIN_V = 560   # px desde abajo (Shorts tapa ~25 % inferior con UI)
SAFE_MARGIN_H = 100
FONT_SIZE = 82
MAX_WORDS = 3
MAX_CHARS = 18


def _ts(t: float) -> str:
    t = max(t, 0.0)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def mark_important(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rellena `hl` cuando no fue decidido manualmente en el editor."""
    kw = set(keywords([" ".join(w["w"] for w in words)], top=5))
    for w in words:
        if w.get("hl") is None:
            w["hl"] = is_important_word(w["w"], kw)
    return words


def chunk_words(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    for w in words:
        if cur:
            chars = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
            gap = w["start"] - cur[-1]["end"]
            if (len(cur) >= MAX_WORDS or chars > MAX_CHARS or gap > 0.45
                    or cur[-1]["w"].rstrip().endswith((".", "!", "?", ",", "…"))):
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(words: list[dict[str, Any]], width: int = config.OUT_WIDTH, height: int = config.OUT_HEIGHT,
              font: str = config.SUBTITLE_FONT) -> str:
    """`words`: [{w, start, end, hl}] con tiempos ya relativos al clip editado."""
    words = [w for w in words if w.get("w", "").strip()]
    mark_important(words)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{font},{FONT_SIZE},{COLOR_TEXT},{COLOR_TEXT},{COLOR_OUTLINE},&H80000000,-1,0,0,0,100,100,1,0,1,7,3,2,{SAFE_MARGIN_H},{SAFE_MARGIN_H},{SAFE_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    chunks = chunk_words(words)
    for ci, chunk in enumerate(chunks):
        next_start = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else None
        chunk_end = chunk[-1]["end"] + 0.25
        if next_start is not None:
            chunk_end = min(chunk_end, next_start)
        for wi, w in enumerate(chunk):
            ev_start = w["start"]
            ev_end = chunk[wi + 1]["start"] if wi + 1 < len(chunk) else chunk_end
            if ev_end - ev_start < 0.05:
                ev_end = ev_start + 0.05
            parts = []
            for k, other in enumerate(chunk):
                word = _esc(other["w"].strip().upper())
                if k == wi:
                    parts.append("{\\c" + COLOR_CURRENT + "&\\fscx112\\fscy112"
                                 "\\t(0,90,\\fscx118\\fscy118)\\t(90,180,\\fscx112\\fscy112)}" + word +
                                 "{\\r}")
                elif other.get("hl"):
                    parts.append("{\\c" + COLOR_IMPORTANT + "&}" + word + "{\\r}")
                else:
                    parts.append(word)
            lines.append(f"Dialogue: 0,{_ts(ev_start)},{_ts(ev_end)},Word,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(lines) + "\n"


def build_srt(words: list[dict[str, Any]]) -> str:
    out = []
    for i, chunk in enumerate(chunk_words([w for w in words if w.get("w", "").strip()]), 1):
        def f(t: float) -> str:
            ms = int(round(max(t, 0) * 1000))
            return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
        out.append(f"{i}\n{f(chunk[0]['start'])} --> {f(chunk[-1]['end'])}\n"
                   f"{' '.join(w['w'].strip() for w in chunk)}\n")
    return "\n".join(out)


def write_ass(words: list[dict[str, Any]], path: str | Path) -> Path:
    path = Path(path)
    path.write_text(build_ass(words), encoding="utf-8")
    return path


def check_safe_area(ass_text: str) -> list[str]:
    """Verifica márgenes seguros declarados en el estilo (para el control de calidad)."""
    issues = []
    for line in ass_text.splitlines():
        if line.startswith("Style: Word,"):
            fields = line.split(",")
            margin_l, margin_r, margin_v = int(fields[-4]), int(fields[-3]), int(fields[-2])
            if margin_v < 400:
                issues.append("Subtítulos demasiado abajo: los taparía la interfaz de Shorts.")
            if min(margin_l, margin_r) < 60:
                issues.append("Márgenes laterales de subtítulos demasiado pequeños.")
    return issues
