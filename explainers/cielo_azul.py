"""Video explicativo vertical: ¿Por qué el cielo es azul… y el atardecer naranja?

Uso (desde la raíz del repo):
    python explainers/cielo_azul.py              -> video con voz (Piper) y música
    python explainers/cielo_azul.py --sin-voz    -> solo texto en pantalla + música
    python explainers/cielo_azul.py --voz es_MX-ald-medium
    python explainers/cielo_azul.py frames       -> fotogramas de muestra en preview/

Resultado: data/explicativos/cielo_azul/cielo_azul_short.mp4
Todo es original: animaciones dibujadas por código y música sintetizada (sin derechos de terceros).
"""
import argparse, math, os, random, subprocess, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = str(ROOT / "data" / "explicativos" / "cielo_azul")
def _pick_font(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise SystemExit("No se encontró una fuente gruesa. Instala: sudo apt-get install -y fonts-dejavu-core")

# Inter si existe; si no, DejaVu (viene con fonts-dejavu-core en el devcontainer).
FONT = _pick_font("/usr/share/fonts/opentype/inter/Inter-Black.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_SB = _pick_font("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
YELLOW = (255, 214, 10)
WHITE = (255, 255, 255)
random.seed(7)

_font_cache = {}
def font(size, path=FONT):
    k = (size, path)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(path, size)
    return _font_cache[k]

def lerp(a, b, t): return a + (b - a) * t
def clamp(x, lo=0.0, hi=1.0): return max(lo, min(hi, x))
def ease(t): t = clamp(t); return t * t * (3 - 2 * t)
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def mix(c1, c2, t): return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))

def gradient(stops):
    """stops: [(pos 0-1, (r,g,b)), ...] -> array H x W x 3"""
    ys = np.linspace(0, 1, H)
    col = np.zeros((H, 3), np.float32)
    for ch in range(3):
        col[:, ch] = np.interp(ys, [p for p, _ in stops], [c[ch] for _, c in stops])
    return np.repeat(col[:, None, :], W, axis=1)

def to_img(arr): return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")

def glow(radius, color, strength=1.0):
    size = radius * 2
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2) / radius
    a = np.clip(1 - d, 0, 1) ** 2.2 * 255 * strength
    img = np.zeros((size, size, 4), np.uint8)
    img[..., 0], img[..., 1], img[..., 2] = color
    img[..., 3] = np.clip(a, 0, 255)
    return Image.fromarray(img, "RGBA")

def paste_center(base, overlay, cx, cy):
    base.alpha_composite(overlay, (int(cx - overlay.width / 2), int(cy - overlay.height / 2)))

# ------------------------------------------------------------------ texto
def layout(words, size, max_w=900):
    f = font(size)
    lines, cur, cur_w = [], [], 0
    space = f.getlength(" ")
    for w in words:
        ww = f.getlength(w[0])
        if cur and cur_w + space + ww > max_w:
            lines.append(cur); cur, cur_w = [], 0
        cur.append(w); cur_w += (space if len(cur) > 1 else 0) + ww
    if cur: lines.append(cur)
    return lines

def draw_text(img, text, t, start, y, size=96, hl=(), color=WHITE, per_word=0.085, max_w=900, out_at=None):
    """Palabras que entran una a una (fade + subida). `hl`: palabras en amarillo."""
    if t < start: return
    words = [(w.replace("*", ""), w.startswith("*") or w.strip("¿?¡!.,:…").upper() in hl) for w in text.split()]
    lines = layout(words, size, max_w)
    f = font(size)
    line_h = int(size * 1.12)
    draw = ImageDraw.Draw(img)
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
                td.text((20 + 5, 20 + 7), w, font=f, fill=(0, 0, 0, 150))  # sombra
                td.text((20, 20), w, font=f, fill=c + (255,), stroke_width=max(4, size // 14), stroke_fill=(0, 0, 0, 255))
                if a < 1:
                    alpha = txt.getchannel("A").point(lambda v: int(v * a))
                    txt.putalpha(alpha)
                img.alpha_composite(txt, (int(x - 20), int(y + li * line_h + dy - 20)))
            x += f.getlength(w) + space
            i += 1

def progress_bar(img, gt, total):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=(0, 0, 0, 90))
    d.rectangle([0, 0, int(W * gt / total), 10], fill=YELLOW + (255,))

# ------------------------------------------------------------------ escenas
SKY = gradient([(0, (40, 110, 220)), (0.55, (110, 175, 245)), (1, (205, 230, 255))])
SPACE = gradient([(0, (6, 8, 22)), (0.6, (14, 20, 48)), (1, (24, 30, 70))])
SUNSET = gradient([(0, (40, 30, 90)), (0.35, (180, 70, 90)), (0.62, (255, 130, 50)), (1, (255, 200, 110))])
DUSK = gradient([(0, (14, 14, 40)), (0.5, (70, 40, 90)), (1, (200, 90, 70))])
SUN_GLOW = glow(260, (255, 236, 160), 0.9)
SUN_GLOW_ORANGE = glow(300, (255, 150, 60), 0.95)
RAINBOW = [(255, 59, 48), (255, 149, 0), (255, 214, 10), (52, 199, 89), (0, 170, 255), (40, 90, 255), (150, 70, 230)]

def clouds(img, t, y0, alpha=200):
    d = ImageDraw.Draw(img)
    for k, (bx, by, s) in enumerate([(120, 0, 1.0), (620, 120, 0.8), (900, -60, 0.6)]):
        x = (bx + t * 18 * (1 + k * 0.3)) % (W + 400) - 200
        y = y0 + by
        for ox, oy, r in [(0, 0, 70), (70, -30, 85), (150, 0, 70), (75, 25, 75)]:
            rr = r * s
            d.ellipse([x + ox * s - rr, y + oy * s - rr, x + ox * s + rr, y + oy * s + rr], fill=(255, 255, 255, alpha))

def sun(img, cx, cy, r, t, orange=False):
    pulse = 1 + 0.04 * math.sin(t * 3)
    g = SUN_GLOW_ORANGE if orange else SUN_GLOW
    g2 = g.resize((int(g.width * pulse * 1.2), int(g.height * pulse * 1.2)))
    paste_center(img, g2, cx, cy)
    d = ImageDraw.Draw(img)
    col = (255, 170, 70) if orange else (255, 245, 200)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (255,))

def wave_points(x0, y0, x1, y1, amp, wl, phase, steps=120):
    pts = []
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    for i in range(steps + 1):
        s = L * i / steps
        off = amp * math.sin(2 * math.pi * s / wl - phase)
        pts.append((x0 + ux * s + nx * off, y0 + uy * s + ny * off))
    return pts

def scene_hook(t, dur):
    img = to_img(SKY).convert("RGBA")
    sun(img, 820, 1260, 95, t)
    clouds(img, t, 1500, 230)
    s = 1 + 0.05 * math.sin(t * 2.2)
    draw_text(img, "¿POR QUÉ EL CIELO ES", t, 0.15, 430, size=84, max_w=980)
    if t > 0.75:
        p = ease_out((t - 0.75) / 0.35)
        f = font(int(250 * (0.6 + 0.4 * p) * s))
        txt = Image.new("RGBA", (1000, 360), (0, 0, 0, 0))
        d = ImageDraw.Draw(txt)
        d.text((500, 180), "AZUL?", font=f, anchor="mm", fill=YELLOW + (255,), stroke_width=14, stroke_fill=(0, 0, 0, 255))
        txt.putalpha(txt.getchannel("A").point(lambda v: int(v * p)))
        paste_center(img, txt, W / 2, 790)
    draw_text(img, "(y por qué el atardecer es naranja)", t, 2.2, 990, size=50, per_word=0.05)
    return img

def scene_white_light(t, dur):
    img = to_img(SPACE).convert("RGBA")
    d = ImageDraw.Draw(img)
    rnd = random.Random(1)
    for _ in range(90):
        x, y = rnd.randrange(W), rnd.randrange(H)
        b = int(120 + 120 * abs(math.sin(t * 2 + x)))
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(b, b, b, 255))
    sun(img, 150, 1150, 80, t)
    # haz blanco que avanza y se abre en colores
    reach = ease_out(t / 1.3)
    split_x = 520
    bx = lerp(200, split_x, reach)
    d.line([(200, 1150), (bx, 1150)], fill=(255, 255, 255, 255), width=26)
    if t > 1.3:
        p = ease_out((t - 1.3) / 1.2)
        for k, c in enumerate(RAINBOW):
            ang = math.radians(-24 + k * 8)
            L = 560 * p
            ex, ey = split_x + math.cos(ang) * L, 1150 + math.sin(ang) * L
            d.line([(split_x, 1150), (ex, ey)], fill=c + (255,), width=22)
        d.ellipse([split_x - 22, 1128, split_x + 22, 1172], fill=(255, 255, 255, 255))
    draw_text(img, "LA LUZ DEL SOL PARECE BLANCA…", t, 0.2, 380, size=84)
    draw_text(img, "PERO TRAE *TODOS *LOS *COLORES", t, 2.2, 640, size=96)
    return img

MOLS = [(random.randrange(60, W - 60), random.randrange(1000, 1560), random.random() * 6.28) for _ in range(46)]

def scene_molecules(t, dur):
    img = to_img(gradient([(0, (18, 40, 90)), (1, (40, 90, 170))])).convert("RGBA")
    d = ImageDraw.Draw(img)
    for x, y, ph in MOLS:
        mx, my = x + 8 * math.sin(t * 1.5 + ph), y + 8 * math.cos(t * 1.3 + ph)
        d.ellipse([mx - 11, my - 11, mx + 11, my + 11], fill=(230, 240, 255, 230))
        d.ellipse([mx + 6, my - 6, mx + 22, my + 10], fill=(200, 220, 255, 230))
    # rayo rojo: pasa recto
    rr = ease((t - 0.8) / 2.2)
    if rr > 0:
        d.line(wave_points(0, 1180, W * rr, 1180, 16, 120, t * 8), fill=(255, 70, 60, 255), width=10)
    # rayo azul: choca y se dispersa
    hit = (560, 1400)
    rb = ease((t - 1.2) / 1.4)
    if rb > 0:
        end = (lerp(0, hit[0], rb), lerp(1400, hit[1], rb))
        d.line(wave_points(0, 1400, end[0] + 0.01, end[1], 12, 60, t * 10), fill=(60, 160, 255, 255), width=10)
    if t > 2.6:
        q = ease_out((t - 2.6) / 1.4)
        for k in range(12):
            ang = 2 * math.pi * k / 12 + 0.2
            L = 30 + 330 * q
            ex, ey = hit[0] + math.cos(ang) * L, hit[1] + math.sin(ang) * L
            sx, sy = hit[0] + math.cos(ang) * 30, hit[1] + math.sin(ang) * 30
            d.line(wave_points(sx, sy, ex, ey, 9, 50, t * 10), fill=(90, 180, 255, int(255 * (1 - 0.4 * q))), width=8)
        paste_center(img, glow(90, (120, 200, 255), 0.8), *hit)
    draw_text(img, "AL ENTRAR AL AIRE, CHOCA CON *MOLÉCULAS *DIMINUTAS", t, 0.2, 360, size=84)
    draw_text(img, "el rojo sigue de largo · el azul rebota", t, 3.2, 860, size=48, per_word=0.05)
    return img

def scene_compare(t, dur):
    img = to_img(gradient([(0, (12, 18, 40)), (1, (28, 40, 80))])).convert("RGBA")
    d = ImageDraw.Draw(img)
    base_y = 1560
    p = ease_out((t - 0.9) / 1.6)
    bars = [("ROJO", "700 nm", (255, 70, 60), 1.0, 250), ("AZUL", "450 nm", (60, 160, 255), 5.86, 630)]
    for name, nm, col, val, x in bars:
        h = 105 * val * p
        d.rounded_rectangle([x, base_y - h, x + 200, base_y], radius=18, fill=col + (255,))
        d.text((x + 100, base_y + 50), name, font=font(64), anchor="mm", fill=WHITE + (255,))
        d.text((x + 100, base_y + 115), nm, font=font(40, FONT_SB), anchor="mm", fill=(170, 185, 220, 255))
        if p > 0.95:
            label = "1×" if val == 1 else "≈ 6×"
            d.text((x + 100, base_y - h - 60), label, font=font(70), anchor="mm",
                   fill=(YELLOW if val > 1 else WHITE) + (255,), stroke_width=5, stroke_fill=(0, 0, 0, 255))
    draw_text(img, "EL AZUL SE DISPERSA CASI *6 *VECES MÁS QUE EL ROJO", t, 0.2, 300, size=82)
    draw_text(img, "(dispersión de Rayleigh: la luz de onda corta rebota mucho más)", t, 2.6, 730, size=40, per_word=0.04)
    return img

def person(d, cx, base):
    d.ellipse([cx - 34, base - 230, cx + 34, base - 162], fill=(20, 24, 40, 255))
    d.rounded_rectangle([cx - 46, base - 160, cx + 46, base - 40], radius=30, fill=(20, 24, 40, 255))
    d.rectangle([cx - 36, base - 60, cx - 10, base], fill=(20, 24, 40, 255))
    d.rectangle([cx + 10, base - 60, cx + 36, base], fill=(20, 24, 40, 255))

def scene_everywhere(t, dur):
    k = ease(t / 2.5)
    arr = SKY * (0.75 + 0.25 * k) + np.array([0, 0, 25 * k])
    img = to_img(arr).convert("RGBA")
    d = ImageDraw.Draw(img)
    ground = 1480
    d.rectangle([0, ground, W, H], fill=(46, 120, 70, 255))
    cx = W / 2
    person(d, cx, ground)
    rnd = random.Random(3)
    for i in range(26):
        ang = math.radians(rnd.uniform(195, 345))
        phase = (t * 0.55 + rnd.random()) % 1
        r0 = 900 * (1 - phase) + 120
        x, y = cx + math.cos(ang) * r0, ground - 200 + math.sin(ang) * r0
        a = int(255 * min(1, phase * 3) * min(1, (1 - phase) * 4))
        d.ellipse([x - 13, y - 13, x + 13, y + 13], fill=(255, 255, 255, a))
        d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(40, 120, 255, a))
    draw_text(img, "POR ESO EL AZUL TE LLEGA DESDE *TODO *EL *CIELO", t, 0.2, 360, size=92)
    return img

def scene_sunset(t, dur):
    k = ease((t - 0.6) / 3.0)
    arr = SKY * (1 - k) + SUNSET * k
    img = to_img(arr).convert("RGBA")
    d = ImageDraw.Draw(img)
    # Tierra curva + capa de aire
    R = 2600
    ecx, ecy = W / 2, 1420 + R
    d.ellipse([ecx - R - 160, ecy - R - 160, ecx + R + 160, ecy + R + 160], fill=(140, 200, 255, int(70 + 40 * k)))
    d.ellipse([ecx - R, ecy - R, ecx + R, ecy + R], fill=(30, 60, 50, 255))
    obs = (W / 2, 1420)
    person(d, obs[0], obs[1] + 4)
    # sol que baja hacia el horizonte
    sx = lerp(W / 2 + 120, W - 140, k)
    sy = lerp(560, 1290, k)
    sun(img, sx, sy, 70, t, orange=k > 0.5)
    d = ImageDraw.Draw(img)
    # camino de la luz por el aire
    col = mix((255, 255, 255), (255, 120, 40), k)
    d.line([(sx - 50, sy + 10), (obs[0] + 40, obs[1] - 200)], fill=col + (255,), width=12)
    if k > 0.4:  # el azul sale del camino
        rnd = random.Random(5)
        for i in range(10):
            s = rnd.random()
            px, py = lerp(sx - 50, obs[0] + 40, s), lerp(sy + 10, obs[1] - 200, s)
            out = ((t * 0.8 + rnd.random()) % 1) * 140
            ang = rnd.uniform(0, 6.28)
            d.ellipse([px + math.cos(ang) * out - 8, py + math.sin(ang) * out - 8,
                       px + math.cos(ang) * out + 8, py + math.sin(ang) * out + 8], fill=(60, 140, 255, 200))
    draw_text(img, "¿Y EL ATARDECER?", t, 0.15, 300, size=104, out_at=2.4)
    draw_text(img, "LA LUZ CRUZA MUCHO MÁS AIRE: EL AZUL SE PIERDE Y LLEGAN *NARANJAS *Y *ROJOS", t, 2.7, 300,
              size=78, per_word=0.07)
    return img

def scene_outro(t, dur):
    k = ease(t / 2.0)
    img = to_img(SUNSET * (1 - k) + DUSK * k).convert("RGBA")
    d = ImageDraw.Draw(img)
    rnd = random.Random(9)
    for _ in range(int(60 * k)):
        x, y = rnd.randrange(W), rnd.randrange(900)
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, int(200 * k)))
    sun(img, W - 120, 1500 + 200 * k, 70, t, orange=True)
    draw_text(img, "AHORA YA LO *SABES", t, 0.2, 640, size=104)
    draw_text(img, "¿Qué otro misterio quieres que explique?", t, 1.2, 960, size=54, per_word=0.05)
    return img

SCENES = [
    ("01_hook", scene_hook, 4.5),
    ("02_luz", scene_white_light, 6.0),
    ("03_moleculas", scene_molecules, 7.0),
    ("04_compara", scene_compare, 6.0),
    ("05_todo_cielo", scene_everywhere, 5.5),
    ("06_atardecer", scene_sunset, 8.0),
    ("07_cierre", scene_outro, 3.5),
]
TOTAL = sum(d for _, _, d in SCENES)

# Narración (una por escena). Frases cortas y naturales, al ritmo del texto en pantalla.
NARRATION = [
    "¿Por qué el cielo es azul? ¿Y por qué al atardecer se pone naranja?",
    "La luz del Sol parece blanca, pero en realidad trae todos los colores mezclados.",
    "Al entrar a la atmósfera, esa luz choca con moléculas diminutas de aire. El rojo pasa casi de largo, pero el azul rebota para todos lados.",
    "De hecho, el azul se dispersa casi seis veces más que el rojo. A esto se le llama dispersión de Rayleigh.",
    "Por eso, mires a donde mires, el azul te llega desde todo el cielo.",
    "¿Y el atardecer? Cuando el Sol está bajo, su luz cruza mucho más aire. El azul se pierde en el camino, y lo que llega son los naranjas y los rojos.",
    "Ahora ya lo sabes. ¿Qué otro misterio quieres que te explique?",
]
VOICE_LEAD = 0.25   # segundos de aire antes de que hable cada escena
VOICE_TAIL = 0.6    # aire después de la última palabra


def prepare_voice(voice_name, work):
    """Genera la voz de cada escena y alarga las escenas para que quepa lo narrado."""
    global SCENES, TOTAL
    from app.services import voice as V
    wavs = []
    new = []
    for i, ((name, fn, dur), text) in enumerate(zip(SCENES, NARRATION)):
        out = os.path.join(work, f"{i + 1:02d}.wav")
        V.synthesize(text, out, voice=voice_name)
        vlen = V.wav_duration(out)
        wavs.append(out)
        new.append((name, fn, round(max(dur, VOICE_LEAD + vlen + VOICE_TAIL), 2)))
        print(f"voz {name}: {vlen:.1f} s", flush=True)
    SCENES = new
    TOTAL = sum(d for _, _, d in SCENES)
    return wavs


def read_mono(path, sr=44100):
    import numpy as _np
    with wave.open(path, "rb") as wf:
        rate, ch, n = wf.getframerate(), wf.getnchannels(), wf.getnframes()
        x = _np.frombuffer(wf.readframes(n), _np.int16).astype(_np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if rate != sr:
        t_old = _np.arange(len(x)) / rate
        t_new = _np.arange(int(len(x) * sr / rate)) / sr
        x = _np.interp(t_new, t_old, x).astype(_np.float32)
    return x


def voice_track(wavs, sr=44100):
    track = np.zeros(int((TOTAL + 1) * sr), np.float32)
    start = 0.0
    for (name, _, dur), path in zip(SCENES, wavs):
        x = read_mono(path, sr)
        s0 = int((start + VOICE_LEAD) * sr)
        track[s0:s0 + len(x)] += x[:len(track) - s0]
        start += dur
    return track
XFADE = 8  # fotogramas de fundido dentro del archivo de cada escena

def frame(idx, t, gt, prev_last=None, fi=0):
    name, fn, dur = SCENES[idx]
    img = fn(t, dur)
    progress_bar(img, gt, TOTAL)
    rgb = img.convert("RGB")
    if prev_last is not None and fi < XFADE:
        rgb = Image.blend(prev_last, rgb, (fi + 1) / (XFADE + 1))
    return rgb

def render_scene(idx, prev_last, t_offset):
    name, fn, dur = SCENES[idx]
    n = int(round(dur * FPS))
    tmp = os.path.join(OUT, "scenes", f"{name}.tmp.mp4")
    final = os.path.join(OUT, "scenes", f"{name}.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                          "-pix_fmt", "yuv420p", "-r", str(FPS), tmp], stdin=subprocess.PIPE)
    last = None
    for fi in range(n):
        t = fi / FPS
        last = frame(idx, t, t_offset + t, prev_last, fi)
        p.stdin.write(last.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise SystemExit(f"ffmpeg falló en {name}")
    os.replace(tmp, final)
    return last

# ------------------------------------------------------------------ música original (sintetizada)
def music(path, voice=None):
    sr = 44100
    n = int(TOTAL * sr) + sr
    t = np.arange(n) / sr
    out = np.zeros(n, np.float32)
    bpm = 96
    beat = 60 / bpm
    def note(f): return 440 * 2 ** ((f - 69) / 12)
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    bar = beat * 4
    # pad suave
    for b in range(int(TOTAL / bar) + 2):
        ch = chords[b % 4]
        s0, s1 = int(b * bar * sr), int((b + 1) * bar * sr)
        seg = t[s0:s1] - b * bar
        env = np.minimum(1, seg / 0.6) * np.minimum(1, (bar - seg) / 0.6)
        for m in ch:
            f = note(m)
            out[s0:s1] += 0.05 * env * (np.sin(2 * np.pi * f * seg) + 0.3 * np.sin(2 * np.pi * 2 * f * seg))
    # arpegio pluck
    step = beat / 2
    for i in range(int(TOTAL / step)):
        b = int(i * step / bar)
        ch = chords[b % 4]
        m = ch[[0, 1, 2, 1][i % 4]] + 12
        f = note(m)
        s0 = int(i * step * sr); L = int(0.5 * sr)
        seg = np.arange(L) / sr
        env = np.exp(-seg * 7)
        out[s0:s0 + L] += (0.07 * env * (np.sin(2 * np.pi * f * seg) + 0.25 * np.sin(2 * np.pi * 3 * f * seg)))[:len(out[s0:s0 + L])]
    # golpe suave en cada tiempo (a partir del gancho)
    for i in range(int(TOTAL / beat)):
        s0 = int(i * beat * sr); L = int(0.25 * sr)
        seg = np.arange(L) / sr
        k = 0.22 * np.exp(-seg * 18) * np.sin(2 * np.pi * (55 + 60 * np.exp(-seg * 30)) * seg)
        out[s0:s0 + L] += k[:len(out[s0:s0 + L])] * (0.4 if i % 2 else 0.7)
    # "whoosh" en cada cambio de escena
    rng = np.random.default_rng(0)
    acc = 0.0
    for _, _, dur in SCENES[:-1]:
        acc += dur
        L = int(0.5 * sr); s0 = int((acc - 0.3) * sr)
        noise = rng.standard_normal(L).astype(np.float32)
        noise = np.convolve(noise, np.ones(30) / 30, mode="same")
        env = np.sin(np.linspace(0, np.pi, L)) ** 2
        out[s0:s0 + L] += 0.5 * noise * env
    # final: desvanecer
    fade = int(1.5 * sr)
    end = int(TOTAL * sr)
    out[end - fade:end] *= np.linspace(1, 0, fade)
    out[end:] = 0
    out /= np.max(np.abs(out)) + 1e-6
    out *= 0.8
    if voice is not None:
        # La música baja mientras se habla ("ducking") y la voz va al frente.
        v = np.zeros_like(out); v[:min(len(voice), len(out))] = voice[:len(out)]
        env = np.convolve(np.abs(v), np.ones(int(0.25 * sr)) / (0.25 * sr), mode="same")
        duck = 1 - 0.7 * np.clip(env / 0.03, 0, 1)
        vpeak = np.max(np.abs(v)) + 1e-6
        out = 0.32 * out * duck + 0.9 * v / vpeak
        out /= max(1.0, np.max(np.abs(out)) / 0.95)
    stereo = np.stack([out, np.roll(out, 220)], axis=1)
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((stereo * 32767).astype(np.int16).tobytes())

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", nargs="?", default="render", choices=["render", "frames"])
    ap.add_argument("--sin-voz", action="store_true", help="sin narración")
    ap.add_argument("--voz", default=None, help="voz de Piper (por defecto es_MX-claude-high)")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if args.modo == "frames":
        os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
        picks = [(0, 1.6), (1, 3.5), (2, 4.0), (3, 3.5), (4, 2.5), (5, 2.0), (5, 6.5), (6, 2.5)]
        for idx, t in picks:
            gt = sum(d for _, _, d in SCENES[:idx]) + t
            frame(idx, t, gt).save(os.path.join(OUT, "preview", f"{SCENES[idx][0]}_{t}.jpg"), quality=88)
        print("Fotogramas en", os.path.join(OUT, "preview"))
        return

    voice = None
    if not args.sin_voz:
        from app.services import voice as V
        if not V.piper_available():
            raise SystemExit("Piper no está instalado. Ejecuta: pip install piper-tts\n"
                             "(o usa --sin-voz para hacer el video solo con texto y música)")
        work = os.path.join(OUT, "voz")
        os.makedirs(work, exist_ok=True)
        wavs = prepare_voice(args.voz or V.DEFAULT_VOICE, work)
        voice = voice_track(wavs)

    os.makedirs(os.path.join(OUT, "scenes"), exist_ok=True)
    prev, acc = None, 0.0
    for idx, (name, _, dur) in enumerate(SCENES):
        prev = render_scene(idx, prev, acc)
        acc += dur
        print("escena", name, "ok", flush=True)
    with open(os.path.join(OUT, "scenes", "list.txt"), "w") as f:
        for name, _, _ in SCENES:
            f.write(f"file '{name}.mp4'\n")
    music(os.path.join(OUT, "audio.wav"), voice)
    silent = os.path.join(OUT, "silent.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i",
                    os.path.join(OUT, "scenes", "list.txt"), "-c", "copy", silent], check=True)
    final = os.path.join(OUT, "cielo_azul_short.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", silent, "-i", os.path.join(OUT, "audio.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart",
                    final + ".tmp.mp4"], check=True)
    os.replace(final + ".tmp.mp4", final)
    print(f"Listo: {final} ({TOTAL:.1f} s)")


if __name__ == "__main__":
    main()
