"""Voz con Piper: rutas de descarga y síntesis (con un Piper simulado, sin descargar modelos)."""
from __future__ import annotations

import sys
import types
import wave

from app.services import voice


def test_voice_url():
    assert voice.voice_url("es_MX-claude-high", ".onnx") == (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx")
    assert voice.voice_url("es_MX-ald-medium", ".onnx.json").endswith("es/es_MX/ald/medium/es_MX-ald-medium.onnx.json")


def test_synthesize_with_fake_piper(tmp_path, monkeypatch):
    calls = {}

    class FakeVoice:
        @staticmethod
        def load(path):
            calls["model"] = path
            return FakeVoice()

        def synthesize_wav(self, text, wf, syn_config=None):
            calls["length_scale"] = syn_config.length_scale
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
            wf.writeframes(b"\x00\x00" * 22050)

    fake = types.ModuleType("piper")
    fake.PiperVoice = FakeVoice
    fake.SynthesisConfig = lambda length_scale: types.SimpleNamespace(length_scale=length_scale)
    monkeypatch.setitem(sys.modules, "piper", fake)
    monkeypatch.setattr(voice, "VOICES_DIR", tmp_path)
    monkeypatch.setattr(voice, "_loaded", {})
    for suf in (".onnx", ".onnx.json"):
        (tmp_path / f"es_MX-claude-high{suf}").write_bytes(b"x")  # evita la descarga

    out = voice.synthesize("Hola chat", tmp_path / "a.wav", speed=1.25)
    assert abs(voice.wav_duration(out) - 1.0) < 0.01
    assert abs(calls["length_scale"] - 0.8) < 1e-6
    with wave.open(str(out)) as wf:
        assert wf.getframerate() == 22050
