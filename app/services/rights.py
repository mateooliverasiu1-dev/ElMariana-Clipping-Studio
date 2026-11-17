"""Revisión de derechos de uso (skill: copyright-guard).

La app NO puede verificar legalmente un permiso: evalúa la declaración documentada
por el usuario y aplica reglas conservadoras. Nunca aprueba si hay incertidumbre.

Estados:
  BLOCKED          no se puede procesar ni exportar.
  REVIEW REQUIRED  se puede analizar, pero no exportar hasta resolver los riesgos.
  APPROVED         se puede exportar (sigue requiriendo aprobación humana para publicar).
"""
from __future__ import annotations

from typing import Any

PERMISSION_TYPES = {
    "own": "Contenido propio",
    "written_permission": "Permiso escrito del creador",
    "license": "Licencia o contrato",
    "creative_commons": "Creative Commons (reutilización permitida)",
    "other": "Otro",
    "none": "Sin permiso",
}
THIRD_PARTY = {
    "no": "No contiene",
    "yes_licensed": "Sí, con licencia documentada",
    "yes": "Sí, sin licencia",
    "unknown": "No lo sé",
}

APPROVED, REVIEW, BLOCKED = "APPROVED", "REVIEW REQUIRED", "BLOCKED"


def normalize(decl: dict[str, Any] | None) -> dict[str, Any]:
    d = dict(decl or {})
    return {
        "source_description": str(d.get("source_description", "")).strip(),
        "source_url": str(d.get("source_url", "")).strip(),
        "rights_holder": str(d.get("rights_holder", "")).strip(),
        "creator_name": str(d.get("creator_name", "")).strip(),
        "permission_type": d.get("permission_type") if d.get("permission_type") in PERMISSION_TYPES else "none",
        "evidence": str(d.get("evidence", "")).strip(),
        "third_party_music": d.get("third_party_music") if d.get("third_party_music") in THIRD_PARTY else "unknown",
        "third_party_footage": d.get("third_party_footage") if d.get("third_party_footage") in THIRD_PARTY else "unknown",
        "confirmed": str(d.get("confirmed", "")).lower() in ("true", "1", "on", "yes", "sí", "si"),
        "notes": str(d.get("notes", "")).strip(),
    }


def evaluate(decl: dict[str, Any]) -> dict[str, Any]:
    d = normalize(decl)
    risks: list[str] = []
    actions: list[str] = []
    blocked = False
    review = False

    if not d["confirmed"]:
        blocked = True
        actions.append("Confirma que tienes derechos documentados para usar este video.")
    if d["permission_type"] == "none":
        blocked = True
        risks.append("No hay permiso de uso declarado.")
        actions.append("Consigue permiso del titular antes de usar el material.")
    if not d["rights_holder"]:
        blocked = True
        actions.append("Indica quién es el titular de los derechos.")
    if not d["source_description"]:
        review = True
        actions.append("Describe la fuente original del video.")

    if d["permission_type"] in ("written_permission", "license", "creative_commons") and not d["evidence"]:
        review = True
        risks.append("Se declara permiso pero no hay evidencia registrada.")
        actions.append("Registra la evidencia: enlace al correo/contrato, licencia o publicación del permiso.")
    if d["permission_type"] == "other":
        review = True
        risks.append("Tipo de permiso poco claro.")
        actions.append("Especifica el permiso con un tipo concreto y su evidencia.")

    for key, label in (("third_party_music", "música"), ("third_party_footage", "imágenes/video")):
        val = d[key]
        if val == "yes":
            review = True
            risks.append(f"Contiene {label} de terceros sin licencia: riesgo de reclamo de Content ID.")
            actions.append(f"Elimina/silencia esa {label} o documenta su licencia.")
        elif val == "unknown":
            review = True
            risks.append(f"No se sabe si contiene {label} de terceros.")
            actions.append(f"Revisa el clip y declara si contiene {label} de terceros.")
        elif val == "yes_licensed" and not d["evidence"]:
            review = True
            actions.append(f"Registra la evidencia de la licencia de la {label}.")

    status = BLOCKED if blocked else REVIEW if review else APPROVED
    return {
        "status": status,
        "declaration": d,
        "risks": risks,
        "required_actions": actions,
        "monetization_note": (
            "YouTube puede limitar la monetización del contenido reutilizado con poca aportación original. "
            "Añade comentario, análisis o una transformación significativa. Esto no garantiza la monetización."
        ),
        "credit_note": "Dar crédito no sustituye al permiso.",
        "can_process": status != BLOCKED,
        "can_export": status == APPROVED,
    }
