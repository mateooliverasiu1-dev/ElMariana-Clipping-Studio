"""Detección de momentos interesantes (skill: stream-highlight-finder).

Combina, de forma explicable:
  * transcripción: reacciones, exclamaciones, preguntas, densidad de habla;
  * contexto: que el clip empiece y termine en límites de frase;
  * audio: picos de energía relativos a la mediana del video (risas, gritos);
  * escenas: cambios de plano (dinamismo visual);
  * estructura narrativa (skill streamer-storytelling): gancho al inicio y remate al final.

Cada candidato recibe una puntuación 0–100 y una lista de razones legibles.
Nunca se inventa diálogo: el texto mostrado es exactamente el transcrito.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .. import config
from . import text as txt
from .signals import window_energy

WEIGHTS = {
    "energy": 22, "reactions": 22, "hook": 14, "payoff": 10,
    "density": 10, "context": 10, "scenes": 6, "liveliness": 6,
}
assert sum(WEIGHTS.values()) == 100


def _clip01(x: float) -> float:
    return float(min(max(x, 0.0), 1.0))


def _units(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in transcript.get("segments", []) if s.get("text") and s["end"] > s["start"]]


def _words_in(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [w for u in units for w in u.get("words", [])]


def _dead_air(words: list[dict[str, Any]], start: float, end: float, min_gap: float = 1.0) -> float:
    """Segundos sin habla (huecos > min_gap) dentro de la ventana."""
    total, prev = 0.0, start
    for w in words:
        gap = w["start"] - prev
        if gap > min_gap:
            total += gap
        prev = max(prev, w["end"])
    if end - prev > min_gap:
        total += end - prev
    return total


def score_window(units: list[dict[str, Any]], energy: dict[str, Any] | None, scenes: list[float],
                 prev_end: float | None, next_start: float | None, duration: float) -> dict[str, Any]:
    start, end = units[0]["start"], units[-1]["end"]
    length = max(end - start, 0.1)
    text = " ".join(u["text"] for u in units)
    words = _words_in(units)
    f: dict[str, float] = {}
    reasons: list[str] = []

    # Energía de audio relativa a todo el video.
    if energy and energy.get("db"):
        med = energy["median"]
        win = window_energy(energy, start, end)
        smooth = np.convolve(win, np.ones(2) / 2, mode="same") if win.size > 2 else win
        peak, mean = float(smooth.max()), float(win.mean())
        f["energy"] = 0.6 * _clip01((peak - med) / 12) + 0.4 * _clip01((mean - med) / 6)
        if peak - med > 9:
            reasons.append(f"Pico de audio fuerte (+{peak - med:.0f} dB sobre lo normal): posible grito o risa")
        first = window_energy(energy, start, min(start + 3, end))
        last = window_energy(energy, start + 0.6 * length, end)
        hook_energy = _clip01((float(first.max()) - med) / 8)
        payoff_energy = _clip01((float(last.max()) - med) / 9)
    else:
        f["energy"], hook_energy, payoff_energy = 0.3, 0.0, 0.0

    # Reacciones en el texto.
    hits = txt.reaction_hits(text)
    f["reactions"] = _clip01(hits / max(3.0, length / 10))
    if hits >= 2:
        reasons.append(f"{hits} expresiones de reacción/emoción en el diálogo")

    # Gancho: algo potente en los primeros 3 s (storytelling).
    first_text = " ".join(u["text"] for u in units if u["start"] < start + 3)
    hook_text_score = _clip01(txt.reaction_hits(first_text) / 2)
    speaks_fast = 1.0 if words and words[0]["start"] - start < 1.0 else 0.4
    f["hook"] = speaks_fast * max(hook_text_score, hook_energy, 0.25)
    if f["hook"] > 0.6:
        reasons.append("Arranque con gancho en los primeros 3 segundos")

    # Remate en el último 40 %.
    tail_text = " ".join(u["text"] for u in units if u["start"] >= start + 0.6 * length)
    f["payoff"] = max(_clip01(txt.reaction_hits(tail_text) / 2), payoff_energy)
    if f["payoff"] > 0.6:
        reasons.append("Remate o reacción cerca del final")

    # Densidad de habla (2–3.5 palabras/s es ritmo de Short).
    wps = len(words) / length
    f["density"] = _clip01(wps / 2.5)

    # Contexto completo: empieza tras una pausa y termina con frase cerrada.
    starts_clean = prev_end is None or start - prev_end >= 0.35
    ends_clean = txt.ends_sentence(units[-1]["text"]) or next_start is None or next_start - end >= 0.5
    f["context"] = 0.5 * starts_clean + 0.5 * ends_clean
    if starts_clean and ends_clean:
        reasons.append("Conversación completa: empieza y termina en límites naturales")

    # Cambios de escena (ni estático ni caótico).
    n_sc = sum(1 for t in scenes if start <= t <= end)
    per10 = n_sc / length * 10
    f["scenes"] = _clip01(per10 / 1.5) if per10 <= 4 else 0.6

    # Penaliza silencios largos.
    dead = _dead_air(words, start, end)
    f["liveliness"] = _clip01(1 - dead / (0.35 * length))
    if dead > 0.25 * length:
        reasons.append(f"Ojo: {dead:.0f} s de silencio; se recortarán pausas al editar")

    score = sum(WEIGHTS[k] * f.get(k, 0) for k in WEIGHTS)

    context_note = ""
    if not starts_clean:
        context_note = ("Empieza a mitad de conversación; revisa si hace falta incluir la frase anterior "
                        f"({start - (prev_end or start):.1f} s antes).")
    elif not ends_clean:
        context_note = "La última frase podría quedar cortada; considera extender el final."

    if f["reactions"] > 0.6 or f["energy"] > 0.6:
        style = "Zoom suave en la reacción + subtítulos con énfasis en exclamaciones"
    elif f["density"] > 0.8:
        style = "Ritmo rápido: cortar pausas, subtítulos de 2–3 palabras"
    else:
        style = "Encuadre estable, subtítulos limpios, zoom solo en el remate"

    return {
        "start": round(start, 2), "end": round(end, 2), "duration": round(length, 2),
        "score": int(round(score)), "features": {k: round(v, 3) for k, v in f.items()},
        "reasons": reasons or ["Fragmento con habla continua y ritmo aceptable"],
        "context_note": context_note, "edit_style": style, "text": text,
        "hook_text": units[0]["text"], "payoff_text": units[-1]["text"],
        "keywords": txt.keywords([text], top=6),
    }


def find_highlights(transcript: dict[str, Any], duration: float, energy: dict[str, Any] | None = None,
                    scenes: list[float] | None = None, min_len: float | None = None,
                    max_len: float | None = None, max_candidates: int | None = None) -> list[dict[str, Any]]:
    """Genera candidatos no solapados ordenados por puntuación."""
    min_len = min_len or config.CLIP_MIN_SECONDS
    max_len = max_len or config.CLIP_MAX_SECONDS
    max_candidates = max_candidates or config.MAX_CANDIDATES
    scenes = scenes or []
    units = _units(transcript)
    if not units:
        return []

    # Si todo el video es más corto que el mínimo, se propone completo.
    total_speech = units[-1]["end"] - units[0]["start"]
    if total_speech < min_len:
        min_len = max(total_speech, 1.0)

    candidates = []
    n = len(units)
    for i in range(n):
        for j in range(i, n):
            length = units[j]["end"] - units[i]["start"]
            if length > max_len:
                break
            if length < min_len:
                continue
            c = score_window(units[i:j + 1], energy, scenes,
                             units[i - 1]["end"] if i > 0 else None,
                             units[j + 1]["start"] if j + 1 < n else None, duration)
            candidates.append(c)

    candidates.sort(key=lambda c: (c["score"], -abs(c["duration"] - 35)), reverse=True)

    chosen: list[dict[str, Any]] = []
    for c in candidates:
        if len(chosen) >= max_candidates:
            break
        clash = False
        for o in chosen:
            overlap = min(c["end"], o["end"]) - max(c["start"], o["start"])
            if overlap > 0.25 * min(c["duration"], o["duration"]):
                clash = True
                break
            if txt.jaccard(set(c["keywords"]), set(o["keywords"])) > 0.6:
                clash = True  # evita clips repetitivos
                break
        if not clash:
            chosen.append(c)

    # Margen pequeño para no cortar la primera/última sílaba.
    for c in chosen:
        c["start"] = round(max(c["start"] - 0.25, 0.0), 2)
        c["end"] = round(min(c["end"] + 0.4, duration) if duration else c["end"] + 0.4, 2)
        c["duration"] = round(c["end"] - c["start"], 2)
    return chosen
