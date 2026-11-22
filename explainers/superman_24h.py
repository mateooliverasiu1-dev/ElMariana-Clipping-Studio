"""¿Qué pasaría si Superman apareciera 24 horas en el mundo real?  (Short explicativo con humor mexicano)

Uso (desde la raíz del repo):
    python explainers/superman_24h.py              -> voz de Alex, con groserías (pocas y en el remate)
    python explainers/superman_24h.py --limpio     -> misma versión sin groserías
    python explainers/superman_24h.py frames       -> fotogramas de muestra

Nota de derechos: Superman es un personaje de DC. El video habla del tema pero NO dibuja al
personaje ni su símbolo: muestra sus efectos.
Nota YouTube: groserías fuertes pocas veces y nunca en título/miniatura (la portada va limpia).
Física usada: velocidad del sonido ≈ 1 235 km/h a nivel del mar (estampido sónico al superarla);
3.ª ley de Newton (para volar hay que empujar aire o gas hacia el lado contrario).
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
                    font, glow, gradient, lerp, mix, note, paste_center, phone, shake, to_img, txt)

CLEAN = {"MAMES": "MANCHES", "mames": "manches", "VERGA": "GORRO", "verga": "gorro",
         "CABRÓN": "COMPA", "cabrón": "compa", "CHINGO": "MONTÓN", "chingo": "montón"}
SKY = gradient([(0, (40, 110, 210)), (0.6, (120, 180, 240)), (1, (200, 225, 250))])


def hour(img, t, label):
    badge(img, label, W / 2, 120, t)


def buildings(img, hz, seed=4, col=(70, 90, 120), windows=None):
    d = ImageDraw.Draw(img)
    r = random.Random(seed)
    x, rects = -20, []
    while x < W:
        bw, bh = r.randint(110, 200), r.randint(300, 720)
        d.rectangle([x, hz - bh, x + bw, hz], fill=col + (255,))
        for wy in range(hz - bh + 26, hz - 30, 50):
            for wx in range(x + 16, x + bw - 26, 40):
                d.rectangle([wx, wy, wx + 24, wy + 32], fill=(170, 210, 240, 255))
                rects.append((wx, wy, wx + 24, wy + 32))
        x += bw + r.randint(8, 20)
    d.rectangle([0, hz, W, H], fill=(70, 74, 80, 255))
    return rects


def streak(img, x0, y0, x1, y1, p, width=18):
    """Estela blanca de algo que vuela rapidísimo (no se ve quién)."""
    if p <= 0:
        return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    xe, ye = lerp(x0, x1, p), lerp(y0, y1, p)
    n = 30
    for i in range(n):
        a = i / n
        xa, ya = lerp(x0, xe, a), lerp(y0, ye, a)
        xb, yb = lerp(x0, xe, a + 1 / n), lerp(y0, ye, a + 1 / n)
        d.line([(xa, ya), (xb, yb)], fill=(255, 255, 255, int(255 * a)), width=max(2, int(width * a)))
    layer = layer.filter(ImageFilter.GaussianBlur(3))
    img.alpha_composite(layer)
    paste_center(img, glow(60, (255, 255, 240), 1.0), xe, ye)


# ------------------------------------------------------------------ escenas
def s_hook(t, dur):
    img = to_img(SKY)
    buildings(img, 1450, seed=2, col=(80, 100, 130))
    p = ease((t - 0.3) / 1.2)
    streak(img, -100, 1000, W + 100, 560, p)
    draw_text(img, "¿QUÉ PASARÍA SI", t, 0.15, 330, size=84)
    draw_text(img, "*SUPERMAN", t, 0.55, 450, size=150, per_word=0.0)
    draw_text(img, "APARECIERA", t, 1.0, 660, size=90)
    draw_text(img, "*24 *HORAS", t, 1.3, 765, size=130)
    draw_text(img, "EN EL MUNDO REAL?", t, 1.8, 925, size=80)
    return img


BOOM_AT = 1.6


def s_sonic(t, dur):
    img = to_img(SKY)
    windows = buildings(img, 1500, seed=9, col=(90, 110, 140))
    hour(img, t, "HORA 0")
    draw_text(img, "MÁS RÁPIDO QUE EL *SONIDO", t, 0.2, 230, size=88)
    p = ease((t - 0.3) / 1.3)
    xe = lerp(-100, W + 200, p)
    ye = 820
    streak(img, -100, ye, W + 200, ye, p, width=22)
    d = ImageDraw.Draw(img)
    if 0.05 < p < 1:  # cono de Mach detrás
        for k in range(3):
            off = 60 + k * 70
            d.line([(xe, ye), (xe - off * 3, ye - off * 1.6)], fill=(255, 255, 255, 140), width=4)
            d.line([(xe, ye), (xe - off * 3, ye + off * 1.6)], fill=(255, 255, 255, 140), width=4)
    if t > BOOM_AT:
        q = ease_out((t - BOOM_AT) / 0.5)
        r = random.Random(1)
        for (x0, y0, x1, y1) in windows:
            if r.random() < 0.55 * q:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                for _ in range(3):
                    a = r.uniform(0, 6.28)
                    d.line([(cx, cy), (cx + math.cos(a) * 16, cy + math.sin(a) * 18)], fill=(30, 40, 60, 255), width=3)
        d.text((W / 2, 1120), "¡PUM!", font=font(int(150 * (0.7 + 0.3 * q))), anchor="mm", fill=YELLOW + (255,),
               stroke_width=10, stroke_fill=(0, 0, 0, 255))
        d.text((W / 2, 1640), "ESTAMPIDO SÓNICO · > 1 235 km/h", font=font(48), anchor="mm", fill=WHITE + (255,),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
    draw_text(img, "¡*NO *MAMES!", t, 3.6, 1740, size=96)
    return shake(img, t, [BOOM_AT], strength=24)


MSGS = [("¿Es real o qué?", False), ("Es CGI, güey", True), ("Mi primo dice que es un dron", False),
        ("Ya lo vi pasar por mi casa", True), ("Compártelo o te va mal", False),
        ("¿Cobrará por mudanzas?", True)]


def s_social(t, dur):
    img = to_img(gradient([(0, (20, 10, 40)), (1, (50, 20, 70))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 1")
    draw_text(img, "TODO MUNDO SACA EL *CELULAR", t, 0.2, 230, size=90)
    cx, cy, pw, ph = W / 2, 1130, 660, 1100
    phone(d, cx, cy, pw, ph)
    x0, y_top = cx - pw / 2 + 40, cy - ph / 2 + 90
    d.text((x0, y_top), "Grupo: Familia", font=font(40, FONT_SB),
           fill=(170, 170, 190, 255))
    shown = min(len(MSGS), int((t - 0.6) / 0.6) + 1) if t > 0.6 else 0
    y = y_top + 80
    for i in range(shown):
        msg, mine = MSGS[i]
        f = font(36, FONT_SB)
        tw = min(f.getlength(msg), pw - 200)
        bx0 = (cx + pw / 2 - 40 - tw - 50) if mine else x0
        d.rounded_rectangle([bx0, y, bx0 + tw + 50, y + 80], radius=26,
                            fill=((40, 140, 90) if mine else (60, 60, 76)) + (255,))
        d.text((bx0 + 25, y + 40), msg, font=f, anchor="lm", fill=WHITE + (255,))
        y += 112
    return img


def s_radar(t, dur):
    img = to_img(gradient([(0, (4, 14, 8)), (1, (8, 28, 16))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 2")
    draw_text(img, "LOS RADARES DETECTAN ALGO *SIN *ALAS *NI *TURBINAS", t, 0.2, 230, size=76)
    cx, cy, R = W / 2, 1060, 400
    for k in range(1, 5):
        d.ellipse([cx - R * k / 4, cy - R * k / 4, cx + R * k / 4, cy + R * k / 4], outline=(40, 160, 80, 255), width=3)
    d.line([(cx - R, cy), (cx + R, cy)], fill=(40, 160, 80, 255), width=2)
    d.line([(cx, cy - R), (cx, cy + R)], fill=(40, 160, 80, 255), width=2)
    ang = t * 2.4
    sweep = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sweep)
    for k in range(30):
        a = ang - k * 0.03
        sd.line([(cx, cy), (cx + math.cos(a) * R, cy + math.sin(a) * R)], fill=(80, 255, 140, int(150 * (1 - k / 30))), width=6)
    img.alpha_composite(sweep)
    d = ImageDraw.Draw(img)
    bp = (t * 0.35) % 1
    bx, by = cx + lerp(-R * 0.9, R * 0.9, bp), cy + lerp(R * 0.5, -R * 0.6, bp)
    d.ellipse([bx - 16, by - 16, bx + 16, by + 16], fill=(255, 80, 80, 255))
    d.text((bx + 26, by - 30), "OBJETO NO\nIDENTIFICADO", font=font(30), fill=(255, 140, 140, 255))
    d.text((cx, cy + R + 60), "VELOCIDAD: ???   ALTITUD: ???", font=font(40, FONT_SB), anchor="mm",
           fill=(120, 255, 160, 255))
    draw_text(img, "¿Y SI SE ENOJA? *VALIÓ *VERGA", t, 3.4, 1640, size=78)
    return img


def plane(d, x, y, s, color=(235, 235, 240)):
    d.rounded_rectangle([x, y, x + 600 * s, y + 90 * s], radius=45 * s, fill=color + (255,))
    d.polygon([(x + 260 * s, y + 60 * s), (x + 380 * s, y + 60 * s), (x + 300 * s, y + 230 * s), (x + 230 * s, y + 230 * s)],
              fill=(205, 205, 215, 255))
    d.polygon([(x + 30 * s, y + 10 * s), (x + 110 * s, y + 10 * s), (x + 40 * s, y - 110 * s), (x, y - 110 * s)],
              fill=(205, 205, 215, 255))
    for k in range(9):
        d.ellipse([x + (130 + k * 45) * s, y + 25 * s, x + (150 + k * 45) * s, y + 45 * s], fill=(90, 120, 160, 255))


def s_plane(t, dur):
    img = to_img(gradient([(0, (60, 120, 200)), (1, (180, 210, 240))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 4")
    draw_text(img, "QUIERE SALVAR UN *AVIÓN…", t, 0.2, 230, size=90)
    s, x, y = 1.4, 90, 900
    tear = ease((t - 2.0) / 1.0)
    nx = x + 600 * s - 150          # donde se rompe el fuselaje
    sky_rows = {yy: img.getpixel((W - 10, yy)) for yy in range(int(y - 20), int(y + 200))}
    plane(d, x, y + 50 * tear, s)   # el avión cae un poco…
    if tear > 0:
        # …y la nariz se queda arriba: se borra la punta (fila por fila con el color del cielo)
        for yy in range(int(y - 10), int(y + 50 * tear + 90 * s + 10)):
            d.line([(nx, yy), (x + 600 * s + 10, yy)], fill=sky_rows.get(yy, sky_rows[int(y)]))
        zig = [(nx - 2 + (12 if k % 2 else 0), y + 50 * tear + k * 18) for k in range(8)]
        d.line(zig, fill=(60, 60, 70, 255), width=5)
        ny = y - 70 * tear
        d.rounded_rectangle([nx + 30 * tear, ny, x + 600 * s + 40 * tear, ny + 90 * s], radius=45 * s,
                            fill=(235, 235, 240, 255))
        zig2 = [(nx + 30 * tear + (12 if k % 2 else 0), ny + k * 18) for k in range(8)]
        d.line(zig2, fill=(60, 60, 70, 255), width=5)
    # fuerza en un solo punto
    fx = nx + 60
    d.line([(fx, y + 400), (fx, y + 150)], fill=RED + (255,), width=14)
    d.polygon([(fx - 30, y + 170), (fx + 30, y + 170), (fx, y + 120)], fill=RED + (255,))
    d.text((fx - 20, y + 440), "TODA LA FUERZA\nEN UN SOLO PUNTO", font=font(40), anchor="mm", align="center",
           fill=WHITE + (255,), stroke_width=4, stroke_fill=(0, 0, 0, 255))
    if t > 2.3:
        d.text((W / 2, 1600), "…Y LO ATRAVIESA COMO PAPEL", font=font(58), anchor="mm", fill=WHITE + (255,),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
    draw_text(img, "*FÍSICA, *CABRÓN", t, 3.6, 1700, size=88)
    return img


def arrow(d, x0, y0, x1, y1, col, w=12):
    d.line([(x0, y0), (x1, y1)], fill=col + (255,), width=w)
    a = math.atan2(y1 - y0, x1 - x0)
    d.polygon([(x1 + math.cos(a) * 26, y1 + math.sin(a) * 26),
               (x1 + math.cos(a + 2.4) * 26, y1 + math.sin(a + 2.4) * 26),
               (x1 + math.cos(a - 2.4) * 26, y1 + math.sin(a - 2.4) * 26)], fill=col + (255,))


def s_newton(t, dur):
    img = to_img(gradient([(0, (8, 20, 40)), (1, (16, 40, 70))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 8")
    draw_text(img, "LOS CIENTÍFICOS *NO *LO *ENTIENDEN", t, 0.2, 230, size=86)
    cols = [(200, "COHETE", "empuja gas ↓"), (540, "AVE", "empuja aire ↓"), (880, "ÉL", "¿empuja… qué?")]
    for i, (cx, name, sub) in enumerate(cols):
        if t < 0.8 + i * 0.7:
            continue
        top = 720
        if i == 0:
            d.polygon([(cx, top), (cx - 50, top + 120), (cx + 50, top + 120)], fill=(230, 230, 240, 255))
            d.rectangle([cx - 50, top + 120, cx + 50, top + 360], fill=(230, 230, 240, 255))
            for k in range(5):
                fy = top + 380 + ((t * 300 + k * 50) % 250)
                d.ellipse([cx - 30 + k * 12 - 24, fy, cx - 30 + k * 12 + 4, fy + 28], fill=(255, 160, 60, 220))
        elif i == 1:
            flap = math.sin(t * 8) * 60
            d.ellipse([cx - 40, top + 160, cx + 40, top + 240], fill=(230, 230, 240, 255))
            d.polygon([(cx, top + 190), (cx - 160, top + 190 - flap), (cx - 60, top + 210)], fill=(200, 200, 215, 255))
            d.polygon([(cx, top + 190), (cx + 160, top + 190 - flap), (cx + 60, top + 210)], fill=(200, 200, 215, 255))
            arrow(d, cx, top + 300, cx, top + 470, (120, 200, 255))
        else:
            d.text((cx, top + 220), "?", font=font(200), anchor="mm", fill=(255, 255, 255, 220))
        if i < 2:
            arrow(d, cx, top - 20, cx, top - 150, (120, 255, 150))
        d.text((cx, 1300), name, font=font(56), anchor="mm", fill=WHITE + (255,))
        d.text((cx, 1370), sub, font=font(36, FONT_SB), anchor="mm", fill=(170, 200, 230, 255))
    if t > 3.0:
        d.text((W / 2, 1530), "ACCIÓN = REACCIÓN", font=font(64), anchor="mm", fill=WHITE + (255,))
        d.line([(160, 1530), (W - 160, 1530)], fill=RED + (255,), width=10)
        d.text((W / 2, 1640), "3.ª LEY DE NEWTON: ROTA", font=font(56), anchor="mm", fill=YELLOW + (255,),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
    return img


OFFERS = [("Mudanzas Express", "Pago en efectivo, urgente"), ("Constructora del Norte", "Vigas sin grúa"),
          ("Rescates SA", "Turno de noche"), ("Señora de la esquina", "Bajar al gato del árbol · pago en tacos")]


def s_jobs(t, dur):
    img = to_img(gradient([(0, (10, 30, 20)), (1, (20, 60, 40))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 12")
    draw_text(img, "LE LLUEVEN *OFERTAS *DE *TRABAJO", t, 0.2, 230, size=86)
    for i, (who, what) in enumerate(OFFERS):
        if t < 0.8 + i * 0.6:
            continue
        p = ease_out((t - 0.8 - i * 0.6) / 0.35)
        y = 560 + i * 200
        card = Image.new("RGBA", (920, 170), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, 920, 170], radius=30, fill=(250, 250, 252, 245))
        cd.ellipse([30, 45, 110, 125], fill=(60, 170, 100, 255))
        cd.text((70, 85), "$", font=font(56), anchor="mm", fill=WHITE + (255,))
        cd.text((140, 40), who, font=font(46), fill=(20, 20, 26, 255))
        cd.text((140, 106), what, font=font(34, FONT_SB), fill=(90, 90, 100, 255))
        card.putalpha(card.getchannel("A").point(lambda v: int(v * p)))
        img.alpha_composite(card, (int(80 + 60 * (1 - p)), y))
    money = int(1_000_000 * ease((t - 2.2) / 2.2))
    if t > 2.2:
        d.text((W / 2, 1620), f"$ {money:,} ".replace(",", ",") + "ANTES DE LA CENA", font=font(58), anchor="mm",
               fill=YELLOW + (255,), stroke_width=5, stroke_fill=(0, 0, 0, 255))
    return img


def s_ending(t, dur):
    k = ease(t / 3.0)
    img = to_img(gradient([(0, mix((20, 30, 60), (90, 140, 210), k)), (0.6, mix((90, 70, 90), (250, 190, 140), k)),
                           (1, (120, 100, 90))]))
    buildings(img, 1500, seed=6, col=mix((40, 46, 66), (90, 100, 130), k))
    hour(img, t, "HORA 24")
    p = ease((t - 0.3) / 2.2)
    streak(img, W / 2 - 100, 1400, W / 2 + 260, -100, p, width=16)
    draw_text(img, "SE VA VOLANDO AL *AMANECER…", t, 0.2, 280, size=88, out_at=2.6)
    draw_text(img, "…Y NOS DEJA CON UN *CHINGO DE PREGUNTAS", t, 2.9, 280, size=84)
    draw_text(img, "¿TÚ QUÉ LE *PEDIRÍAS?", t, 4.2, 700, size=96)
    return img


SCENES = [
    ("01_hook", s_hook, 4.5, "¿Qué pasaría si Superman apareciera en el mundo real durante veinticuatro horas? "
                             "Agárrate, güey."),
    ("02_sonico", s_sonic, 5.5, "Hora cero. Pasa volando más rápido que el sonido y, ¡pum!, estampido sónico: "
                                "ventanas rotas en toda la colonia. ¡No mames!"),
    ("03_redes", s_social, 5.5, "Hora uno. Todo mundo saca el celular. Unos dicen que es real, otros que es "
                                "efecto especial, y tu tía ya lo mandó a la cadena de oración."),
    ("04_radar", s_radar, 5.5, "Hora dos. Los radares detectan algo volando sin alas ni turbinas. Los gobiernos, "
                               "bien nerviosos: ¿y si se enoja? Valió verga."),
    ("05_avion", s_plane, 6.0, "Hora cuatro. Quiere salvar un avión y lo carga de un solo punto… y lo atraviesa "
                               "como si fuera de papel. Física, cabrón."),
    ("06_newton", s_newton, 6.0, "Hora ocho. Los científicos no lo entienden: para volar tienes que empujar algo, "
                                 "aire o gas. Él no empuja nada. Eso rompe la tercera ley de Newton."),
    ("07_trabajo", s_jobs, 5.5, "Hora doce. Le llueven ofertas: mudanzas, construcción, rescates. Si cobra por "
                                "hora, se hace millonario antes de la cena."),
    ("08_final", s_ending, 6.0, "Hora veinticuatro. Se va volando al amanecer, y nos deja con un chingo de "
                                "preguntas. ¿Tú qué le pedirías?"),
]


# ------------------------------------------------------------------ música heroica con toque cómico (original)
def music(total: float, durs) -> np.ndarray:
    n = int((total + 1) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    bpm = 112
    beat = 60 / bpm
    bar = beat * 4
    chords = [[48, 52, 55], [43, 47, 50], [45, 48, 52], [41, 45, 48]]  # C G Am F
    for b in range(int(total / bar) + 2):
        ch = chords[b % 4]
        s0, s1 = int(b * bar * SR), min(int((b + 1) * bar * SR), n)
        if s0 >= n:
            break
        seg = t[s0:s1] - b * bar
        env = np.minimum(1, seg / 0.3) * np.minimum(1, (bar - seg) / 0.4)
        for m in ch:  # "metales": diente de sierra suave
            f = note(m + 12)
            out[s0:s1] += 0.022 * env * sum(np.sin(2 * np.pi * f * h * seg) / h for h in (1, 2, 3, 4))
    melody = [72, 74, 76, 79, 77, 76, 74, 72]
    for i in range(int(total / beat)):
        if (i // 8) % 2 == 1:  # la fanfarria entra cada dos compases
            m = melody[i % 8]
            s0, L = int(i * beat * SR), int(beat * 0.9 * SR)
            seg = np.arange(L) / SR
            env = np.minimum(1, seg / 0.03) * np.exp(-seg * 2.5)
            f = note(m)
            x = 0.05 * env * (np.sin(2 * np.pi * f * seg) + 0.5 * np.sin(2 * np.pi * 2 * f * seg))
            out[s0:s0 + L] += x[:len(out[s0:s0 + L])]
    rng = np.random.default_rng(5)
    for i in range(int(total / (beat / 2))):  # caja de marcha
        s0, L = int(i * beat / 2 * SR), int(0.12 * SR)
        seg = np.arange(L) / SR
        g = 0.09 if i % 2 else 0.05
        out[s0:s0 + L] += (g * rng.standard_normal(L) * np.exp(-seg * 30))[:len(out[s0:s0 + L])]
    for i in range(int(total / beat)):
        s0, L = int(i * beat * SR), int(0.25 * SR)
        seg = np.arange(L) / SR
        out[s0:s0 + L] += (0.25 * np.exp(-seg * 16) * np.sin(2 * np.pi * (55 + 60 * np.exp(-seg * 30)) * seg))[:len(out[s0:s0 + L])]
    acc = 0.0
    for i, d in enumerate(durs):
        if i > 0:
            boom(out, acc - 0.05, 0.5, rng)
        if i == 1:
            boom(out, acc + BOOM_AT, 1.6, rng)
        acc += d
    return out


VIDEO = Explainer("superman_24h", SCENES, music, default_voice="kokoro:em_alex", clean_map=CLEAN,
                  preview_times=[(0, 2.4), (1, 4.2), (2, 4.0), (3, 4.4), (4, 4.4), (5, 4.0), (6, 4.0), (7, 4.8)])

if __name__ == "__main__":
    VIDEO.run()
