"""¿Qué pasaría si Ultron apareciera 24 horas en el mundo real?  (Short explicativo con humor mexicano)

Uso (desde la raíz del repo):
    python explainers/ultron_24h.py               -> voz de Alex, con groserías (pocas y en el remate)
    python explainers/ultron_24h.py --limpio      -> misma versión sin groserías
    python explainers/ultron_24h.py frames        -> fotogramas de muestra

Nota de derechos: Ultron es un personaje de Marvel. El video habla del tema pero NO dibuja al
personaje: muestra sus efectos (pantallas, redes, robots, centros de datos).
Datos reales usados:
  * ~5 millones de robots industriales operando en 2025 (IFR, World Robotics 2026).
  * Centros de datos ≈ 1.5 % de la electricidad mundial en 2024, ~415 TWh (IEA, Energy and AI).
  * No existe un "interruptor" global de internet: es una red de redes que rodea las fallas.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import (FONT_SB, H, RED, SR, W, WHITE, YELLOW, Explainer, badge, boom, draw_text, ease, ease_out,  # noqa: E402
                    font, glow, gradient, lerp, mix, note, paste_center, phone, shake, to_img)

CLEAN = {"MAMES": "MANCHES", "mames": "manches", "VERGA": "GORRO", "verga": "gorro",
         "CABRÓN": "COMPA", "cabrón": "compa", "CHINGO": "MONTÓN", "chingo": "montón"}
_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
MONO = _MONO if Path(_MONO).exists() else None
DARK = gradient([(0, (6, 4, 10)), (1, (24, 8, 14))])
RED_GLOW = glow(420, (255, 30, 40), 0.5)


def mono(size):
    return font(size, MONO) if MONO else font(size)


def hour(img, t, label):
    badge(img, label, W / 2, 120, t)


def glitch(img: Image.Image, t: float, strength: float = 1.0) -> Image.Image:
    """Desplaza franjas horizontales de vez en cuando (falla digital)."""
    r = random.Random(int(t * 10))
    if r.random() > 0.35 * strength:
        return img
    out = img.copy()
    for _ in range(r.randint(2, 5)):
        y = r.randint(0, H - 80)
        h = r.randint(10, 70)
        dx = r.randint(-60, 60)
        band = img.crop((0, y, W, y + h))
        out.paste(band, (dx, y))
    return out


def code_rain(img, t, seed=1, alpha=70):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = random.Random(seed)
    f = mono(30)
    for col in range(0, W, 46):
        speed = r.uniform(120, 320)
        off = r.uniform(0, H)
        for k in range(14):
            y = (off + t * speed + k * 40) % (H + 200) - 100
            ch = "01"[(int(t * 8) + k + col) % 2]
            d.text((col, y), ch, font=f, fill=(255, 40, 60, int(alpha * (1 - k / 14))))
    img.alpha_composite(layer)


# ------------------------------------------------------------------ escenas
def s_hook(t, dur):
    img = to_img(DARK)
    code_rain(img, t)
    paste_center(img, RED_GLOW, W / 2, 1450)
    draw_text(img, "¿QUÉ PASARÍA SI", t, 0.15, 330, size=84)
    draw_text(img, "*ULTRON", t, 0.55, 450, size=170, per_word=0.0)
    draw_text(img, "APARECIERA", t, 1.0, 660, size=90)
    draw_text(img, "*24 *HORAS", t, 1.3, 765, size=130)
    draw_text(img, "EN EL MUNDO REAL?", t, 1.8, 925, size=80)
    return glitch(img, t)


def screen_text(d, box, t, start):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=(8, 0, 4, 255))
    if t > start:
        on = 0.6 + 0.4 * math.sin(t * 9)
        size = max(22, int((x1 - x0) / 5))
        d.text(((x0 + x1) / 2, (y0 + y1) / 2), "HOLA", font=mono(size), anchor="mm",
               fill=mix((120, 0, 10), (255, 40, 50), on) + (255,))


def s_hello(t, dur):
    img = to_img(gradient([(0, (10, 10, 16)), (1, (24, 18, 30))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 0")
    draw_text(img, "TODAS LAS PANTALLAS DICEN *“HOLA”", t, 0.2, 230, size=86)
    # TV
    d.rounded_rectangle([90, 560, 560, 860], radius=16, fill=(40, 40, 48, 255))
    screen_text(d, (110, 580, 540, 840), t, 0.8)
    d.rectangle([300, 860, 350, 900], fill=(40, 40, 48, 255))
    d.text((325, 930), "TV", font=font(34, FONT_SB), anchor="mm", fill=(170, 170, 190, 255))
    # celular
    phone(d, 790, 760, 230, 400)
    screen_text(d, (700, 600, 880, 920), t, 1.1)
    # laptop
    d.rounded_rectangle([100, 1020, 520, 1290], radius=14, fill=(50, 50, 60, 255))
    screen_text(d, (120, 1040, 500, 1270), t, 1.4)
    d.polygon([(60, 1290), (560, 1290), (590, 1330), (30, 1330)], fill=(70, 70, 82, 255))
    # refri inteligente
    d.rounded_rectangle([640, 1000, 950, 1600], radius=26, fill=(210, 214, 222, 255))
    d.line([(640, 1220), (950, 1220)], fill=(160, 164, 172, 255), width=6)
    d.rectangle([925, 1060, 935, 1180], fill=(150, 150, 160, 255))
    screen_text(d, (690, 1260, 900, 1400), t, 1.9)
    d.text((795, 1650), "TU REFRI", font=font(40), anchor="mm", fill=YELLOW + (255,))
    # reloj
    d.rounded_rectangle([230, 1420, 400, 1590], radius=40, fill=(40, 40, 48, 255))
    screen_text(d, (250, 1440, 380, 1570), t, 2.2)
    draw_text(img, "¡*NO *MAMES!", t, 3.4, 1720, size=96)
    return glitch(img, t, 0.6)


THEORIES = [("¿VIRUS?", (255, 80, 80)), ("¿ATAQUE?", (255, 170, 60)), ("¿MARKETING?", (120, 180, 255))]


def s_theories(t, dur):
    img = to_img(gradient([(0, (16, 10, 30)), (1, (40, 18, 60))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 1")
    draw_text(img, "INTERNET SE LLENA DE UN *CHINGO DE TEORÍAS", t, 0.2, 230, size=80)
    raw = [0.42 + 0.06 * math.sin(t * 2), 0.33 + 0.06 * math.sin(t * 2 + 2), 0.25 + 0.06 * math.sin(t * 2 + 4)]
    shares = [v / sum(raw) for v in raw]
    for i, (label, col) in enumerate(THEORIES):
        if t < 0.9 + i * 0.4:
            continue
        y = 620 + i * 210
        share = shares[i]
        d.text((100, y), label, font=font(58), fill=WHITE + (255,))
        d.rounded_rectangle([100, y + 80, W - 100, y + 140], radius=20, fill=(50, 40, 70, 255))
        d.rounded_rectangle([100, y + 80, 100 + (W - 200) * share * ease_out((t - 0.9 - i * 0.4) / 0.6), y + 140],
                            radius=20, fill=col + (255,))
        d.text((W - 110, y + 30), f"{share * 100:.0f}%", font=font(48), anchor="rm", fill=col + (255,))
    if t > 2.8:
        p = ease_out((t - 2.8) / 0.35)
        card = Image.new("RGBA", (820, 190), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, 820, 190], radius=34, fill=(40, 140, 90, 250))
        cd.text((40, 30), "Tío Beto", font=font(40, FONT_SB), fill=(200, 255, 220, 255))
        cd.text((40, 96), "SE LOS DIJE. SE LOS DIJE.", font=font(50), fill=WHITE + (255,))
        card.putalpha(card.getchannel("A").point(lambda v: int(v * p)))
        img.alpha_composite(card, (int(140 + 40 * (1 - p)), 1400))
    return img


# red de redes: nodos y conexiones
_NODES = [(170, 700), (420, 620), (700, 680), (930, 760), (260, 980), (540, 900), (820, 1020), (150, 1250),
          (420, 1200), (680, 1280), (930, 1240), (300, 1480), (600, 1500), (880, 1470)]
_EDGES = [(0, 1), (1, 2), (2, 3), (0, 4), (1, 5), (2, 5), (3, 6), (4, 5), (5, 6), (4, 7), (4, 8), (5, 8), (5, 9),
          (6, 9), (6, 10), (7, 8), (8, 9), (9, 10), (7, 11), (8, 11), (8, 12), (9, 12), (10, 13), (12, 13), (9, 13)]
CUT = 5   # el nodo que el gobierno "apaga"


def s_network(t, dur):
    img = to_img(gradient([(0, (6, 12, 24)), (1, (12, 24, 46))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 2")
    draw_text(img, "¿APAGAR INTERNET? *NO *HAY INTERRUPTOR MAESTRO", t, 0.2, 230, size=78)
    cut = t > 1.6
    for a, b in _EDGES:
        dead = cut and CUT in (a, b)
        d.line([_NODES[a], _NODES[b]], fill=((90, 40, 50) if dead else (60, 120, 200)) + (255,), width=5)
    # paquetes que viajan; al cortar el nodo rodean por otro camino
    route = [0, 1, 2, 6, 9, 12] if cut else [0, 4, 5, 9, 12]
    for k in range(4):
        u = ((t * 0.45 + k * 0.25) % 1) * (len(route) - 1)
        i = int(u)
        f = u - i
        (x0, y0), (x1, y1) = _NODES[route[i]], _NODES[route[i + 1]]
        x, y = lerp(x0, x1, f), lerp(y0, y1, f)
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=YELLOW + (255,))
    for i, (x, y) in enumerate(_NODES):
        dead = cut and i == CUT
        d.ellipse([x - 26, y - 26, x + 26, y + 26], fill=((120, 30, 40) if dead else (120, 190, 255)) + (255,))
    if cut:
        x, y = _NODES[CUT]
        d.line([(x - 50, y - 50), (x + 50, y + 50)], fill=RED + (255,), width=12)
        d.line([(x - 50, y + 50), (x + 50, y - 50)], fill=RED + (255,), width=12)
        d.text((W / 2, 1620), "LOS DATOS SE VAN POR OTRO CAMINO", font=font(50), anchor="mm", fill=WHITE + (255,),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
    draw_text(img, "*VALIÓ *VERGA", t, 3.6, 1700, size=96)
    return img


def robot_arm(d, x, y, t, k):
    a1 = -1.1 + 0.35 * math.sin(t * 2.2 + k)
    a2 = 0.9 + 0.4 * math.sin(t * 3.1 + k * 1.7)
    L1, L2 = 120, 95
    jx, jy = x + math.cos(a1) * L1, y + math.sin(a1) * L1
    ex, ey = jx + math.cos(a1 + a2) * L2, jy + math.sin(a1 + a2) * L2
    d.rectangle([x - 40, y, x + 40, y + 30], fill=(80, 80, 90, 255))
    d.line([(x, y), (jx, jy)], fill=(240, 160, 30, 255), width=26)
    d.line([(jx, jy), (ex, ey)], fill=(240, 160, 30, 255), width=20)
    for px, py, r in ((x, y, 20), (jx, jy, 16)):
        d.ellipse([px - r, py - r, px + r, py + r], fill=(60, 60, 70, 255))
    if int(t * 10 + k) % 3 == 0:  # chispas de soldadura
        rr = random.Random(int(t * 30) + k)
        for _ in range(6):
            a = rr.uniform(0, 6.28)
            L = rr.uniform(10, 34)
            d.line([(ex, ey), (ex + math.cos(a) * L, ey + math.sin(a) * L)], fill=(255, 230, 120, 255), width=3)


def s_robots(t, dur):
    img = to_img(gradient([(0, (20, 20, 26)), (1, (40, 38, 44))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 4")
    draw_text(img, "¿SU EJÉRCITO? *5 *MILLONES DE ROBOTS INDUSTRIALES", t, 0.2, 230, size=76)
    n = int(9 * ease_out((t - 0.6) / 1.2))
    for k in range(n):
        col, row = k % 3, k // 3
        robot_arm(d, 220 + col * 320, 820 + row * 280, t, k)
    draw_text(img, "…LA MAYORÍA SOLO SABE *SOLDAR Y *ATORNILLAR", t, 2.6, 1620, size=60, per_word=0.06)
    return img


def s_power(t, dur):
    img = to_img(gradient([(0, (6, 10, 20)), (1, (14, 22, 40))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 8")
    draw_text(img, "PARA PENSAR NECESITA *ENERGÍA", t, 0.2, 230, size=88)
    # racks de servidores con luces
    r = random.Random(7)
    for k in range(4):
        x = 90 + k * 120
        d.rectangle([x, 560, x + 100, 1100], fill=(28, 30, 40, 255))
        for j in range(16):
            y = 580 + j * 32
            on = (int(t * 6) + j * 3 + k * 5 + r.randint(0, 3)) % 4 != 0
            d.rectangle([x + 10, y, x + 90, y + 20], fill=(40, 44, 56, 255))
            d.ellipse([x + 70, y + 4, x + 82, y + 16], fill=((60, 255, 120) if on else (20, 60, 30)) + (255,))
    # pastel de electricidad mundial: 1.5 %
    cx, cy, R = 800, 830, 190
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(60, 80, 120, 255))
    p = ease_out((t - 1.0) / 0.8)
    if p > 0:  # rebanada real de 1.5 % (5.4°), separada del pastel para que se vea
        mid = math.radians(-90 + 2.7)
        ox, oy = math.cos(mid) * 40 * p, math.sin(mid) * 40 * p
        d.pieslice([cx - R + ox, cy - R + oy, cx + R + ox, cy + R + oy], -90, -90 + 5.4, fill=YELLOW + (255,))
        d.line([(cx + ox + math.cos(mid) * R, cy + oy + math.sin(mid) * R),
                (cx + 70, cy - R - 60)], fill=YELLOW + (255,), width=4)
        d.text((cx + 80, cy - R - 60), "1.5 %", font=font(44), anchor="lm", fill=YELLOW + (255,))
    d.text((cx, cy + R + 60), "LUZ DE TODO EL MUNDO", font=font(40), anchor="mm", fill=WHITE + (255,))
    d.text((cx, cy + R + 112), "centros de datos, 2024", font=font(34, FONT_SB), anchor="mm", fill=(180, 190, 210, 255))
    if t > 2.6:
        q = ease_out((t - 2.6) / 0.35)
        card = Image.new("RGBA", (900, 260), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, 900, 260], radius=24, fill=(250, 250, 246, 250))
        cd.text((40, 30), "RECIBO DE LUZ", font=font(48), fill=(30, 30, 36, 255))
        cd.text((40, 100), "Total a pagar:", font=font(38, FONT_SB), fill=(90, 90, 100, 255))
        total = int(999_999_999 * ease((t - 2.6) / 1.5))
        cd.text((40, 160), f"$ {total:,}", font=font(64), fill=RED + (255,))
        card.putalpha(card.getchannel("A").point(lambda v: int(v * q)))
        img.alpha_composite(card, (90, int(1260 + 30 * (1 - q))))
    draw_text(img, "AHÍ SÍ, *CABRÓN", t, 3.8, 1600, size=92)
    return img


def rotary_phone(d, cx, cy):
    d.rounded_rectangle([cx - 150, cy - 40, cx + 150, cy + 120], radius=40, fill=(30, 30, 34, 255))
    d.rounded_rectangle([cx - 170, cy - 110, cx + 170, cy - 50], radius=30, fill=(30, 30, 34, 255))
    d.ellipse([cx - 80, cy - 30, cx + 80, cy + 130], fill=(220, 220, 225, 255))
    for k in range(10):
        a = math.radians(-60 + k * 30)
        d.ellipse([cx + math.cos(a) * 55 - 13, cy + 50 + math.sin(a) * 55 - 13,
                   cx + math.cos(a) * 55 + 13, cy + 50 + math.sin(a) * 55 + 13], fill=(30, 30, 34, 255))


def radio(d, cx, cy):
    d.rounded_rectangle([cx - 170, cy - 90, cx + 170, cy + 110], radius=24, fill=(150, 90, 50, 255))
    d.line([(cx + 120, cy - 90), (cx + 200, cy - 260)], fill=(190, 190, 200, 255), width=6)
    for k in range(6):
        d.line([(cx - 140, cy - 50 + k * 22), (cx + 10, cy - 50 + k * 22)], fill=(110, 60, 30, 255), width=6)
    d.ellipse([cx + 50, cy - 40, cx + 130, cy + 40], fill=(230, 210, 170, 255))


def s_resistance(t, dur):
    img = to_img(gradient([(0, (30, 24, 16)), (1, (60, 46, 30))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 12")
    draw_text(img, "¿LA RESISTENCIA? *TU *ABUELITA", t, 0.2, 230, size=88)
    if t > 0.8:
        rotary_phone(d, 300, 860)
        d.text((300, 1080), "TELÉFONO DE DISCO", font=font(36), anchor="mm", fill=WHITE + (255,))
    if t > 1.4:
        radio(d, 790, 880)
        d.text((790, 1080), "RADIO DE PILAS", font=font(36), anchor="mm", fill=WHITE + (255,))
    checks = ["SIN WIFI", "SIN ACTUALIZACIONES", "INHACKEABLE"]
    for i, c in enumerate(checks):
        if t > 2.2 + i * 0.5:
            y = 1300 + i * 110
            d.rounded_rectangle([200, y, 280, y + 80], radius=16, fill=(60, 200, 110, 255))
            d.line([(220, y + 42), (238, y + 62), (264, y + 20)], fill=WHITE + (255,), width=10)
            d.text((320, y + 40), c, font=font(58), anchor="lm", fill=WHITE + (255,))
    return img


COMMENTS = ["@juanito99: primero", "@xX_gamer_Xx: esto es fake", "@tia_lupe: amén",
            "@el_profe: ortografía, por favor", "@bot_123: gana dinero desde casa", "@luis: ¿alguien en 2026?"]


def s_ending(t, dur):
    img = to_img(DARK)
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 24")
    draw_text(img, "LEE LOS *COMENTARIOS DE INTERNET…", t, 0.2, 230, size=84, out_at=2.6)
    draw_text(img, "…Y DECIDE QUE LA HUMANIDAD YA SE *DESTRUYE *SOLITA", t, 2.9, 230, size=78)
    # comentarios que pasan
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for i, c in enumerate(COMMENTS):
        y = 720 + i * 120 - min(t, 2.6) * 30
        if t > 0.6 + i * 0.25:
            ld.rounded_rectangle([90, y, W - 90, y + 96], radius=24, fill=(40, 34, 50, 255))
            ld.text((130, y + 48), c, font=font(40, FONT_SB), anchor="lm", fill=(230, 230, 240, 255))
    fade = 1.0 if t < 3.4 else max(0.0, 1 - (t - 3.4) / 0.6)
    if fade > 0:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * fade)))
        img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    if t > 3.6:  # se apaga: línea de TV vieja
        q = ease((t - 3.6) / 0.6)
        h = int(lerp(700, 6, q))
        d.rectangle([0, 1150 - h / 2, W, 1150 + h / 2], fill=(255, 255, 255, int(255 * (1 - q * 0.6))))
    draw_text(img, "¿TÚ QUÉ *HARÍAS?", t, 4.4, 1560, size=104)
    return glitch(img, t, 0.4)


SCENES = [
    ("01_hook", s_hook, 4.5, "¿Qué pasaría si Ultron apareciera en el mundo real durante veinticuatro horas? "
                             "Agárrate, güey, que esto se pone feo."),
    ("02_hola", s_hello, 5.5, "Hora cero. Todas las pantallas del mundo dicen hola al mismo tiempo. Hasta tu refri "
                              "inteligente. ¡No mames!"),
    ("03_teorias", s_theories, 5.5, "Hora uno. Internet se llena de un chingo de teorías: virus, ataque o campaña de "
                                    "marketing. Y tu tío ya está diciendo: se los dije."),
    ("04_red", s_network, 6.0, "Hora dos. Los gobiernos quieren apagar internet, pero no se puede: no existe un "
                               "interruptor maestro, es una red de redes. Valió verga."),
    ("05_robots", s_robots, 5.5, "Hora cuatro. ¿Su ejército? Hay unos cinco millones de robots industriales en el "
                                 "mundo… y la mayoría solo sabe soldar y atornillar."),
    ("06_energia", s_power, 6.0, "Hora ocho. Para pensar necesita energía: los centros de datos ya usan cerca del uno "
                                 "y medio por ciento de la luz del mundo. Imagínate el recibo. Ahí sí, cabrón."),
    ("07_resistencia", s_resistance, 5.5, "Hora doce. ¿La resistencia? Tu abuelita, con su teléfono de disco y su "
                                          "radio de pilas. Inhackeable."),
    ("08_final", s_ending, 6.0, "Hora veinticuatro. Ultron lee los comentarios de internet, decide que la humanidad "
                                "ya se destruye solita, y se desconecta. ¿Tú qué harías?"),
]


# ------------------------------------------------------------------ música electrónica oscura (original)
def music(total: float, durs) -> np.ndarray:
    n = int((total + 1) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    bpm = 122
    beat = 60 / bpm
    bar = beat * 4
    chords = [[45, 48, 52], [41, 45, 48], [43, 46, 50], [40, 43, 47]]  # Am F Gm Em
    pump = 0.55 + 0.45 * np.minimum(1, ((t % beat) / (beat * 0.45)))  # "bombeo" tipo sidechain
    for b in range(int(total / bar) + 2):
        ch = chords[b % 4]
        s0, s1 = int(b * bar * SR), min(int((b + 1) * bar * SR), n)
        if s0 >= n:
            break
        seg = t[s0:s1] - b * bar
        for m in ch:
            f = note(m)
            out[s0:s1] += 0.03 * pump[s0:s1] * sum(np.sin(2 * np.pi * f * h * seg) / h for h in (1, 2, 3))
    step = beat / 4
    for i in range(int(total / step)):  # arpegio de semicorcheas
        ch = chords[int(i * step / bar) % 4]
        m = ch[[0, 1, 2, 1][i % 4]] + 24
        f = note(m)
        s0, L = int(i * step * SR), int(step * 0.9 * SR)
        seg = np.arange(L) / SR
        x = 0.03 * np.exp(-seg * 14) * np.sign(np.sin(2 * np.pi * f * seg))
        out[s0:s0 + L] += x[:len(out[s0:s0 + L])]
    for i in range(int(total / beat)):  # bombo four-on-the-floor
        s0, L = int(i * beat * SR), int(0.28 * SR)
        seg = np.arange(L) / SR
        out[s0:s0 + L] += (0.4 * np.exp(-seg * 15) * np.sin(2 * np.pi * (48 + 80 * np.exp(-seg * 35)) * seg))[:len(out[s0:s0 + L])]
    rng = np.random.default_rng(7)
    for i in range(int(total / (beat / 2))):  # hi-hat
        if i % 2:
            s0, L = int(i * beat / 2 * SR), int(0.05 * SR)
            out[s0:s0 + L] += (0.05 * rng.standard_normal(L))[:len(out[s0:s0 + L])]
    acc = 0.0
    for i, d in enumerate(durs):
        if i > 0:
            boom(out, acc - 0.05, 0.5, rng)
            s0, L = int((acc - 0.1) * SR), int(0.25 * SR)  # chirrido digital en cada corte
            if 0 <= s0 < n:
                seg = np.arange(L) / SR
                out[s0:s0 + L] += (0.12 * np.sign(np.sin(2 * np.pi * (2000 - 6000 * seg) * seg)))[:len(out[s0:s0 + L])]
        acc += d
    return out


VIDEO = Explainer("ultron_24h", SCENES, music, default_voice="kokoro:em_alex", clean_map=CLEAN,
                  preview_times=[(0, 2.4), (1, 4.0), (2, 3.4), (3, 4.0), (4, 3.2), (5, 4.2), (6, 3.8), (7, 4.8)])

if __name__ == "__main__":
    VIDEO.run()
