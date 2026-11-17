"""Almacenamiento de proyectos en disco (un JSON por proyecto, sin base de datos).

Estructura:
    data/projects/<project_id>/
        project.json      metadatos, derechos, transcripción, clips
        source.<ext>      video original subido
        audio.wav         audio 16 kHz mono para Whisper
        preview.mp4       proxy ligero si el navegador no puede reproducir el original
        clips/<clip_id>.ass / .mp4   subtítulos y exportaciones
"""
from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from . import config

_lock = threading.RLock()


class ProjectNotFound(KeyError):
    pass


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:10]


def project_dir(pid: str) -> Path:
    # Evita rutas fuera del directorio de datos.
    if not pid.isalnum():
        raise ProjectNotFound(pid)
    return config.PROJECTS_DIR / pid


def _json_path(pid: str) -> Path:
    return project_dir(pid) / "project.json"


def create_project(data: dict[str, Any]) -> dict[str, Any]:
    config.ensure_dirs()
    pid = data.get("id") or new_id()
    data["id"] = pid
    data.setdefault("created_at", time.time())
    data.setdefault("status", "uploaded")
    data.setdefault("progress", {"stage": "uploaded", "percent": 0, "message": ""})
    data.setdefault("clips", [])
    (project_dir(pid) / "clips").mkdir(parents=True, exist_ok=True)
    save_project(data)
    return data


def save_project(data: dict[str, Any]) -> None:
    with _lock:
        path = _json_path(data["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = time.time()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)  # escritura atómica


def load_project(pid: str) -> dict[str, Any]:
    with _lock:
        path = _json_path(pid)
        if not path.exists():
            raise ProjectNotFound(pid)
        return json.loads(path.read_text(encoding="utf-8"))


def update_project(pid: str, fn: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Lee, modifica con `fn` y guarda bajo el mismo candado (evita carreras con los jobs)."""
    with _lock:
        data = load_project(pid)
        fn(data)
        save_project(data)
        return data


def list_projects() -> list[dict[str, Any]]:
    config.ensure_dirs()
    items = []
    for d in config.PROJECTS_DIR.iterdir():
        if (d / "project.json").exists():
            try:
                items.append(load_project(d.name))
            except (ValueError, ProjectNotFound):
                continue
    items.sort(key=lambda p: p.get("created_at", 0), reverse=True)
    return items


def delete_project(pid: str) -> None:
    with _lock:
        d = project_dir(pid)
        if not d.exists():
            raise ProjectNotFound(pid)
        shutil.rmtree(d)


def find_clip(project: dict[str, Any], cid: str) -> dict[str, Any]:
    for c in project.get("clips", []):
        if c["id"] == cid:
            return c
    raise KeyError(cid)


def set_progress(pid: str, stage: str, percent: float, message: str = "", status: str | None = None) -> None:
    def _fn(p: dict[str, Any]) -> None:
        p["progress"] = {"stage": stage, "percent": round(percent, 1), "message": message}
        if status:
            p["status"] = status
    try:
        update_project(pid, _fn)
    except ProjectNotFound:
        pass
