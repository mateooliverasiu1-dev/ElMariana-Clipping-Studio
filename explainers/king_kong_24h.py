"""¿Qué pasaría si King Kong apareciera 24 horas en el mundo real?  (Short explicativo, ~55-60 s)

Uso (desde la raíz del repo):
    python explainers/king_kong_24h.py                   -> voz de Alex (Kokoro)
    python explainers/king_kong_24h.py frames            -> fotogramas de muestra

Nota de derechos: King Kong es un personaje protegido (sus versiones de cine tienen dueño).
El video habla del tema pero NO dibuja al personaje: muestra sus efectos.
Cuentas usadas (gorila macho ≈ 1.7 m y 160 kg, escalado ×59 a 100 m):
  masa ≈ 160 kg × 59³ ≈ 32 500 t  (≈ 4.5 veces las 7 300 t de hierro de la Torre Eiffel)
  comida ≈ 18 kg/día × (59³)^0.75 (ley de Kleiber) ≈ 170 t de plantas al día
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

GREEN = (60, 220, 120)


def hour(img, t, label):
    badge(img, label, W / 2, 120, t)


def _skyline(seed=3, h=700, color=(10, 18, 14)) -> Image.Image:
    img = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = random.Random(seed)
    x = -20
    while x < W:
        bw, bh = r.randint(70, 160), r.randint(200, h - 60)
        top = h - bh
        d.rectangle([x, top, x + bw, h], fill=color + (255,))
        for wy in range(top + 20, h - 20, 34):
            for wx in range(x + 12, x + bw - 16, 28):
                if r.random() < 0.33:
                    d.rectangle([wx, wy, wx + 12, wy + 16], fill=(255, 210, 120, r.randint(110, 220)))
        x += bw + r.randint(4, 16)
    return img


SKYLINE = _skyline()
SKYLINE_DRONES = _skyline(seed=7, h=520, color=(14, 20, 28))
ROOFTOPS = _skyline(seed=21, h=560, color=(18, 16, 24))
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
JUNGLE_NIGHT = gradient([(0, (4, 12, 10)), (0.6, (14, 44, 30)), (1, (40, 70, 40))])
FOG = glow(560, (150, 210, 170), 0.45)


def fog_layer(img, t, y, alpha=90, speed=20, seed=1):
    """Bancos de niebla semitransparentes (se dibujan en una capa aparte y se mezclan)."""
    r = random.Random(seed)
    layer = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for k in range(7):
        x = (r.randint(0, W) + t * speed * (1 + k * 0.15)) % (W + 600) - 300
        w, h = r.randint(300, 520), r.randint(50, 90)
        d.ellipse([x - w, 160 - h + k * 18, x + w, 160 + h + k * 18], fill=(170, 205, 185, 255))
    layer = layer.filter(ImageFilter.GaussianBlur(28))
    layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha / 255)))
    img.alpha_composite(layer, (0, int(y - 160)))


# ------------------------------------------------------------------ escenas
BEATS = [1.0, 1.18, 1.36, 1.54, 2.6, 2.78, 2.96, 3.14]   # golpes rápidos, como un pecho golpeado


def s_hook(t, dur):
    img = to_img(JUNGLE_NIGHT)
    paste_center(img, FOG, W / 2, 1250)
    img.alpha_composite(SKYLINE, (0, H - 700))
    fog_layer(img, t, 1420, 80)
    draw_text(img, "¿QUÉ PASARÍA SI", t, 0.15, 340, size=84)
    draw_text(img, "*KING *KONG", t, 0.55, 460, size=150, per_word=0.12)
    draw_text(img, "APARECIERA", t, 1.0, 660, size=90)
    draw_text(img, "*24 *HORAS", t, 1.3, 765, size=130)
    draw_text(img, "EN EL MUNDO REAL?", t, 1.8, 925, size=80)
    return shake(img, t, BEATS, strength=9)


def eiffel(d, cx, base, h, color):
    """Silueta simple de la Torre Eiffel."""
    w = h * 0.36
    d.polygon([(cx - w / 2, base), (cx - w * 0.08, base - h * 0.62), (cx, base - h),
               (cx + w * 0.08, base - h * 0.62), (cx + w / 2, base)], fill=color)
    d.polygon([(cx - w * 0.26, base), (cx, base - h * 0.28), (cx + w * 0.26, base)], fill=(10, 14, 28, 255))
    d.rectangle([cx - w * 0.3, base - h * 0.30, cx + w * 0.3, base - h * 0.27], fill=color)
    d.rectangle([cx - w * 0.16, base - h * 0.62, cx + w * 0.16, base - h * 0.59], fill=color)


def s_weight(t, dur):
    img = to_img(gradient([(0, (8, 12, 26)), (1, (20, 28, 52))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 0")
    draw_text(img, "UN GORILA DE *100 *METROS PESARÍA UNAS *30 *MIL TONELADAS", t, 0.2, 230, size=78)
    # balanza
    p = ease_out((t - 1.0) / 1.2)
    tilt = 0.12 * p
    cx, cy, arm = W / 2, 1060, 380
    d.polygon([(cx - 40, 1560), (cx + 40, 1560), (cx + 14, cy), (cx - 14, cy)], fill=(150, 150, 170, 255))
    lx, ly = cx - arm * math.cos(tilt), cy + arm * math.sin(tilt)
    rx, ry = cx + arm * math.cos(tilt), cy - arm * math.sin(tilt)
    d.line([(lx, ly), (rx, ry)], fill=(200, 200, 215, 255), width=14)
    d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=(220, 220, 235, 255))
    for px, py in ((lx, ly), (rx, ry)):
        d.line([(px, py), (px - 120, py + 200)], fill=(170, 170, 185, 255), width=4)
        d.line([(px, py), (px + 120, py + 200)], fill=(170, 170, 185, 255), width=4)
        d.rounded_rectangle([px - 150, py + 200, px + 150, py + 222], radius=10, fill=(200, 200, 215, 255))
    # izquierda: el peso desconocido; derecha: torres Eiffel
    d.rounded_rectangle([lx - 145, ly + 40, lx + 145, ly + 200], radius=18, fill=(40, 40, 52, 255),
                        outline=YELLOW + (255,), width=5)
    d.text((lx, ly + 120), "≈ 30 000 t", font=font(44), anchor="mm", fill=YELLOW + (255,))
    for k in range(4):
        if t > 1.6 + k * 0.35:
            eiffel(d, rx - 105 + k * 70, ry + 200, 150, (205, 160, 90, 255))
    if t > 3.2:
        d.text((W / 2, 1660), "MÁS QUE 4 TORRES EIFFEL", font=font(64), anchor="mm", fill=WHITE + (255,),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
    return img


def drone(d, x, y, s, t):
    d.line([(x - s, y - s), (x + s, y + s)], fill=(220, 220, 230, 255), width=5)
    d.line([(x - s, y + s), (x + s, y - s)], fill=(220, 220, 230, 255), width=5)
    for ox, oy in ((-s, -s), (s, s), (-s, s), (s, -s)):
        r = s * 0.55
        d.ellipse([x + ox - r, y + oy - r, x + ox + r, y + oy + r], outline=(200, 200, 215, 255), width=3)
    if int(t * 4 + x) % 2 == 0:
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=RED + (255,))


def s_drones(t, dur):
    img = to_img(gradient([(0, (18, 30, 50)), (1, (40, 60, 70))]))
    d = ImageDraw.Draw(img)
    img.alpha_composite(SKYLINE_DRONES, (0, H - 520))
    hour(img, t, "HORA 1")
    draw_text(img, "CIENTOS DE *DRONES… Y EL *MEME DEL AÑO", t, 0.2, 230, size=84)
    cx, cy = W / 2, 1150
    paste_center(img, glow(260, (255, 220, 160), 0.35), cx, cy)
    d.text((cx, cy), "?", font=font(180), anchor="mm", fill=(255, 255, 255, 60))
    r = random.Random(11)
    for k in range(34):
        ang = t * (0.5 + r.random() * 0.6) + r.random() * 6.28
        rad = 170 + r.random() * 330
        x, y = cx + math.cos(ang) * rad, cy + math.sin(ang) * rad * 0.6 + 12 * math.sin(t * 3 + k)
        drone(d, x, y, 14 + r.random() * 8, t + k)
    if t > 2.8:
        p = ease_out((t - 2.8) / 0.35)
        card = Image.new("RGBA", (760, 170), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, 760, 170], radius=30, fill=(255, 255, 255, 240))
        cd.text((40, 38), "MEME DEL AÑO", font=font(56), fill=(20, 20, 26, 255))
        cd.text((40, 110), f"{int(1 + 230 * ease((t - 2.8) / 2.5))} millones de vistas", font=font(36, FONT_SB),
                fill=(90, 90, 100, 255))
        card.putalpha(card.getchannel("A").point(lambda v: int(v * p)))
        paste_center(img, card, W / 2, 1640 - 30 * (1 - p))
    return img


def s_divided(t, dur):
    img = to_img(gradient([(0, (14, 14, 22)), (1, (26, 24, 36))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 2")
    draw_text(img, "EL MUNDO SE *DIVIDE", t, 0.2, 240, size=96)
    share = 0.5 + 0.12 * math.sin(t * 1.7) * ease(t / 1.5)
    top, bot = 560, 1160
    split = int(80 + (W - 160) * share)
    d.rounded_rectangle([80, top, W - 80, bot], radius=40, fill=(40, 40, 52, 255))
    d.rounded_rectangle([80, top, split, bot], radius=40, fill=(200, 50, 50, 255))
    d.rectangle([split - 40, top, split, bot], fill=(200, 50, 50, 255))
    d.rounded_rectangle([split, top, W - 80, bot], radius=40, fill=(40, 170, 90, 255))
    d.rectangle([split, top, split + 40, bot], fill=(40, 170, 90, 255))
    d.line([(split, top - 20), (split, bot + 20)], fill=WHITE + (255,), width=8)
    d.text(((80 + split) / 2, top + 210), "DETENERLO", font=font(60), anchor="mm", fill=WHITE + (255,))
    d.text(((80 + split) / 2, top + 300), f"{share * 100:.0f}%", font=font(88), anchor="mm", fill=WHITE + (255,))
    d.text(((split + W - 80) / 2, top + 210), "PROTEGERLO", font=font(60), anchor="mm", fill=WHITE + (255,))
    d.text(((split + W - 80) / 2, top + 300), f"{(1 - share) * 100:.0f}%", font=font(88), anchor="mm",
           fill=WHITE + (255,))
    if t > 2.6:
        p = ease_out((t - 2.6) / 0.4)
        y = lerp(1460, 1400, p)
        card = Image.new("RGBA", (900, 240), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, 900, 240], radius=40, fill=(30, 30, 38, 250), outline=GREEN + (255,), width=5)
        cd.ellipse([40, 70, 140, 170], fill=GREEN + (255,))
        cd.text((90, 120), "☎", font=font(56, DEJAVU) if Path(DEJAVU).exists() else font(56),
                anchor="mm", fill=(10, 30, 20, 255))
        cd.text((170, 62), "LLAMADA URGENTE", font=font(50), fill=WHITE + (255,))
        cd.text((170, 136), "Expertos en primates", font=font(42, FONT_SB), fill=(200, 230, 210, 255))
        card.putalpha(card.getchannel("A").point(lambda v: int(v * p)))
        img.alpha_composite(card, (90, int(y)))
    return img


def s_city(t, dur):
    img = to_img(gradient([(0, (20, 18, 30)), (0.6, (60, 30, 40)), (1, (30, 24, 30))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 4")
    draw_text(img, "PUENTES *CERRADOS… Y GENTE EN LAS *AZOTEAS", t, 0.2, 230, size=84)
    # puente colgante
    by = 1080
    d.rectangle([0, by, W, by + 26], fill=(150, 150, 165, 255))
    for tx in (260, 820):
        d.rectangle([tx - 18, by - 360, tx + 18, by + 200], fill=(170, 170, 185, 255))
    for a, b in ((0, 260), (260, 820), (820, W)):
        pts = []
        for i in range(41):
            x = lerp(a, b, i / 40)
            if a == 260:
                y = by - 340 + 300 * (1 - ((x - 540) / 280) ** 2)
            elif a == 0:
                y = by - 340 + 320 * ((260 - x) / 260)
            else:
                y = by - 340 + 320 * ((x - 820) / 260)
            pts.append((x, y))
        d.line(pts, fill=(170, 170, 185, 255), width=6)
        for i in range(0, 41, 4):
            d.line([pts[i], (pts[i][0], by)], fill=(130, 130, 145, 255), width=2)
    d.rectangle([0, by + 26, W, by + 260], fill=(14, 30, 50, 255))
    # barrera
    p = ease_out((t - 0.8) / 0.4)
    bx = 120
    for k in range(6):
        col = (230, 40, 40, 255) if k % 2 == 0 else (245, 245, 245, 255)
        d.rectangle([bx + k * 70, by - 90 * p, bx + k * 70 + 70, by - 90 * p + 40], fill=col)
    if p > 0.9:
        d.text((bx + 210, by - 150), "CERRADO", font=font(64), anchor="mm", fill=RED + (255,), stroke_width=5,
               stroke_fill=(0, 0, 0, 255))
    # azoteas con gente grabando
    img.alpha_composite(ROOFTOPS, (0, H - 560))
    d = ImageDraw.Draw(img)
    r = random.Random(4)
    for k in range(26):
        x = r.randint(30, W - 30)
        y = H - r.randint(300, 540)
        flick = 0.5 + 0.5 * math.sin(t * 6 + k)
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(230, 210, 190, 255))
        d.rectangle([x + 10, y - 26, x + 22, y - 6], fill=mix((120, 180, 230), (220, 245, 255), flick) + (255,))
    return img


def truck(d, x, y, fill):
    d.rounded_rectangle([x, y, x + 150, y + 70], radius=10, fill=(230, 170, 40, 255))
    d.rectangle([x + 8, y + 8, x + 8 + 134 * fill, y + 40], fill=(60, 170, 70, 255))
    d.rounded_rectangle([x + 150, y + 20, x + 200, y + 70], radius=10, fill=(200, 140, 30, 255))
    for wx in (x + 30, x + 120, x + 175):
        d.ellipse([wx - 18, y + 58, wx + 18, y + 94], fill=(30, 30, 34, 255))


def s_food(t, dur):
    img = to_img(gradient([(0, (10, 30, 18)), (1, (24, 56, 30))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 8")
    draw_text(img, "¿Y LA *COMIDA?", t, 0.2, 230, size=100)
    draw_text(img, "*MÁS *DE *100 *TONELADAS de plantas al día", t, 1.0, 400, size=72)
    for k in range(16):
        col, row = k % 4, k // 4
        x, y = 90 + col * 235, 800 + row * 200
        f = ease((t - 1.6 - k * 0.12) / 0.5)
        if f > 0:
            truck(d, x, y, f)
    if t > 3.8:
        d.text((W / 2, 1680), "≈ 17 CAMIONES LLENOS, CADA DÍA", font=font(56), anchor="mm", fill=YELLOW + (255,),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
    return img


def heart_shape(d, cx, cy, s, color):
    d.ellipse([cx - s, cy - s * 0.8, cx, cy + s * 0.2], fill=color)
    d.ellipse([cx, cy - s * 0.8, cx + s, cy + s * 0.2], fill=color)
    d.polygon([(cx - s * 0.98, cy - s * 0.2), (cx + s * 0.98, cy - s * 0.2), (cx, cy + s)], fill=color)


def s_body(t, dur):
    img = to_img(gradient([(0, (30, 8, 12)), (1, (60, 16, 20))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 12")
    draw_text(img, "SU CUERPO SERÍA SU *PEOR *ENEMIGO", t, 0.2, 230, size=88)
    # termómetro
    tx, top, bot = 250, 760, 1540
    d.rounded_rectangle([tx - 40, top, tx + 40, bot], radius=40, fill=(230, 230, 240, 255))
    d.ellipse([tx - 75, bot - 40, tx + 75, bot + 110], fill=(230, 230, 240, 255))
    lvl = lerp(bot - 60, top + 40, ease((t - 0.8) / 2.5))
    d.rounded_rectangle([tx - 22, lvl, tx + 22, bot], radius=22, fill=RED + (255,))
    d.ellipse([tx - 55, bot - 20, tx + 55, bot + 90], fill=RED + (255,))
    d.text((tx, bot + 170), "SE SOBRE-\nCALENTARÍA", font=font(44), anchor="mm", align="center", fill=WHITE + (255,))
    # corazón que bombea hacia arriba 100 m
    hx, hy = 720, 1420
    beat = 1 + 0.12 * max(0, math.sin(t * 7)) ** 8
    heart_shape(d, hx, hy, 110 * beat, (230, 40, 60, 255))
    arr_top = 820
    d.line([(hx, hy - 150), (hx, arr_top)], fill=(255, 120, 120, 255), width=16)
    d.polygon([(hx - 40, arr_top + 30), (hx + 40, arr_top + 30), (hx, arr_top - 30)], fill=(255, 120, 120, 255))
    flow = (t * 300) % 500
    for k in range(4):
        yy = hy - 160 - ((flow + k * 125) % 500)
        if yy > arr_top + 30:
            d.ellipse([hx - 12, yy - 12, hx + 12, yy + 12], fill=(255, 220, 220, 255))
    d.text((hx + 110, 880), "100 m", font=font(64), anchor="lm", fill=YELLOW + (255,), stroke_width=5,
           stroke_fill=(0, 0, 0, 255))
    d.text((hx, 1710), "PRESIÓN EXTREMA", font=font(44), anchor="mm", fill=WHITE + (255,))
    return img


def s_ending(t, dur):
    k = ease(t / 3.0)
    img = to_img(gradient([(0, mix((10, 20, 26), (60, 90, 100), k)), (0.5, mix((40, 60, 50), (210, 180, 120), k)),
                           (1, (20, 40, 26))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 24")
    # selva al amanecer con niebla
    r = random.Random(6)
    for layer, (ybase, col) in enumerate(((1000, (24, 50, 34)), (1200, (16, 38, 24)), (1420, (10, 26, 16)))):
        pts = [(0, H)]
        for x in range(0, W + 60, 60):
            pts.append((x, ybase - r.randint(0, 120)))
        pts.append((W, H))
        d.polygon(pts, fill=col + (255,))
        fog_layer(img, t, ybase + 60, alpha=70 + 20 * layer, speed=15 + 8 * layer, seed=layer)
        d = ImageDraw.Draw(img)
    # huellas de nudillos (rasgo genérico de los gorilas) que se pierden en la niebla
    prints = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(prints)
    for j in range(6):
        y = 1820 - j * 120
        x = W / 2 + (60 if j % 2 else -60) * (1 - j * 0.1)
        s = 1 - j * 0.12
        a = int(220 * (1 - j / 7) * ease((t - 0.5 - j * 0.25) / 0.4))
        for q in range(4):
            d.ellipse([x - 70 * s + q * 38 * s, y - 16 * s, x - 40 * s + q * 38 * s, y + 16 * s], fill=(8, 16, 10, a))
    img.alpha_composite(prints)
    draw_text(img, "SE PIERDE EN LA *NIEBLA…", t, 0.2, 280, size=92, out_at=2.6)
    draw_text(img, "…PERO EL MUNDO *NUNCA SERÍA IGUAL", t, 2.9, 280, size=92)
    draw_text(img, "¿TÚ LO *PROTEGERÍAS O LO *DETENDRÍAS?", t, 4.2, 690, size=84)
    return img


SCENES = [
    ("01_hook", s_hook, 4.5, "¿Qué pasaría si King Kong apareciera en el mundo real durante veinticuatro horas?"),
    ("02_peso", s_weight, 5.0, "Hora cero. Un gorila de cien metros pesaría unas treinta mil toneladas: "
                               "más que cuatro torres Eiffel juntas."),
    ("03_drones", s_drones, 5.5, "Hora uno. Cientos de drones volando a su alrededor para grabarlo, "
                                 "y el gorila gigante convertido en el meme del año."),
    ("04_dividido", s_divided, 6.0, "Hora dos. El mundo se divide: unos piden detenerlo y otros exigen protegerlo. "
                                    "Los gobiernos llaman de urgencia a expertos en primates."),
    ("05_ciudad", s_city, 5.0, "Hora cuatro. Puentes cerrados, ciudades evacuadas, y gente subiendo a las azoteas "
                               "para verlo de cerca."),
    ("06_comida", s_food, 5.5, "Hora ocho. ¿Y la comida? Según la biología, necesitaría más de cien toneladas "
                               "de plantas al día."),
    ("07_cuerpo", s_body, 6.0, "Hora doce. Su cuerpo sería su peor enemigo: se sobrecalentaría, y su corazón "
                               "tendría que bombear sangre a cien metros de altura."),
    ("08_final", s_ending, 6.0, "Hora veinticuatro. Se pierde en la niebla de la selva. Pero el mundo ya nunca "
                                "sería igual. ¿Tú lo protegerías, o lo detendrías?"),
]


# ------------------------------------------------------------------ música: tambores de selva + tensión (original)
def music(total: float, durs) -> np.ndarray:
    n = int((total + 1) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    bpm = 100
    beat = 60 / bpm
    bar = beat * 4
    chords = [[52, 55, 59], [48, 52, 55], [50, 53, 57], [47, 51, 54]]  # Em C Dm B
    out += 0.08 * np.sin(2 * np.pi * note(28) * t)  # bordón grave (E1)
    for b in range(int(total / bar) + 2):
        ch = chords[b % 4]
        s0, s1 = int(b * bar * SR), min(int((b + 1) * bar * SR), n)
        if s0 >= n:
            break
        seg = t[s0:s1] - b * bar
        env = np.minimum(1, seg / 0.8) * np.minimum(1, (bar - seg) / 0.8)
        for m in ch:
            f = note(m)
            out[s0:s1] += 0.035 * env * (np.sin(2 * np.pi * f * seg) + 0.4 * np.sin(2 * np.pi * 2 * f * seg))

    def tom(at, f0, g):
        s0, L = int(at * SR), int(0.35 * SR)
        if s0 >= n:
            return
        seg = np.arange(L) / SR
        x = g * np.exp(-seg * 11) * np.sin(2 * np.pi * (f0 + 40 * np.exp(-seg * 30)) * seg)
        out[s0:s0 + L] += x[:len(out[s0:s0 + L])]

    pattern = [(0, 90, 0.45), (0.75, 120, 0.25), (1.5, 90, 0.35), (2, 70, 0.5), (2.5, 120, 0.25), (3, 90, 0.35),
               (3.5, 140, 0.25)]
    for b in range(int(total / bar) + 1):
        for off, f0, g in pattern:
            tom(b * bar + off * beat, f0, g)
    rng = np.random.default_rng(2)
    acc = 0.0
    for i, d in enumerate(durs):
        if i > 0:
            boom(out, acc - 0.05, 0.65, rng)
        acc += d
    for at in BEATS:  # golpes rápidos del gancho
        tom(at, 60, 0.9)
    return out


VIDEO = Explainer("king_kong_24h", SCENES, music, default_voice="kokoro:em_alex",
                  preview_times=[(0, 1.9), (1, 3.5), (2, 3.6), (3, 3.2), (4, 2.5), (5, 4.2), (6, 3.0), (7, 4.6)])

if __name__ == "__main__":
    VIDEO.run()
