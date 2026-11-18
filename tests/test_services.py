"""Pruebas de los servicios (no requieren FastAPI ni Faster-Whisper)."""
from __future__ import annotations

from app.services import highlights, media, rights, seo, signals, subtitles, text
from app.services.render import keep_intervals, remap, remap_words, zoom_expr

from .conftest import fake_transcript


# ---------------------------------------------------------------- FFmpeg
def test_probe_reports_duration_resolution_audio(sample_video):
    info = media.probe(sample_video)
    assert abs(info["duration"] - 60) < 0.5
    assert (info["width"], info["height"]) == (1280, 720)
    assert info["has_audio"] and info["audio_codec"] == "aac"
    assert info["orientation"] == "horizontal"
    assert media.validate_source(info) == []


def test_extract_audio_and_energy_detects_peak(sample_video, tmp_path):
    wav = media.extract_audio(sample_video, tmp_path / "a.wav")
    energy = signals.audio_energy(wav)
    db = energy["db"]
    assert 120 <= len(db) <= 121  # 60 s / 0.5 s (+ relleno del códec AAC)
    peak_idx = max(range(len(db)), key=db.__getitem__)
    assert 28 <= peak_idx * energy["hop"] <= 30.5
    assert db[peak_idx] - energy["median"] > 9


def test_scene_changes_runs(sample_video):
    assert isinstance(signals.scene_changes(sample_video), list)


# ---------------------------------------------------------------- texto
def test_reactions_and_important_words():
    assert text.reaction_hits("¡No manches, jajaja!") >= 2
    assert text.reaction_hits("Vamos a revisar el inventario") <= 1
    assert text.is_important_word("jajaja")
    assert text.is_important_word("increíble!")
    assert not text.is_important_word("de")


# ---------------------------------------------------------------- momentos
def test_highlights_scores_and_bounds(sample_video, tmp_path):
    wav = media.extract_audio(sample_video, tmp_path / "a.wav")
    energy = signals.audio_energy(wav)
    tr = fake_transcript(60)
    clips = highlights.find_highlights(tr, 60, energy, [])
    assert clips, "debería proponer al menos un clip"
    for c in clips:
        assert 0 <= c["score"] <= 100
        assert 19 <= c["duration"] <= 61
        assert c["reasons"] and c["text"]
    # No se solapan más de un 25 %.
    for i, a in enumerate(clips):
        for b in clips[i + 1:]:
            ov = min(a["end"], b["end"]) - max(a["start"], b["start"])
            assert ov <= 0.25 * min(a["duration"], b["duration"]) + 0.7
    # El mejor clip debería incluir el pico de audio + reacciones (≈ 28–30 s).
    assert clips[0]["start"] <= 29 <= clips[0]["end"]


def test_highlights_empty_transcript():
    assert highlights.find_highlights({"segments": []}, 60) == []


def test_highlights_never_invent_dialogue():
    tr = fake_transcript(60)
    original = " ".join(s["text"] for s in tr["segments"])
    for c in highlights.find_highlights(tr, 60):
        assert c["text"] in original


# ---------------------------------------------------------------- edición
def test_keep_intervals_removes_long_pauses():
    words = [{"w": "a", "start": 1.0, "end": 1.3}, {"w": "b", "start": 1.4, "end": 1.7},
             {"w": "c", "start": 4.0, "end": 4.3}]
    iv = keep_intervals(words, 0.8, 4.6, True)
    assert len(iv) == 2
    total = sum(b - a for a, b in iv)
    assert total < 3.8 - 1.5
    assert remap(4.0, iv) is not None and remap(3.0, iv) is None
    rw = remap_words(words, iv)
    assert [w["w"] for w in rw] == ["a", "b", "c"]
    assert rw[2]["start"] < 2.0
    assert keep_intervals(words, 0.8, 4.6, False) == [(0.8, 4.6)]


def test_zoom_expression():
    assert zoom_expr([], 0.1) == "1"
    expr = zoom_expr([(1.0, 2.5)], 0.07)
    assert expr.startswith("(1+0.07*") and "clip(" in expr


def test_ass_subtitles_word_by_word():
    words = [{"w": "Hola", "start": 0.1, "end": 0.4, "hl": None},
             {"w": "jajaja!", "start": 0.5, "end": 0.9, "hl": None},
             {"w": "increíble", "start": 1.0, "end": 1.5, "hl": True}]
    ass = subtitles.build_ass(words)
    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    assert len(dialogues) == 3  # un evento por palabra
    assert subtitles.COLOR_CURRENT in ass and subtitles.COLOR_IMPORTANT in ass
    assert "INCREÍBLE" in ass
    assert subtitles.check_safe_area(ass) == []
    srt = subtitles.build_srt(words)
    assert "-->" in srt and "Hola" in srt


# ---------------------------------------------------------------- derechos
def test_rights_rules():
    from .conftest import APPROVED_RIGHTS
    assert rights.evaluate(APPROVED_RIGHTS)["status"] == "APPROVED"
    assert rights.evaluate({**APPROVED_RIGHTS, "confirmed": False})["status"] == "BLOCKED"
    assert rights.evaluate({**APPROVED_RIGHTS, "permission_type": "none"})["status"] == "BLOCKED"
    assert rights.evaluate({**APPROVED_RIGHTS, "third_party_music": "unknown"})["status"] == "REVIEW REQUIRED"
    assert rights.evaluate({**APPROVED_RIGHTS, "third_party_footage": "yes"})["status"] == "REVIEW REQUIRED"
    r = rights.evaluate({**APPROVED_RIGHTS, "permission_type": "written_permission", "evidence": ""})
    assert r["status"] == "REVIEW REQUIRED" and not r["can_export"] and r["can_process"]


# ---------------------------------------------------------------- SEO
def test_seo_uses_real_phrases():
    clip = {"text": "Hoy vamos a probar el mapa. ¡No manches, jajaja, qué susto! Bueno, sigamos."}
    meta = seo.generate(clip, creator="ElMariana", language="es", source_url="https://ejemplo.com/v")
    assert len(meta["titles"]) == 3
    assert "No manches" in meta["titles"][0]
    assert all(len(t) <= 72 for t in meta["titles"])
    assert meta["hashtags"][0] == "#shorts" and "#elmariana" in meta["hashtags"]
    assert "https://ejemplo.com/v" in meta["description"]
    assert "viral" not in (meta["description"] + " ".join(meta["titles"])).lower()


def test_seo_avoids_repeated_titles():
    used: set[str] = set()
    clip = {"text": "¡No manches, jajaja, qué susto! Miren esto, está muy raro."}
    a = seo.generate(clip, used_quotes=used)["titles"][0]
    b = seo.generate(clip, used_quotes=used)["titles"][0]
    assert a != b


def test_framing_survives_broken_opencv(sample_video, monkeypatch):
    """Regresión: en Codespaces apareció un cv2 sin CascadeClassifier y el render fallaba."""
    import sys
    import types

    from app.services import framing
    monkeypatch.setitem(sys.modules, "cv2", types.ModuleType("cv2"))
    res = framing.detect_subject(sample_video, 0, 10)
    assert res["face_found"] is False and res["center_x"] == 0.5
    assert res["detector"].startswith("no disponible")
    assert framing.opencv_status() == "instalación incompleta"


# ---------------------------------------------------------------- portadas
def test_cover_text_helpers():
    from app.services import cover
    assert cover.default_cover_text("ElMariana: “Espera, espera, ¿qué fue eso?”") == "Espera, espera, ¿qué fue eso?"
    assert cover.clean_text("Hola 😂🔥 chat") == "Hola chat"
    lines = cover.wrap_lines("UNA FRASE MUY LARGA QUE NO CABE EN UNA SOLA LÍNEA DE LA PORTADA PARA NADA")
    assert len(lines) <= cover.MAX_LINES and lines[-1].endswith("…")
    ass = cover.build_cover_ass("¡No manches, jajaja!")
    assert "JAJAJA" in ass and cover.YELLOW in ass


def test_generate_cover_1080x1920(sample_video, tmp_path):
    from app.services import cover
    info = media.probe(sample_video)
    energy = signals.audio_energy(media.extract_audio(sample_video, tmp_path / "a.wav"))
    words = [w for s in fake_transcript(60)["segments"] for w in s["words"]]
    clip = {"id": "c1", "start": 18.0, "end": 42.0, "title": "“¡No manches, jajaja, qué susto!” 😂"}
    res = cover.generate_cover(sample_video, info, clip, words, energy, tmp_path)
    out = tmp_path / res["file"]
    probe = media.probe(out)
    assert (probe["width"], probe["height"]) == (1080, 1920)
    assert res["size_bytes"] < 2 * 1024 * 1024
    assert 18.5 <= res["at"] <= 41.5
    assert res["text"] == "¡No manches, jajaja, qué susto!"
    manual = cover.generate_cover(sample_video, info, clip, words, energy, tmp_path, text="Otro texto", at=5)
    assert manual["at"] == 5 and manual["reason"] == "elegido a mano"
