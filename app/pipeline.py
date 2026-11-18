"""Orquestación: procesamiento de proyectos y exportación de clips.

Los datos pesados (transcripción, señales) van en archivos aparte para mantener
project.json pequeño y rápido de leer desde la interfaz.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from . import storage
from .services import cover, highlights, media, quality, render, rights, seo, signals, transcribe

log = logging.getLogger("elmariana.pipeline")


def source_path(project: dict[str, Any]) -> Path:
    return storage.project_dir(project["id"]) / project["source_file"]


def _read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def load_transcript(pid: str) -> dict[str, Any] | None:
    return _read_json(storage.project_dir(pid) / "transcript.json")


def load_signals(pid: str) -> dict[str, Any]:
    return _read_json(storage.project_dir(pid) / "signals.json", {}) or {}


def process_project(pid: str, transcript_override: dict[str, Any] | None = None) -> None:
    """Audio → energía → escenas → transcripción → momentos → SEO. `transcript_override` es para pruebas."""
    project = storage.load_project(pid)
    pdir = storage.project_dir(pid)
    src = source_path(project)
    rv = rights.evaluate(project.get("rights", {}))
    if not rv["can_process"]:
        storage.set_progress(pid, "blocked", 0, "Derechos BLOCKED: completa la declaración de derechos.", "blocked")
        return

    info = project.get("media") or media.probe(src)
    duration = info["duration"]

    storage.set_progress(pid, "audio", 3, "Extrayendo audio…", "processing")
    wav = media.extract_audio(src, pdir / "audio.wav")

    if not media.browser_playable(info, src) and not (pdir / "preview.mp4").exists():
        storage.set_progress(pid, "preview", 6, "Creando vista previa compatible con el navegador…")
        media.make_preview(src, pdir / "preview.mp4")

    storage.set_progress(pid, "signals", 10, "Midiendo energía del audio…")
    energy = signals.audio_energy(wav)
    storage.set_progress(pid, "scenes", 14, "Detectando cambios de escena…")
    try:
        scenes = signals.scene_changes(src)
    except media.MediaError as exc:  # no es crítico
        log.warning("Detección de escenas falló: %s", exc)
        scenes = []
    (pdir / "signals.json").write_text(json.dumps({"energy": energy, "scenes": scenes}), encoding="utf-8")

    if transcript_override is not None:
        tr = transcript_override
    else:
        storage.set_progress(pid, "transcribe", 18, "Transcribiendo con Faster-Whisper (puede tardar)…")
        t0 = time.time()

        def _prog(frac: float) -> None:
            storage.set_progress(pid, "transcribe", 18 + 67 * frac,
                                 f"Transcribiendo… {frac:.0%} ({time.time() - t0:.0f} s)")

        tr = transcribe.transcribe(wav, language=project.get("language", "auto"),
                                   model_size=project.get("whisper_model"), duration=duration, on_progress=_prog)
    (pdir / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False), encoding="utf-8")

    storage.set_progress(pid, "highlights", 88, "Buscando momentos interesantes…")
    cands = highlights.find_highlights(tr, duration, energy, scenes)
    decl = rights.normalize(project.get("rights"))
    lang = tr.get("language") if tr.get("language") in ("es", "en") else "es"
    clips = []
    used_quotes: set[str] = set()
    for i, c in enumerate(cands):
        cid = f"c{i + 1:02d}"
        meta = seo.generate(c, creator=decl["creator_name"] or decl["rights_holder"], language=lang,
                            source_url=decl["source_url"], rights_holder=decl["rights_holder"],
                            used_quotes=used_quotes)
        try:
            media.thumbnail(src, pdir / "clips" / f"{cid}.jpg", c["start"] + min(2.0, c["duration"] / 2))
            thumb = f"{cid}.jpg"
        except media.MediaError:
            thumb = None
        clip = {**c, "id": cid, "title": meta["titles"][0], "seo": meta, "thumbnail": thumb,
                "words": None, "render": None, "qc": None, "status": "candidate", "cover": None}
        storage.set_progress(pid, "covers", 90 + 9 * i / max(len(cands), 1), f"Creando portada {i + 1}/{len(cands)}…")
        try:
            words = render.clip_words(transcribe.all_words(tr), c["start"], c["end"])
            clip["cover"] = cover.generate_cover(src, info, clip, words, energy, pdir / "clips")
        except Exception as exc:  # la portada nunca bloquea el análisis
            log.warning("Portada de %s falló: %s", cid, exc)
        clips.append(clip)

    def _save(p: dict[str, Any]) -> None:
        p["clips"] = clips
        p["language_detected"] = tr.get("language")
        p["transcript_stats"] = {"segments": len(tr.get("segments", [])),
                                 "words": len(transcribe.all_words(tr)), "model": tr.get("model")}
        p["status"] = "ready"
        p["progress"] = {"stage": "done", "percent": 100,
                         "message": f"{len(clips)} clips candidatos" if clips else
                         "No se detectó habla suficiente para proponer clips."}
    storage.update_project(pid, _save)


def clip_source_words(pid: str, clip: dict[str, Any]) -> list[dict[str, Any]]:
    """Palabras del clip: las editadas por el usuario o las de la transcripción."""
    if clip.get("words"):
        return [dict(w) for w in clip["words"] if w.get("w", "").strip()]
    tr = load_transcript(pid) or {}
    return render.clip_words(transcribe.all_words(tr), float(clip["start"]), float(clip["end"]))


def render_and_check(pid: str, cid: str, options: dict[str, Any]) -> None:
    project = storage.load_project(pid)
    clip = storage.find_clip(project, cid)
    rv = rights.evaluate(project.get("rights", {}))
    if not rv["can_process"]:
        raise PermissionError("Derechos BLOCKED: no se puede editar este video.")
    pdir = storage.project_dir(pid)
    src = source_path(project)
    words = clip_source_words(pid, clip)
    energy = load_signals(pid).get("energy")

    def _mark(status: str, extra: dict[str, Any] | None = None) -> None:
        def fn(p: dict[str, Any]) -> None:
            c = storage.find_clip(p, cid)
            c["status"] = status
            c.update(extra or {})
        storage.update_project(pid, fn)

    _mark("rendering", {"render_progress": 0, "error": None})

    last = [0.0]

    def _prog(frac: float) -> None:
        if frac - last[0] >= 0.05:
            last[0] = frac
            _mark("rendering", {"render_progress": round(frac * 100)})

    report = render.render_clip(src, project["media"], clip, words, energy, pdir / "clips", options, _prog)
    edited_words = render.remap_words(words, [(t["source_start"], t["source_end"]) for t in report["timeline"]])
    ass = pdir / "clips" / report["ass"] if report.get("ass") else None
    qc = quality.check(pdir / "clips" / report["output"], clip, report, rv["status"], edited_words, ass)
    _mark("exported" if qc["status"] == "PASS" else "qc_failed",
          {"render": report, "qc": qc, "render_progress": 100, "rendered_at": time.time()})


def make_cover(pid: str, cid: str, text: str | None = None, at: float | None = None,
               layout: str = "auto") -> dict[str, Any]:
    """Genera (o regenera) la portada 1080x1920 de un clip y la guarda en el proyecto."""
    project = storage.load_project(pid)
    clip = storage.find_clip(project, cid)
    words = clip_source_words(pid, clip)
    energy = load_signals(pid).get("energy")
    result = cover.generate_cover(source_path(project), project["media"], clip, words, energy,
                                  storage.project_dir(pid) / "clips", text=text, at=at, layout=layout)
    result["updated_at"] = time.time()

    def fn(p: dict[str, Any]) -> None:
        storage.find_clip(p, cid)["cover"] = result
    storage.update_project(pid, fn)
    return result


def make_missing_covers(pid: str, regenerate: bool = False) -> int:
    project = storage.load_project(pid)
    n = 0
    for c in project.get("clips", []):
        if regenerate or not c.get("cover"):
            try:
                make_cover(pid, c["id"])
                n += 1
            except Exception as exc:
                log.warning("Portada de %s falló: %s", c["id"], exc)
    return n


def mark_clip_error(pid: str, cid: str, exc: Exception) -> None:
    def fn(p: dict[str, Any]) -> None:
        c = storage.find_clip(p, cid)
        c["status"] = "error"
        c["error"] = str(exc)
    try:
        storage.update_project(pid, fn)
    except Exception:  # pragma: no cover
        log.exception("No se pudo registrar el error del clip")


def mark_project_error(pid: str, exc: Exception) -> None:
    storage.set_progress(pid, "error", 0, str(exc), "error")
