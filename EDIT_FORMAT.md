# Formato del plan de edición (`edit.json`)

Todos los tiempos (`t`, `cuts`, etc.) están en **segundos del video original**, los mismos
que aparecen en `work/<nombre>/transcript.txt`. El render los traslada al timeline final
aunque haya cortes o segmentos reordenados. Un evento que cae en una parte cortada se ignora.

```jsonc
{
  "source": "input/clip.mp4",
  "transcript": "work/clip/transcript.json",
  "output": "output/clip_short.mp4",
  "fps": 30,                       // opcional (30 por defecto)
  "size": [1080, 1920],            // opcional

  // ---- encuadre vertical
  "layout": {"mode": "crop", "x": "auto"},   // recorte 9:16 que sigue la cara (o x: 0.0-1.0 fijo)
  // {"mode": "blur", "y": 0.5, "fg_scale": 1.0, "bg_dim": 0.55}  video completo + fondo desenfocado
  // {"mode": "fit"}                                               video completo + barras negras
  // {"mode": "split", "top": [x,y,w,h], "bottom": [x,y,w,h], "ratio": 0.4, "line_color": "#FFE600"}
  //     pantalla dividida (facecam arriba / juego abajo); rects normalizados 0-1 del original

  // ---- cortes: segmentos que se conservan, EN EL ORDEN en que aparecerán
  //      (se puede poner un momento posterior primero como gancho)
  "cuts": [[42.0, 44.5], [10.2, 55.0]],
  "remove_silences": {"min_gap": 0.45, "pad": 0.12},   // jump-cuts automáticos en pausas

  // ---- subtítulos palabra por palabra
  "subtitles": {
    "style": "pop_amarillo",       // pop_amarillo | neon_verde | rojo_impacto | comic | minimal
    "y": 0.70,                     // posición vertical (0 arriba, 1 abajo)
    "max_words": 3, "max_chars": 14,
    "font": "Montserrat Black", "size": 110, "color": "#FFFFFF", "highlight": "#FFE600",  // overrides
    "uppercase": true, "pop": true,
    "replace": {"maca": "marca"},                    // corrige palabras mal transcritas (todas)
    "fixes": [{"t": 13.38, "w": "marca"}],          // corrige una palabra concreta por tiempo
    "emphasis": [{"word": "millón", "color": "#3CFF5A", "scale": 1.25, "t": 15.6}],  // t opcional
    "hide": [[30.0, 34.0]]                           // tramos sin subtítulos
  },                               // "subtitles": false  -> sin subtítulos

  // ---- textos en pantalla (gancho, títulos, notas). "|" = salto de línea
  "texts": [{"t": 0.0, "dur": 2.5, "text": "NO ESPERABA ESTO|😳", "y": 0.16, "size": 86,
             "color": "#FFFFFF", "box": "#E0115F", "angle": -3}],

  // ---- zooms
  "zooms": [{"t": 12.3, "dur": 1.0, "scale": 1.3, "style": "punch", "x": "face", "y": "face"}],
  // style: punch (golpe seco) | smooth (entra/sale suave) | slow (empuje lento de tensión) | hold
  // x/y: "face" o 0.0-1.0 en el cuadro de salida

  // ---- efectos de sonido (ver `python -m studio.sfx --list`, o mete tus .wav en assets/sfx/)
  "sfx": [{"t": 12.3, "name": "boom", "gain": 0.7, "offset": -0.05}],   // o "db": -6

  // ---- efectos visuales
  "effects": [{"t": 12.3, "dur": 0.35, "type": "shake", "intensity": 1.0}],
  // type: shake | flash (rgb opcional) | bw | vignette | red_tint

  // ---- música de fondo (archivo tuyo con derechos), baja sola cuando hablan
  "music": {"file": "assets/music/tema.mp3", "db": -20, "duck": true, "duck_db": -8},

  "audio": {"loudness": -14, "voice_db": 0},
  "progress_bar": {"color": "#FFE600", "height": 10}
}
```

## Efectos de sonido incluidos (generados por código, sin copyright)

| Uso | Nombres |
|---|---|
| Transiciones | `whoosh`, `whoosh_down`, `swoosh_fast`, `glitch`, `tape_stop` |
| Impacto / tensión | `boom`, `impact`, `bass_drop`, `suspense_hit`, `riser`, `drumroll`, `heartbeat`, `tick_tock` |
| Pop / interfaz | `pop`, `bubble_pop`, `click`, `ding`, `notification`, `camera_shutter`, `typing`, `coin`, `magic_sparkle` |
| Humor | `boing`, `record_scratch`, `rimshot`, `sad_trombone`, `airhorn`, `crickets`, `correct`, `wrong_buzzer`, `slide_whistle_up`, `slide_whistle_down` |
