"""Transcribe un video con Whisper (gratis, corre local) y guarda tiempos palabra por palabra.

Uso:
    python -m studio.transcribe input/video.mp4 [--model small|medium|large-v3] [--lang es]

Genera:
    work/<nombre>/transcript.json   -> palabras con inicio/fin (lo usa el render)
    work/<nombre>/transcript.txt    -> versión legible con tiempos (la lee Claude para editar)
    work/<nombre>/info.json         -> duración, resolución, fps, picos de volumen
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    info = {"duration": float(data["format"]["duration"]), "has_audio": a is not None}
    if v:
        num, den = (v.get("avg_frame_rate") or "30/1").split("/")
        fps = float(num) / float(den) if float(den) else 30.0
        w, h = int(v["width"]), int(v["height"])
        rot = 0
        for sd in v.get("side_data_list", []):
            if "rotation" in sd:
                rot = int(sd["rotation"])
        if abs(rot) in (90, 270):
            w, h = h, w
        info.update({"width": w, "height": h, "fps": round(fps, 3)})
    return info


def load_audio(path: Path, sr=16000) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def loudness_peaks(audio: np.ndarray, sr=16000, top=12) -> list[dict]:
    """Momentos con más energía (gritos, risas, golpes): pistas para zooms y efectos."""
    hop = sr // 10
    n = len(audio) // hop
    if n < 5:
        return []
    rms = np.sqrt(np.mean(audio[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    med = np.median(db)
    order = np.argsort(db)[::-1]
    picks: list[int] = []
    for i in order:
        if db[i] < med + 6:
            break
        if all(abs(i - j) > 15 for j in picks):
            picks.append(int(i))
        if len(picks) >= top:
            break
    return [{"t": round(i * 0.1, 2), "db_over_median": round(float(db[i] - med), 1)} for i in sorted(picks)]


def transcribe(video: Path, model_name="small", lang=None) -> Path:
    from faster_whisper import WhisperModel

    name = video.stem
    wd = ROOT / "work" / name
    wd.mkdir(parents=True, exist_ok=True)

    info = probe(video)
    audio = load_audio(video) if info["has_audio"] else np.zeros(16000, dtype=np.float32)
    info["loud_moments"] = loudness_peaks(audio)
    info["source"] = str(video)

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, meta = model.transcribe(
        audio, language=lang, word_timestamps=True, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300}, beam_size=5,
    )
    words, segs = [], []
    for s in segments:
        sw = []
        for w in s.words or []:
            item = {"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "p": round(w.probability, 2)}
            if item["w"]:
                words.append(item)
                sw.append(item)
        segs.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        print(f"[{s.start:7.2f} -> {s.end:7.2f}] {s.text.strip()}", flush=True)

    info["language"] = meta.language
    (wd / "transcript.json").write_text(json.dumps({"language": meta.language, "words": words, "segments": segs}, ensure_ascii=False, indent=1))
    (wd / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))

    # Versión legible: una línea por frase + palabras con tiempos (para elegir zooms/SFX al milímetro)
    lines = [f"# {name}  |  {info.get('width')}x{info.get('height')} @ {info.get('fps')}fps  |  {info['duration']:.1f}s  |  idioma: {meta.language}", ""]
    lines.append("## Momentos de volumen alto (posibles gritos/risas/golpes)")
    lines += [f"- {m['t']:.1f}s (+{m['db_over_median']} dB)" for m in info["loud_moments"]] or ["- ninguno"]
    lines.append("")
    lines.append("## Transcripción")
    for s in segs:
        lines.append(f"[{s['start']:.2f}-{s['end']:.2f}] {s['text']}")
        ws = [w for w in words if s["start"] - 0.05 <= w["start"] <= s["end"] + 0.05]
        lines.append("    " + " ".join(f"{w['w']}@{w['start']:.2f}" + ("?" if w["p"] < 0.5 else "") for w in ws))
    (wd / "transcript.txt").write_text("\n".join(lines))
    print(f"\nListo: {wd.relative_to(ROOT)}/transcript.txt")
    return wd


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--model", default="small", help="tiny/base/small/medium/large-v3 (más grande = más preciso y lento)")
    ap.add_argument("--lang", default=None, help="código de idioma, p.ej. es / en (auto si se omite)")
    a = ap.parse_args()
    transcribe(a.video.resolve(), a.model, a.lang)
