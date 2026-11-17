"""Control de calidad del Short exportado (skill: youtube-quality-control).

Todo lo que se marca como verificado se mide de verdad sobre el archivo final con
FFprobe/FFmpeg. Lo que no se puede comprobar automáticamente (p. ej. ortografía)
se lista como revisión manual, nunca como aprobado.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import config
from .media import MediaError, probe, run
from .subtitles import check_safe_area
from .text import ends_sentence

_BLACK_RE = re.compile(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)")
_I_RE = re.compile(r"I:\s+(-?[0-9.]+|-inf) LUFS")
_LRA_RE = re.compile(r"LRA:\s+([0-9.]+) LU")
_MAX_RE = re.compile(r"max_volume:\s+(-?[0-9.]+|-inf) dB")
_MEAN_RE = re.compile(r"mean_volume:\s+(-?[0-9.]+|-inf) dB")


def _f(m: re.Match | None, default: float) -> float:
    if not m or m.group(1) == "-inf":
        return default
    return float(m.group(1))


def measure(path: Path) -> dict[str, Any]:
    """Una sola pasada: decodifica todo (detecta corrupción), negros, loudness y picos."""
    proc = run([config.FFMPEG, "-hide_banner", "-nostats", "-v", "info", "-i", str(path),
                "-vf", "blackdetect=d=0.3:pix_th=0.10",
                "-af", "ebur128=framelog=quiet,volumedetect", "-f", "null", "-"])
    err = proc.stderr
    blacks = [(float(a), float(b), float(c)) for a, b, c in _BLACK_RE.findall(err)]
    decode_errors = [ln for ln in err.splitlines()
                     if re.search(r"(error while decoding|corrupt|Invalid data)", ln, re.I)]
    return {
        "black_segments": blacks,
        "black_total": round(sum(b[2] for b in blacks), 2),
        "integrated_lufs": _f(_I_RE.search(err), -70.0),
        "lra": _f(_LRA_RE.search(err), 0.0),
        "max_volume_db": _f(_MAX_RE.search(err), -91.0),
        "mean_volume_db": _f(_MEAN_RE.search(err), -91.0),
        "decode_errors": decode_errors[:5],
    }


def check(output: Path, clip: dict[str, Any], report: dict[str, Any], rights_status: str,
          words: list[dict[str, Any]] | None = None, ass_file: Path | None = None) -> dict[str, Any]:
    problems: list[dict[str, str]] = []
    technical: list[str] = []
    editorial: list[str] = []
    manual: list[str] = []

    def err(area: str, msg: str, fix: str = "") -> None:
        problems.append({"level": "error", "area": area, "message": msg, "fix": fix})

    def warn(area: str, msg: str, fix: str = "") -> None:
        problems.append({"level": "warning", "area": area, "message": msg, "fix": fix})

    if not output.exists():
        err("técnico", "No existe el archivo exportado.", "Vuelve a exportar.")
        return _result(problems, technical, editorial, manual, {})

    # --- Formato ---
    try:
        info = probe(output)
    except MediaError as exc:
        err("técnico", f"El archivo no se puede leer: {exc}", "Vuelve a exportar.")
        return _result(problems, technical, editorial, manual, {})
    w, h = info["width"], info["height"]
    if (w, h) == (config.OUT_WIDTH, config.OUT_HEIGHT):
        technical.append(f"Resolución {w}x{h} (9:16) correcta.")
    elif h and abs(w / h - 9 / 16) < 0.01:
        warn("técnico", f"Proporción 9:16 pero resolución {w}x{h}.")
    else:
        err("técnico", f"Proporción incorrecta: {w}x{h}.", "Exporta en 1080x1920.")
    if info["video_codec"] != "h264" or info["pix_fmt"] != "yuv420p":
        err("técnico", f"Códec de video no recomendado: {info['video_codec']}/{info['pix_fmt']}.")
    if not info["has_audio"]:
        err("audio", "El Short no tiene audio.")
    dur = info["duration"]
    if dur < 5 or dur > 180:
        err("técnico", f"Duración no válida para Shorts: {dur:.1f} s.", "Ajusta inicio/fin (5–180 s).")
    elif not (20 <= dur <= 60):
        warn("editorial", f"Duración {dur:.1f} s fuera del rango recomendado de 20–60 s.")
    else:
        technical.append(f"Duración {dur:.1f} s dentro del rango recomendado.")

    # --- Decodificación, negros y audio ---
    m = measure(output)
    if m["decode_errors"]:
        err("técnico", "Errores de decodificación (posible corrupción).", "Vuelve a exportar.")
    else:
        technical.append("El video se decodifica completo sin errores.")
    if any(s < 0.5 for s, _, _ in m["black_segments"]):
        err("visual", "Empieza con pantalla negra: mata el gancho.", "Mueve el inicio del clip.")
    if m["black_total"] > 1.0:
        err("visual", f"{m['black_total']} s de fotogramas negros.", "Recorta las partes en negro.")
    elif m["black_total"] > 0:
        warn("visual", f"{m['black_total']} s de fotogramas negros.")
    else:
        technical.append("Sin fotogramas negros.")
    lufs = m["integrated_lufs"]
    if m["mean_volume_db"] < -40 or lufs < -30:
        err("audio", f"Audio casi inaudible ({lufs:.1f} LUFS).", "Revisa la pista de audio del original.")
    elif not (-18 <= lufs <= -10):
        warn("audio", f"Volumen integrado {lufs:.1f} LUFS (objetivo ≈ -14).")
    else:
        technical.append(f"Volumen integrado {lufs:.1f} LUFS (objetivo -14).")
    if m["max_volume_db"] >= -0.1:
        warn("audio", "Picos al límite: posible saturación/clipping.")
    if m["lra"] > 15:
        warn("audio", f"Rango de volumen amplio (LRA {m['lra']:.0f} LU): cambios bruscos de volumen.")
    manual.append("Escuchar la claridad de la voz y el nivel de música de fondo.")

    # --- Subtítulos ---
    opts = report.get("options", {})
    if opts.get("subtitles"):
        if not ass_file or not ass_file.exists() or report.get("subtitle_words", 0) == 0:
            err("subtítulos", "Se pidieron subtítulos pero no se generaron.",
                "Verifica que el clip tenga transcripción.")
        else:
            for issue in check_safe_area(ass_file.read_text(encoding="utf-8")):
                err("subtítulos", issue)
            technical.append(f"{report['subtitle_words']} palabras subtituladas, sincronizadas con Whisper "
                             "y dentro de márgenes seguros.")
            low = [x["w"] for x in (words or []) if x.get("p") is not None and x["p"] < 0.5]
            if low:
                warn("subtítulos", f"{len(low)} palabras con baja confianza de transcripción: "
                     + ", ".join(low[:8]), "Revísalas en el editor de subtítulos.")
            manual.append("Revisar ortografía y puntuación de los subtítulos (no se verifica automáticamente).")

    # --- Editorial ---
    if words:
        if words[0]["start"] > 1.5:
            warn("editorial", f"La primera palabra llega a los {words[0]['start']:.1f} s: gancho lento.",
                 "Mueve el inicio más cerca del primer diálogo.")
        else:
            editorial.append("El diálogo arranca en el primer segundo y medio (gancho rápido).")
        if not ends_sentence(words[-1]["w"]) and not clip.get("allow_open_ending"):
            warn("editorial", "El final podría cortar una frase.", "Extiende el final hasta que termine la idea.")
        else:
            editorial.append("El clip termina en una frase completa.")
    if clip.get("context_note"):
        warn("editorial", clip["context_note"])
    removed = report.get("removed_seconds", 0)
    original_len = float(clip["end"]) - float(clip["start"])
    if original_len and removed / original_len > 0.4:
        warn("editorial", f"Se recortó el {removed / original_len:.0%} del tramo: revisa que no cambie el sentido.")
    zooms = report.get("zooms", [])
    if dur and len(zooms) > dur / 4:
        warn("visual", "Demasiados zooms para la duración.")
    editorial.append(f"Encuadre '{report.get('layout')}', {len(zooms)} zoom(s), {report.get('cuts', 0)} corte(s).")
    manual.append("Ver el clip completo y confirmar que no se saca de contexto al hablante.")

    # --- Derechos ---
    if rights_status != "APPROVED":
        err("derechos", f"Estado de derechos: {rights_status}.", "Completa la declaración de derechos del proyecto.")
    else:
        technical.append("Derechos de uso declarados y aprobados.")

    return _result(problems, technical, editorial, manual, {**m, **{"probe": info}})


def _result(problems, technical, editorial, manual, metrics) -> dict[str, Any]:
    status = "FAIL" if any(p["level"] == "error" for p in problems) else "PASS"
    return {"status": status, "problems": problems, "technical_report": technical,
            "editorial_report": editorial, "manual_checks": manual,
            "required_corrections": [p["fix"] or p["message"] for p in problems if p["level"] == "error"],
            "metrics": metrics}
