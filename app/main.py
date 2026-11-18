"""API FastAPI + servidor de la interfaz web.

Ejecutar:  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import logging
import mimetypes
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, config, jobs, pipeline, storage
from .services import framing, media, rights, transcribe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("elmariana.api")

app = FastAPI(title="ElMariana Clipping Studio", version=__version__)
config.ensure_dirs()


# ---------------------------------------------------------------- utilidades
def _project_or_404(pid: str) -> dict[str, Any]:
    try:
        return storage.load_project(pid)
    except storage.ProjectNotFound:
        raise HTTPException(404, "Proyecto no encontrado")


def _clip_or_404(project: dict[str, Any], cid: str) -> dict[str, Any]:
    try:
        return storage.find_clip(project, cid)
    except KeyError:
        raise HTTPException(404, "Clip no encontrado")


def _public(project: dict[str, Any]) -> dict[str, Any]:
    p = dict(project)
    p["rights_review"] = rights.evaluate(project.get("rights", {}))
    p["processing"] = jobs.is_running(f"process:{project['id']}")
    for c in p.get("clips", []):
        c["rendering"] = jobs.is_running(f"render:{project['id']}:{c['id']}")
    return p


_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def _media_response(path: Path, request: Request, download_name: str | None = None) -> Response:
    """Respuesta con soporte de Range (necesario para buscar en <video>)."""
    if not path.exists():
        raise HTTPException(404, "Archivo no encontrado")
    size = path.stat().st_size
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {"Accept-Ranges": "bytes"}
    if download_name:
        headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
    rng = request.headers.get("range")
    m = _RANGE_RE.fullmatch(rng.strip()) if rng else None
    if not m:
        return FileResponse(path, media_type=ctype, headers=headers)
    start_s, end_s = m.groups()
    if start_s == "":
        length = int(end_s or 0)
        start, end = max(size - length, 0), size - 1
    else:
        start = int(start_s)
        end = min(int(end_s), size - 1) if end_s else size - 1
    if start >= size or start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    def _iter() -> Iterator[bytes]:
        with path.open("rb") as fh:
            fh.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = fh.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers.update({"Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(end - start + 1)})
    return StreamingResponse(_iter(), status_code=206, media_type=ctype, headers=headers)


def _start_processing(pid: str) -> bool:
    return jobs.submit(f"process:{pid}", pipeline.process_project, pid,
                       on_error=lambda exc: pipeline.mark_project_error(pid, exc))


# ---------------------------------------------------------------- sistema
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "version": __version__,
        "ffmpeg": media.ffmpeg_available(),
        "faster_whisper": transcribe.whisper_available(),
        "face_detection": framing.opencv_status(),
        "whisper_default_model": config.WHISPER_DEFAULT_MODEL,
        "whisper_models": list(config.WHISPER_MODELS),
        "languages": list(config.LANGUAGES),
        "allowed_extensions": sorted(config.ALLOWED_EXTENSIONS),
        "clip_range_seconds": [config.CLIP_MIN_SECONDS, config.CLIP_MAX_SECONDS],
        "permission_types": rights.PERMISSION_TYPES,
        "third_party_options": rights.THIRD_PARTY,
    }


# ---------------------------------------------------------------- proyectos
@app.get("/api/projects")
def list_projects() -> list[dict[str, Any]]:
    out = []
    for p in storage.list_projects():
        out.append({k: p.get(k) for k in ("id", "name", "status", "progress", "created_at", "media")}
                   | {"clip_count": len(p.get("clips", [])),
                      "rights_status": rights.evaluate(p.get("rights", {}))["status"],
                      "exported": sum(1 for c in p.get("clips", []) if c.get("status") == "exported")})
    return out


class RightsUpdate(BaseModel):
    source_description: str = ""
    source_url: str = ""
    rights_holder: str = ""
    creator_name: str = ""
    permission_type: str = "none"
    evidence: str = ""
    third_party_music: str = "unknown"
    third_party_footage: str = "unknown"
    confirmed: bool = False
    notes: str = ""


# ---------------------------------------------------------------- subida por partes
# El túnel de puertos de Codespaces rechaza peticiones grandes (HTTP 413), así que la
# interfaz sube el video en trozos pequeños que el servidor une en disco.
_UPLOAD_ID_RE = re.compile(r"^[a-f0-9]{16,32}$")
MAX_CHUNK_BYTES = 16 * 1024 * 1024


def _uploads_dir() -> Path:
    d = config.DATA_DIR / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _upload_paths(uid: str) -> tuple[Path, Path]:
    if not _UPLOAD_ID_RE.match(uid):
        raise HTTPException(404, "Subida no encontrada")
    base = _uploads_dir() / uid
    return base.with_suffix(".part"), base.with_suffix(".json")


def _cleanup_old_uploads(max_age: float = 24 * 3600) -> None:
    now = time.time()
    for f in _uploads_dir().iterdir():
        if now - f.stat().st_mtime > max_age:
            f.unlink(missing_ok=True)


class UploadInit(BaseModel):
    filename: str
    size: int = Field(..., gt=0)


@app.post("/api/uploads", status_code=201)
def upload_init(body: UploadInit) -> dict[str, Any]:
    ext = Path(body.filename).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Formato no permitido ({ext or 'sin extensión'}). Usa MP4, MOV o MKV.")
    if body.size > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "El archivo supera el tamaño máximo permitido.")
    _cleanup_old_uploads()
    uid = uuid.uuid4().hex
    part, meta = _upload_paths(uid)
    part.write_bytes(b"")
    meta.write_text(json.dumps({"filename": body.filename, "size": body.size, "received": 0}), encoding="utf-8")
    return {"upload_id": uid, "max_chunk_bytes": MAX_CHUNK_BYTES}


@app.put("/api/uploads/{uid}")
async def upload_chunk(uid: str, request: Request, offset: int = 0) -> dict[str, Any]:
    """Añade un trozo. `offset` debe coincidir con lo ya recibido (permite reintentar)."""
    part, meta = _upload_paths(uid)
    if not meta.exists():
        raise HTTPException(404, "Subida no encontrada")
    info = json.loads(meta.read_text(encoding="utf-8"))
    offset = int(offset)
    if offset != info["received"]:
        # Reintento de un trozo ya guardado o fuera de orden: se informa lo recibido.
        return {"received": info["received"], "size": info["size"]}
    data = await request.body()
    if not data or len(data) > MAX_CHUNK_BYTES:
        raise HTTPException(400, "Trozo vacío o demasiado grande")
    if info["received"] + len(data) > info["size"]:
        raise HTTPException(400, "Se recibieron más datos de los anunciados")
    with part.open("ab") as fh:
        fh.write(data)
    info["received"] += len(data)
    meta.write_text(json.dumps(info), encoding="utf-8")
    return {"received": info["received"], "size": info["size"]}


@app.delete("/api/uploads/{uid}", status_code=204)
def upload_cancel(uid: str) -> Response:
    for f in _upload_paths(uid):
        f.unlink(missing_ok=True)
    return Response(status_code=204)


@app.post("/api/rights/evaluate")
def rights_evaluate(body: RightsUpdate) -> dict[str, Any]:
    """Revisión previa (la interfaz la usa antes de subir el video)."""
    return rights.evaluate(body.model_dump())


# ---------------------------------------------------------------- creación de proyectos
@app.post("/api/projects", status_code=201)
async def create_project(
    file: Optional[UploadFile] = File(None),
    upload_id: str = Form(""),
    name: str = Form(""),
    language: str = Form("auto"),
    whisper_model: str = Form(config.WHISPER_DEFAULT_MODEL),
    source_description: str = Form(""),
    source_url: str = Form(""),
    rights_holder: str = Form(""),
    creator_name: str = Form(""),
    permission_type: str = Form("none"),
    evidence: str = Form(""),
    third_party_music: str = Form("unknown"),
    third_party_footage: str = Form("unknown"),
    confirmed: str = Form("false"),
    notes: str = Form(""),
) -> dict[str, Any]:
    """Crea un proyecto con un archivo directo (`file`) o con una subida por partes (`upload_id`)."""
    if upload_id:
        part, meta = _upload_paths(upload_id)
        if not meta.exists():
            raise HTTPException(404, "Subida no encontrada o caducada")
        up = json.loads(meta.read_text(encoding="utf-8"))
        if up["received"] != up["size"]:
            raise HTTPException(400, "La subida está incompleta")
        filename = up["filename"]
    elif file is not None and file.filename:
        filename = file.filename
    else:
        raise HTTPException(400, "Falta el video")

    ext = Path(filename).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Formato no permitido ({ext or 'sin extensión'}). Usa MP4, MOV o MKV.")
    if language not in config.LANGUAGES:
        raise HTTPException(400, "Idioma no válido")
    if whisper_model not in config.WHISPER_MODELS:
        raise HTTPException(400, "Modelo de Whisper no válido")

    decl = rights.normalize(dict(
        source_description=source_description, source_url=source_url, rights_holder=rights_holder,
        creator_name=creator_name, permission_type=permission_type, evidence=evidence,
        third_party_music=third_party_music, third_party_footage=third_party_footage,
        confirmed=confirmed, notes=notes))
    review = rights.evaluate(decl)
    if not review["can_process"]:
        # No se guarda ni procesa material sin autorización.
        if upload_id:
            for f in _upload_paths(upload_id):
                f.unlink(missing_ok=True)
        raise HTTPException(403, {"message": "Derechos BLOCKED: no se puede subir este video.",
                                  "required_actions": review["required_actions"]})

    pid = storage.new_id()
    pdir = storage.project_dir(pid)
    pdir.mkdir(parents=True, exist_ok=True)
    dst = pdir / f"source{ext}"
    try:
        if upload_id:
            part, meta = _upload_paths(upload_id)
            shutil.move(str(part), dst)
            meta.unlink(missing_ok=True)
        else:
            written = 0
            with dst.open("wb") as fh:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > config.MAX_UPLOAD_BYTES:
                        raise HTTPException(413, "El archivo supera el tamaño máximo permitido.")
                    fh.write(chunk)
        info = media.probe(dst)
        errors = media.validate_source(info)
        if errors:
            raise HTTPException(400, " ".join(errors))
    except HTTPException:
        shutil.rmtree(pdir, ignore_errors=True)
        raise
    except media.MediaError as exc:
        shutil.rmtree(pdir, ignore_errors=True)
        raise HTTPException(400, f"No se pudo analizar el video: {exc}")

    project = storage.create_project({
        "id": pid, "name": name.strip() or Path(filename).stem,
        "original_filename": filename, "source_file": dst.name, "media": info,
        "language": language, "whisper_model": whisper_model, "rights": decl, "status": "queued",
        "progress": {"stage": "queued", "percent": 0, "message": "En cola para procesar…"},
    })
    _start_processing(pid)
    return _public(project)


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> dict[str, Any]:
    return _public(_project_or_404(pid))


@app.delete("/api/projects/{pid}", status_code=204)
def delete_project(pid: str) -> Response:
    _project_or_404(pid)
    if jobs.is_running(f"process:{pid}"):
        raise HTTPException(409, "El proyecto se está procesando; espera a que termine.")
    storage.delete_project(pid)
    return Response(status_code=204)


@app.put("/api/projects/{pid}/rights")
def update_rights(pid: str, body: RightsUpdate) -> dict[str, Any]:
    _project_or_404(pid)
    decl = rights.normalize(body.model_dump())
    project = storage.update_project(pid, lambda p: p.__setitem__("rights", decl))
    return _public(project)


@app.post("/api/projects/{pid}/process", status_code=202)
def reprocess(pid: str) -> dict[str, Any]:
    project = _project_or_404(pid)
    if not rights.evaluate(project.get("rights", {}))["can_process"]:
        raise HTTPException(403, "Derechos BLOCKED: completa la declaración antes de procesar.")
    if not _start_processing(pid):
        raise HTTPException(409, "Ya se está procesando.")
    storage.set_progress(pid, "queued", 0, "En cola para procesar…", "queued")
    return _public(storage.load_project(pid))


@app.get("/api/projects/{pid}/media")
def project_media(pid: str, request: Request) -> Response:
    project = _project_or_404(pid)
    pdir = storage.project_dir(pid)
    preview = pdir / "preview.mp4"
    path = preview if preview.exists() else pdir / project["source_file"]
    return _media_response(path, request)


@app.get("/api/projects/{pid}/transcript")
def project_transcript(pid: str) -> dict[str, Any]:
    _project_or_404(pid)
    tr = pipeline.load_transcript(pid)
    if tr is None:
        raise HTTPException(404, "Aún no hay transcripción")
    return tr


# ---------------------------------------------------------------- clips
@app.get("/api/projects/{pid}/clips/{cid}")
def get_clip(pid: str, cid: str) -> dict[str, Any]:
    project = _project_or_404(pid)
    clip = dict(_clip_or_404(project, cid))
    clip["subtitle_words"] = pipeline.clip_source_words(pid, clip)
    return clip


class Word(BaseModel):
    w: str
    start: float
    end: float
    hl: Optional[bool] = None
    p: Optional[float] = None


class SeoUpdate(BaseModel):
    titles: Optional[list[str]] = None
    description: Optional[str] = None
    hashtags: Optional[list[str]] = None
    pinned_comment: Optional[str] = None


class ClipUpdate(BaseModel):
    title: Optional[str] = None
    start: Optional[float] = Field(None, ge=0)
    end: Optional[float] = Field(None, ge=0)
    words: Optional[list[Word]] = None
    reset_words: bool = False
    seo: Optional[SeoUpdate] = None
    allow_open_ending: Optional[bool] = None


@app.put("/api/projects/{pid}/clips/{cid}")
def update_clip(pid: str, cid: str, body: ClipUpdate) -> dict[str, Any]:
    project = _project_or_404(pid)
    clip = _clip_or_404(project, cid)
    if jobs.is_running(f"render:{pid}:{cid}"):
        raise HTTPException(409, "El clip se está exportando.")
    duration = project["media"]["duration"]
    start = body.start if body.start is not None else clip["start"]
    end = body.end if body.end is not None else clip["end"]
    if end > duration + 0.01 or end - start < 3:
        raise HTTPException(400, "Tiempos no válidos (mínimo 3 s y dentro de la duración del video).")

    def fn(p: dict[str, Any]) -> None:
        c = storage.find_clip(p, cid)
        video_changed = False
        if body.title is not None:
            c["title"] = body.title.strip()[:100]
        if (start, end) != (c["start"], c["end"]):
            c["start"], c["end"], c["duration"] = round(start, 2), round(end, 2), round(end - start, 2)
            if c.get("words"):  # conserva ediciones dentro del nuevo rango
                c["words"] = [w for w in c["words"] if w["end"] > start and w["start"] < end] or None
            video_changed = True
        if body.reset_words:
            c["words"] = None
            video_changed = True
        if body.words is not None:
            c["words"] = [w.model_dump() for w in body.words if w.w.strip()
                          and w.end > c["start"] and w.start < c["end"]]
            video_changed = True
        if body.seo is not None:
            c.setdefault("seo", {}).update({k: v for k, v in body.seo.model_dump().items() if v is not None})
        if body.allow_open_ending is not None:
            c["allow_open_ending"] = body.allow_open_ending
            video_changed = True
        if video_changed and c.get("render"):
            c["status"] = "edited"  # la exportación anterior ya no corresponde
            c["qc"] = None
    updated = storage.update_project(pid, fn)
    return storage.find_clip(updated, cid)


class RenderOptions(BaseModel):
    layout: str = "auto"
    zoom: str = "suave"
    subtitles: bool = True
    remove_pauses: bool = True


@app.post("/api/projects/{pid}/clips/{cid}/render", status_code=202)
def render_clip(pid: str, cid: str, body: RenderOptions) -> dict[str, Any]:
    project = _project_or_404(pid)
    _clip_or_404(project, cid)
    if body.layout not in ("auto", "crop", "fit") or body.zoom not in ("off", "suave", "normal"):
        raise HTTPException(400, "Opciones de edición no válidas")
    review = rights.evaluate(project.get("rights", {}))
    if not review["can_process"]:
        raise HTTPException(403, "Derechos BLOCKED.")
    if project.get("status") != "ready":
        raise HTTPException(409, "El proyecto aún no termina de procesarse.")
    key = f"render:{pid}:{cid}"
    ok = jobs.submit(key, pipeline.render_and_check, pid, cid, body.model_dump(),
                     on_error=lambda exc: pipeline.mark_clip_error(pid, cid, exc))
    if not ok:
        raise HTTPException(409, "Este clip ya se está exportando.")

    def fn(p: dict[str, Any]) -> None:
        c = storage.find_clip(p, cid)
        c["status"] = "queued"
        c["render_progress"] = 0
        c["error"] = None
    return storage.find_clip(storage.update_project(pid, fn), cid)


@app.get("/api/projects/{pid}/clips/{cid}/output")
def clip_output(pid: str, cid: str, request: Request) -> Response:
    """Vista previa del clip editado (aunque no haya pasado el control de calidad)."""
    project = _project_or_404(pid)
    clip = _clip_or_404(project, cid)
    if not clip.get("render"):
        raise HTTPException(404, "El clip aún no se ha exportado")
    return _media_response(storage.project_dir(pid) / "clips" / clip["render"]["output"], request)


def _safe_name(s: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", s, flags=re.UNICODE).strip().replace(" ", "_")
    return s[:60] or "short"


@app.get("/api/projects/{pid}/clips/{cid}/download")
def clip_download(pid: str, cid: str, request: Request, kind: str = "mp4") -> Response:
    """Descarga final: solo si derechos APPROVED y control de calidad PASS."""
    project = _project_or_404(pid)
    clip = _clip_or_404(project, cid)
    review = rights.evaluate(project.get("rights", {}))
    if not clip.get("render") or not clip.get("qc"):
        raise HTTPException(404, "El clip aún no se ha exportado")
    if review["status"] != "APPROVED":
        raise HTTPException(403, f"Exportación bloqueada: derechos en estado {review['status']}.")
    if clip["qc"]["status"] != "PASS" or clip.get("status") != "exported":
        raise HTTPException(409, "Exportación bloqueada: el control de calidad no pasó o el clip cambió.")
    base = _safe_name(clip.get("title") or cid)
    clips_dir = storage.project_dir(pid) / "clips"
    if kind == "srt" and clip["render"].get("srt"):
        return FileResponse(clips_dir / clip["render"]["srt"], media_type="text/plain",
                            filename=f"{base}.srt")
    if kind == "metadata":
        seo = clip.get("seo", {})
        text = (f"TÍTULO:\n{clip.get('title', '')}\n\nOPCIONES DE TÍTULO:\n" + "\n".join(seo.get("titles", []))
                + f"\n\nDESCRIPCIÓN:\n{seo.get('description', '')}\n\nHASHTAGS:\n{' '.join(seo.get('hashtags', []))}"
                + f"\n\nCOMENTARIO FIJADO:\n{seo.get('pinned_comment', '')}\n")
        return Response(text, media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{base}.txt"'})
    return _media_response(clips_dir / clip["render"]["output"], request, download_name=f"{base}.mp4")


class CoverRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=120)
    at: Optional[float] = Field(None, ge=0)
    layout: str = "auto"


@app.post("/api/projects/{pid}/covers")
def generate_covers(pid: str, regenerate: bool = False) -> dict[str, Any]:
    """Crea las portadas que falten (o todas con ?regenerate=true)."""
    project = _project_or_404(pid)
    if project.get("status") != "ready":
        raise HTTPException(409, "El proyecto aún no termina de procesarse.")
    if not rights.evaluate(project.get("rights", {}))["can_process"]:
        raise HTTPException(403, "Derechos BLOCKED.")
    created = pipeline.make_missing_covers(pid, regenerate=str(regenerate).lower() in ("1", "true"))
    return {"created": created, "project": _public(storage.load_project(pid))}


@app.post("/api/projects/{pid}/clips/{cid}/cover")
def regenerate_cover(pid: str, cid: str, body: CoverRequest) -> dict[str, Any]:
    project = _project_or_404(pid)
    _clip_or_404(project, cid)
    if body.layout not in ("auto", "crop", "fit"):
        raise HTTPException(400, "Encuadre no válido")
    if body.at is not None and body.at > project["media"]["duration"]:
        raise HTTPException(400, "El tiempo está fuera del video.")
    if not rights.evaluate(project.get("rights", {}))["can_process"]:
        raise HTTPException(403, "Derechos BLOCKED.")
    try:
        pipeline.make_cover(pid, cid, text=body.text, at=body.at, layout=body.layout)
    except media.MediaError as exc:
        raise HTTPException(500, f"No se pudo crear la portada: {exc}")
    return storage.find_clip(storage.load_project(pid), cid)


@app.get("/api/projects/{pid}/clips/{cid}/cover")
def clip_cover(pid: str, cid: str, download: bool = False) -> Response:
    """Vista previa de la portada; con ?download=true exige derechos APPROVED."""
    project = _project_or_404(pid)
    clip = _clip_or_404(project, cid)
    if not clip.get("cover"):
        raise HTTPException(404, "Este clip aún no tiene portada")
    path = storage.project_dir(pid) / "clips" / clip["cover"]["file"]
    if str(download).lower() in ("1", "true"):
        status = rights.evaluate(project.get("rights", {}))["status"]
        if status != "APPROVED":
            raise HTTPException(403, f"Descarga bloqueada: derechos en estado {status}.")
        return FileResponse(path, media_type="image/jpeg",
                            filename=f"{_safe_name(clip.get('title') or cid)}_portada.jpg")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@app.get("/api/projects/{pid}/clips/{cid}/thumbnail")
def clip_thumbnail(pid: str, cid: str) -> Response:
    project = _project_or_404(pid)
    clip = _clip_or_404(project, cid)
    if not clip.get("thumbnail"):
        raise HTTPException(404, "Sin miniatura")
    return FileResponse(storage.project_dir(pid) / "clips" / clip["thumbnail"], media_type="image/jpeg")


@app.exception_handler(storage.ProjectNotFound)
def _nf(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse({"detail": "Proyecto no encontrado"}, status_code=404)


# ---------------------------------------------------------------- interfaz
@app.get("/")
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
