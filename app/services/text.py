"""Utilidades de texto en español e inglés: palabras vacías, reacciones e importancia.

Son reglas transparentes (sin modelos de lenguaje ni APIs de pago).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable

STOPWORDS = set("""
a al algo algunos ante antes aquí así aun aunque bien cada como con contra cual cuando de del desde
donde dos el ella ellas ello ellos en entre era eran es esa esas ese eso esos esta estaba estado
estamos estan están estar este esto estos estoy fue fueron ha hace hacia han has hasta hay he la
las le les lo los me mi mis mucho muy más nada ni no nos nosotros o otra otro para pero poco por
porque pues que qué quien se sea ser si sí sin sobre solo son su sus también tan tanto te tengo
tiene tienen todo todos tu tus un una uno unos y ya yo eh este bueno o sea entonces como que pues
the a an and are as at be been but by can could did do does for from had has have he her his i if
in into is it its just like me my no not of on or our out so that the their them then there they
this to too up us was we were what when where which who will with would you your yeah okay ok um uh
""".split())

# Expresiones que suelen indicar risa, sorpresa o emoción (es/en, incluye México).
REACTION_PATTERNS = [
    r"\b(ja){2,}\b", r"\bjaja\w*", r"\bjeje\w*", r"\bjiji\w*", r"\b(ha){2,}\b", r"\bhaha\w*", r"\blol\b", r"\blmao\b",
    r"\bno manches\b", r"\bno mames\b", r"\bno puede ser\b", r"\bqué onda\b", r"\bnet[oa]\b", r"\bincre[ií]ble\b",
    r"\bwow\b", r"\bguau\b", r"\bdios m[ií]o\b", r"\bme muero\b", r"\bqu[eé] (fue|pas[oó])\b", r"\bah[ií] est[aá]\b",
    r"\bvamos\b", r"\bgolazo\b", r"\bgg\b", r"\bdale\b", r"\bmira\b", r"\bnooo+\b", r"\bs[ií]{2,}\b", r"\bay+\b",
    r"\bwhat\b", r"\bno way\b", r"\boh my god\b", r"\bomg\b", r"\bwtf\b", r"\bholy\b", r"\binsane\b", r"\blet'?s go\b",
    r"\bcrazy\b", r"\bbro\b", r"\bdude\b", r"\bwait\b", r"\bespera\b", r"\bcorre\b", r"\bc[oó]mo\?",
]
_REACTION_RE = [re.compile(p, re.IGNORECASE) for p in REACTION_PATTERNS]

_WORD_RE = re.compile(r"[\wáéíóúüñ']+", re.IGNORECASE)


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


def reaction_hits(text: str) -> int:
    t = text.lower()
    hits = sum(len(r.findall(t)) for r in _REACTION_RE)
    hits += t.count("!") + 0.5 * t.count("?")
    return int(round(hits))


def keywords(texts: Iterable[str], top: int = 8) -> list[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        for tok in tokens(text):
            if len(tok) >= 4 and tok not in STOPWORDS and not tok.isdigit():
                counts[tok] += 1
    return [w for w, _ in counts.most_common(top)]


def is_important_word(word: str, keyword_set: set[str] | None = None) -> bool:
    """Decide si una palabra se resalta en los subtítulos."""
    raw = word.strip()
    clean = raw.lower().strip(".,;:¡!¿?\"'()…-")
    if not clean or clean in STOPWORDS:
        return False
    if any(r.search(raw.lower()) for r in _REACTION_RE):
        return True
    if "!" in raw or any(ch.isdigit() for ch in clean):
        return True
    if keyword_set and clean in keyword_set:
        return True
    if raw.isupper() and len(clean) >= 3:
        return True
    return len(clean) >= 7  # palabras largas suelen cargar el significado


def ends_sentence(text: str) -> bool:
    return text.rstrip().endswith((".", "!", "?", "…"))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
