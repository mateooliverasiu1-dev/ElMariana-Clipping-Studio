"""Render real con FFmpeg + control de calidad sobre el archivo final."""
from __future__ import annotations

from app.services import media, quality, render, signals

from .conftest import fake_transcript


def _words(tr):
    return [w for s in tr["segments"] for w in s["words"]]


def test_render_vertical_short_and_qc_pass(sample_video, tmp_path):
    info = media.probe(sample_video)
    energy = signals.audio_energy(media.extract_audio(sample_video, tmp_path / "a.wav"))
    clip = {"id": "t1", "start": 18.0, "end": 42.0}
    words = render.clip_words(_words(fake_transcript(60)), clip["start"], clip["end"])
    rep = render.render_clip(sample_video, info, clip, words, energy, tmp_path / "out",
                             {"layout": "fit", "zoom": "suave"})
    out = tmp_path / "out" / rep["output"]
    probe = media.probe(out)
    assert (probe["width"], probe["height"]) == (1080, 1920)
    assert probe["video_codec"] == "h264" and probe["audio_codec"] == "aac"
    assert rep["cuts"] >= 1 and rep["removed_seconds"] > 0          # se recortaron pausas
    assert rep["subtitle_words"] == len(words)
    assert len(rep["zooms"]) >= 1                                    # zoom en la reacción
    assert abs(probe["duration"] - rep["duration"]) < 0.3

    edited = render.remap_words(words, [(t["source_start"], t["source_end"]) for t in rep["timeline"]])
    qc = quality.check(out, clip, rep, "APPROVED", edited, tmp_path / "out" / rep["ass"])
    errors = [p for p in qc["problems"] if p["level"] == "error"]
    assert qc["status"] == "PASS", errors
    assert -16.5 <= qc["metrics"]["integrated_lufs"] <= -11.5      # normalizado a ≈ -14 LUFS


def test_qc_fails_without_rights(sample_video, tmp_path):
    info = media.probe(sample_video)
    clip = {"id": "t2", "start": 5.0, "end": 30.0}
    rep = render.render_clip(sample_video, info, clip, [], None, tmp_path / "out",
                             {"layout": "crop", "zoom": "off", "subtitles": False, "remove_pauses": False})
    qc = quality.check(tmp_path / "out" / rep["output"], clip, rep, "REVIEW REQUIRED", [], None)
    assert qc["status"] == "FAIL"
    assert any(p["area"] == "derechos" for p in qc["problems"])


def test_qc_detects_wrong_format(sample_video, tmp_path):
    qc = quality.check(sample_video, {"start": 0, "end": 60}, {"options": {}}, "APPROVED")
    assert qc["status"] == "FAIL"
    assert any("Proporción" in p["message"] for p in qc["problems"])
