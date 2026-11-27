# ElMariana Clipping Studio

Editor de Shorts/Reels/TikTok manejado por Claude. Tú mandas el video, Claude lo transcribe,
decide la edición (cortes, subtítulos, zooms, efectos de sonido y visuales) y entrega un MP4
vertical 1080x1920 listo para subir. 100 % gratis: solo FFmpeg, Whisper local y OpenCV.

## Qué hace
- Subtítulos palabra por palabra con resaltado animado y palabras clave en color (5 estilos).
- Zooms estratégicos (golpe, suave, empuje lento) enfocados en la cara.
- 32 efectos de sonido originales generados por código (humor, impacto, transiciones) — sin copyright.
- Efectos visuales: temblor, flash, blanco y negro, viñeta, tinte rojo, barra de progreso.
- Encuadre vertical: recorte que sigue la cara, fondo desenfocado, o pantalla dividida (facecam + juego).
- Jump-cuts automáticos en silencios, reordenar segmentos (gancho al inicio), música con ducking.
- Audio normalizado a -14 LUFS (estándar de YouTube).

## Uso (lo hace Claude)
```bash
python -m studio.transcribe input/video.mp4 --lang es   # -> work/video/transcript.txt
# Claude escribe work/video/edit.json  (ver EDIT_FORMAT.md)
python -m studio.render work/video/edit.json --preview  # revisión rápida
python -m studio.sheet output/video_short_preview.mp4   # hoja de fotogramas para revisar
python -m studio.render work/video/edit.json            # render final
```

Ver `CLAUDE.md` para el flujo completo y `EDIT_FORMAT.md` para todas las opciones.

## Importante
Solo material propio o con permiso de uso. Nada se publica sin aprobación humana.
