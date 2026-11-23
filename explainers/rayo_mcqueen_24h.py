"""¿Qué pasaría si el Rayo McQueen apareciera 24 horas en el mundo real?  (humor mexicano)

Uso (desde la raíz del repo):
    python explainers/rayo_mcqueen_24h.py            -> voz de Alex, con groserías (pocas)
    python explainers/rayo_mcqueen_24h.py --limpio   -> sin groserías
    python explainers/rayo_mcqueen_24h.py frames

Nota de derechos: el Rayo McQueen es un personaje de Disney/Pixar. NO se dibuja al personaje
(ningún auto rojo de carreras ni sus símbolos); el video muestra sus efectos.
Datos: autos de NASCAR ≈ 5 mpg (≈ 2 km/L) y velocidades de carrera de ~200 mph (≈ 320 km/h);
límite en autopistas de México: 110 km/h (Ley General de Movilidad y Seguridad Vial).
Llantas lisas de carreras (slicks): sin dibujo, pierden agarre con agua.
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

CLEAN = {"MAMES": "MANCHES", "mames": "manches", "VERGA": "GORRO", "verga": "gorro",
         "CABRÓN": "COMPA", "cabrón": "compa", "CHINGO": "MONTÓN", "chingo": "montón",
         "qué pedo": "qué onda", "QUÉ PEDO": "QUÉ ONDA"}


def hour(img, t, label):
    badge(img, label, W / 2, 120, t)


def speed_lines(img, t, y0, y1, n=40, seed=3, col=(255, 255, 255)):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = random.Random(seed)
    for _ in range(n):
        y = r.uniform(y0, y1)
        L = r.uniform(120, 420)
        x = (r.uniform(0, W + L) - t * r.uniform(1200, 2400)) % (W + L) - L
        d.line([(x, y), (x + L, y)], fill=col + (r.randint(60, 160),), width=r.randint(2, 6))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1)))


def s_hook(t, dur):
    img = to_img(gradient([(0, (8, 10, 24)), (0.6, (20, 24, 50)), (1, (40, 40, 50))]))
    d = ImageDraw.Draw(img)
    for x in (120, 960):  # luces del estadio
        paste_center(img, glow(260, (255, 250, 220), 0.6), x, 330)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 1380, W, H], fill=(46, 46, 52, 255))
    for k in range(0, W, 80):  # bandera a cuadros en la línea de meta
        for j in range(3):
            if (k // 80 + j) % 2 == 0:
                d.rectangle([k, 1380 + j * 40, k + 80, 1420 + j * 40], fill=(240, 240, 240, 255))
    speed_lines(img, t, 1500, 1900, n=50)
    draw_text(img, "¿QUÉ PASARÍA SI EL", t, 0.15, 330, size=80)
    draw_text(img, "*RAYO *MCQUEEN", t, 0.55, 450, size=112, per_word=0.12, max_w=1020)
    draw_text(img, "APARECIERA", t, 1.0, 640, size=90)
    draw_text(img, "*24 *HORAS", t, 1.3, 745, size=130)
    draw_text(img, "EN EL MUNDO REAL?", t, 1.8, 905, size=80)
    return img


def gauge(d, cx, cy, R, value, vmax, label):
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(20, 22, 30, 255), outline=(90, 95, 110, 255), width=8)
    for k in range(0, vmax + 1, 20):
        a = math.radians(140 + 260 * k / vmax)
        r0 = R - (40 if k % 100 == 0 else 22)
        d.line([(cx + math.cos(a) * r0, cy + math.sin(a) * r0), (cx + math.cos(a) * (R - 10), cy + math.sin(a) * (R - 10))],
               fill=((255, 80, 80) if k > 110 else (220, 220, 230)) + (255,), width=5 if k % 100 == 0 else 3)
        if k % 100 == 0:
            d.text((cx + math.cos(a) * (R - 80), cy + math.sin(a) * (R - 80)), str(k), font=font(40), anchor="mm",
                   fill=WHITE + (255,))
    a = math.radians(140 + 260 * min(value, vmax) / vmax)
    d.line([(cx, cy), (cx + math.cos(a) * (R - 50), cy + math.sin(a) * (R - 50))], fill=(255, 70, 50, 255), width=12)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(230, 230, 240, 255))
    d.text((cx, cy + R * 0.5), f"{int(value)} {label}", font=font(60), anchor="mm", fill=YELLOW + (255,))


def s_speed(t, dur):
    img = to_img(gradient([(0, (12, 14, 24)), (1, (26, 30, 46))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 0")
    draw_text(img, "UN AUTO DE CARRERAS PASA DE LOS *300 *KM/H", t, 0.2, 230, size=80)
    v = 320 * ease_out((t - 0.6) / 1.6)
    gauge(d, W / 2, 900, 300, v, 340, "km/h")
    if t > 2.2:  # señal de límite
        cx, cy = 230, 1400
        d.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], fill=WHITE + (255,), outline=(220, 30, 30, 255), width=24)
        d.text((cx, cy), "110", font=font(96), anchor="mm", fill=(20, 20, 26, 255))
        d.text((cx + 170, cy - 40), "MÁXIMO EN", font=font(46), anchor="lm", fill=WHITE + (255,))
        d.text((cx + 170, cy + 20), "AUTOPISTAS DE MÉXICO", font=font(40), anchor="lm", fill=WHITE + (255,))
    draw_text(img, "¡*NO *MAMES, LA MULTA!", t, 3.4, 1640, size=88)
    return img


def s_license(t, dur):
    img = to_img(gradient([(0, (14, 30, 50)), (1, (30, 60, 90))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 1")
    draw_text(img, "UN AUTO QUE *HABLA Y *MANEJA *SOLO…", t, 0.2, 230, size=84)
    p = ease_out((t - 0.7) / 0.6)
    card = Image.new("RGBA", (860, 520), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([0, 0, 860, 520], radius=36, fill=(235, 240, 245, 255))
    cd.rectangle([0, 0, 860, 110], fill=(40, 90, 160, 255))
    cd.text((40, 55), "LICENCIA DE CONDUCIR", font=font(52), anchor="lm", fill=WHITE + (255,))
    cd.rounded_rectangle([40, 150, 300, 470], radius=20, fill=(190, 196, 206, 255))
    cd.text((170, 310), "?", font=font(180), anchor="mm", fill=(240, 244, 248, 255))
    for k, (lab, val) in enumerate((("Nombre", "???"), ("Tipo", "¿Persona? ¿Auto?"), ("Firma", "No tiene manos"))):
        cd.text((340, 170 + k * 100), lab, font=font(34, FONT_SB), fill=(110, 120, 140, 255))
        cd.text((340, 210 + k * 100), val, font=font(44), fill=(30, 40, 60, 255))
    card.putalpha(card.getchannel("A").point(lambda v: int(v * p)))
    paste_center(img, card, W / 2, 900 + 40 * (1 - p))
    if t > 2.4:
        draw_text(img, "LOS ABOGADOS NO SABEN NI *QUÉ *PEDO", t, 2.4, 1360, size=76)
    return img


def s_kids(t, dur):
    img = to_img(gradient([(0, (40, 12, 60)), (1, (90, 30, 90))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 2")
    draw_text(img, "LOS NIÑOS *PIERDEN *LA *CABEZA", t, 0.2, 230, size=88)
    cx, cy, pw, ph = W / 2, 1150, 660, 1080
    phone(d, cx, cy, pw, ph)
    for j in range(3):
        if t < 0.8 + j * 0.5:
            continue
        vy = cy - ph / 2 + 90 + j * 300
        x0 = cx - pw / 2 + 40
        d.rounded_rectangle([x0, vy, x0 + pw - 80, vy + 260], radius=24, fill=(50, 40, 70, 255))
        d.polygon([(x0 + 250, vy + 90), (x0 + 250, vy + 170), (x0 + 320, vy + 130)], fill=(230, 230, 240, 255))
        views = int(250_000 * (1 + (t - 0.8 - j * 0.5) * (3 + j)) ** 1.5)
        d.text((x0 + 20, vy + 215), f"{views:,} vistas", font=font(32, FONT_SB), fill=(220, 220, 235, 255))
        d.text((x0 + 20, vy + 20), ["«¡Dí tu frase!»", "Mi sobrino llorando de emoción", "¿Me firmas la mochila?"][j],
               font=font(34), fill=WHITE + (255,))
    draw_text(img, "UN *CHINGO DE VIDEOS", t, 2.6, 1730, size=80)
    return img


def s_fuel(t, dur):
    img = to_img(gradient([(0, (30, 20, 10)), (1, (60, 40, 20))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 4")
    draw_text(img, "RINDE UNOS *2 *KM *POR *LITRO", t, 0.2, 230, size=90)
    rows = [("AUTO DE CARRERAS", 2, (255, 90, 70)), ("AUTO COMPACTO COMÚN", 14, (90, 200, 120))]
    for i, (lab, kml, col) in enumerate(rows):
        if t < 0.8 + i * 0.4:
            continue
        y = 560 + i * 190
        p = ease_out((t - 0.8 - i * 0.4) / 0.7)
        d.text((100, y), lab, font=font(46), fill=WHITE + (255,))
        d.rounded_rectangle([100, y + 70, 100 + max(30, (W - 440) * kml / 14 * p), y + 130], radius=20, fill=col + (255,))
        d.text((W - 100, y + 100), f"≈ {kml} km/L", font=font(44), anchor="rm", fill=col + (255,))
    # bomba de gasolina
    bx, by = 260, 1060
    d.rounded_rectangle([bx - 140, by, bx + 140, by + 520], radius=26, fill=(220, 50, 50, 255))
    d.rounded_rectangle([bx - 110, by + 40, bx + 110, by + 200], radius=12, fill=(20, 24, 20, 255))
    pesos = int(3000 * ease((t - 1.6) / 2.4))
    d.text((bx, by + 120), f"${pesos:,}", font=font(56), anchor="mm", fill=(120, 255, 140, 255))
    d.line([(bx + 140, by + 260), (bx + 260, by + 300), (bx + 300, by + 420)], fill=(30, 30, 34, 255), width=14)
    if t > 2.8:
        d.text((720, 1300), "LA GASOLINERA", font=font(52), anchor="mm", fill=WHITE + (255,))
        d.text((720, 1380), "SE QUEDA SIN", font=font(52), anchor="mm", fill=WHITE + (255,))
        d.text((720, 1470), "PREMIUM", font=font(84), anchor="mm", fill=YELLOW + (255,), stroke_width=6,
               stroke_fill=(0, 0, 0, 255))
    return img


def tire(d, cx, cy, R, slick, t):
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(28, 28, 32, 255))
    if not slick:  # dibujo de llanta de calle
        for k in range(24):
            a = 2 * math.pi * k / 24 + t * 0.5
            d.line([(cx + math.cos(a) * (R - 40), cy + math.sin(a) * (R - 40)), (cx + math.cos(a) * (R - 5), cy + math.sin(a) * (R - 5))],
                   fill=(70, 70, 76, 255), width=10)
    d.ellipse([cx - R * 0.5, cy - R * 0.5, cx + R * 0.5, cy + R * 0.5], fill=(170, 175, 185, 255))
    d.ellipse([cx - R * 0.15, cy - R * 0.15, cx + R * 0.15, cy + R * 0.15], fill=(90, 95, 105, 255))


def s_tires(t, dur):
    img = to_img(gradient([(0, (30, 40, 56)), (1, (60, 70, 86))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 6")
    draw_text(img, "SUS LLANTAS DE CARRERAS SON *LISAS", t, 0.2, 230, size=84)
    tire(d, 280, 860, 190, True, t)
    d.text((280, 1100), "DE CARRERAS", font=font(42), anchor="mm", fill=WHITE + (255,))
    tire(d, 800, 860, 190, False, t)
    d.text((800, 1100), "DE CALLE", font=font(42), anchor="mm", fill=WHITE + (255,))
    rain = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rain)
    r = random.Random(1)
    for _ in range(90):
        x = r.uniform(0, W)
        y = (r.uniform(0, H) + t * 1400) % H
        rd.line([(x, y), (x - 10, y + 40)], fill=(170, 200, 255, 120), width=3)
    img.alpha_composite(rain)
    d = ImageDraw.Draw(img)
    if t > 1.8:  # bache
        d.ellipse([200, 1260, 880, 1440], fill=(20, 20, 24, 255))
        d.ellipse([240, 1290, 840, 1420], fill=(40, 50, 70, 255))
        d.text((540, 1350), "BACHE", font=font(64), anchor="mm", fill=(230, 230, 240, 255))
    draw_text(img, "CON LLUVIA Y BACHES… *VALIÓ *VERGA", t, 3.0, 1560, size=78)
    return img


def s_cdmx(t, dur):
    img = to_img(gradient([(0, (230, 230, 236)), (1, (200, 200, 210))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 12")
    draw_text(img, "LLEGA A LA CDMX Y LE TOCA *HOY *NO *CIRCULA", t, 0.2, 230, size=80)
    p = ease_out((t - 0.7) / 0.5)
    d.rounded_rectangle([W / 2 - 330, 620, W / 2 + 330, 960], radius=30, fill=(200, 40, 40, int(255 * p)))
    d.text((W / 2, 720), "HOY NO", font=font(110), anchor="mm", fill=WHITE + (255,))
    d.text((W / 2, 860), "CIRCULA", font=font(110), anchor="mm", fill=WHITE + (255,))
    items = ["Verificación", "Placas", "Tarjeta de circulación"]
    for i, it in enumerate(items):
        if t < 1.6 + i * 0.4:
            continue
        y = 1060 + i * 130
        d.rounded_rectangle([200, y, 280, y + 80], radius=14, fill=(230, 70, 70, 255))
        d.line([(220, y + 20), (260, y + 60)], fill=WHITE + (255,), width=10)
        d.line([(260, y + 20), (220, y + 60)], fill=WHITE + (255,), width=10)
        d.text((310, y + 40), it, font=font(52), anchor="lm", fill=(30, 40, 60, 255))
    draw_text(img, "AHÍ SÍ, *CABRÓN", t, 3.2, 1560, size=96)
    return img


def s_ending(t, dur):
    img = to_img(gradient([(0, (26, 24, 30)), (1, (50, 44, 40))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 24")
    # taller: herramientas en la pared
    d.rectangle([60, 520, W - 60, 1060], fill=(70, 60, 50, 255))
    for k in range(7):
        x = 140 + k * 130
        d.line([(x, 560), (x, 760 + (k % 3) * 40)], fill=(190, 195, 205, 255), width=14)
        d.ellipse([x - 26, 740 + (k % 3) * 40, x + 26, 792 + (k % 3) * 40], outline=(190, 195, 205, 255), width=10)
    d.rectangle([60, 1060, W - 60, 1090], fill=(110, 90, 70, 255))
    draw_text(img, "TERMINA EN UN *TALLER…", t, 0.2, 260, size=92, out_at=2.4)
    if t > 1.0:
        p = ease_out((t - 1.0) / 0.4)
        bub = Image.new("RGBA", (900, 320), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bub)
        bd.rounded_rectangle([0, 0, 900, 270], radius=50, fill=(255, 255, 255, 250))
        bd.polygon([(160, 260), (260, 260), (150, 320)], fill=(255, 255, 255, 250))
        bd.text((450, 90), "«Uy, joven…", font=font(64), anchor="mm", fill=(20, 20, 26, 255))
        bd.text((450, 180), "esto va a salir caro»", font=font(64), anchor="mm", fill=(20, 20, 26, 255))
        bub.putalpha(bub.getchannel("A").point(lambda v: int(v * p)))
        paste_center(img, bub, W / 2, 1300)
    draw_text(img, "¿TÚ QUÉ LE *PREGUNTARÍAS?", t, 3.6, 1600, size=90)
    return img


SCENES = [
    ("01_hook", s_hook, 4.5, "¿Qué pasaría si el Rayo McQueen apareciera en el mundo real durante veinticuatro "
                             "horas? Agárrate, güey."),
    ("02_velocidad", s_speed, 5.5, "Hora cero. Un auto de carreras como él pasa de los trescientos kilómetros por "
                                   "hora. En las autopistas de México el máximo es de ciento diez. ¡No mames, la multa!"),
    ("03_licencia", s_license, 5.0, "Hora uno. Un auto que habla y maneja solo: ¿quién saca la licencia? ¿Él? ¿Su "
                                    "dueño? Los abogados no saben ni qué pedo."),
    ("04_ninos", s_kids, 5.0, "Hora dos. Los niños pierden la cabeza, y en redes hay un chingo de videos "
                              "pidiéndole su frase."),
    ("05_gasolina", s_fuel, 5.5, "Hora cuatro. Los autos de carreras rinden unos dos kilómetros por litro. Cada "
                                 "carga sale carísima, y la gasolinera se queda sin premium."),
    ("06_llantas", s_tires, 5.5, "Hora seis. Sus llantas de carreras son lisas: perfectas en la pista, pero con "
                                 "lluvia y baches, valió verga."),
    ("07_cdmx", s_cdmx, 5.5, "Hora doce. Llega a la Ciudad de México y le toca Hoy No Circula. Sin verificación y "
                             "sin placas. Ahí sí, cabrón."),
    ("08_final", s_ending, 5.5, "Hora veinticuatro. Termina en un taller, y el mecánico solo dice: uy, joven, esto "
                                "va a salir caro. ¿Tú qué le preguntarías?"),
]


def music(total: float, durs) -> np.ndarray:
    """Rock de carreras: power chords, batería rápida y motor (original)."""
    n = int((total + 1) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    bpm = 140
    beat = 60 / bpm
    bar = beat * 4
    roots = [40, 40, 43, 45]  # E E G A
    step = beat / 2
    for i in range(int(total / step)):  # power chords en corcheas (onda cuadrada suave)
        root = roots[int(i * step / bar) % 4]
        s0, L = int(i * step * SR), int(step * 0.95 * SR)
        seg = np.arange(L) / SR
        env = np.exp(-seg * 6)
        x = sum(np.tanh(3 * np.sin(2 * np.pi * note(m) * seg)) for m in (root, root + 7, root + 12)) / 3
        out[s0:s0 + L] += (0.07 * env * x)[:len(out[s0:s0 + L])]
    rng = np.random.default_rng(13)
    for i in range(int(total / beat)):
        s0, L = int(i * beat * SR), int(0.25 * SR)
        seg = np.arange(L) / SR
        if i % 2 == 0:
            out[s0:s0 + L] += (0.35 * np.exp(-seg * 16) * np.sin(2 * np.pi * (50 + 70 * np.exp(-seg * 30)) * seg))[:len(out[s0:s0 + L])]
        else:
            out[s0:s0 + L] += (0.14 * rng.standard_normal(L) * np.exp(-seg * 20))[:len(out[s0:s0 + L])]
    acc = 0.0
    for i, d in enumerate(durs):
        if i > 0:
            boom(out, acc - 0.05, 0.45, rng)
        if i == 1:  # rugido de motor que sube con el velocímetro
            s0, L = int((acc + 0.5) * SR), int(2.0 * SR)
            seg = np.arange(L) / SR
            f = 60 + 160 * np.minimum(1, seg / 1.6)
            ph = 2 * np.cumsum(np.pi * f / SR)
            eng = 0.25 * np.tanh(4 * np.sin(ph)) * np.minimum(1, seg / 0.2) * np.minimum(1, (2.0 - seg) / 0.3)
            out[s0:s0 + L] += eng[:len(out[s0:s0 + L])]
        acc += d
    return out


VIDEO = Explainer("rayo_mcqueen_24h", SCENES, music, default_voice="kokoro:em_alex", clean_map=CLEAN,
                  preview_times=[(0, 2.4), (1, 4.0), (2, 3.4), (3, 3.4), (4, 3.6), (5, 3.8), (6, 3.8), (7, 4.2)])

if __name__ == "__main__":
    VIDEO.run()
