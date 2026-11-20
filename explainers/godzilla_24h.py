"""¿Qué pasaría si Godzilla apareciera 24 horas en el mundo real?  (Short explicativo, ~55 s)

Uso (desde la raíz del repo):
    python explainers/godzilla_24h.py                    -> voz de Alex (Kokoro)
    python explainers/godzilla_24h.py --voz es_MX-claude-high
    python explainers/godzilla_24h.py frames             -> fotogramas de muestra

Nota de derechos: Godzilla es un personaje registrado de Toho. El video habla del tema,
pero NO dibuja al personaje: muestra sus efectos (sismógrafos, alertas, redes, ciudades).
Animaciones y música son originales, generadas por código.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import (FONT_SB, H, RED, SR, W, WHITE, YELLOW, Explainer, badge, draw_text, ease, ease_out, font,  # noqa: E402
                    glow, gradient, lerp, mix, note, paste_center, to_img)

rnd = random.Random(24)

# ------------------------------------------------------------------ elementos comunes
def _skyline() -> Image.Image:
    img = Image.new("RGBA", (W, 760), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = -20
    r = random.Random(3)
    while x < W:
        bw = r.randint(70, 170)
        bh = r.randint(220, 640)
        top = 760 - bh
        d.rectangle([x, top, x + bw, 760], fill=(12, 10, 18, 255))
        for wy in range(top + 20, 740, 34):
            for wx in range(x + 12, x + bw - 16, 28):
                if r.random() < 0.38:
                    d.rectangle([wx, wy, wx + 12, wy + 16], fill=(255, 200, 90, r.randint(120, 230)))
        x += bw + r.randint(4, 18)
    return img


SKYLINE = _skyline()
NIGHT_RED = gradient([(0, (8, 6, 18)), (0.55, (52, 10, 22)), (1, (120, 32, 18))])
DARK = gradient([(0, (10, 10, 24)), (1, (26, 22, 48))])
RED_GLOW = glow(520, (255, 60, 30), 0.7)


def shake(img: Image.Image, t: float, hits, strength=14) -> Image.Image:
    """Sacude el cuadro justo después de cada impacto."""
    amp = sum(strength * math.exp(-(t - h) * 9) for h in hits if t >= h)
    if amp < 0.5:
        return img
    dx = int(amp * math.sin(t * 91))
    dy = int(amp * math.cos(t * 77))
    return img.transform(img.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), fillcolor=(0, 0, 0, 255))


def hour(img, t, label):
    badge(img, label, W / 2, 120, t)


def phone(d: ImageDraw.ImageDraw, cx, cy, w, h):
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=60, fill=(20, 20, 26, 255),
                        outline=(70, 70, 90, 255), width=8)
    d.rounded_rectangle([cx - 70, cy - h / 2 + 18, cx + 70, cy - h / 2 + 42], radius=12, fill=(8, 8, 12, 255))


def fmt(n: float) -> str:
    return f"{int(n):,}".replace(",", ",")


# ------------------------------------------------------------------ escenas
STOMPS_1 = [1.0, 2.3, 3.6]


def s_hook(t, dur):
    img = to_img(NIGHT_RED)
    pulse = 0.75 + 0.25 * math.sin(t * 2.5)
    g = RED_GLOW.resize((int(1040 * pulse * 1.3), int(1040 * pulse * 1.3)))
    paste_center(img, g, W / 2, 1300)
    img.alpha_composite(SKYLINE, (0, H - 760))
    # luz de sirena
    siren = Image.new("RGBA", (W, H), (255, 30, 30, int(40 * (0.5 + 0.5 * math.sin(t * 6)))))
    img.alpha_composite(siren)
    draw_text(img, "¿QUÉ PASARÍA SI", t, 0.15, 360, size=84)
    draw_text(img, "*GODZILLA", t, 0.55, 480, size=150, per_word=0.0)
    draw_text(img, "APARECIERA", t, 1.0, 670, size=90)
    draw_text(img, "*24 *HORAS", t, 1.3, 775, size=130)
    draw_text(img, "EN EL MUNDO REAL?", t, 1.8, 935, size=80)
    return shake(img, t, STOMPS_1)


STEP_EVERY, STEP_FIRST = 1.3, 0.5


def s_physics(t, dur):
    img = to_img(DARK)
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 0")
    draw_text(img, "*100 METROS = DECENAS DE MILES DE *TONELADAS", t, 0.2, 260, size=82)
    # sismógrafo
    top, bot, left, right = 860, 1380, 70, 1010
    d.rounded_rectangle([left, top, right, bot], radius=24, fill=(238, 236, 228, 255))
    for gy in range(top + 40, bot, 60):
        d.line([(left + 10, gy), (right - 10, gy)], fill=(205, 200, 190, 255), width=2)
    for gx in range(left + 40, right, 80):
        d.line([(gx, top + 10), (gx, bot - 10)], fill=(215, 210, 200, 255), width=2)
    mid = (top + bot) / 2
    pen_x, speed = 900, 260
    steps = [STEP_FIRST + k * STEP_EVERY for k in range(20)]
    pts = []
    for x in range(left + 12, pen_x, 3):
        tau = t - (pen_x - x) / speed
        a = 4 * math.sin(53 * tau) + 3 * math.sin(31 * tau + 1)
        for s in steps:
            if 0 <= tau - s < 2:
                a += 210 * math.exp(-(tau - s) * 3.5) * math.sin(2 * math.pi * 8 * (tau - s))
        pts.append((x, mid + max(-240, min(240, a))))
    if len(pts) > 1:
        d.line(pts, fill=(200, 30, 30, 255), width=5)
    d.line([(pen_x, pts[-1][1] if pts else mid), (right - 10, mid - 300)], fill=(60, 60, 70, 255), width=6)
    d.ellipse([pen_x - 10, (pts[-1][1] if pts else mid) - 10, pen_x + 10, (pts[-1][1] if pts else mid) + 10],
              fill=(30, 30, 40, 255))
    d.text((left + 30, top + 26), "SISMÓGRAFO · ESTACIÓN A 4 km", font=font(36, FONT_SB), fill=(90, 90, 100, 255))
    draw_text(img, "cada paso = un pequeño *sismo", t, 2.2, 1460, size=60, per_word=0.06)
    return shake(img, t, [s for s in steps if s < dur], strength=10)


def s_social(t, dur):
    img = to_img(gradient([(0, (24, 8, 40)), (1, (60, 20, 80))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 1")
    draw_text(img, "TENDENCIA MUNDIAL EN *MINUTOS", t, 0.2, 240, size=88)
    cx, cy, pw, ph = W / 2, 1130, 640, 1080
    phone(d, cx, cy, pw, ph)
    x0, y0 = cx - pw / 2 + 50, cy - ph / 2 + 90
    d.text((x0, y0), "Tendencias · Mundial", font=font(40, FONT_SB), fill=(170, 170, 190, 255))
    rows = [("#Godzilla", 48e6), ("#24Horas", 21e6), ("#EsIA", 9e6)]
    grow = ease_out(t / 4)
    for i, (tag, n) in enumerate(rows):
        y = y0 + 80 + i * 110
        d.text((x0, y), f"{i + 1}", font=font(46), fill=(120, 120, 140, 255))
        d.text((x0 + 60, y - 4), tag, font=font(52), fill=WHITE + (255,))
        d.text((x0 + 60, y + 58), f"{n * (0.2 + 0.8 * grow) / 1e6:.1f} M publicaciones", font=font(32, FONT_SB),
               fill=(150, 150, 170, 255))
    for j in range(2):
        vy = y0 + 440 + j * 260
        d.rounded_rectangle([x0, vy, x0 + pw - 100, vy + 220], radius=26, fill=(40, 40, 54, 255))
        tri = [(x0 + 250, vy + 70), (x0 + 250, vy + 150), (x0 + 320, vy + 110)]
        d.polygon(tri, fill=(220, 220, 235, 255))
        d.rounded_rectangle([x0 + 20, vy + 20, x0 + 170, vy + 66], radius=10, fill=RED + (255,))
        d.text((x0 + 95, vy + 43), "EN VIVO", font=font(30), anchor="mm", fill=WHITE + (255,))
        viewers = 1.2e6 * (1 + t * (2.4 + j)) ** 1.6
        d.text((x0 + 20, vy + 170), f"{fmt(viewers)} viendo", font=font(32, FONT_SB), fill=(210, 210, 225, 255))
    if t > 3.2:
        p = ease_out((t - 3.2) / 0.3)
        st = Image.new("RGBA", (560, 200), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        sd.rounded_rectangle([8, 8, 552, 192], radius=24, outline=YELLOW + (255,), width=12)
        sd.text((280, 100), "¿ES IA?", font=font(110), anchor="mm", fill=YELLOW + (255,), stroke_width=6,
                stroke_fill=(0, 0, 0, 255))
        st = st.rotate(-12, expand=True, resample=Image.BICUBIC)
        sc = 1.6 - 0.6 * p
        st = st.resize((int(st.width * sc), int(st.height * sc)))
        st.putalpha(st.getchannel("A").point(lambda v: int(v * p)))
        paste_center(img, st, cx + 40, cy + 120)
    return img


def s_government(t, dur):
    img = to_img(gradient([(0, (8, 14, 30)), (1, (14, 30, 54))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 2")
    draw_text(img, "ALERTAS, CIELO *CERRADO Y REUNIÓN DE *LA *ONU", t, 0.2, 230, size=80)
    # mapa simple
    top = 920
    d.rounded_rectangle([60, top, W - 60, 1720], radius=30, fill=(18, 44, 78, 255))
    land = random.Random(8)
    for _ in range(9):
        x, y = land.randint(120, W - 120), land.randint(top + 60, 1660)
        rw, rh = land.randint(90, 220), land.randint(60, 150)
        d.ellipse([x - rw, y - rh, x + rw, y + rh], fill=(52, 70, 70, 255))
    zx, zy = 640, 1330
    pr = 150 + 18 * math.sin(t * 4)
    d.ellipse([zx - pr, zy - pr, zx + pr, zy + pr], fill=(255, 40, 40, 70), outline=RED + (255,), width=6)
    d.text((zx, zy), "ZONA\nRESTRINGIDA", font=font(38), anchor="mm", align="center", fill=WHITE + (255,))
    for k in range(5):  # aviones desviados alrededor de la zona
        ang = t * 0.45 + k * 1.26
        r = 290 + 30 * k
        px, py = zx + math.cos(ang) * r, zy + math.sin(ang) * r * 0.75
        if 80 < px < W - 80 and top + 30 < py < 1700:
            h = ang + math.pi / 2
            tri = [(px + math.cos(h) * 26, py + math.sin(h) * 26),
                   (px + math.cos(h + 2.5) * 16, py + math.sin(h + 2.5) * 16),
                   (px + math.cos(h - 2.5) * 16, py + math.sin(h - 2.5) * 16)]
            d.polygon(tri, fill=(240, 240, 250, 255))
    # notificación de emergencia
    if t > 0.9:
        p = ease_out((t - 0.9) / 0.4)
        y = lerp(560, 640, p)
        card = Image.new("RGBA", (920, 230), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, 920, 230], radius=34, fill=(32, 32, 40, 245), outline=RED + (255,), width=5)
        cd.polygon([(70, 55), (30, 125), (110, 125)], fill=YELLOW + (255,))
        cd.text((70, 105), "!", font=font(50), anchor="mm", fill=(0, 0, 0, 255))
        cd.text((140, 48), "ALERTA DE EMERGENCIA", font=font(48), fill=WHITE + (255,))
        cd.text((140, 118), "Evacúe la zona costera de inmediato.", font=font(36, FONT_SB), fill=(210, 210, 220, 255))
        cd.text((140, 168), "Protección Civil · ahora", font=font(30, FONT_SB), fill=(150, 150, 165, 255))
        card.putalpha(card.getchannel("A").point(lambda v: int(v * p)))
        img.alpha_composite(card, (80, int(y)))
    return img


def s_crowds(t, dur):
    img = to_img(gradient([(0, (30, 26, 30)), (1, (60, 24, 20))]))
    d = ImageDraw.Draw(img)
    paste_center(img, RED_GLOW, W / 2, H + 120)
    hour(img, t, "HORA 3")
    draw_text(img, "CARRETERAS *COLAPSADAS… Y *CURIOSOS QUE VAN A *GRABARLO", t, 0.2, 230, size=74)
    rl, rr = 250, 830
    d.rectangle([rl, 760, rr, H], fill=(46, 46, 52, 255))
    for lx in (rl + 145, rl + 290, rl + 435):
        for y in range(760 + int(t * 60) % 80 - 80, H, 80):
            d.rectangle([lx - 4, y, lx + 4, y + 40], fill=(230, 210, 120, 255))
    cars = random.Random(5)
    colors = [(220, 60, 60), (230, 230, 235), (60, 120, 220), (40, 40, 48), (240, 190, 40)]
    for lane in range(3):
        for k in range(14):
            base = 760 + k * 92 + cars.randint(-10, 10)
            jitter = 6 * math.sin(t * 2 + k + lane)
            y = base - (t * 14 * (1 + lane * 0.2)) % 92 + jitter
            x = rl + 40 + lane * 145
            d.rounded_rectangle([x, y, x + 64, y + 76], radius=12, fill=colors[(k + lane) % 5] + (255,))
            d.rectangle([x + 10, y + 8, x + 54, y + 22], fill=(255, 240, 200, 200))
    # curiosos que caminan hacia el peligro con su celular
    ppl = random.Random(9)
    for k in range(18):
        x = ppl.randint(880, 1040)
        y = 780 + ((ppl.random() * 1200) + t * 120) % 1140
        d.ellipse([x - 13, y - 13, x + 13, y + 13], fill=(240, 220, 200, 255))
        d.rectangle([x + 12, y - 22, x + 24, y - 2], fill=(150, 220, 255, 255))
    d.text((540, 820), "▲ EVACUACIÓN", font=font(44), anchor="mm", fill=WHITE + (255,), stroke_width=4,
           stroke_fill=(0, 0, 0, 255))
    d.text((960, 740), "CURIOSOS ▼", font=font(38), anchor="mm", fill=YELLOW + (255,), stroke_width=4,
           stroke_fill=(0, 0, 0, 255))
    return img


def s_economy(t, dur):
    img = to_img(gradient([(0, (6, 10, 18)), (1, (16, 22, 34))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 6")
    draw_text(img, "LAS BOLSAS SE *DESPLOMAN", t, 0.2, 250, size=92)
    draw_text(img, "y las aseguradoras entran en pánico", t, 1.6, 500, size=52, per_word=0.05)
    left, right, top, bot = 90, 990, 760, 1460
    for gy in range(top, bot + 1, 100):
        d.line([(left, gy), (right, gy)], fill=(40, 48, 64, 255), width=2)
    p = ease(t / 3.2)
    n = int(80 * p) + 2
    r = random.Random(4)
    pts, val = [], 0.0
    for i in range(n):
        val += r.uniform(-0.6, 0.9) + (2.6 if 30 < i < 60 else 0.3)
        pts.append((left + i * (right - left) / 80, top + 80 + val * 7))
    if len(pts) > 1:
        poly = pts + [(pts[-1][0], bot), (pts[0][0], bot)]
        d.polygon(poly, fill=(255, 40, 40, 60))
        d.line(pts, fill=(255, 70, 60, 255), width=8)
        d.ellipse([pts[-1][0] - 12, pts[-1][1] - 12, pts[-1][0] + 12, pts[-1][1] + 12], fill=(255, 90, 80, 255))
    tickers = [("BOLSAS MUNDIALES", 1), ("ASEGURADORAS", 2), ("AEROLÍNEAS", 1)]
    for i, (name, n_tri) in enumerate(tickers):
        y = 1560 + i * 90
        if t > 1.0 + i * 0.4:
            d.text((120, y), name, font=font(48), fill=WHITE + (255,))
            for k in range(n_tri):
                x = 880 + k * 50
                d.polygon([(x, y + 12), (x + 40, y + 12), (x + 20, y + 46)], fill=RED + (255,))
    return img


def cube(d, cx, cy, s, top_c, left_c, right_c):
    h = s * 0.5
    top = [(cx, cy - s), (cx + s, cy - s + h), (cx, cy - s + 2 * h), (cx - s, cy - s + h)]
    left = [(cx - s, cy - s + h), (cx, cy - s + 2 * h), (cx, cy + 2 * h), (cx - s, cy + h)]
    right = [(cx + s, cy - s + h), (cx, cy - s + 2 * h), (cx, cy + 2 * h), (cx + s, cy + h)]
    d.polygon(left, fill=left_c + (255,))
    d.polygon(right, fill=right_c + (255,))
    d.polygon(top, fill=top_c + (255,))


def s_science(t, dur):
    img = to_img(gradient([(0, (6, 22, 40)), (1, (10, 50, 80))]))
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 60):
        d.line([(gx, 700), (gx, H)], fill=(20, 70, 110, 255), width=1)
    for gy in range(700, H, 60):
        d.line([(0, gy), (W, gy)], fill=(20, 70, 110, 255), width=1)
    hour(img, t, "HORA 12")
    draw_text(img, "EL MISTERIO DEL SIGLO: ¿CÓMO NO SE *ROMPE LOS *HUESOS?", t, 0.2, 230, size=80)
    cube(d, 240, 1260, 50, (120, 200, 255), (60, 130, 200), (40, 100, 170))
    d.text((240, 1400), "×1", font=font(52), anchor="mm", fill=WHITE + (255,))
    g = ease_out((t - 1.0) / 1.6)
    if g > 0:
        cube(d, 680, 1300, 50 + 230 * g, (255, 200, 80), (220, 140, 40), (190, 110, 30))
    if t > 2.6:
        labels = [("TAMAÑO ×10", WHITE), ("PESO ×1000", YELLOW), ("FUERZA DEL HUESO ×100", (130, 210, 255))]
        for i, (txt, col) in enumerate(labels):
            if t > 2.6 + i * 0.6:
                d.text((W / 2, 1640 + i * 80), txt, font=font(58), anchor="mm", fill=col + (255,), stroke_width=5,
                       stroke_fill=(0, 0, 0, 255))
    draw_text(img, "(ley cuadrado-cúbica)", t, 2.0, 640, size=44, per_word=0.05)
    return img


def s_ending(t, dur):
    k = ease(t / 3.0)
    img = to_img(gradient([(0, mix((10, 14, 40), (40, 60, 120), k)), (0.5, mix((80, 40, 60), (255, 150, 90), k)),
                           (0.52, (14, 46, 64)), (1, (6, 20, 32))]))
    d = ImageDraw.Draw(img)
    hz = int(H * 0.51)
    sun_y = hz + 60 - 160 * k
    paste_center(img, glow(240, (255, 170, 90), 0.8), W / 2 + 220, sun_y)
    d.ellipse([W / 2 + 220 - 60, sun_y - 60, W / 2 + 280, sun_y + 60], fill=(255, 210, 140, 255))
    d.rectangle([0, hz, W, H], fill=(14, 46, 64, 255))
    hour(img, t, "HORA 24")
    cx, cy = W / 2 - 80, 1320
    for j in range(6):
        r = ((t * 120 + j * 90) % 540)
        a = int(200 * (1 - r / 540))
        d.ellipse([cx - r * 1.6, cy - r * 0.45, cx + r * 1.6, cy + r * 0.45], outline=(180, 220, 240, a), width=5)
    bub = random.Random(2)
    for _ in range(14):
        bx = cx + bub.randint(-120, 120)
        by = cy - ((t * 90 + bub.random() * 200) % 200)
        rr = bub.randint(5, 12)
        d.ellipse([bx - rr, by - rr, bx + rr, by + rr], outline=(220, 240, 255, 200), width=3)
    draw_text(img, "SE HUNDE EN EL *OCÉANO…", t, 0.2, 280, size=92, out_at=2.6)
    draw_text(img, "…PERO EL MUNDO *NUNCA SERÍA IGUAL", t, 2.9, 280, size=92)
    draw_text(img, "*¿TÚ *QUÉ *HARÍAS?", t, 4.2, 1560, size=104)
    return img


# Narración: frases cortas, ~135 palabras en total (≈ 55 s con la voz de Alex).
SCENES = [
    ("01_hook", s_hook, 4.5, "¿Qué pasaría si Godzilla apareciera en el mundo real durante veinticuatro horas?"),
    ("02_fisica", s_physics, 5.5, "Hora cero. Algo de cien metros pesaría decenas de miles de toneladas. "
                                  "Cada paso sería un pequeño sismo."),
    ("03_redes", s_social, 6.0, "Hora uno. Sería tendencia mundial en minutos, con millones de transmisiones en vivo, "
                                "y medio internet diciendo que es inteligencia artificial."),
    ("04_gobiernos", s_government, 6.0, "Hora dos. Alertas de emergencia en todos los celulares, el espacio aéreo "
                                        "cerrado y una reunión urgente de la ONU."),
    ("05_multitudes", s_crowds, 5.5, "Hora tres. Carreteras colapsadas, evacuaciones masivas, y miles de curiosos "
                                     "yendo hacia él para grabarlo."),
    ("06_economia", s_economy, 4.5, "Hora seis. Las bolsas se desplomarían y las aseguradoras entrarían en pánico."),
    ("07_ciencia", s_science, 6.0, "Hora doce. Los científicos tendrían el misterio del siglo: ¿cómo puede sostenerse "
                                   "algo tan grande sin romperse los huesos?"),
    ("08_final", s_ending, 6.0, "Hora veinticuatro. Se hunde en el océano. Pero el mundo ya nunca sería igual. "
                                "¿Tú qué harías?"),
]


# ------------------------------------------------------------------ música de suspenso (original)
def music(total: float, durs) -> np.ndarray:
    n = int((total + 1) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    bpm = 104
    beat = 60 / bpm
    bar = beat * 4
    chords = [[50, 53, 57], [46, 50, 53], [43, 46, 50], [45, 49, 52]]  # Dm Bb Gm A
    out += 0.10 * np.sin(2 * np.pi * note(26) * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.1 * t))  # bordón grave
    for b in range(int(total / bar) + 2):
        ch = chords[b % 4]
        s0, s1 = int(b * bar * SR), min(int((b + 1) * bar * SR), n)
        if s0 >= n:
            break
        seg = t[s0:s1] - b * bar
        env = np.minimum(1, seg / 0.8) * np.minimum(1, (bar - seg) / 0.8)
        for m in ch:
            f = note(m)
            out[s0:s1] += 0.04 * env * (np.sin(2 * np.pi * f * seg) + 0.4 * np.sin(2 * np.pi * 2 * f * seg))
    # bajo en corcheas
    step = beat / 2
    for i in range(int(total / step)):
        ch = chords[int(i * step / bar) % 4]
        f = note(ch[0] - 12)
        s0, L = int(i * step * SR), int(0.22 * SR)
        seg = np.arange(L) / SR
        wave_ = (np.sin(2 * np.pi * f * seg) + 0.5 * np.sin(2 * np.pi * 2 * f * seg) + 0.25 * np.sin(2 * np.pi * 3 * f * seg))
        out[s0:s0 + L] += (0.09 * np.exp(-seg * 9) * wave_)[:len(out[s0:s0 + L])]
    # latido (doble golpe) cada compás
    for b in range(int(total / bar) + 1):
        for off, g in ((0, 0.8), (0.28, 0.5)):
            s0, L = int((b * bar + off) * SR), int(0.3 * SR)
            seg = np.arange(L) / SR
            k = g * 0.3 * np.exp(-seg * 14) * np.sin(2 * np.pi * (48 + 50 * np.exp(-seg * 25)) * seg)
            out[s0:s0 + L] += k[:len(out[s0:s0 + L])]
    rng = np.random.default_rng(1)

    def boom(at, gain=1.0):
        s0, L = int(at * SR), int(1.4 * SR)
        if s0 >= n:
            return
        seg = np.arange(L) / SR
        b = np.sin(2 * np.pi * (70 * np.exp(-seg * 2.2) + 28) * seg) * np.exp(-seg * 3)
        noise = np.convolve(rng.standard_normal(L), np.ones(60) / 60, mode="same") * np.exp(-seg * 6)
        out[s0:s0 + L] += (gain * (0.6 * b + 0.5 * noise))[:len(out[s0:s0 + L])]

    acc = 0.0
    for i, d in enumerate(durs):
        if i > 0:
            boom(acc - 0.05, 0.7)
        acc += d
    for s in STOMPS_1:
        boom(s, 0.9)
    acc = durs[0]
    for k in range(20):  # pasos del sismógrafo
        at = STEP_FIRST + k * STEP_EVERY
        if at < durs[1]:
            boom(acc + at, 0.6)
    return out


VIDEO = Explainer("godzilla_24h", SCENES, music, default_voice="kokoro:em_alex",
                  preview_times=[(0, 1.9), (1, 3.0), (2, 4.0), (3, 2.5), (4, 3.0), (5, 3.5), (6, 4.5), (7, 4.6)])

if __name__ == "__main__":
    VIDEO.run()
