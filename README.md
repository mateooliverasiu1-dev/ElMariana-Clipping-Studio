# ElMariana Clipping Studio

Estudio de producción asistido por IA para YouTube Shorts. Convierte **videos con derechos de uso documentados** en candidatos a Shorts verticales con subtítulos dinámicos, listos para revisar y publicar.

> **Importante:** solo se procesa material con derechos de uso documentados. No hay publicación automática: cada Short se descarga y lo publica una persona después de revisarlo.

## Qué hace

1. **Subida** de videos MP4, MOV y MKV con la declaración de derechos obligatoria. El video se sube en trozos de hasta 4 MB, porque el túnel de puertos de Codespaces rechaza peticiones grandes con HTTP 413. Si la conexión se corta, la subida se reanuda desde donde se quedó. Para videos muy grandes puedes copiarlos a `data/entrada/` en el servidor e importarlos desde el diálogo, sin subirlos por el navegador.
2. **Análisis con FFmpeg**: duración, resolución, fps, códecs y pistas de audio.
3. **Transcripción** local con **Faster-Whisper** (español e inglés, marcas de tiempo por palabra, CPU int8).
4. **Detección de momentos** combinando transcripción (reacciones, preguntas, exclamaciones), contexto (frases completas), energía del audio (risas o gritos) y cambios de escena.
5. **Clips candidatos** con puntuación de 0 a 100, razones explicadas, título sugerido, inicio y final.
6. **Vista previa** del fragmento original y del Short editado.
7. **Edición automática 9:16** (1080x1920): recorte centrado en la cara (OpenCV) o el video completo sobre fondo desenfocado.
8. **Subtítulos dinámicos** palabra por palabra: la palabra actual en amarillo y las importantes en verde, dentro de márgenes seguros.
9. **Cortes y zooms**: se recortan las pausas largas y se añaden zooms suaves en las reacciones (máximo uno cada 4 s).
10. **Exportación MP4**: H.264 High, CRF 20, 30 fps, AAC 192k estéreo y audio normalizado a -14 LUFS en dos pasadas.
11. **Títulos, descripción y hashtags** generados con reglas locales a partir de frases reales del clip (sin APIs de pago).
12. **Portadas 1080×1920** para cada clip, en JPG de menos de 2 MB. Se elige el fotograma más nítido de una reacción o de un pico de audio (con cara si la hay) y se pone encima la frase del clip con una palabra resaltada. El texto y el fotograma se pueden cambiar.
13. **Control de calidad y derechos** antes de habilitar la descarga: la descarga solo se activa con QC **PASS** y derechos **APPROVED**.

## Ejecutar en GitHub Codespaces

1. En GitHub: **Code → Codespaces → Create codespace** (elige una máquina de 8 GB).
   El `devcontainer` instala FFmpeg, las fuentes y las dependencias de Python de forma automática.
2. En la terminal:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. Abre el puerto **8000** desde la pestaña *Ports* (se abre solo).

La primera transcripción descarga el modelo de Whisper elegido desde Hugging Face. Es gratis: *tiny* pesa unos 75 MB, *base* unos 145 MB y *small* unos 480 MB.

### Instalación manual (sin devcontainer)

```bash
sudo apt-get install -y ffmpeg fonts-dejavu-core
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Pruebas

```bash
pytest -q                                    # servicios, render real, QC y API
python scripts/smoke_test.py --fake-whisper  # prueba de extremo a extremo por HTTP (33 comprobaciones)
python scripts/smoke_test.py                 # igual, pero con Faster-Whisper real
RUN_WHISPER_TEST=1 pytest tests/test_transcribe.py   # descarga el modelo tiny y transcribe voz sintética
```

## Videos grandes en Codespaces

El túnel de puertos de Codespaces no es ideal para archivos de varios GB. Además, si el Codespace se suspende por inactividad, la subida se corta (el túnel responde 404).

- **Opción A:** en el Explorador de VS Code, arrastra el video a la carpeta `data/entrada/`. Luego, en la app: **Nuevo proyecto → ¿Video muy grande? → elegir el video**.
- **Opción B:** sube por el navegador como siempre. Si se corta, vuelve a tocar **Subir y analizar** y continuará donde se quedó.
- Sube el tiempo de suspensión en GitHub → Settings → Codespaces → *Default idle timeout*.

## Configuración (variables de entorno)

| Variable | Por defecto | Uso |
|---|---|---|
| `ELMARIANA_WHISPER_MODEL` | `base` | Modelo por defecto: `tiny`, `base` o `small` |
| `ELMARIANA_WHISPER_THREADS` | núcleos de CPU | Hilos de Whisper |
| `ELMARIANA_DATA_DIR` | `./data` | Dónde se guardan los proyectos |
| `ELMARIANA_MAX_UPLOAD_MB` | `4096` | Tamaño máximo de subida |
| `ELMARIANA_CLIP_MIN` / `ELMARIANA_CLIP_MAX` | `20` / `60` | Duración de los candidatos (s) |
| `ELMARIANA_CRF` / `ELMARIANA_X264_PRESET` | `20` / `veryfast` | Calidad y velocidad del render |

## Arquitectura

```
app/
  main.py          API FastAPI + servidor de la interfaz
  pipeline.py      orquesta análisis y exportación
  storage.py       proyectos en disco (JSON, sin base de datos)
  jobs.py          cola de un solo worker (protege los 8 GB de RAM)
  config.py
  services/
    media.py       FFprobe/FFmpeg: análisis, audio, proxy de vista previa, miniaturas
    transcribe.py  Faster-Whisper (CPU, int8, word_timestamps, VAD)
    signals.py     energía de audio y cambios de escena
    highlights.py  puntuación de momentos      (skill stream-highlight-finder + streamer-storytelling)
    framing.py     encuadre 9:16 con OpenCV
    subtitles.py   subtítulos ASS palabra por palabra
    render.py      cortes, zooms, subtítulos y exportación (skill shorts-video-editor)
    seo.py         títulos, descripción y hashtags    (skill youtube-seo)
    cover.py       portadas verticales 1080x1920
    rights.py      revisión de derechos               (skill copyright-guard)
    quality.py     control de calidad del MP4 final   (skill youtube-quality-control)
static/            interfaz web (HTML/CSS/JS sin dependencias)
tests/             pytest
scripts/smoke_test.py
```

Flujo de datos de un proyecto: `data/projects/<id>/` contiene `project.json`, `source.*`, `audio.wav`, `transcript.json`, `signals.json`, `preview.mp4` (solo cuando hace falta) y `clips/`.

## Limitaciones conocidas

- **La publicación en YouTube (YouTube Data API) no está implementada.** El flujo termina en la descarga del MP4, el `.srt` y el `.txt` con los metadatos.
- **La detección de momentos usa reglas explicables, no un modelo de lenguaje.** Detecta reacciones, picos de audio y estructura, pero no "entiende" el humor. Revisa siempre los candidatos.
- **Los títulos y descripciones también se generan con plantillas** a partir de frases reales del clip. Edítalos antes de publicar.
- **El encuadre por cara es estático por clip** (mediana de varias muestras). No sigue a la persona si se mueve mucho.
- **La revisión de derechos evalúa lo que declaras**, pero no puede verificar legalmente un permiso.
- **En CPU, Whisper `base` tarda aproximadamente entre 0.3x y 1x la duración del audio**, según los núcleos. Para streams largos, usa `tiny` o recorta el video antes de subirlo.
