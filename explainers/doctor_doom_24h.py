"""¿Qué pasaría si el Doctor Doom apareciera 24 horas en el mundo real?  (humor mexicano)

Uso (desde la raíz del repo):
    python explainers/doctor_doom_24h.py            -> voz de Alex, con groserías (pocas)
    python explainers/doctor_doom_24h.py --limpio   -> sin groserías
    python explainers/doctor_doom_24h.py frames

Nota de derechos: Doctor Doom es un personaje de Marvel. No se dibuja al personaje ni su
armadura; el video muestra sus efectos.
Datos: armadura completa de la Baja Edad Media ≈ 20-25 kg, y caminar con ella cansa más que
cargar ese peso en mochila (Formenti et al.). Admisión en la ONU: recomendación del Consejo de
Seguridad y votación de dos tercios en la Asamblea General (Carta de la ONU, arts. 4 y 18).
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
GREEN = (60, 200, 110)


def hour(img, t, label):
    badge(img, label, W / 2, 120, t)


def lightning(d, x, y0, y1, seed, width=6):
    r = random.Random(seed)
    pts, y = [(x, y0)], y0
    while y < y1:
        y += r.randint(40, 90)
        x += r.randint(-60, 60)
        pts.append((x, y))
    d.line(pts, fill=(230, 240, 255, 255), width=width)


def s_hook(t, dur):
    flash = 1.0 if (1.2 < t < 1.32 or 2.9 < t < 3.0) else 0.0
    img = to_img(gradient([(0, mix((10, 14, 18), (90, 110, 130), flash)), (0.7, (20, 30, 28)), (1, (10, 16, 14))]))
    d = ImageDraw.Draw(img)
    if flash:
        lightning(d, 300 if t < 2 else 800, 0, 900, int(t * 10))
    r = random.Random(1)
    x = -20
    while x < W:  # colinas oscuras
        w = r.randint(200, 340)
        d.ellipse([x, 1450, x + w * 2, 2100], fill=(14, 22, 18, 255))
        x += w
    draw_text(img, "¿QUÉ PASARÍA SI", t, 0.15, 330, size=84)
    draw_text(img, "*DOCTOR *DOOM", t, 0.55, 470, size=110, per_word=0.12, max_w=1020)
    draw_text(img, "APARECIERA", t, 1.0, 660, size=90)
    draw_text(img, "*24 *HORAS", t, 1.3, 765, size=130)
    draw_text(img, "EN EL MUNDO REAL?", t, 1.8, 925, size=80)
    return shake(img, t, [1.2, 2.9], strength=10)


def s_un(t, dur):
    img = to_img(gradient([(0, (10, 26, 46)), (1, (20, 44, 74))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 0")
    draw_text(img, "LLEGA A LA ONU EXIGIENDO QUE *RECONOZCAN *SU *PAÍS", t, 0.2, 230, size=76)
    cx, cy = W / 2, 1180
    r = random.Random(4)
    votes = []
    for ring in range(5):
        R = 220 + ring * 75
        n = 12 + ring * 5
        for k in range(n):
            a = math.pi + math.pi * (k + 0.5) / n
            votes.append((cx + math.cos(a) * R, cy + math.sin(a) * R, r.random()))
    p = ease((t - 0.8) / 2.0)
    for i, (x, y, v) in enumerate(votes):
        shown = i / len(votes) < p
        col = (90, 100, 120)
        if shown:
            col = (220, 60, 60) if v < 0.72 else GREEN  # la mayoría vota en contra
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=col + (255,))
    d.rounded_rectangle([cx - 140, cy - 40, cx + 140, cy + 60], radius=18, fill=(30, 50, 80, 255))
    d.text((cx, cy + 10), "PODIO", font=font(40), anchor="mm", fill=(170, 190, 220, 255))
    if t > 2.6:
        d.text((W / 2, 1360), "NECESITA AL CONSEJO DE SEGURIDAD", font=font(50), anchor="mm", fill=WHITE + (255,),
               stroke_width=4, stroke_fill=(0, 0, 0, 255))
        d.text((W / 2, 1440), "+ 2/3 DE LA ASAMBLEA", font=font(64), anchor="mm", fill=YELLOW + (255,),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
    draw_text(img, "¡*NO *MAMES, QUÉ TRÁMITE!", t, 3.8, 1580, size=86)
    return img


def s_armor(t, dur):
    img = to_img(gradient([(0, (60, 26, 10)), (1, (120, 54, 20))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 1")
    draw_text(img, "UNA ARMADURA DE VERDAD PESA *20 *A *25 *KILOS", t, 0.2, 230, size=78)
    rows = [("MOCHILA DE 25 kg", 0.55, (120, 190, 255)), ("ARMADURA DE 25 kg", 0.9, (255, 120, 80))]
    for i, (label, val, col) in enumerate(rows):
        if t < 1.0 + i * 0.5:
            continue
        y = 640 + i * 200
        p = ease_out((t - 1.0 - i * 0.5) / 0.8)
        d.text((100, y), label, font=font(48), fill=WHITE + (255,))
        d.rounded_rectangle([100, y + 70, W - 100, y + 130], radius=20, fill=(60, 30, 20, 255))
        d.rounded_rectangle([100, y + 70, 100 + (W - 200) * val * p, y + 130], radius=20, fill=col + (255,))
    if t > 2.0:
        d.text((W / 2, 1060), "ENERGÍA QUE GASTAS AL CAMINAR", font=font(40, FONT_SB), anchor="mm",
               fill=(255, 220, 190, 255))
    # termómetro de Monterrey
    tx, top, bot = W / 2, 1180, 1620
    d.rounded_rectangle([tx - 36, top, tx + 36, bot], radius=36, fill=(240, 240, 245, 255))
    d.ellipse([tx - 66, bot - 30, tx + 66, bot + 100], fill=(240, 240, 245, 255))
    lvl = lerp(bot - 40, top + 30, ease((t - 2.4) / 1.5))
    d.rounded_rectangle([tx - 20, lvl, tx + 20, bot], radius=20, fill=RED + (255,))
    d.ellipse([tx - 48, bot - 12, tx + 48, bot + 84], fill=RED + (255,))
    if t > 2.6:
        d.text((tx + 100, (top + bot) / 2), "CON EL CALOR\nDE MONTERREY", font=font(48), anchor="lm",
               fill=YELLOW + (255,), stroke_width=4, stroke_fill=(0, 0, 0, 255))
    return img


MEMES = ["EL SEÑOR DE LA LATA", "¿DOCTOR DE QUÉ? ¿DE LAS LATAS?", "CUANDO TE DICEN «VE POR LAS TORTILLAS»",
         "YO A LAS 6 AM CON MI ARMADURA DE SUEÑO"]


def s_memes(t, dur):
    img = to_img(gradient([(0, (24, 10, 40)), (1, (54, 20, 70))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 2")
    draw_text(img, "INTERNET LE HACE UN *CHINGO DE MEMES", t, 0.2, 230, size=82)
    cx, cy, pw, ph = W / 2, 1150, 680, 1100
    phone(d, cx, cy, pw, ph)
    for i, m in enumerate(MEMES):
        if t < 0.8 + i * 0.6:
            continue
        p = ease_out((t - 0.8 - i * 0.6) / 0.35)
        y = cy - ph / 2 + 90 + i * 240
        card = Image.new("RGBA", (pw - 80, 210), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, pw - 80, 210], radius=24, fill=(250, 250, 250, 255))
        cd.rectangle([20, 20, 170, 190], fill=(150, 150, 160, 255))
        cd.text((95, 105), "?", font=font(90), anchor="mm", fill=(230, 230, 236, 255))
        f = font(34)
        words, lines, cur = m.split(), [], ""
        for w in words:
            if f.getlength(cur + " " + w) > 380:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
        for k, ln in enumerate(lines[:3]):
            cd.text((195, 40 + k * 46), ln, font=f, fill=(20, 20, 26, 255))
        card.putalpha(card.getchannel("A").point(lambda v: int(v * p)))
        img.alpha_composite(card, (int(cx - pw / 2 + 40), int(y + 20 * (1 - p))))
    return img


def s_sat(t, dur):
    img = to_img(gradient([(0, (230, 232, 236)), (1, (200, 204, 212))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 4")
    draw_text(img, "QUIERE COMPRAR *MEDIA *CIUDAD… Y EL *SAT LE PIDE PAPELES", t, 0.2, 230, size=72)
    d.rounded_rectangle([110, 600, W - 110, 1380], radius=26, fill=(255, 255, 255, 255), outline=(170, 175, 185, 255),
                        width=4)
    d.text((150, 640), "REQUISITOS", font=font(50), fill=(30, 40, 60, 255))
    d.text((W - 150, 650), f"TURNO {int(lerp(12, 487, ease(t / 3)))}", font=font(38, FONT_SB), anchor="ra",
           fill=(120, 130, 150, 255))
    items = ["RFC", "Comprobante de domicilio", "Constancia de situación fiscal", "Identificación oficial"]
    for i, it in enumerate(items):
        if t < 0.9 + i * 0.45:
            continue
        y = 760 + i * 140
        d.rounded_rectangle([150, y, 230, y + 80], radius=14, fill=(230, 70, 70, 255))
        d.line([(170, y + 20), (210, y + 60)], fill=WHITE + (255,), width=10)
        d.line([(210, y + 20), (170, y + 60)], fill=WHITE + (255,), width=10)
        d.text((260, y + 40), it, font=font(42, FONT_SB), anchor="lm", fill=(30, 40, 60, 255))
    draw_text(img, "*VALIÓ *VERGA", t, 3.4, 1500, size=104)
    return img


def scientist(d, cx, cy, col):
    d.ellipse([cx - 40, cy - 150, cx + 40, cy - 70], fill=(240, 210, 180, 255))
    d.rounded_rectangle([cx - 70, cy - 70, cx + 70, cy + 120], radius=30, fill=(245, 245, 250, 255))
    d.rectangle([cx - 8, cy - 70, cx + 8, cy + 60], fill=col + (255,))


def s_science(t, dur):
    img = to_img(gradient([(0, (8, 24, 44)), (1, (16, 48, 80))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 8")
    draw_text(img, "LOS CIENTÍFICOS QUIEREN ESTUDIAR SU *TECNOLOGÍA", t, 0.2, 230, size=78)
    cols = [(60, 140, 230), (230, 120, 60), (120, 200, 90)]
    for i in range(3):
        if t > 0.8 + i * 0.35:
            scientist(d, 250 + i * 290, 1000, cols[i])
    if t > 2.0:
        d.text((W / 2, 1250), "«SOLO HABLO CON GENIOS»", font=font(56), anchor="mm", fill=WHITE + (255,),
               stroke_width=4, stroke_fill=(0, 0, 0, 255))
    if t > 3.0:
        p = ease_out((t - 3.0) / 0.3)
        st = Image.new("RGBA", (720, 200), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        sd.rounded_rectangle([8, 8, 712, 192], radius=24, outline=RED + (255,), width=12)
        sd.text((360, 100), "DESPEDIDOS", font=font(100), anchor="mm", fill=RED + (255,))
        st = st.rotate(10, expand=True, resample=Image.BICUBIC)
        sc = 1.5 - 0.5 * p
        st = st.resize((int(st.width * sc), int(st.height * sc)))
        st.putalpha(st.getchannel("A").point(lambda v: int(v * p)))
        paste_center(img, st, W / 2, 980)
    return img


def s_traffic(t, dur):
    img = to_img(gradient([(0, (40, 34, 40)), (1, (70, 50, 46))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 12")
    draw_text(img, "AMENAZA CON *CONQUISTAR *EL *MUNDO… Y SE ATORA EN EL *PERIFÉRICO", t, 0.2, 230, size=70)
    rl, rr = 140, 940
    d.rectangle([rl, 720, rr, H], fill=(52, 52, 58, 255))
    for lane in range(1, 4):
        lx = rl + lane * 200
        for y in range(720, H, 90):
            d.rectangle([lx - 4, y, lx + 4, y + 45], fill=(230, 210, 120, 255))
    cars = random.Random(2)
    colors = [(220, 220, 225), (40, 40, 48), (60, 110, 200), (200, 60, 60), (240, 190, 40)]
    for lane in range(4):
        for k in range(12):
            y = 760 + k * 100 + 4 * math.sin(t * 1.5 + k + lane)
            x = rl + 50 + lane * 200
            d.rounded_rectangle([x, y, x + 100, y + 80], radius=14, fill=colors[(k * 3 + lane) % 5] + (255,))
    clock_h = int(lerp(0, 3, ease((t - 0.8) / 2.5)) * 60)
    d.rounded_rectangle([W / 2 - 230, 600, W / 2 + 230, 700], radius=20, fill=(0, 0, 0, 200))
    d.text((W / 2, 650), f"ATORADO: {clock_h // 60} h {clock_h % 60:02d} min", font=font(46), anchor="mm",
           fill=YELLOW + (255,))
    draw_text(img, "AHÍ SÍ, *CABRÓN", t, 3.4, 1700, size=96)
    return img


def s_ending(t, dur):
    img = to_img(gradient([(0, (14, 22, 40)), (1, (30, 40, 70))]))
    d = ImageDraw.Draw(img)
    hour(img, t, "HORA 24")
    draw_text(img, "SE VA PROMETIENDO *VOLVER…", t, 0.2, 260, size=92, out_at=2.6)
    draw_text(img, "…CON SU TRÁMITE A MEDIAS", t, 2.9, 260, size=92)
    # urna de votación
    d.rounded_rectangle([340, 900, 740, 1300], radius=20, fill=(220, 225, 235, 255))
    d.rectangle([440, 890, 640, 912], fill=(60, 70, 90, 255))
    p = (t * 0.8) % 1
    y = lerp(620, 900, ease(p))
    d.rectangle([480, y - 60, 600, y + 60], fill=(255, 255, 255, 255), outline=(150, 150, 160, 255), width=3)
    d.text((540, y), "✓", font=font(60), anchor="mm", fill=(60, 160, 90, 255))
    d.text((540, 1120), "VOTO", font=font(60), anchor="mm", fill=(60, 70, 90, 255))
    draw_text(img, "¿TÚ *VOTARÍAS *POR *ÉL?", t, 4.0, 1460, size=100)
    return img


SCENES = [
    ("01_hook", s_hook, 4.5, "¿Qué pasaría si el Doctor Doom apareciera en el mundo real durante veinticuatro "
                             "horas? Agárrate, güey."),
    ("02_onu", s_un, 6.0, "Hora cero. Llega a la ONU exigiendo que reconozcan a su país. Malas noticias: necesita "
                          "al Consejo de Seguridad y dos tercios de la Asamblea. ¡No mames, qué trámite!"),
    ("03_armadura", s_armor, 6.0, "Hora uno. Una armadura de verdad pesa unos veinte kilos, y caminar con ella "
                                  "cansa más que cargar lo mismo en una mochila. Ahora imagínala con el calor de "
                                  "Monterrey."),
    ("04_memes", s_memes, 5.0, "Hora dos. Internet le hace un chingo de memes y lo bautiza el señor de la lata."),
    ("05_sat", s_sat, 5.5, "Hora cuatro. Quiere comprar media ciudad, y el SAT le pide su RFC, comprobante de "
                           "domicilio y constancia de situación fiscal. Valió verga."),
    ("06_ciencia", s_science, 5.0, "Hora ocho. Los científicos quieren estudiar su tecnología, pero él solo habla con "
                                   "genios. Se presentan tres. Los corre a los tres."),
    ("07_trafico", s_traffic, 5.5, "Hora doce. Amenaza con conquistar el mundo, y se atora tres horas en el "
                                   "Periférico. Ahí sí, cabrón."),
    ("08_final", s_ending, 5.5, "Hora veinticuatro. Se va prometiendo volver, con su trámite a medias. "
                                "¿Tú votarías por él?"),
]


def music(total: float, durs) -> np.ndarray:
    """Marcha villana: órgano grave, timbales y coro sintético (original)."""
    n = int((total + 1) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    bpm = 96
    beat = 60 / bpm
    bar = beat * 4
    chords = [[38, 41, 45], [34, 38, 41], [36, 40, 43], [33, 37, 40]]  # Dm Bb C A
    for b in range(int(total / bar) + 2):
        ch = chords[b % 4]
        s0, s1 = int(b * bar * SR), min(int((b + 1) * bar * SR), n)
        if s0 >= n:
            break
        seg = t[s0:s1] - b * bar
        env = np.minimum(1, seg / 0.2) * np.minimum(1, (bar - seg) / 0.3)
        for m in ch:
            for octv in (0, 12, 24):  # órgano: varias octavas
                f = note(m + octv)
                out[s0:s1] += (0.03 / (1 + octv / 12)) * env * np.sin(2 * np.pi * f * seg)
    for i in range(int(total / beat)):  # timbales de marcha
        if i % 4 in (0, 2, 3):
            s0, L = int(i * beat * SR), int(0.4 * SR)
            seg = np.arange(L) / SR
            g = 0.35 if i % 4 == 0 else 0.22
            out[s0:s0 + L] += (g * np.exp(-seg * 7) * np.sin(2 * np.pi * (70 + 20 * np.exp(-seg * 20)) * seg))[:len(out[s0:s0 + L])]
    rng = np.random.default_rng(11)
    acc = 0.0
    for i, d in enumerate(durs):
        if i > 0:
            boom(out, acc - 0.05, 0.55, rng)
        acc += d
    boom(out, 1.2, 1.0, rng)
    boom(out, 2.9, 0.8, rng)
    return out


VIDEO = Explainer("doctor_doom_24h", SCENES, music, default_voice="kokoro:em_alex", clean_map=CLEAN,
                  preview_times=[(0, 2.4), (1, 4.2), (2, 3.4), (3, 3.2), (4, 3.8), (5, 3.6), (6, 3.8), (7, 4.4)])

if __name__ == "__main__":
    VIDEO.run()
