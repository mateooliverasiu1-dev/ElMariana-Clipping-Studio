"""Edición automática y exportación de Shorts (skill: shorts-video-editor).

Pipeline por clip:
  1. Cortes dinámicos: elimina pausas largas entre palabras (sin alterar el orden ni el sentido).
  2. Encuadre 9:16 (recorte centrado en la cara o fondo desenfocado).
  3. Zooms suaves en reacciones/picos de audio (máx. 1 cada 4 s, intensidad moderada).
  4. Subtítulos ASS palabra por palabra quemados en el video.
  5. Audio normalizado a -14 LUFS (referencia de YouTube) y exportación H.264/AAC 1080x1920.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from .. import config
from . import framing, subtitles
from .media import MediaError
from .text import reaction_hits

ZOOM_LEVELS = {"off": 0.0, "suave": 0.07, "normal": 0.12}
PAUSE_THRESHOLD = 0.6   # pausas más largas que esto se acortan
PAUSE_KEEP = 0.15       # aire que se conserva a cada lado del corte
MIN_ZOOM_SPACING = 4.0


def clip_words(transcript_words: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    """Palabras del clip (copias) con tiempos absolutos del video original."""
    return [dict(w, hl=w.get("hl")) for w in transcript_words
            if w["end"] > start and w["start"] < end and w.get("w", "").strip()]


def keep_intervals(words: list[dict[str, Any]], start: float, end: float, remove_pauses: bool) -> list[tuple[float, float]]:
    """Intervalos del original que se conservan (tiempos absolutos)."""
    if not remove_pauses or not words:
        return [(start, end)]
    intervals: list[tuple[float, float]] = []
    cur_s = start
    prev_end = start
    first = True
    for w in words:
        ws = max(w["start"], start)
        if ws - prev_end > PAUSE_THRESHOLD:
            if not first:
                intervals.append((cur_s, prev_end + PAUSE_KEEP))
            cur_s = ws - PAUSE_KEEP
        first = False
        prev_end = max(prev_end, min(w["end"], end))
    if end - prev_end > PAUSE_THRESHOLD:
        intervals.append((cur_s, prev_end + PAUSE_KEEP))
    else:
        intervals.append((cur_s, end))
    return [(round(a, 3), round(b, 3)) for a, b in intervals if b - a > 0.05]


def remap(t: float, intervals: list[tuple[float, float]]) -> float | None:
    """Tiempo original -> tiempo en el clip editado (None si cae en un hueco recortado)."""
    acc = 0.0
    for a, b in intervals:
        if t < a:
            return None
        if t <= b:
            return acc + (t - a)
        acc += b - a
    return None


def remap_words(words: list[dict[str, Any]], intervals: list[tuple[float, float]]) -> list[dict[str, Any]]:
    out = []
    for w in words:
        s = remap(w["start"], intervals)
        e = remap(w["end"], intervals)
        if s is None and e is None:
            continue
        if s is None:
            s = max((e or 0) - 0.2, 0)
        if e is None:
            e = s + max(w["end"] - w["start"], 0.1)
        out.append(dict(w, start=round(s, 3), end=round(e, 3)))
    return out


def zoom_events(words: list[dict[str, Any]], energy: dict[str, Any] | None, intervals: list[tuple[float, float]],
                total: float) -> list[tuple[float, float]]:
    """Momentos de énfasis (tiempos ya editados): reacciones del texto y picos de audio."""
    moments: list[tuple[float, float]] = []  # (tiempo, peso)
    for w in words:
        if reaction_hits(w["w"]) > 0:
            moments.append((w["start"], 2.0))
        elif w.get("hl"):
            moments.append((w["start"], 0.5))
    if energy and energy.get("db"):
        hop, med = energy["hop"], energy["median"]
        for a, b in intervals:
            for i in range(int(a / hop), int(b / hop) + 1):
                if i < len(energy["db"]) and energy["db"][i] - med > 9:
                    t = remap(i * hop, intervals)
                    if t is not None:
                        moments.append((t, 1.5))
    moments.sort(key=lambda m: m[1], reverse=True)
    chosen: list[float] = []
    for t, _ in moments:
        if 0.8 < t < total - 1.2 and all(abs(t - c) >= MIN_ZOOM_SPACING for c in chosen):
            chosen.append(t)
        if len(chosen) >= max(1, int(total / 8)):
            break
    return sorted((round(max(t - 0.15, 0), 2), round(min(t + 1.5, total), 2)) for t in chosen)


def zoom_expr(events: list[tuple[float, float]], amount: float) -> str:
    """Expresión Z(t) con rampas suavizadas (smoothstep) de entrada 0.3 s y salida 0.45 s."""
    if not events or amount <= 0:
        return "1"
    terms = []
    for s, e in events:
        rin = f"clip((t-{s})/0.3,0,1)"
        rout = f"clip(({e}-t)/0.45,0,1)"
        terms.append(f"({rin}*{rin}*(3-2*{rin}))*({rout}*{rout}*(3-2*{rout}))")
    return f"(1+{amount}*min(1,{'+'.join(terms)}))"


def measure_loudness(src: Path, start: float, end: float) -> dict[str, str] | None:
    """Primera pasada de loudnorm (solo audio, rápida) para normalizar con precisión a -14 LUFS."""
    import json as _json
    try:
        proc = subprocess.run(
            [config.FFMPEG, "-hide_banner", "-nostats", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
             "-i", str(src), "-vn", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
            capture_output=True, text=True, timeout=600)
        blob = proc.stderr[proc.stderr.rindex("{"):proc.stderr.rindex("}") + 1]
        data = _json.loads(blob)
        if data.get("input_i") in (None, "-inf") or float(data["input_i"]) < -70:
            return None
        return data
    except Exception:
        return None


def loudnorm_filter(measured: dict[str, str] | None) -> str:
    if not measured:
        return "loudnorm=I=-14:TP=-1.5:LRA=11"
    return ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true"
            f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}")


def _ass_path_for_filter(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def build_filtergraph(intervals: list[tuple[float, float]], seek: float, layout: str, info: dict[str, Any],
                      center_x: float, zexpr: str, ass_file: Path | None,
                      loudness: dict[str, str] | None = None) -> str:
    W, H = config.OUT_WIDTH, config.OUT_HEIGHT
    parts = []
    n = len(intervals)
    for k, (a, b) in enumerate(intervals):
        ra, rb = a - seek, b - seek
        d = rb - ra
        parts.append(f"[0:v]trim=start={ra:.3f}:end={rb:.3f},setpts=PTS-STARTPTS[v{k}]")
        fade = min(0.02, d / 4)
        parts.append(f"[0:a]atrim=start={ra:.3f}:end={rb:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={fade:.3f},afade=t=out:st={max(d - fade, 0):.3f}:d={fade:.3f}[a{k}]")
    concat_in = "".join(f"[v{k}][a{k}]" for k in range(n))
    parts.append(f"{concat_in}concat=n={n}:v=1:a=1[vc][ac]")
    parts.append(f"[vc]fps={config.OUT_FPS}[vf]")
    parts.append(framing.layout_filter(layout, info, center_x, W, H, "vf", "vl"))
    chain = "[vl]"
    if zexpr != "1":
        z = zexpr
        chain += (f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame:flags=bicubic,"
                  f"crop={W}:{H},")
    if ass_file is not None:
        chain += f"ass='{_ass_path_for_filter(ass_file)}',"
    chain += "format=yuv420p[vout]"
    parts.append(chain)
    parts.append(f"[ac]{loudnorm_filter(loudness)},aresample=48000[aout]")
    return ";\n".join(parts)


def render_clip(src: Path, info: dict[str, Any], clip: dict[str, Any], words_abs: list[dict[str, Any]],
                energy: dict[str, Any] | None, out_dir: Path, options: dict[str, Any] | None = None,
                on_progress: Callable[[float], None] | None = None) -> dict[str, Any]:
    """Renderiza el clip y devuelve el informe de edición (línea de tiempo, zooms, ajustes)."""
    opts = {"layout": "auto", "zoom": "suave", "subtitles": True, "remove_pauses": True}
    opts.update({k: v for k, v in (options or {}).items() if v is not None})
    start, end = float(clip["start"]), float(clip["end"])
    if end - start < 1:
        raise MediaError("El clip debe durar al menos 1 segundo.")
    out_dir.mkdir(parents=True, exist_ok=True)

    intervals = keep_intervals(words_abs, start, end, bool(opts["remove_pauses"]))
    total = sum(b - a for a, b in intervals)
    words = remap_words(words_abs, intervals)
    subtitles.mark_important(words)

    subject = framing.detect_subject(src, start, end)
    layout = framing.resolve_layout(opts["layout"], info, subject)

    amount = ZOOM_LEVELS.get(opts["zoom"], ZOOM_LEVELS["suave"])
    zevents = zoom_events(words, energy, intervals, total) if amount > 0 else []
    zexpr = zoom_expr(zevents, amount)

    ass_file = None
    if opts["subtitles"] and words:
        ass_file = subtitles.write_ass(words, out_dir / f"{clip['id']}.ass")
        (out_dir / f"{clip['id']}.srt").write_text(subtitles.build_srt(words), encoding="utf-8")

    seek = max(start - 1.0, 0.0)  # búsqueda rápida + recorte exacto en el filtro
    loudness = measure_loudness(src, start, end)
    graph = build_filtergraph(intervals, seek, layout, info, subject["center_x"], zexpr, ass_file, loudness)
    graph_file = out_dir / f"{clip['id']}.filter.txt"
    graph_file.write_text(graph, encoding="utf-8")
    out_file = out_dir / f"{clip['id']}.mp4"
    tmp_file = out_dir / f"{clip['id']}.tmp.mp4"

    cmd = [
        config.FFMPEG, "-y", "-hide_banner", "-nostats", "-progress", "pipe:1",
        "-ss", f"{seek:.3f}", "-t", f"{end - seek + 0.5:.3f}", "-i", str(src),
        "-filter_complex_script", str(graph_file), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", config.OUT_PRESET, "-crf", str(config.OUT_CRF),
        "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(config.OUT_FPS),
        "-c:a", "aac", "-b:a", config.OUT_AUDIO_BITRATE, "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(tmp_file),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out_re = re.compile(r"out_time_(?:ms|us)=(\d+)")
    assert proc.stdout is not None
    for line in proc.stdout:
        m = out_re.match(line.strip())
        if m and on_progress and total:
            on_progress(min(int(m.group(1)) / 1e6 / total, 1.0))
    stderr = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0:
        tail = "\n".join(stderr.strip().splitlines()[-10:])
        tmp_file.unlink(missing_ok=True)
        raise MediaError(f"FFmpeg no pudo exportar el clip: {tail}")
    tmp_file.replace(out_file)

    return {
        "output": out_file.name,
        "ass": ass_file.name if ass_file else None,
        "srt": f"{clip['id']}.srt" if ass_file else None,
        "duration": round(total, 2),
        "timeline": [{"source_start": a, "source_end": b} for a, b in intervals],
        "cuts": len(intervals) - 1,
        "removed_seconds": round((end - start) - total, 2),
        "zooms": [{"start": s, "end": e} for s, e in zevents],
        "zoom_amount": amount,
        "layout": layout,
        "subject": subject,
        "subtitle_words": len(words) if ass_file else 0,
        "export_settings": {
            "resolution": f"{config.OUT_WIDTH}x{config.OUT_HEIGHT}", "fps": config.OUT_FPS,
            "video": f"H.264 high, CRF {config.OUT_CRF}, preset {config.OUT_PRESET}",
            "audio": f"AAC {config.OUT_AUDIO_BITRATE} 48 kHz estéreo, loudnorm -14 LUFS "
                     + ("(2 pasadas)" if loudness else "(1 pasada)"),
            "container": "MP4 (faststart)",
        },
        "options": opts,
    }
