"""Títulos, descripción y hashtags (skill: youtube-seo).

Generación por reglas a partir de frases reales del clip: no usa APIs de pago ni
modelos externos, y nunca promete resultados virales. Los textos son sugerencias
editables en la interfaz.
"""
from __future__ import annotations

import re
from typing import Any

from .text import keywords, reaction_hits, strip_accents

MAX_TITLE = 70


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" .,;:-\"'“”")


def _shorten(s: str, limit: int) -> str:
    s = _clean(s)
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text)
    return [_clean(p) for p in parts if len(_clean(p)) >= 8]


def best_quote(text: str, exclude: set[str] | None = None) -> str:
    """Frase real más llamativa del clip; evita repetir las ya usadas en otros clips."""
    sents = _sentences(text) or [_clean(text)]
    sents.sort(key=lambda s: (reaction_hits(s), -abs(len(s) - 40)), reverse=True)
    for s in sents:
        if not exclude or s.lower() not in exclude:
            return s
    return sents[0]


def _tag(word: str) -> str:
    t = re.sub(r"[^A-Za-z0-9]", "", strip_accents(word))
    return f"#{t.lower()}" if len(t) >= 3 else ""


def suggest_title(text: str, creator: str = "", language: str = "es") -> str:
    return generate({"text": text}, creator=creator, language=language)["titles"][0]


def generate(clip: dict[str, Any], creator: str = "", language: str = "es", source_url: str = "",
             rights_holder: str = "", used_quotes: set[str] | None = None) -> dict[str, Any]:
    """`used_quotes`: frases ya usadas como título en otros clips (se actualiza in situ)."""
    text = clip.get("text", "")
    raw_quote = best_quote(text, used_quotes)
    if used_quotes is not None:
        used_quotes.add(raw_quote.lower())
    quote = _shorten(raw_quote, 52)
    kws = clip.get("keywords") or keywords([text], top=6)
    funny = reaction_hits(text) >= 2
    en = language == "en"
    creator = creator.strip()

    if en:
        titles = [
            f"“{quote}”" + (" 😂" if funny else ""),
            f"{creator}: “{_shorten(quote, 40)}”" if creator else f"The moment: “{_shorten(quote, 44)}”",
            f"{creator} wasn't ready for this" if creator and funny else
            f"{kws[0].capitalize()} — {_shorten(quote, 40)}" if kws else f"“{_shorten(quote, 50)}”",
        ]
    else:
        titles = [
            f"“{quote}”" + (" 😂" if funny else ""),
            f"{creator}: “{_shorten(quote, 40)}”" if creator else f"El momento: “{_shorten(quote, 44)}”",
            f"La reacción de {creator} 😳" if creator and funny else
            f"{kws[0].capitalize()}: {_shorten(quote, 42)}" if kws else f"“{_shorten(quote, 50)}”",
        ]
    titles = [_shorten(t, MAX_TITLE) if len(t) > MAX_TITLE else t for t in titles]
    # Quita duplicados conservando el orden.
    seen: set[str] = set()
    titles = [t for t in titles if not (t in seen or seen.add(t))]

    hashtags = ["#shorts"]
    if creator and _tag(creator):
        hashtags.append(_tag(creator))
    for k in kws[:4]:
        tag = _tag(k)
        if tag and tag not in hashtags:
            hashtags.append(tag)
        if len(hashtags) >= 5:
            break

    summary = _shorten(text, 150)
    holder = rights_holder or creator
    if en:
        desc = (f"{('Clip from ' + creator + '. ') if creator else ''}{summary}\n\n"
                + (f"Original: {source_url}\n" if source_url else "")
                + (f"Used with permission from {holder}.\n" if holder else "")
                + "\n" + " ".join(hashtags))
        pinned = (f"What would you have done? Full stream from {creator}" if creator else
                  "What would you have done?") + (f": {source_url}" if source_url else "")
    else:
        desc = (f"{('Clip de ' + creator + '. ') if creator else ''}{summary}\n\n"
                + (f"Video original: {source_url}\n" if source_url else "")
                + (f"Usado con permiso de {holder}.\n" if holder else "")
                + "\n" + " ".join(hashtags))
        pinned = (f"¿Qué hubieras hecho tú? Stream completo de {creator}" if creator else
                  "¿Qué hubieras hecho tú?") + (f": {source_url}" if source_url else "")

    return {"titles": titles, "description": desc, "hashtags": hashtags,
            "keywords": kws, "pinned_comment": pinned, "generator": "reglas locales (sin IA externa)"}
