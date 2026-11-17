"""Pruebas de la API con FastAPI TestClient (Whisper simulado para que sean rápidas)."""
from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from .conftest import APPROVED_RIGHTS, fake_transcript  # noqa: E402


@pytest.fixture()
def client(data_dir, monkeypatch):
    from app.services import transcribe
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **k: fake_transcript(60))
    from app.main import app
    return TestClient(app)


def _wait(fn, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = fn()
        if r is not None:
            return r
        time.sleep(0.3)
    raise TimeoutError


def _upload(client, path, **over):
    form = {k: str(v).lower() if isinstance(v, bool) else v for k, v in {**APPROVED_RIGHTS, **over}.items()}
    with open(path, "rb") as fh:
        return client.post("/api/projects", data=form, files={"file": (path.name, fh, "video/mp4")})


def test_full_flow(client, sample_video):
    assert client.get("/api/health").json()["ffmpeg"]
    assert client.get("/").status_code == 200

    assert _upload(client, sample_video, confirmed=False).status_code == 403

    r = _upload(client, sample_video)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    p = _wait(lambda: (lambda j: j if j["status"] in ("ready", "error") else None)(
        client.get(f"/api/projects/{pid}").json()))
    assert p["status"] == "ready", p["progress"]
    assert p["clips"]
    cid = p["clips"][0]["id"]

    r = client.get(f"/api/projects/{pid}/media", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100

    words = client.get(f"/api/projects/{pid}/clips/{cid}").json()["subtitle_words"]
    words[0]["w"] = "EDITADO"
    r = client.put(f"/api/projects/{pid}/clips/{cid}", json={"words": words})
    assert r.status_code == 200 and r.json()["words"][0]["w"] == "EDITADO"

    r = client.post(f"/api/projects/{pid}/clips/{cid}/render", json={"layout": "fit", "zoom": "suave"})
    assert r.status_code == 202
    c = _wait(lambda: (lambda j: j if j["status"] in ("exported", "qc_failed", "error") else None)(
        client.get(f"/api/projects/{pid}/clips/{cid}").json()))
    assert c["status"] == "exported", c.get("error") or c.get("qc")
    r = client.get(f"/api/projects/{pid}/clips/{cid}/download")
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4"

    # Si los derechos dejan de estar claros, la descarga se bloquea.
    body = {**APPROVED_RIGHTS, "third_party_music": "unknown"}
    assert client.put(f"/api/projects/{pid}/rights", json=body).status_code == 200
    assert client.get(f"/api/projects/{pid}/clips/{cid}/download").status_code == 403

    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_rejects_bad_extension(client, tmp_path):
    bad = tmp_path / "x.avi"
    bad.write_bytes(b"0" * 100)
    assert _upload(client, bad).status_code == 400
