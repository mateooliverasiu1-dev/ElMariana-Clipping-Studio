"""Biblioteca de efectos de sonido generados por código (100% originales, sin copyright).

Uso:
    python -m studio.sfx            # genera todos los .wav en assets/sfx/
    python -m studio.sfx --list     # lista los nombres disponibles

Puedes añadir tus propios efectos: deja cualquier .wav/.mp3 en assets/sfx/
y úsalo por su nombre de archivo (sin extensión) en el edit.json.
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np

SR = 48000
ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = ROOT / "assets" / "sfx"
RNG = np.random.default_rng(7)


# ---------------------------------------------------------------- utilidades
def t_axis(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def env_exp(dur: float, decay: float) -> np.ndarray:
    return np.exp(-t_axis(dur) * decay)


def adsr(n: int, a=0.005, d=0.05, s=0.7, r=0.1) -> np.ndarray:
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    s_n = max(0, n - a_n - d_n - r_n)
    e = np.concatenate([
        np.linspace(0, 1, a_n, endpoint=False),
        np.linspace(1, s, d_n, endpoint=False),
        np.full(s_n, s),
        np.linspace(s, 0, r_n),
    ])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def osc(freq, dur: float, kind="sine") -> np.ndarray:
    """Oscilador con frecuencia constante o variable (array)."""
    n = int(dur * SR)
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,)) if np.ndim(freq) == 0 else np.asarray(freq)[:n]
    ph = 2 * np.pi * np.cumsum(f) / SR
    if kind == "sine":
        return np.sin(ph)
    if kind == "square":
        return np.sign(np.sin(ph))
    if kind == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1.0) - 1
    if kind == "tri":
        return 2 * np.abs(2 * ((ph / (2 * np.pi)) % 1.0) - 1) - 1
    raise ValueError(kind)


def noise(dur: float) -> np.ndarray:
    return RNG.uniform(-1, 1, int(dur * SR))


def lowpass(x: np.ndarray, cutoff) -> np.ndarray:
    """Filtro paso bajo de un polo; cutoff puede variar en el tiempo."""
    c = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    a = 1 - np.exp(-2 * np.pi * c / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def highpass(x: np.ndarray, cutoff) -> np.ndarray:
    return x - lowpass(x, cutoff)


def bandpass(x, lo, hi):
    return lowpass(highpass(x, lo), hi)


def fft_filter(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def sat(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def norm(x, peak=0.89):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def fade(x, fin=0.002, fout=0.01):
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def place(dst: np.ndarray, src: np.ndarray, at: float, gain=1.0):
    i = int(at * SR)
    j = min(len(dst), i + len(src))
    dst[i:j] += src[: j - i] * gain
    return dst


def reverb(x, room=0.25, wet=0.25):
    """Reverb sencilla con varias líneas de retardo."""
    out = np.pad(x, (0, int(SR * (room * 4 + 0.2))))
    dry = out.copy()
    for k, d in enumerate([0.0297, 0.0371, 0.0411, 0.0437, 0.053, 0.067]):
        dl = int(d * SR * (1 + room * 3))
        g = 0.7 ** (k + 1) * 1.2
        tmp = np.zeros_like(out)
        tmp[dl:] = dry[:-dl] * g
        for rep in range(1, 5):
            off = dl * (rep + 1)
            if off < len(out):
                tmp[off:] += dry[:-off] * g * (0.55 ** rep)
        out = out + tmp * wet
    return out


# ---------------------------------------------------------------- efectos
def whoosh(dur=0.55, up=True):
    n = noise(dur)
    tt = t_axis(dur)
    sweep = (tt / dur) if up else (1 - tt / dur)
    cut = 300 + 5200 * sweep ** 1.5
    x = lowpass(highpass(n, 150), cut)
    e = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 1.6
    return fade(norm(x * e))


def swoosh_fast():
    return whoosh(0.28, up=True)


def pop():
    dur = 0.09
    tt = t_axis(dur)
    f = 900 * np.exp(-tt * 40) + 300
    x = osc(f, dur) * env_exp(dur, 45)
    x += highpass(noise(dur), 2000) * env_exp(dur, 300) * 0.3
    return fade(norm(x), 0.0005)


def bubble_pop():
    dur = 0.12
    tt = t_axis(dur)
    f = 400 + 2200 * (tt / dur) ** 0.7
    return fade(norm(osc(f, dur) * env_exp(dur, 30)))


def boom():
    """Golpe cinematográfico grave con cola (para revelaciones / momentos épicos)."""
    dur = 2.2
    tt = t_axis(dur)
    f = 38 + 90 * np.exp(-tt * 9)
    body = osc(f, dur) * env_exp(dur, 2.2)
    sub = osc(f * 0.5, dur) * env_exp(dur, 1.6) * 0.6
    click = lowpass(noise(dur), 1800) * env_exp(dur, 60) * 0.9
    x = sat(body + sub + click, 2.5)
    return fade(norm(reverb(x, 0.35, 0.18)), 0.0005, 0.3)


def impact():
    """Puñetazo/golpe seco."""
    dur = 0.45
    tt = t_axis(dur)
    thump = osc(60 + 120 * np.exp(-tt * 30), dur) * env_exp(dur, 12)
    crack = bandpass(noise(dur), 800, 6000) * env_exp(dur, 55)
    return fade(norm(sat(thump * 1.2 + crack * 0.8, 3)), 0.0005, 0.05)


def ding():
    dur = 1.6
    partials = [(1.0, 1.0), (2.76, 0.5), (5.40, 0.25), (8.93, 0.12)]
    base = 1318.5
    x = sum(a * osc(base * r, dur) * env_exp(dur, 3.0 + r * 1.2) for r, a in partials)
    return fade(norm(x), 0.001, 0.2)


def correct():
    """Dos notas ascendentes de 'acierto'."""
    out = np.zeros(int(0.5 * SR))
    for k, f in enumerate([880.0, 1318.5]):
        n = osc(f, 0.3, "tri") * env_exp(0.3, 9)
        place(out, n, k * 0.11, 0.8)
    return fade(norm(out))


def wrong_buzzer():
    dur = 0.7
    x = osc(110, dur, "square") * 0.6 + osc(116, dur, "saw") * 0.5
    x = lowpass(x, 1800) * adsr(int(dur * SR), 0.005, 0.05, 0.9, 0.08)
    return fade(norm(x))


def boing():
    dur = 0.75
    tt = t_axis(dur)
    f = 220 + 140 * np.sin(2 * np.pi * 14 * tt) * np.exp(-tt * 3) + 260 * tt
    x = osc(f, dur, "tri") * env_exp(dur, 4)
    return fade(norm(x))


def record_scratch():
    dur = 0.55
    tt = t_axis(dur)
    speed = np.abs(np.sin(2 * np.pi * 3.2 * tt)) ** 0.7
    base = noise(dur)
    x = bandpass(base, 300, 900 + 2600 * speed) * (0.3 + speed)
    x += osc(180 + 500 * speed, dur, "saw") * 0.15 * speed
    return fade(norm(sat(x, 2)) * env_exp(dur, 2.5))


def rimshot():
    """Ba-dum-tss (chiste malo)."""
    out = np.zeros(int(1.4 * SR))
    for at, f in [(0.0, 190), (0.16, 140)]:
        d = 0.25
        tt = t_axis(d)
        tom = osc(f * (1 + 0.6 * np.exp(-tt * 25)), d) * env_exp(d, 14)
        place(out, tom, at)
    d = 1.0
    cym = highpass(noise(d), 5000) * env_exp(d, 4.5) * 0.55
    snare = bandpass(noise(0.2), 1500, 7000) * env_exp(0.2, 30) * 0.8
    place(out, cym, 0.33)
    place(out, snare, 0.33)
    return fade(norm(out), 0.001, 0.1)


def sad_trombone():
    """Wah wah wah waaah (fracaso)."""
    notes = [(293.7, 0.38), (277.2, 0.38), (261.6, 0.38), (246.9, 1.1)]
    out = np.zeros(int(sum(d for _, d in notes) * SR) + SR // 4)
    at = 0.0
    for i, (f, d) in enumerate(notes):
        tt = t_axis(d)
        vib = 1 + (0.03 * np.sin(2 * np.pi * 6 * tt) * (tt / d) if i == 3 else 0.008 * np.sin(2 * np.pi * 5 * tt))
        x = osc(f * vib, d, "saw") * 0.6 + osc(f * 2 * vib, d, "saw") * 0.2
        wah = 400 + 1600 * np.sin(np.pi * np.clip(tt / d, 0, 1))
        x = lowpass(x, wah) * adsr(len(x), 0.03, 0.08, 0.85, 0.12)
        place(out, x, at)
        at += d
    return fade(norm(out))


def airhorn():
    dur_one = 0.22
    out = np.zeros(int(1.3 * SR))
    for k, d in enumerate([dur_one, dur_one, 0.7]):
        x = sum(osc(f, d, "saw") for f in (466.0, 470.0, 699.0, 932.0))
        x = sat(lowpass(x, 3500), 3) * adsr(int(d * SR), 0.01, 0.03, 0.9, 0.05)
        place(out, x, k * 0.26)
    return fade(norm(out))


def crickets():
    """Silencio incómodo."""
    out = np.zeros(int(2.4 * SR))
    for start in np.arange(0.05, 2.2, 0.55):
        for j in range(3):
            d = 0.035
            c = osc(4300, d) * np.sin(np.pi * t_axis(d) / d) * (osc(30, d) * 0.5 + 0.5)
            place(out, c, start + j * 0.055, 0.8)
    return fade(norm(reverb(out, 0.4, 0.3)) * 0.8)


def riser(dur=2.0):
    """Subida de tensión antes de una revelación."""
    tt = t_axis(dur)
    p = tt / dur
    tone = osc(200 * 2 ** (p * 2.5), dur, "saw") * 0.25
    n = highpass(noise(dur), 1000 + 6000 * p) * 0.6
    x = lowpass(tone + n, 800 + 9000 * p) * p ** 1.8
    return fade(norm(x), 0.01, 0.005)


def suspense_hit():
    """Dun dun duuun."""
    out = np.zeros(int(3.0 * SR))
    for k, (f, d) in enumerate([(98.0, 0.35), (92.5, 0.35), (82.4, 1.8)]):
        x = (osc(f, d, "saw") + osc(f * 1.5, d, "saw") * 0.6 + osc(f * 2, d, "saw") * 0.4)
        x = sat(lowpass(x, 1200), 2) * adsr(int(d * SR), 0.01, 0.1, 0.8, 0.2)
        place(out, x, k * 0.45)
    return fade(norm(reverb(out, 0.4, 0.25)))


def glitch():
    dur = 0.5
    out = np.zeros(int(dur * SR))
    pos = 0.0
    while pos < dur - 0.03:
        seg = RNG.uniform(0.015, 0.06)
        kind = RNG.integers(0, 3)
        if kind == 0:
            x = osc(RNG.uniform(200, 2000), seg, "square")
        elif kind == 1:
            x = noise(seg)
        else:
            x = np.round(osc(RNG.uniform(80, 400), seg, "saw") * 3) / 3
        place(out, x * RNG.uniform(0.4, 1), pos)
        pos += seg
    return fade(norm(out * 0.8))


def camera_shutter():
    out = np.zeros(int(0.3 * SR))
    for at in (0.0, 0.07):
        c = bandpass(noise(0.05), 1500, 8000) * env_exp(0.05, 90)
        place(out, c, at)
    return fade(norm(out))


def click():
    d = 0.03
    return fade(norm(bandpass(noise(d), 2000, 9000) * env_exp(d, 250)), 0.0002, 0.005)


def coin():
    out = np.zeros(int(0.6 * SR))
    place(out, osc(1760, 0.08, "square") * 0.5, 0.0)
    place(out, osc(2637, 0.45, "square") * 0.5 * env_exp(0.45, 7), 0.07)
    return fade(norm(lowpass(out, 6000)))


def heartbeat():
    out = np.zeros(int(1.6 * SR))
    for beat in (0.0, 0.8):
        for k, at in enumerate((0.0, 0.18)):
            d = 0.18
            tt = t_axis(d)
            x = osc(55 + 30 * np.exp(-tt * 30), d) * env_exp(d, 20) * (1.0 if k == 0 else 0.7)
            place(out, x, beat + at)
    return fade(norm(sat(out, 1.5)))


def drumroll(dur=1.8):
    out = np.zeros(int((dur + 0.8) * SR))
    t = 0.0
    while t < dur:
        hit = bandpass(noise(0.05), 300, 5000) * env_exp(0.05, 60)
        place(out, hit, t, 0.4 + 0.6 * t / dur)
        t += 0.032
    final = boom()[: int(0.8 * SR)] * 0.8 + np.pad(highpass(noise(0.8), 5000) * env_exp(0.8, 4) * 0.5, (0, 0))
    place(out, final, dur)
    return fade(norm(out))


def tick_tock():
    out = np.zeros(int(2.0 * SR))
    for k in range(4):
        f = 2400 if k % 2 == 0 else 1800
        d = 0.04
        place(out, bandpass(noise(d), f * 0.8, f * 1.2) * env_exp(d, 120) + osc(f, d) * env_exp(d, 90) * 0.4, k * 0.5)
    return fade(norm(out))


def bass_drop():
    dur = 1.5
    tt = t_axis(dur)
    f = 30 + 200 * np.exp(-tt * 3.5)
    x = sat(osc(f, dur) + osc(f * 2, dur, "saw") * 0.15, 3) * env_exp(dur, 1.5)
    return fade(norm(x), 0.001, 0.2)


def magic_sparkle():
    out = np.zeros(int(1.2 * SR))
    for k in range(9):
        f = 2000 * 2 ** (k / 6)
        d = 0.4
        place(out, osc(f, d) * env_exp(d, 9), k * 0.06, 0.5)
    return fade(norm(reverb(out, 0.3, 0.3)))


def slide_whistle_up():
    dur = 0.7
    tt = t_axis(dur)
    f = 500 * 2 ** (2.2 * (tt / dur))
    return fade(norm(osc(f, dur) * adsr(int(dur * SR), 0.02, 0.05, 0.9, 0.1)))


def slide_whistle_down():
    dur = 0.8
    tt = t_axis(dur)
    f = 2000 * 2 ** (-2.2 * (tt / dur))
    return fade(norm(osc(f, dur) * adsr(int(dur * SR), 0.02, 0.05, 0.9, 0.1)))


def typing():
    out = np.zeros(int(1.2 * SR))
    t = 0.0
    while t < 1.1:
        place(out, click(), t, RNG.uniform(0.4, 1))
        t += RNG.uniform(0.06, 0.14)
    return fade(norm(out))


def notification():
    out = np.zeros(int(0.7 * SR))
    for k, f in enumerate((1046.5, 1568.0)):
        place(out, osc(f, 0.35) * env_exp(0.35, 10), k * 0.12)
    return fade(norm(out))


def tape_stop():
    dur = 0.9
    tt = t_axis(dur)
    f = 330 * (1 - tt / dur) ** 2 + 20
    x = osc(f, dur, "saw") * 0.5 + osc(f * 1.5, dur, "saw") * 0.3
    return fade(norm(lowpass(x, 300 + 3000 * (1 - tt / dur))))


EFFECTS = {
    # transiciones
    "whoosh": whoosh,
    "whoosh_down": lambda: whoosh(0.55, up=False),
    "swoosh_fast": swoosh_fast,
    "glitch": glitch,
    "tape_stop": tape_stop,
    # énfasis / impacto
    "boom": boom,
    "impact": impact,
    "bass_drop": bass_drop,
    "suspense_hit": suspense_hit,
    "riser": riser,
    "drumroll": drumroll,
    "heartbeat": heartbeat,
    # UI / pop
    "pop": pop,
    "bubble_pop": bubble_pop,
    "click": click,
    "ding": ding,
    "notification": notification,
    "camera_shutter": camera_shutter,
    "typing": typing,
    "coin": coin,
    "magic_sparkle": magic_sparkle,
    # humor
    "boing": boing,
    "record_scratch": record_scratch,
    "rimshot": rimshot,
    "sad_trombone": sad_trombone,
    "airhorn": airhorn,
    "crickets": crickets,
    "correct": correct,
    "wrong_buzzer": wrong_buzzer,
    "slide_whistle_up": slide_whistle_up,
    "slide_whistle_down": slide_whistle_down,
    "tick_tock": tick_tock,
}


def write_wav(path: Path, x: np.ndarray):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def generate_all(force=False):
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    for name, fn in EFFECTS.items():
        p = SFX_DIR / f"{name}.wav"
        if p.exists() and not force:
            continue
        write_wav(p, fn())
        print("generado", p.relative_to(ROOT))


def available() -> list[str]:
    names = set(EFFECTS)
    if SFX_DIR.exists():
        names |= {p.stem for p in SFX_DIR.iterdir() if p.suffix.lower() in (".wav", ".mp3", ".ogg", ".flac", ".m4a")}
    return sorted(names)


def find(name: str) -> Path:
    for ext in (".wav", ".mp3", ".ogg", ".flac", ".m4a"):
        p = SFX_DIR / f"{name}{ext}"
        if p.exists():
            return p
    if name in EFFECTS:
        SFX_DIR.mkdir(parents=True, exist_ok=True)
        p = SFX_DIR / f"{name}.wav"
        write_wav(p, EFFECTS[name]())
        return p
    raise FileNotFoundError(f"Efecto '{name}' no existe. Disponibles: {', '.join(available())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.list:
        print("\n".join(available()))
    else:
        generate_all(a.force)
