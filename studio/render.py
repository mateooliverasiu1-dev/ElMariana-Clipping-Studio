"""Renderiza un Short a partir de un plan de edición (edit.json).

Uso:
    python -m studio.render work/<nombre>/edit.json [--preview] [--out ruta.mp4]

Todos los tiempos del edit.json están en segundos del VIDEO ORIGINAL (los mismos de
transcript.txt). El render los traslada solo al timeline final, aunque haya cortes o
segmentos reordenados. Ver EDIT_FORMAT.md para la referencia completa.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from . import sfx as sfxlib
from .transcribe import probe

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
SR = 48000

SUB_PRESETS = {
    # nombre: (fuente, tamaño, color, color_resaltado, contorno, sombra, mayúsculas, animación pop)
    "pop_amarillo": dict(font="Montserrat Black", size=110, color="#FFFFFF", highlight="#FFE600", outline=8, shadow=4, uppercase=True, pop=True),
    "neon_verde": dict(font="Montserrat Black", size=110, color="#FFFFFF", highlight="#3CFF5A", outline=8, shadow=4, uppercase=True, pop=True),
    "rojo_impacto": dict(font="Anton", size=118, color="#FFFFFF", highlight="#FF2D2D", outline=7, shadow=3, uppercase=True, pop=True),
    "comic": dict(font="Bangers", size=124, color="#FFFFFF", highlight="#FFB800", outline=8, shadow=5, uppercase=True, pop=True),
    "minimal": dict(font="Montserrat ExtraBold", size=78, color="#FFFFFF", highlight="#FFFFFF", outline=5, shadow=2, uppercase=False, pop=False),
}


# ============================================================== utilidades
def ass_color(hex_color: str, alpha: int = 0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_escape(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def norm_word(w: str) -> str:
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "", w)


def ease_in_out(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def ease_out(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def rel(path: str | Path, base: Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    for cand in (base / p, ROOT / p):
        if cand.exists():
            return cand.resolve()
    return (ROOT / p).resolve()


# ============================================================== timeline
@dataclass
class Seg:
    a: float          # inicio en el original
    b: float          # fin en el original
    n: int            # frames en la salida
    out0: float       # inicio en la salida


class Timeline:
    def __init__(self, cuts: list[tuple[float, float]], fps: float):
        self.fps = fps
        self.segs: list[Seg] = []
        out = 0.0
        frames = 0
        for a, b in cuts:
            n = int(round((b - a) * fps))
            if n <= 0:
                continue
            self.segs.append(Seg(a, a + n / fps, n, frames / fps))
            frames += n
        self.total_frames = frames
        self.duration = frames / fps

    def to_out(self, t: float) -> float | None:
        for s in self.segs:
            if s.a - 1e-6 <= t < s.b:
                return s.out0 + (t - s.a)
        return None

    def seg_index(self, t: float) -> int:
        for i, s in enumerate(self.segs):
            if s.a - 1e-6 <= t < s.b:
                return i
        return -1

    def to_src(self, t_out: float) -> float:
        for s in self.segs:
            if t_out < s.out0 + s.n / self.fps:
                return s.a + (t_out - s.out0)
        return self.segs[-1].b


def build_cuts(plan: dict, info: dict, words: list[dict]) -> list[tuple[float, float]]:
    dur = info["duration"]
    cuts = [(float(a), float(b)) for a, b in plan.get("cuts") or [[0, dur]]]
    cuts = [(max(0.0, a), min(dur, b)) for a, b in cuts if b > a]
    rs = plan.get("remove_silences")
    if rs and words:
        min_gap = float(rs.get("min_gap", 0.5))
        pad = float(rs.get("pad", 0.12))
        new = []
        for a, b in cuts:
            ws = [w for w in words if w["start"] >= a and w["end"] <= b]
            cur = a
            for w1, w2 in zip(ws, ws[1:]):
                if w2["start"] - w1["end"] > min_gap:
                    new.append((cur, w1["end"] + pad))
                    cur = w2["start"] - pad
            new.append((cur, b))
        cuts = [(a, b) for a, b in new if b - a > 0.08]
    return cuts


# ============================================================== caras (encuadre inteligente)
def track_faces(src: Path, segs: list[Seg], cache: Path, step=0.4) -> dict:
    if cache.exists():
        data = json.loads(cache.read_text())
        if data.get("key") == [[s.a, s.b] for s in segs]:
            return data
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    samples = []
    W = 640
    info = probe(src)
    H = int(round(W * info["height"] / info["width"] / 2) * 2)
    for s in segs:
        cmd = ["ffmpeg", "-v", "error", "-ss", f"{s.a:.3f}", "-t", f"{s.b - s.a:.3f}", "-i", str(src),
               "-vf", f"fps={1 / step},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
        raw = subprocess.run(cmd, capture_output=True, check=True).stdout
        fsz = W * H
        for k in range(len(raw) // fsz):
            img = np.frombuffer(raw[k * fsz:(k + 1) * fsz], np.uint8).reshape(H, W)
            faces = casc.detectMultiScale(img, 1.15, 5, minSize=(W // 20, W // 20))
            t = s.a + k * step
            if len(faces):
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                samples.append([round(t, 2), (x + w / 2) / W, (y + h / 2) / H, w / W])
            else:
                samples.append([round(t, 2), None, None, None])
    data = {"key": [[s.a, s.b] for s in segs], "samples": samples}
    cache.write_text(json.dumps(data))
    return data


class FaceTrack:
    def __init__(self, data: dict | None):
        pts = [s for s in (data or {}).get("samples", []) if s[1] is not None]
        self.t = np.array([p[0] for p in pts]) if pts else None
        self.x = np.array([p[1] for p in pts]) if pts else None
        self.y = np.array([p[2] for p in pts]) if pts else None

    def at(self, t: float, default=(0.5, 0.4)) -> tuple[float, float]:
        if self.t is None or len(self.t) == 0:
            return default
        return float(np.interp(t, self.t, self.x)), float(np.interp(t, self.t, self.y))

    def smooth_x(self, seg: Seg, fps: float) -> np.ndarray:
        """Posición X de recorte por frame del segmento, suavizada (sin temblores)."""
        ts = seg.a + np.arange(seg.n) / fps
        if self.t is None or len(self.t) == 0:
            return np.full(seg.n, 0.5)
        inside = (self.t >= seg.a - 0.5) & (self.t <= seg.b + 0.5)
        if not inside.any():
            return np.full(seg.n, float(np.median(self.x)))
        xs = self.x[inside]
        if np.std(xs) < 0.04:  # sujeto quieto -> encuadre fijo
            return np.full(seg.n, float(np.median(xs)))
        raw = np.interp(ts, self.t[inside], xs)
        k = max(1, int(fps * 1.2))
        pad = np.pad(raw, (k, k), mode="edge")
        sm = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
        return sm


# ============================================================== subtítulos (ASS)
def build_ass(plan: dict, words: list[dict], tl: Timeline, W: int, H: int, layout_mode: str) -> str:
    sub = plan.get("subtitles", {})
    texts = plan.get("texts", [])
    enabled = sub is not False and sub.get("enabled", True) if isinstance(sub, dict) else bool(sub)
    sub = sub if isinstance(sub, dict) else {}
    cfg = dict(SUB_PRESETS.get(sub.get("style", "pop_amarillo"), SUB_PRESETS["pop_amarillo"]))
    cfg.update({k: v for k, v in sub.items() if k in cfg})
    scale = H / 1920
    size = int(cfg["size"] * scale)
    default_y = {"split": plan.get("layout", {}).get("ratio", 0.42)}.get(layout_mode, 0.70)
    y = float(sub.get("y", default_y)) * H
    max_words = int(sub.get("max_words", 3))
    max_chars = int(sub.get("max_chars", 14 if cfg["size"] >= 95 else 20))

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{cfg['font']},{size},{ass_color(cfg['color'])},{ass_color(cfg['color'])},&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,{cfg['outline'] * scale:.1f},{cfg['shadow'] * scale:.1f},5,{int(50 * scale)},{int(50 * scale)},0,1
Style: Title,Montserrat Black,{int(86 * scale)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,3,{int(18 * scale)},0,5,{int(70 * scale)},{int(70 * scale)},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev: list[str] = []

    # ---- correcciones de transcripción
    repl = {norm_word(k): v for k, v in (sub.get("replace") or {}).items()}
    fixes = sub.get("fixes") or []
    hidden = [tuple(x) for x in sub.get("hide", [])]
    emph = []
    for e in sub.get("emphasis") or []:
        if isinstance(e, str):
            e = {"word": e}
        emph.append({"word": norm_word(e["word"]), "t": e.get("t"), "color": e.get("color", "#FF3B30"), "scale": e.get("scale", 1.15)})

    out_words = []
    for w in words:
        text = w["w"]
        for f in fixes:
            if abs(f["t"] - w["start"]) < 0.25:
                text = f["w"]
        nk = norm_word(text)
        if nk in repl:
            text = repl[nk]
        if not text.strip():
            continue
        if any(a <= w["start"] < b for a, b in hidden):
            continue
        s = tl.to_out(w["start"])
        if s is None:
            continue
        e = tl.to_out(max(w["start"] + 0.01, w["end"] - 0.01))
        e = (e + 0.01) if e is not None else s + 0.3
        em = next((x for x in emph if x["word"] == norm_word(text) and (x["t"] is None or abs(x["t"] - w["start"]) < 0.3)), None)
        shown = text.upper() if cfg["uppercase"] else text
        if sub.get("strip_punctuation", True):
            shown = re.sub(r"[.,;:]+$", "", shown)
        out_words.append({"text": ass_escape(shown), "s": s, "e": max(e, s + 0.08), "raw": text, "em": em, "seg": tl.seg_index(w["start"])})

    # ---- agrupar en bloques cortos
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in out_words:
        chars = sum(len(x["text"]) + 1 for x in cur) + len(w["text"])
        if cur and (len(cur) >= max_words or chars > max_chars or w["s"] - cur[-1]["e"] > 0.6 or w["seg"] != cur[-1]["seg"]):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.?!…]$", w["raw"]):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)

    hl = ass_color(cfg["highlight"])
    base = ass_color(cfg["color"])
    if enabled:
        for gi, g in enumerate(groups):
            g_end = g[-1]["e"] + 0.25
            if gi + 1 < len(groups):
                g_end = min(g_end, groups[gi + 1][0]["s"])
            for k, w in enumerate(g):
                st = w["s"] if k else g[0]["s"]
                en = g[k + 1]["s"] if k + 1 < len(g) else g_end
                if en - st < 0.02:
                    continue
                parts = []
                for j, x in enumerate(g):
                    col = ass_color(x["em"]["color"]) if x["em"] else base
                    sc = int(100 * (x["em"]["scale"] if x["em"] else 1.0))
                    if j == k:
                        col = ass_color(x["em"]["color"]) if x["em"] else hl
                        if cfg["pop"]:
                            big = int(sc * 1.12)
                            parts.append(f"{{\\c{col}\\fscx{sc}\\fscy{sc}\\t(0,70,\\fscx{big}\\fscy{big})\\t(70,140,\\fscx{sc + 4}\\fscy{sc + 4})}}{x['text']}")
                        else:
                            parts.append(f"{{\\c{col}\\fscx{sc}\\fscy{sc}}}{x['text']}")
                    else:
                        parts.append(f"{{\\c{col}\\fscx{sc}\\fscy{sc}}}{x['text']}")
                intro = ""
                if k == 0 and cfg["pop"]:
                    intro = "\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)"
                txt = f"{{\\an5\\pos({W // 2},{int(y)}){intro}}}" + " ".join(parts)
                ev.append(f"Dialogue: 1,{ass_time(st)},{ass_time(en)},Sub,,0,0,0,,{txt}")

    # ---- textos libres (gancho, títulos, notas)
    for t in texts:
        s = tl.to_out(t["t"]) if not t.get("out_time") else t["t"]
        if s is None:
            continue
        d = float(t.get("dur", 2.5))
        ty = float(t.get("y", 0.17)) * H
        fs = int(t.get("size", 86) * scale)
        col = ass_color(t.get("color", "#FFFFFF"))
        box = ass_color(t.get("box", "#000000"), int(t.get("box_alpha", 0)))
        rot = t.get("angle", 0)
        txt = ass_escape(t["text"]).replace("|", "\\N")
        anim = "\\fscx60\\fscy60\\t(0,120,\\fscx105\\fscy105)\\t(120,200,\\fscx100\\fscy100)"
        ev.append(
            f"Dialogue: 2,{ass_time(s)},{ass_time(s + d)},Title,,0,0,0,,"
            f"{{\\an5\\pos({W // 2},{int(ty)})\\fs{fs}\\c{col}\\3c{box}\\frz{rot}{anim}\\fad(0,150)}}{txt}"
        )
    return head + "\n".join(ev) + "\n"


# ============================================================== zooms / efectos
class Motion:
    def __init__(self, plan: dict, tl: Timeline, faces: FaceTrack, layout: "Layout"):
        self.events = []
        for z in plan.get("zooms", []):
            s = tl.to_out(z["t"])
            if s is None:
                continue
            self.events.append({**z, "s": s, "dur": float(z.get("dur", 1.2)), "scale": float(z.get("scale", 1.25)),
                                "style": z.get("style", "punch")})
        self.events.sort(key=lambda e: e["s"])
        self.fx = []
        for e in plan.get("effects", []):
            s = tl.to_out(e["t"])
            if s is not None:
                self.fx.append({**e, "s": s, "dur": float(e.get("dur", 0.3))})
        self.faces = faces
        self.layout = layout
        self.tl = tl

    def zoom(self, t: float) -> tuple[float, float, float]:
        """Devuelve (escala, foco_x, foco_y) en coordenadas normalizadas de salida."""
        z, fx, fy = 1.0, 0.5, 0.42
        for e in self.events:
            s, d = e["s"], e["dur"]
            if not (s <= t < s + d):
                continue
            p = t - s
            S = e["scale"]
            st = e["style"]
            if st == "punch":       # golpe seco: entra en 2 frames, sale suave
                amt = ease_out(p / 0.06) * (1 - ease_in_out((p - (d - 0.18)) / 0.18))
            elif st == "smooth":    # entra y sale suave
                ramp = min(0.35, d / 3)
                amt = ease_in_out(p / ramp) * (1 - ease_in_out((p - (d - ramp)) / ramp))
            elif st == "slow":      # empuje lento continuo (tensión)
                amt = ease_in_out(p / d) * (1 - ease_in_out((p - (d - 0.12)) / 0.12))
            elif st == "hold":      # entra suave y se queda hasta el final del evento
                amt = ease_in_out(p / 0.3)
            else:
                amt = 1.0
            z = 1 + (S - 1) * amt
            fx, fy = e.get("x", "face"), e.get("y", None)
            if fx == "face" or fy == "face":
                src_t = self.tl.to_src(t)
                fxs, fys = self.layout.face_to_out(self.faces, src_t)
                fx = fxs if fx == "face" else fx
                fy = fys if (fy in (None, "face")) else fy
            fy = 0.42 if fy is None else fy
        return z, float(fx), float(fy)

    def effects_at(self, t: float) -> list[tuple[dict, float]]:
        return [(e, (t - e["s"]) / e["dur"]) for e in self.fx if e["s"] <= t < e["s"] + e["dur"]]


# ============================================================== layouts
class Layout:
    def __init__(self, plan: dict, sw: int, sh: int, W: int, H: int):
        self.cfg = plan.get("layout", {"mode": "crop"})
        self.mode = self.cfg.get("mode", "crop")
        self.sw, self.sh, self.W, self.H = sw, sh, W, H
        target = W / H
        if sw / sh > target:
            self.rh = sh
            self.rw = sh * target
        else:
            self.rw = sw
            self.rh = sw / target
        self.cur_x = 0.5

    def crop_origin(self, cx: float, cy: float = 0.5) -> tuple[float, float]:
        x0 = min(max(cx * self.sw - self.rw / 2, 0), self.sw - self.rw)
        y0 = min(max(cy * self.sh - self.rh / 2, 0), self.sh - self.rh)
        return x0, y0

    def face_to_out(self, faces: FaceTrack, src_t: float) -> tuple[float, float]:
        fx, fy = faces.at(src_t)
        if self.mode == "crop":
            x0, y0 = self.crop_origin(self.cur_x)
            ox = (fx * self.sw - x0) / self.rw
            oy = (fy * self.sh - y0) / self.rh
            return min(max(ox, 0.15), 0.85), min(max(oy, 0.2), 0.8)
        if self.mode == "split":
            return 0.5, 0.25
        return 0.5, 0.5

    @staticmethod
    def fill(img: np.ndarray, rect, W: int, H: int) -> np.ndarray:
        sh, sw = img.shape[:2]
        x, y, w, h = rect
        x, y, w, h = x * sw, y * sh, w * sw, h * sh
        ta = W / H
        if w / h > ta:
            nw = h * ta
            x += (w - nw) / 2
            w = nw
        else:
            nh = w / ta
            y += (h - nh) / 2
            h = nh
        crop = img[int(y):int(y + h), int(x):int(x + w)]
        interp = cv2.INTER_AREA if crop.shape[1] > W else cv2.INTER_CUBIC
        return cv2.resize(crop, (W, H), interpolation=interp)

    def compose(self, frame: np.ndarray, cx: float, z: float, fx: float, fy: float, shake: tuple[float, float]) -> np.ndarray:
        W, H = self.W, self.H
        if self.mode == "crop":
            self.cur_x = cx
            cy = float(self.cfg.get("y", 0.5))
            x0, y0 = self.crop_origin(cx, cy)
            s = self.rw / W
            a = s / z
            tx = x0 + s * fx * W * (1 - 1 / z) + shake[0] * s
            ty = y0 + s * fy * H * (1 - 1 / z) + shake[1] * s
            M = np.array([[a, 0, tx], [0, a, ty]], dtype=np.float32)
            return cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)

        if self.mode in ("blur", "fit"):
            if self.mode == "blur":
                small = cv2.resize(frame, (W // 8, int(W // 8 * frame.shape[0] / frame.shape[1])), interpolation=cv2.INTER_AREA)
                bg = self.fill(small, (0, 0, 1, 1), W // 8, H // 8)
                bg = cv2.GaussianBlur(bg, (0, 0), 6)
                canvas = cv2.resize(bg, (W, H), interpolation=cv2.INTER_LINEAR)
                canvas = (canvas * float(self.cfg.get("bg_dim", 0.55))).astype(np.uint8)
            else:
                canvas = np.zeros((H, W, 3), np.uint8)
            fs = float(self.cfg.get("fg_scale", 1.0))
            fw = int(W * fs)
            fh = int(fw * frame.shape[0] / frame.shape[1])
            fg = cv2.resize(frame, (fw, fh), interpolation=cv2.INTER_AREA if frame.shape[1] > fw else cv2.INTER_CUBIC)
            cyp = int(float(self.cfg.get("y", 0.5)) * H - fh / 2)
            cxp = (W - fw) // 2
            ys, ye = max(cyp, 0), min(cyp + fh, H)
            xs, xe = max(cxp, 0), min(cxp + fw, W)
            canvas[ys:ye, xs:xe] = fg[ys - cyp:ye - cyp, xs - cxp:xe - cxp]
        elif self.mode == "split":
            r = float(self.cfg.get("ratio", 0.42))
            th = int(H * r)
            top = self.cfg.get("top", [0.0, 0.0, 0.3, 0.35])
            bot = self.cfg.get("bottom", [0.2, 0.0, 0.6, 1.0])
            if isinstance(top, dict):
                top = [top["x"], top["y"], top["w"], top["h"]]
            if isinstance(bot, dict):
                bot = [bot["x"], bot["y"], bot["w"], bot["h"]]
            canvas = np.vstack([self.fill(frame, top, W, th), self.fill(frame, bot, W, H - th)])
            lc = self.cfg.get("line_color")
            if lc:
                h = lc.lstrip("#")
                cv2.rectangle(canvas, (0, th - 3), (W, th + 3), (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)), -1)
        else:
            raise ValueError(f"layout.mode desconocido: {self.mode}")

        if z != 1.0 or shake != (0.0, 0.0):
            M = np.array([[1 / z, 0, fx * W * (1 - 1 / z) + shake[0]], [0, 1 / z, fy * H * (1 - 1 / z) + shake[1]]], dtype=np.float32)
            canvas = cv2.warpAffine(canvas, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
        return canvas


# ============================================================== audio
def read_audio(src: Path, a: float, dur: float, has_audio: bool) -> np.ndarray:
    n = int(round(dur * SR))
    if not has_audio:
        return np.zeros((n, 2), np.float32)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.4f}", "-t", f"{dur:.4f}", "-i", str(src),
                          "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2)
    if len(x) < n:
        x = np.vstack([x, np.zeros((n - len(x), 2), np.float32)])
    return x[:n].copy()


def load_any_audio(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def build_audio(plan: dict, src: Path, info: dict, tl: Timeline, words: list[dict], base: Path) -> np.ndarray:
    total = int(round(tl.duration * SR))
    out = np.zeros((total, 2), np.float32)
    xf = int(0.008 * SR)
    voice_gain = 10 ** (float(plan.get("audio", {}).get("voice_db", 0)) / 20)
    for s in tl.segs:
        x = read_audio(src, s.a, s.n / tl.fps, info["has_audio"]) * voice_gain
        if len(x) > 2 * xf:
            x[:xf] *= np.linspace(0, 1, xf)[:, None]
            x[-xf:] *= np.linspace(1, 0, xf)[:, None]
        i = int(round(s.out0 * SR))
        j = min(total, i + len(x))
        out[i:j] += x[: j - i]

    # ---- música de fondo con ducking (baja cuando hablan)
    mus = plan.get("music")
    if mus and mus.get("file"):
        m = load_any_audio(rel(mus["file"], base))
        if len(m):
            reps = int(np.ceil(total / len(m)))
            m = np.tile(m, (reps, 1))[:total]
            g = 10 ** (float(mus.get("db", -20)) / 20)
            env = np.ones(total, np.float32)
            if mus.get("duck", True):
                duck = 10 ** (float(mus.get("duck_db", -8)) / 20)
                speech = np.zeros(total, np.float32)
                for w in words:
                    s = tl.to_out(w["start"])
                    if s is not None:
                        speech[int(s * SR):int((s + (w["end"] - w["start"]) + 0.15) * SR)] = 1
                k = int(0.25 * SR)
                speech = np.convolve(speech, np.ones(k) / k, mode="same")
                env = 1 - (1 - duck) * np.clip(speech * 1.5, 0, 1)
            fi, fo = int(0.5 * SR), int(1.2 * SR)
            env[:fi] *= np.linspace(0, 1, fi)
            env[-fo:] *= np.linspace(1, 0, fo)
            out += m * (g * env)[:, None]

    # ---- efectos de sonido
    cache: dict[str, np.ndarray] = {}
    for e in plan.get("sfx", []):
        s = tl.to_out(e["t"]) if not e.get("out_time") else e["t"]
        if s is None:
            continue
        s += float(e.get("offset", 0))
        name = e["name"]
        if name not in cache:
            cache[name] = load_any_audio(sfxlib.find(name))
        x = cache[name]
        if "db" in e:
            g = 10 ** (float(e["db"]) / 20)
        else:
            g = float(e.get("gain", 0.7))
        i = int(max(0, s) * SR)
        j = min(total, i + len(x))
        if j > i:
            out[i:j] += x[: j - i] * g
    return out


# ============================================================== render principal
def render(plan_path: Path, preview=False, out_override: Path | None = None) -> Path:
    t_start = time.time()
    plan = json.loads(plan_path.read_text())
    base = plan_path.parent
    src = rel(plan["source"], base)
    info = probe(src)
    words: list[dict] = []
    tr = plan.get("transcript")
    if tr and rel(tr, base).exists():
        words = json.loads(rel(tr, base).read_text())["words"]

    fps = float(plan.get("fps", 30))
    W, H = (540, 960) if preview else tuple(plan.get("size", [1080, 1920]))
    cuts = build_cuts(plan, info, words)
    tl = Timeline(cuts, fps)
    if tl.total_frames == 0:
        sys.exit("No hay nada que renderizar (revisa 'cuts').")

    out = out_override or rel(plan.get("output", f"output/{src.stem}_short.mp4"), base)
    if preview:
        out = out.with_name(out.stem + "_preview.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    wd = ROOT / "work" / src.stem
    wd.mkdir(parents=True, exist_ok=True)

    # --- tamaño de decodificación (lado largo máx 1920, o menos en preview)
    sw, sh = info["width"], info["height"]
    cap = 1080 if preview else 1920
    k = min(1.0, cap / max(sw, sh))
    dw, dh = int(round(sw * k / 2) * 2), int(round(sh * k / 2) * 2)

    layout = Layout(plan, dw, dh, W, H)
    lcfg = plan.get("layout", {})
    need_faces = (layout.mode == "crop" and lcfg.get("x", "auto") == "auto") or any(
        z.get("x", "face") == "face" for z in plan.get("zooms", []))
    faces = FaceTrack(track_faces(src, tl.segs, wd / "faces.json") if need_faces else None)
    motion = Motion(plan, tl, faces, layout)

    print(f"Render: {len(tl.segs)} segmentos, {tl.duration:.1f}s, {W}x{H}@{fps:g}, layout={layout.mode}")

    # --- subtítulos y audio
    ass_path = wd / ("subs_preview.ass" if preview else "subs.ass")
    ass_path.write_text(build_ass(plan, words, tl, W, H, layout.mode), encoding="utf-8")
    audio = build_audio(plan, src, info, tl, words, base)
    audio_path = wd / "mix.f32"
    audio.astype("<f4").tofile(audio_path)

    lufs = float(plan.get("audio", {}).get("loudness", -14))
    vf = f"ass='{ass_path}':fontsdir='{FONTS}',format=yuv420p"
    enc = ["ffmpeg", "-y", "-v", "error", "-stats",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{fps:g}", "-i", "-",
           "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(audio_path),
           "-vf", vf, "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample={SR}",
           "-c:v", "libx264", "-preset", "veryfast" if preview else "medium", "-crf", "26" if preview else "18",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-r", f"{fps:g}", "-shortest", str(out)]
    encp = subprocess.Popen(enc, stdin=subprocess.PIPE)

    pb = plan.get("progress_bar")
    fsz = dw * dh * 3
    done = 0
    rng = np.random.default_rng(3)
    try:
        for seg in tl.segs:
            xs = faces.smooth_x(seg, fps) if (layout.mode == "crop" and lcfg.get("x", "auto") == "auto") else np.full(seg.n, float(lcfg.get("x", 0.5)) if lcfg.get("x") != "auto" else 0.5)
            dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{seg.a:.4f}", "-t", f"{seg.n / fps + 0.5:.4f}", "-i", str(src),
                                    "-vf", f"fps={fps:g},scale={dw}:{dh}:flags=lanczos", "-frames:v", str(seg.n), "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                                   stdout=subprocess.PIPE)
            last = None
            for i in range(seg.n):
                buf = dec.stdout.read(fsz)
                if len(buf) == fsz:
                    last = np.frombuffer(buf, np.uint8).reshape(dh, dw, 3)
                elif last is None:
                    last = np.zeros((dh, dw, 3), np.uint8)
                t = seg.out0 + i / fps
                z, fx, fy = motion.zoom(t)
                shake = (0.0, 0.0)
                post = []
                for e, p in motion.effects_at(t):
                    if e["type"] == "shake":
                        amp = float(e.get("intensity", 1.0)) * 22 * (1 - p) * (W / 1080)
                        shake = (amp * math.sin(t * 2 * math.pi * 13 + rng.random()), amp * math.cos(t * 2 * math.pi * 17))
                        z = max(z, 1.05)
                    else:
                        post.append((e, p))
                frame = layout.compose(last, float(xs[i]), z, fx, fy, shake)
                for e, p in post:
                    ty = e["type"]
                    if ty == "flash":
                        a = float(e.get("intensity", 0.85)) * (1 - p) ** 2
                        col = np.array(e.get("rgb", [255, 255, 255])[::-1], np.float32)
                        frame = (frame * (1 - a) + col * a).astype(np.uint8)
                    elif ty == "bw":
                        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        frame = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
                    elif ty == "vignette":
                        if not hasattr(render, "_vig") or render._vig.shape[:2] != (H, W):
                            yy, xx = np.mgrid[0:H, 0:W]
                            d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
                            render._vig = np.clip(1.15 - 0.55 * d ** 2, 0.25, 1)[..., None].astype(np.float32)
                        frame = (frame * render._vig).astype(np.uint8)
                    elif ty == "red_tint":
                        a = float(e.get("intensity", 0.35))
                        frame = (frame * (1 - a) + np.array([30, 30, 220], np.float32) * a).astype(np.uint8)
                if pb:
                    h = lambda c: tuple(int(c.lstrip("#")[k:k + 2], 16) for k in (4, 2, 0))
                    bh = int(pb.get("height", 10) * H / 1920)
                    frame = frame.copy() if not frame.flags.writeable else frame
                    cv2.rectangle(frame, (0, H - bh), (int(W * (done + 1) / tl.total_frames), H), h(pb.get("color", "#FFE600")), -1)
                encp.stdin.write(frame.tobytes())
                done += 1
            dec.stdout.close()
            dec.wait()
    finally:
        encp.stdin.close()
        encp.wait()
    if encp.returncode != 0:
        sys.exit("Error en la codificación final")
    print(f"\nListo: {out}  ({tl.duration:.1f}s de video, render en {time.time() - t_start:.0f}s)")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", type=Path)
    ap.add_argument("--preview", action="store_true", help="render rápido a 540x960 para revisar")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    render(a.plan.resolve(), a.preview, a.out)
