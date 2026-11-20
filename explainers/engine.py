"""Motor reutilizable para videos explicativos verticales (1080x1920, 30 fps).

Cada video define sus escenas: (nombre, función_de_dibujo(t, dur) -> Image RGBA, duración_base, narración).
El motor se encarga de la voz (Piper o Kokoro), de alargar cada escena a lo que dura su
narración, de los fundidos, la barra de progreso, la música con "ducking" y la exportación.
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import wave
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

W, H, FPS = 1080, 1920, 30
YELLOW = (255, 214, 10)
WHITE = (255, 255, 255)
RED = (255, 59, 48)
XFADE = 8           # fotogramas de fundido entre escenas (dentro del archivo de la escena)
VOICE_LEAD = 0.25   # aire antes de que hable cada escena
VOICE_TAIL = 0.55   # aire después de la última palabra
SR = 44100


def _pick_font(*paths: str) -> str:
    for p in paths:
        if os.path.exists(p):
            return p
    raise SystemExit("No se encontró una fuente gruesa. Instala: sudo apt-get install -y fonts-dejavu-core")


FONT = _pick_font("/usr/share/fonts/opentype/inter/Inter-Black.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_SB = _pick_font("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
_fonts: dict = {}


def font(size: int, path: str = FONT) -> ImageFont.FreeTypeFont:
    k = (size, path)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(path, size)
    return _fonts[k]


# ------------------------------------------------------------------ utilidades de dibujo
def lerp(a, b, t): return a + (b - a) * t
def clamp(x, lo=0.0, hi=1.0): return max(lo, min(hi, x))
def ease(t): t = clamp(t); return t * t * (3 - 2 * t)
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def mix(c1, c2, t): return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def gradient(stops) -> np.ndarray:
    ys = np.linspace(0, 1, H)
    col = np.zeros((H, 3), np.float32)
    for ch in range(3):
        col[:, ch] = np.interp(ys, [p for p, _ in stops], [c[ch] for _, c in stops])
    return np.repeat(col[:, None, :], W, axis=1)


def to_img(arr) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def glow(radius: int, color, strength: float = 1.0) -> Image.Image:
    size = radius * 2
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2) / radius
    a = np.clip(1 - d, 0, 1) ** 2.2 * 255 * strength
    img = np.zeros((size, size, 4), np.uint8)
    img[..., 0], img[..., 1], img[..., 2] = color
    img[..., 3] = np.clip(a, 0, 255)
    return Image.fromarray(img, "RGBA")


def paste_center(base: Image.Image, overlay: Image.Image, cx: float, cy: float) -> None:
    base.alpha_composite(overlay, (int(cx - overlay.width / 2), int(cy - overlay.height / 2)))


def _layout(words, size, max_w):
    f = font(size)
    lines, cur, cur_w = [], [], 0.0
    space = f.getlength(" ")
    for w in words:
        ww = f.getlength(w[0])
        if cur and cur_w + space + ww > max_w:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur.append(w)
        cur_w += (space if len(cur) > 1 else 0) + ww
    if cur:
        lines.append(cur)
    return lines


def draw_text(img, text, t, start, y, size=96, color=WHITE, per_word=0.085, max_w=900, out_at=None):
    """Texto que entra palabra por palabra. Las palabras con *asterisco* van en amarillo."""
    if t < start:
        return
    words = [(w.replace("*", ""), w.startswith("*")) for w in text.split()]
    lines = _layout(words, size, max_w)
    f = font(size)
    line_h = int(size * 1.12)
    fade_out = 1.0 if out_at is None else 1 - ease((t - out_at) / 0.25)
    i = 0
    for li, line in enumerate(lines):
        space = f.getlength(" ")
        total = sum(f.getlength(w) for w, _ in line) + space * (len(line) - 1)
        x = (W - total) / 2
        for w, is_hl in line:
            p = ease_out((t - start - i * per_word) / 0.22)
            a = p * fade_out
            if a > 0.01:
                dy = (1 - p) * 26
                c = YELLOW if is_hl else color
                txt = Image.new("RGBA", (int(f.getlength(w)) + 40, line_h + 40), (0, 0, 0, 0))
                td = ImageDraw.Draw(txt)
                td.text((25, 27), w, font=f, fill=(0, 0, 0, 150))
                td.text((20, 20), w, font=f, fill=c + (255,), stroke_width=max(4, size // 14), stroke_fill=(0, 0, 0, 255))
                if a < 1:
                    txt.putalpha(txt.getchannel("A").point(lambda v: int(v * a)))
                img.alpha_composite(txt, (int(x - 20), int(y + li * line_h + dy - 20)))
            x += f.getlength(w) + space
            i += 1


def badge(img, text, cx, cy, t, color=RED, size=54):
    """Etiqueta tipo 'EN VIVO' / 'HORA 3' con punto parpadeante."""
    d = ImageDraw.Draw(img)
    f = font(size)
    w = f.getlength(text) + 110
    h = size + 36
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=h / 2, fill=(0, 0, 0, 170),
                        outline=color + (255,), width=4)
    on = 0.5 + 0.5 * math.sin(t * 7)
    r = 13
    d.ellipse([cx - w / 2 + 28 - r, cy - r, cx - w / 2 + 28 + r, cy + r], fill=mix((90, 20, 20), color, on) + (255,))
    d.text((cx + 22, cy), text, font=f, anchor="mm", fill=WHITE + (255,))


def progress_bar(img, gt, total):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=(0, 0, 0, 90))
    d.rectangle([0, 0, int(W * gt / total), 10], fill=YELLOW + (255,))


# ------------------------------------------------------------------ audio
def read_mono(path, sr=SR) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        rate, ch, n = wf.getframerate(), wf.getnchannels(), wf.getnframes()
        x = np.frombuffer(wf.readframes(n), np.int16).astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if rate != sr:
        t_old = np.arange(len(x)) / rate
        t_new = np.arange(int(len(x) * sr / rate)) / sr
        x = np.interp(t_new, t_old, x).astype(np.float32)
    return x


def note(m: float) -> float:
    return 440 * 2 ** ((m - 69) / 12)


def write_stereo(path, mono: np.ndarray) -> None:
    stereo = np.stack([mono, np.roll(mono, 220)], axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(stereo, -1, 1) * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ video
class Explainer:
    """scenes: [(nombre, fn(t, dur, state) -> Image RGBA, duración_base, narración), ...]
    music_fn(total, durs) -> np.ndarray mono a 44.1 kHz (sin normalizar)."""

    def __init__(self, slug: str, scenes, music_fn: Callable, default_voice: str = "kokoro:em_alex",
                 preview_times=None):
        self.slug = slug
        self.scenes = list(scenes)
        self.music_fn = music_fn
        self.default_voice = default_voice
        self.preview_times = preview_times or [(i, min(2.5, s[2] / 2)) for i, s in enumerate(scenes)]
        self.out = ROOT / "data" / "explicativos" / slug
        self.durs = [s[2] for s in self.scenes]

    @property
    def total(self) -> float:
        return sum(self.durs)

    def start_of(self, idx: int) -> float:
        return sum(self.durs[:idx])

    def frame(self, idx, t, prev_last=None, fi=0) -> Image.Image:
        _, fn, _, _ = self.scenes[idx]
        img = fn(t, self.durs[idx])
        progress_bar(img, self.start_of(idx) + t, self.total)
        rgb = img.convert("RGB")
        if prev_last is not None and fi < XFADE:
            rgb = Image.blend(prev_last, rgb, (fi + 1) / (XFADE + 1))
        return rgb

    def prepare_voice(self, voice_name: str) -> list[str]:
        from app.services import voice as V
        work = self.out / "voz" / voice_name.replace(":", "_")
        work.mkdir(parents=True, exist_ok=True)
        wavs = []
        for i, (name, _, base, text) in enumerate(self.scenes):
            out = work / f"{i + 1:02d}.wav"
            V.synthesize(text, out, voice=voice_name)
            vlen = V.wav_duration(out)
            self.durs[i] = round(max(base, VOICE_LEAD + vlen + VOICE_TAIL), 2)
            wavs.append(str(out))
            print(f"voz {name}: {vlen:.1f} s", flush=True)
        return wavs

    def voice_track(self, wavs) -> np.ndarray:
        track = np.zeros(int((self.total + 1) * SR), np.float32)
        for i, path in enumerate(wavs):
            x = read_mono(path)
            s0 = int((self.start_of(i) + VOICE_LEAD) * SR)
            track[s0:s0 + len(x)] += x[:max(len(track) - s0, 0)]
        return track

    def render_scene(self, idx, prev_last):
        name = self.scenes[idx][0]
        n = int(round(self.durs[idx] * FPS))
        scenes_dir = self.out / "scenes"
        tmp, final = scenes_dir / f"{name}.tmp.mp4", scenes_dir / f"{name}.mp4"
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                              "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                              "-pix_fmt", "yuv420p", "-r", str(FPS), str(tmp)], stdin=subprocess.PIPE)
        last = None
        for fi in range(n):
            last = self.frame(idx, fi / FPS, prev_last, fi)
            p.stdin.write(last.tobytes())
        p.stdin.close()
        if p.wait() != 0:
            raise SystemExit(f"ffmpeg falló en la escena {name}")
        os.replace(tmp, final)
        return last

    def mix_audio(self, path, voice: np.ndarray | None) -> None:
        n = int((self.total + 1) * SR)
        music = np.zeros(n, np.float32)
        m = self.music_fn(self.total, self.durs)
        music[:min(n, len(m))] = m[:n]
        fade = int(1.5 * SR)
        end = int(self.total * SR)
        music[end - fade:end] *= np.linspace(1, 0, fade)
        music[end:] = 0
        music /= np.max(np.abs(music)) + 1e-6
        out = 0.8 * music
        if voice is not None:
            v = np.zeros(n, np.float32)
            v[:min(n, len(voice))] = voice[:n]
            env = np.convolve(np.abs(v), np.ones(int(0.25 * SR)) / (0.25 * SR), mode="same")
            duck = 1 - 0.7 * np.clip(env / 0.03, 0, 1)
            out = 0.32 * music * duck + 0.9 * v / (np.max(np.abs(v)) + 1e-6)
        out /= max(1.0, np.max(np.abs(out)) / 0.95)
        write_stereo(path, out)

    def run(self, argv=None) -> None:
        ap = argparse.ArgumentParser(description=f"Video explicativo: {self.slug}")
        ap.add_argument("modo", nargs="?", default="render", choices=["render", "frames"])
        ap.add_argument("--sin-voz", action="store_true")
        ap.add_argument("--voz", default=None, help=f"por defecto {self.default_voice}")
        args = ap.parse_args(argv)
        self.out.mkdir(parents=True, exist_ok=True)

        if args.modo == "frames":
            pdir = self.out / "preview"
            pdir.mkdir(exist_ok=True)
            for idx, t in self.preview_times:
                self.frame(idx, t).save(pdir / f"{self.scenes[idx][0]}_{t}.jpg", quality=88)
            print("Fotogramas en", pdir)
            return

        voice = None
        voice_name = args.voz or self.default_voice
        if not args.sin_voz:
            from app.services import voice as V
            if not V.engine_available(voice_name):
                pkg = "kokoro-onnx" if V.is_kokoro(voice_name) else "piper-tts"
                raise SystemExit(f"El motor de voz no está instalado. Ejecuta: pip install {pkg}\n"
                                 "(o usa --sin-voz para hacer el video solo con texto y música)")
            voice = self.voice_track(self.prepare_voice(voice_name))

        (self.out / "scenes").mkdir(exist_ok=True)
        prev = None
        for idx in range(len(self.scenes)):
            prev = self.render_scene(idx, prev)
            print("escena", self.scenes[idx][0], "ok", flush=True)
        lst = self.out / "scenes" / "list.txt"
        lst.write_text("".join(f"file '{s[0]}.mp4'\n" for s in self.scenes), encoding="utf-8")
        audio = self.out / "audio.wav"
        self.mix_audio(audio, voice)
        silent = self.out / "silent.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                        str(silent)], check=True)
        suffix = "sin_voz" if args.sin_voz else voice_name.replace(":", "_")
        final = self.out / f"{self.slug}_{suffix}.mp4"
        tmp = final.with_name(final.stem + ".tmp.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(audio), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                        "-shortest", "-movflags", "+faststart", str(tmp)], check=True)
        os.replace(tmp, final)
        print(f"Listo: {final} ({self.total:.1f} s)")
