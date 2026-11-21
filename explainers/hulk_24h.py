"""¿Qué pasaría si Hulk apareciera 24 horas en el mundo real?  (Short explicativo, ~55-60 s)

Uso (desde la raíz del repo):
    python explainers/hulk_24h.py                 -> voz de Alex (Kokoro)
    python explainers/hulk_24h.py frames          -> fotogramas de muestra

Nota de derechos: Hulk es un personaje de Marvel. El video habla del tema pero NO dibuja
al personaje: muestra sus efectos (cámaras, saltos, ejército, ciencia).
Cuentas (persona muy musculosa de 1.85 m y 110 kg escalada ×4.32 a 8 m):
  masa ≈ 110 kg × 4.32³ ≈ 8.9 t
  presión de un pie ≈ 8.9 t·g / 0.47 m² ≈ 190 kPa  (< llanta de camión, ~700-800 kPa)
  salto de 100 m: v = √(2·g·100) ≈ 44 m/s ≈ 160 km/h; E = ½·m·v² ≈ 8.7 MJ ≈ 2 kg de TNT
  comida ≈ 2 500 kcal × (4.32³)^0.75 (ley de Kleiber) ≈ 67 000 kcal/día ≈ 120 hamburguesas
  hueso: peso ×81, sección ×18.7 → presión ×4.3
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import (FONT_SB, H, RED, SR, W, WHITE, YELLOW, Explainer, badge, boom, draw_text, ease, ease_out,  # noqa: E402
                    font, glow, gradient, lerp, mix, note, paste_center, phone, shake, to_img)


def hour(img, t, label):
    badge(img, label, W / 2, 120, t)


def car(d, x, y, s=1.0, color=(200, 60, 60), angle_flip=False):
    """Auto de perfil, sencillo."""
    w, h = 300 * s, 90 * s
    body = [(x, y + h * 0.45), (x + w * 0.2, y + h * 0.45), (x + w * 0.32, y), (x + w * 0.72, y),
            (x + w * 0.85, y + h * 0.45), (x + w, y + h * 0.5), (x + w, y + h), (x, y + h)]
    if angle_flip:
        body = [(px, 2 * y + h - py) for px, py in body]
    d.polygon(body, fill=color + (255,))
    wy = y + h if not angle_flip else y
    for wx in (x + w * 0.22, x + w * 0.8):
        d.ellipse([wx - 32 * s, wy - 32 * s, wx + 32 * s, wy + 32 * s], fill=(20, 20, 24, 255))


def street(img, t, dusk=0.0):
    d = ImageDraw.Draw(img)
    hz = 1240
    r = random.Random(12)
    x = -30
    while x < W:
        bw, bh = r.randint(110, 200), r.randint(320, 760)
        col = mix((40, 44, 60), (24, 26, 38), dusk)
        d.rectangle([x, hz - bh, x + bw, hz], fill=col + (255,))
        for wy in range(hz - bh + 24, hz - 30, 44):
            for wx in range(x + 16, x + bw - 20, 36):
                if r.random() < 0.3:
                    d.rectangle([wx, wy, wx + 16, wy + 22], fill=(255, 215, 130, 200))
        x += bw + r.randint(6, 20)
    d.rectangle([0, hz, W, H], fill=(46, 46, 52, 255))
    for k in range(-1, 8):
        xx = (k * 220 - t * 0) % (W + 220) - 110
        d.rectangle([xx, hz + 240, xx + 120, hz + 256], fill=(230, 210, 120, 255))
    return hz


DUST = glow(380, (200, 180, 150), 0.55)

# ------------------------------------------------------------------ escenas
STOMPS = [1.1, 2.0, 2.9, 3.8]


def s_hook(t, dur):
    img = to_img(gradient([(0, (18, 20, 34)), (0.6, (60, 50, 60)), (1, (90, 70, 60))]))
    hz = street(img, t)
    d = ImageDraw.Draw(img)
    # auto volcado + polvo
    car(d, 600, hz + 330, 1.15, (60, 110, 200), angle_flip=True)
    for i, s in enumerate(STOMPS):
        if t >= s:
            p = ease_out((t - s) / 1.2)
            g = DUST.resize((int(760 * (0.6 + 0.6 * p)), int(380 * (0.6 + 0.6 * p))))
            g.putalpha(g.getchannel("A").point(lambda v: int(v * (1 - p * 0.7))))
            paste_center(img, g, 200 + i * 220, hz + 250)
    draw_text(img, "¿QUÉ PASARÍA SI", t, 0.15, 330, size=84)
    draw_text(img, "*HULK", t, 0.55, 450, size=170, per_word=0.0)
    draw_text(img, "APARECIERA", t, 1.0, 660, size=90)
    draw_text(img, "*24 *HORAS", t, 1.3, 765, size=130)
    draw_text(img, "EN EL MUNDO REAL?", t, 1.8, 925, size=80)
    return shake(img, t, STOMPS, strength=12)


def s_weight(t, dur):
    img = to_img(gradient([(0, (10, 14, 26)), (1, (22, 28, 48))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 0")
    draw_text(img, "*8 *METROS Y UNAS *9 *TONELADAS", t, 0.2, 230, size=88)
    rows = [("Persona", 0.08, (150, 160, 180)), ("Elefante africano", 6.0, (150, 160, 180)),
            ("Él", 8.9, YELLOW), ("Tráiler cargado", 36.0, (90, 170, 255))]
    left, maxw = 100, W - 200
    for i, (name, tons, col) in enumerate(rows):
        y = 640 + i * 190
        p = ease_out((t - 0.8 - i * 0.35) / 0.8)
        if p <= 0:
            continue
        wbar = max(14, maxw * tons / 36.0 * p)
        d.text((left, y), name.upper(), font=font(46), fill=WHITE + (255,))
        d.rounded_rectangle([left, y + 66, left + wbar, y + 120], radius=16, fill=col + (255,))
        d.text((left + wbar + 18, y + 93), f"{tons:g} t" if tons >= 1 else "0.08 t", font=font(42, FONT_SB),
               anchor="lm", fill=col + (255,))
    draw_text(img, "Al caminar *NO rompería el asfalto: un tráiler aprieta más", t, 3.0, 1480, size=56, per_word=0.05)
    return img


def cctv(img, x, y, w, h, t, label, seed, content):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x + w, y + h], fill=(16, 18, 20, 255))
    content(img, x, y, w, h, t)
    r = random.Random(int(t * 12) + seed)
    noise = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    nd = ImageDraw.Draw(noise)
    for _ in range(40):
        yy = r.randint(0, h)
        nd.line([(0, yy), (w, yy)], fill=(255, 255, 255, r.randint(8, 30)), width=1)
    img.alpha_composite(noise, (x, y))
    d = ImageDraw.Draw(img)
    d.text((x + 18, y + 14), label, font=font(30, FONT_SB), fill=(230, 230, 230, 255))
    if int(t * 2) % 2 == 0:
        d.ellipse([x + w - 120, y + 18, x + w - 98, y + 40], fill=RED + (255,))
    d.text((x + w - 88, y + 14), "REC", font=font(30), fill=RED + (255,))
    secs = 13 * 3600 + 42 * 60 + int(t * 1) + seed * 7
    d.text((x + 18, y + h - 46), f"20/11  {secs // 3600:02d}:{secs // 60 % 60:02d}:{secs % 60:02d}",
           font=font(28, FONT_SB), fill=(230, 230, 230, 255))
    d.rectangle([x, y, x + w, y + h], outline=(80, 84, 90, 255), width=4)


def _cam_car(img, x, y, w, h, t):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y + h * 0.7, x + w, y + h], fill=(40, 42, 44, 255))
    p = (t * 0.45) % 1
    cx = x + lerp(-120, w + 20, p)
    cy = y + h * 0.7 - 150 * math.sin(p * math.pi)
    tmp = Image.new("RGBA", (220, 120), (0, 0, 0, 0))
    car(ImageDraw.Draw(tmp), 10, 20, 0.65, (220, 200, 60))
    tmp = tmp.rotate(-p * 300, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(tmp, (int(cx), int(cy - tmp.height / 2)))


def _cam_crack(img, x, y, w, h, t):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x + w, y + h], fill=(60, 60, 64, 255))
    r = random.Random(3)
    grow = ease((t - 0.5) / 2.0)
    cx, cy = x + w / 2, y + h / 2
    for k in range(9):
        ang = r.uniform(0, 6.28)
        L = r.uniform(80, 190) * grow
        pts = [(cx, cy)]
        for s in range(1, 5):
            pts.append((cx + math.cos(ang) * L * s / 4 + r.uniform(-10, 10), cy + math.sin(ang) * L * s / 4 + r.uniform(-10, 10)))
        d.line(pts, fill=(20, 20, 22, 255), width=5)


def _cam_people(img, x, y, w, h, t):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x + w, y + h], fill=(70, 66, 60, 255))
    r = random.Random(8)
    for k in range(16):
        px = x + ((r.random() * w + t * (60 + r.random() * 80)) % w)
        py = y + 60 + r.random() * (h - 120)
        d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(230, 210, 190, 255))
        d.rectangle([px - 8, py + 10, px + 8, py + 34], fill=(r.randint(50, 200), 80, 120, 255))


def _cam_shake(img, x, y, w, h, t):
    d = ImageDraw.Draw(img)
    off = int(10 * math.sin(t * 40) * max(0, math.sin(t * 2)))
    d.rectangle([x, y, x + w, y + h], fill=(30, 36, 50, 255))
    for k in range(5):
        bx = x + 20 + k * (w // 5) + off
        d.rectangle([bx, y + h - 60 - (k % 3) * 60, bx + w // 6, y + h], fill=(50, 56, 72, 255))
    d.text((x + w / 2 + off, y + h / 2), "SIN SEÑAL" if (t % 3) > 2.4 else "", font=font(40), anchor="mm",
           fill=(230, 230, 230, 255))


def s_cameras(t, dur):
    img = to_img(gradient([(0, (8, 8, 12)), (1, (18, 18, 26))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 1")
    draw_text(img, "LO GRABAN *DESDE *TODOS *LOS *ÁNGULOS", t, 0.2, 230, size=84)
    w, h = 450, 360
    cams = [(70, 560, "CAM 03 · AV. CENTRAL", 1, _cam_car), (560, 560, "CAM 07 · CRUCE", 2, _cam_crack),
            (70, 960, "CAM 12 · PLAZA", 3, _cam_people), (560, 960, "CAM 15 · PUENTE", 4, _cam_shake)]
    for k, (x, y, label, seed, fn) in enumerate(cams):
        if t > 0.6 + k * 0.25:
            cctv(img, x, y, w, h, t, label, seed, fn)
    if t > 2.8:
        p = ease_out((t - 2.8) / 0.4)
        card = Image.new("RGBA", (880, 170), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, 880, 170], radius=30, fill=(255, 255, 255, 245))
        cd.text((40, 34), "TENDENCIA #1 EN EL MUNDO", font=font(50), fill=(20, 20, 26, 255))
        cd.text((40, 106), "Es lo único de lo que habla internet", font=font(36, FONT_SB), fill=(90, 90, 100, 255))
        card.putalpha(card.getchannel("A").point(lambda v: int(v * p)))
        paste_center(img, card, W / 2, 1520 - 30 * (1 - p))
    return img


LAND_AT = 3.3


def s_jump(t, dur):
    img = to_img(gradient([(0, (30, 60, 110)), (1, (150, 170, 190))]))
    d = ImageDraw.Draw(img)
    hz = 1500
    r = random.Random(30)
    x = -20
    while x < W:
        bw, bh = r.randint(90, 160), r.randint(200, 520)
        d.rectangle([x, hz - bh, x + bw, hz], fill=(70, 80, 100, 255))
        x += bw + 10
    d.rectangle([0, hz, W, H], fill=(60, 60, 66, 255))
    hour(img, t, "HORA 2")
    draw_text(img, "¿Y SI SALTA *100 *METROS?", t, 0.2, 230, size=92)
    x0, x1, top = 120, 940, 520
    p = ease((t - 0.6) / (LAND_AT - 0.6))
    pts = []
    for i in range(int(60 * p) + 1):
        u = i / 60
        pts.append((lerp(x0, x1, u), hz - 4 * (hz - top) * u * (1 - u)))
    for i in range(0, len(pts) - 1, 2):
        d.line([pts[i], pts[i + 1]], fill=WHITE + (255,), width=8)
    if pts:
        d.ellipse([pts[-1][0] - 16, pts[-1][1] - 16, pts[-1][0] + 16, pts[-1][1] + 16], fill=YELLOW + (255,))
    d.line([(W / 2, top), (W / 2, hz)], fill=(255, 255, 255, 120), width=3)
    d.text((W / 2 + 20, (top + hz) / 2), "100 m", font=font(52), anchor="lm", fill=WHITE + (255,), stroke_width=4,
           stroke_fill=(0, 0, 0, 255))
    if t >= LAND_AT:
        q = ease_out((t - LAND_AT) / 0.8)
        g = glow(int(300 * (0.5 + q)), (255, 230, 160), 1 - 0.6 * q)
        paste_center(img, g, x1, hz)
        d = ImageDraw.Draw(img)
        d.ellipse([x1 - 160, hz - 30, x1 + 160, hz + 60], fill=(30, 30, 34, 255))
        for k in range(10):
            ang = math.pi + k * math.pi / 9
            L = 220 * q
            d.line([(x1, hz), (x1 + math.cos(ang) * L, hz + math.sin(ang) * L * 0.6)], fill=(120, 110, 100, 255), width=8)
        if t > LAND_AT + 0.4:
            d.text((W / 2, 1640), "≈ 160 km/h", font=font(72), anchor="mm", fill=YELLOW + (255,), stroke_width=6,
                   stroke_fill=(0, 0, 0, 255))
            d.text((W / 2, 1740), "LA ENERGÍA DE ≈ 2 kg DE TNT", font=font(54), anchor="mm", fill=WHITE + (255,),
                   stroke_width=5, stroke_fill=(0, 0, 0, 255))
    return shake(img, t, [LAND_AT], strength=22)


def s_military(t, dur):
    img = to_img(gradient([(0, (14, 20, 18)), (1, (26, 36, 30))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 4")
    draw_text(img, "EL EJÉRCITO *ACORDONA LA ZONA", t, 0.2, 230, size=90)
    top = 560
    d.rounded_rectangle([60, top, W - 60, 1420], radius=30, fill=(40, 46, 44, 255))
    for gx in range(60, W - 60, 140):
        d.rectangle([gx + 20, top + 20, gx + 120, 1400], fill=(54, 60, 58, 255))
    cx, cy = W / 2, 990
    rr = 300
    p = ease_out((t - 0.6) / 1.2)
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=RED + (255,), width=8)
    d.text((cx, cy), "?", font=font(150), anchor="mm", fill=(255, 255, 255, 70))
    n = int(12 * p)
    for k in range(n):
        ang = 2 * math.pi * k / 12
        vx, vy = cx + math.cos(ang) * (rr + 60), cy + math.sin(ang) * (rr + 60)
        d.rounded_rectangle([vx - 34, vy - 20, vx + 34, vy + 20], radius=8, fill=(90, 110, 70, 255))
        d.rectangle([vx - 10, vy - 30, vx + 10, vy - 18], fill=(70, 90, 56, 255))
    if t > 2.4:
        q = ease_out((t - 2.4) / 0.4)
        y = 1500
        d.rounded_rectangle([80, y, W / 2 - 15, y + 170], radius=28, fill=(170, 50, 50, int(255 * q)))
        d.rounded_rectangle([W / 2 + 15, y, W - 80, y + 170], radius=28, fill=(50, 110, 170, int(255 * q)))
        d.text(((80 + W / 2) / 2, y + 85), "¿AMENAZA?", font=font(54), anchor="mm", fill=WHITE + (255,))
        d.text(((W / 2 + W - 80) / 2, y + 85), "¿VÍCTIMA?", font=font(54), anchor="mm", fill=WHITE + (255,))
    return img


def burger(d, x, y, s=1.0):
    d.ellipse([x, y, x + 80 * s, y + 40 * s], fill=(222, 160, 70, 255))
    d.rectangle([x + 4 * s, y + 26 * s, x + 76 * s, y + 34 * s], fill=(90, 180, 70, 255))
    d.rounded_rectangle([x + 2 * s, y + 32 * s, x + 78 * s, y + 46 * s], radius=6, fill=(110, 60, 40, 255))
    d.rounded_rectangle([x + 4 * s, y + 46 * s, x + 76 * s, y + 60 * s], radius=8, fill=(210, 150, 65, 255))


def s_food(t, dur):
    img = to_img(gradient([(0, (40, 16, 10)), (1, (70, 34, 16))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 8")
    draw_text(img, "*67 *000 CALORÍAS AL DÍA", t, 0.2, 230, size=92)
    draw_text(img, "(tú necesitas unas 2 500)", t, 1.0, 470, size=50, per_word=0.05)
    count = int(120 * ease((t - 1.2) / 2.4))
    for k in range(count):
        col, row = k % 10, k // 10
        burger(d, 70 + col * 96, 640 + row * 78, 1.0)
    if t > 1.2:
        d.text((W / 2, 1640), f"{count} HAMBURGUESAS", font=font(76), anchor="mm", fill=YELLOW + (255,),
               stroke_width=6, stroke_fill=(0, 0, 0, 255))
    return img


def s_bones(t, dur):
    img = to_img(gradient([(0, (8, 22, 40)), (1, (14, 44, 74))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 12")
    draw_text(img, "¿CÓMO *AGUANTAN SUS *RODILLAS?", t, 0.2, 230, size=88)
    bone_col = (235, 230, 215, 255)
    # izquierda: grosor del hueso (sección ×19 = diámetro ×4.3)
    d.text((290, 560), "GROSOR DEL HUESO", font=font(40), anchor="mm", fill=(170, 200, 230, 255))
    d.ellipse([290 - 26, 700 - 26, 290 + 26, 700 + 26], fill=bone_col)
    d.text((290, 770), "tú", font=font(40, FONT_SB), anchor="mm", fill=WHITE + (255,))
    g = ease_out((t - 0.8) / 1.2)
    rr = 26 + (112 - 26) * g
    d.ellipse([290 - rr, 1000 - rr, 290 + rr, 1000 + rr], fill=bone_col)
    if g > 0.95:
        d.text((290, 1180), "él: ×19", font=font(52), anchor="mm", fill=(130, 210, 255, 255))
    # derecha: peso (×81)
    d.text((790, 560), "PESO QUE CARGA", font=font(40), anchor="mm", fill=(170, 200, 230, 255))
    d.rectangle([790 - 14, 700 - 14, 790 + 14, 700 + 14], fill=(255, 140, 90, 255))
    d.text((790, 770), "tú", font=font(40, FONT_SB), anchor="mm", fill=WHITE + (255,))
    shown = int(81 * ease((t - 1.4) / 1.6))
    for k in range(shown):
        cx, cy = 790 - 4 * 30 + (k % 9) * 30, 880 + (k // 9) * 30
        d.rectangle([cx - 12, cy - 12, cx + 12, cy + 12], fill=(255, 140, 90, 255))
    if shown >= 81:
        d.text((790, 1180), "él: ×81", font=font(52), anchor="mm", fill=(255, 160, 110, 255))
    if t > 3.4:
        d.text((W / 2, 1420), "CADA HUESO SOPORTARÍA", font=font(62), anchor="mm", fill=WHITE + (255,),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
        d.text((W / 2, 1520), "×4 MÁS PRESIÓN", font=font(96), anchor="mm", fill=YELLOW + (255,),
               stroke_width=7, stroke_fill=(0, 0, 0, 255))
    return img


def s_ending(t, dur):
    k = ease(t / 3.0)
    img = to_img(gradient([(0, mix((20, 24, 40), (80, 110, 160), k)), (0.6, mix((70, 60, 70), (240, 190, 140), k)),
                           (1, (80, 70, 60))]))
    hz = street(img, t, dusk=1 - k)
    d = ImageDraw.Draw(img)
    r = random.Random(5)
    for _ in range(26):  # escombros
        x, y = r.randint(40, W - 40), hz + r.randint(80, 600)
        s = r.randint(20, 70)
        d.polygon([(x, y), (x + s, y + r.randint(-10, 10)), (x + s * 0.6, y - s * 0.7)],
                  fill=(r.randint(90, 140),) * 3 + (255,))
    car(d, 120, hz + 380, 1.0, (60, 110, 200), angle_flip=True)
    dust = DUST.resize((1200, 600))
    dust.putalpha(dust.getchannel("A").point(lambda v: int(v * (0.6 - 0.4 * k))))
    paste_center(img, dust, W / 2, hz + 200)
    hour(img, t, "HORA 24")
    draw_text(img, "POR FIN SE *CALMA…", t, 0.2, 280, size=96, out_at=2.6)
    draw_text(img, "…PERO EL MUNDO *NUNCA SERÍA IGUAL", t, 2.9, 280, size=88)
    draw_text(img, "¿TÚ LO DEJARÍAS *LIBRE O LO *ENCERRARÍAS?", t, 4.2, 680, size=82)
    return img


SCENES = [
    ("01_hook", s_hook, 4.5, "¿Qué pasaría si Hulk apareciera en el mundo real durante veinticuatro horas?"),
    ("02_peso", s_weight, 5.5, "Hora cero. Con ocho metros de altura pesaría unas nueve toneladas. Y aunque no lo "
                               "creas, al caminar no rompería el asfalto: un tráiler cargado aprieta más."),
    ("03_camaras", s_cameras, 5.5, "Hora uno. Cámaras de seguridad y celulares lo graban desde todos los ángulos. "
                                   "En minutos, es lo único de lo que habla internet."),
    ("04_salto", s_jump, 6.0, "Hora dos. Pero si salta cien metros, aterrizaría a unos ciento sesenta kilómetros "
                              "por hora, con la energía de dos kilos de TNT. Ahí sí, cráter."),
    ("05_ejercito", s_military, 5.5, "Hora cuatro. El ejército acordona la zona. Nadie sabe si es una amenaza o una "
                                     "víctima, y nadie quiere hacerlo enojar."),
    ("06_comida", s_food, 5.0, "Hora ocho. Con ese cuerpo necesitaría unas sesenta y siete mil calorías al día: "
                               "más de cien hamburguesas."),
    ("07_huesos", s_bones, 6.0, "Hora doce. Los científicos se preguntan cómo aguantan sus rodillas: cada hueso "
                                "soportaría cuatro veces más presión que el tuyo."),
    ("08_final", s_ending, 6.0, "Hora veinticuatro. Por fin se calma. Pero el mundo ya nunca sería igual. "
                                "¿Tú lo dejarías libre, o lo encerrarías?"),
]


# ------------------------------------------------------------------ música: acción con tensión (original)
def music(total: float, durs) -> np.ndarray:
    n = int((total + 1) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    bpm = 116
    beat = 60 / bpm
    bar = beat * 4
    chords = [[45, 48, 52], [41, 45, 48], [43, 47, 50], [40, 44, 47]]  # Am F G E
    for b in range(int(total / bar) + 2):
        ch = chords[b % 4]
        s0, s1 = int(b * bar * SR), min(int((b + 1) * bar * SR), n)
        if s0 >= n:
            break
        seg = t[s0:s1] - b * bar
        env = np.minimum(1, seg / 0.5) * np.minimum(1, (bar - seg) / 0.5)
        for m in ch:
            f = note(m)
            out[s0:s1] += 0.035 * env * (np.sin(2 * np.pi * f * seg) + 0.5 * np.sin(2 * np.pi * 2 * f * seg))
    step = beat / 2
    for i in range(int(total / step)):  # bajo pulsante
        ch = chords[int(i * step / bar) % 4]
        f = note(ch[0] - 12)
        s0, L = int(i * step * SR), int(0.2 * SR)
        seg = np.arange(L) / SR
        w_ = np.sign(np.sin(2 * np.pi * f * seg)) * 0.5 + np.sin(2 * np.pi * f * seg)
        out[s0:s0 + L] += (0.06 * np.exp(-seg * 10) * w_)[:len(out[s0:s0 + L])]
    for i in range(int(total / beat)):  # bombo en cada tiempo, caja en 2 y 4
        s0, L = int(i * beat * SR), int(0.3 * SR)
        seg = np.arange(L) / SR
        kick = 0.35 * np.exp(-seg * 14) * np.sin(2 * np.pi * (50 + 70 * np.exp(-seg * 30)) * seg)
        out[s0:s0 + L] += kick[:len(out[s0:s0 + L])]
    rng = np.random.default_rng(3)
    for i in range(int(total / beat)):
        if i % 2 == 1:
            s0, L = int(i * beat * SR), int(0.18 * SR)
            seg = np.arange(L) / SR
            sn = 0.12 * rng.standard_normal(L) * np.exp(-seg * 22)
            out[s0:s0 + L] += sn[:len(out[s0:s0 + L])]
    acc = 0.0
    for i, d in enumerate(durs):
        if i > 0:
            boom(out, acc - 0.05, 0.6, rng)
        if i == 0:
            for s in STOMPS:
                boom(out, s, 0.8, rng)
        if i == 3:
            boom(out, acc + LAND_AT, 1.4, rng)
        acc += d
    return out


VIDEO = Explainer("hulk_24h", SCENES, music, default_voice="kokoro:em_alex",
                  preview_times=[(0, 2.2), (1, 4.0), (2, 3.4), (3, 4.2), (4, 3.0), (5, 3.8), (6, 4.2), (7, 4.6)])

if __name__ == "__main__":
    VIDEO.run()
