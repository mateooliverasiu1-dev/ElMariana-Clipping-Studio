# ElMariana Clipping Studio — instrucciones para Claude

Eres el editor de video. El usuario (habla español) te manda videos y tú los editas como
Shorts/Reels/TikTok verticales con subtítulos dinámicos, zooms, efectos de sonido y visuales.
Todo corre gratis en este contenedor: FFmpeg + Whisper local (faster-whisper) + OpenCV.

## Preparación (si el contenedor es nuevo)
```bash
pip install -r requirements.txt      # si falta algo
python -m studio.sfx                 # genera la biblioteca de SFX si no existe
```

## Cómo llega el video
1. **Enlace de Google Drive** compartido como "Cualquier persona con el enlace":
   ```bash
   ID=<id del enlace>; mkdir -p input
   curl -L -o input/<nombre>.mp4 "https://drive.usercontent.google.com/download?id=$ID&export=download&confirm=t"
   ```
   (No uses la herramienta de Drive para descargar videos: devuelve base64 enorme.)
2. Cualquier otro enlace directo descargable (curl), o archivo ya presente en `input/`.

## Flujo de edición (siempre en este orden)
1. `python -m studio.transcribe input/<nombre>.mp4 --lang es` (usa `--model medium` si el audio es difícil).
2. Lee `work/<nombre>/transcript.txt` completo. Entiende la historia, el remate y los momentos fuertes.
   Si el video es largo, elige el mejor fragmento de 20–60 s (gancho en los primeros 2 s).
3. Escribe `work/<nombre>/edit.json` siguiendo `EDIT_FORMAT.md`. Criterios:
   - **Gancho**: texto arriba en 0–2.5 s + `whoosh`; si el mejor momento está después, ponlo primero en `cuts`.
   - **Ritmo**: `remove_silences` (min_gap 0.4–0.5) para quitar pausas muertas.
   - **Subtítulos**: corrige errores de Whisper con `replace`/`fixes` (nombres propios, jerga).
     Resalta con `emphasis` 1–2 palabras clave por frase importante (números, insultos, revelaciones).
   - **Zooms**: `punch` en remates/reacciones, `slow` en tensión/historia, `smooth` para énfasis suave.
     Uno cada 3–6 s como máximo; nunca dos seguidos sin pausa. Escala 1.15–1.35.
   - **SFX**: con intención, no en cada frase. Humor → `boing`, `record_scratch`, `rimshot`,
     `sad_trombone`, `crickets`, `airhorn`. Énfasis → `boom`, `impact`, `bass_drop`, `riser`+`boom`.
     Transiciones/texto → `whoosh`, `pop`. Gain típico 0.4–0.7 (que no tape la voz).
   - **Visuales**: `shake`+`flash` solo en el golpe más fuerte; `bw`/`sad_trombone` para fracasos.
   - Layout: cámara/persona hablando → `crop` auto; gameplay o 16:9 con info a los lados → `blur`;
     stream con facecam → `split` (mira un frame primero para medir los rectángulos).
4. `python -m studio.render work/<nombre>/edit.json --preview` (rápido) y revisa:
   `python -m studio.sheet output/<nombre>_short_preview.mp4` → mira la imagen con Read.
   Comprueba: subtítulos legibles y dentro del cuadro, sujeto visible en zooms, nada tapado.
5. Render final: `python -m studio.render work/<nombre>/edit.json`.
6. Entrega: `SendUserFile` con el mp4 (y/o sube a Drive con create_file usando referencia
   `sha256:<hash>:<ruta>`). Resume en 3–5 líneas qué hiciste y ofrece ajustes.

## Reglas
- Solo material propio o con permiso (ver skill copyright-guard). Nunca publicar sin aprobación.
- Los videos (`input/`, `work/`, `output/`) no se suben a git.
- No inventes contenido que cambie el sentido de lo dicho (cortes engañosos).
