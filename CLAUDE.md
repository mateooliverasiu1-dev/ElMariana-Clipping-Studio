# CLAUDE.md — guía para trabajar en ElMariana Clipping Studio

## Qué es
App web (FastAPI + FFmpeg + Faster-Whisper) que convierte videos **autorizados** en Shorts 9:16. Ver README.md.

## Reglas del proyecto
- Entorno objetivo: GitHub Codespaces, 8 GB de RAM, **solo CPU**. No añadir modelos pesados ni dependencias de GPU.
- Whisper: solo `tiny`, `base` o `small` en `int8`. Un único worker de jobs (`app/jobs.py`).
- **No usar servicios ni APIs de pago** sin aprobación explícita del dueño.
- **Nunca** procesar ni descargar videos de terceros sin derechos documentados (`app/services/rights.py`).
- La descarga final exige derechos `APPROVED` y QC `PASS`. No relajar esa regla.
- No inventar diálogo: títulos, subtítulos y candidatos usan solo texto transcrito.
- No documentar como hecho lo que no está implementado (ver "Limitaciones" en README).

## Skills → módulos
| Skill (.claude/skills) | Módulo |
|---|---|
| stream-highlight-finder | `app/services/highlights.py` |
| streamer-storytelling | `highlights.py` (gancho/remate), `render.py` (cortes de pausas) |
| shorts-video-editor | `render.py`, `subtitles.py`, `framing.py` |
| youtube-seo | `seo.py` |
| copyright-guard | `rights.py` |
| youtube-quality-control | `quality.py` |

## Comandos
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pytest -q
python scripts/smoke_test.py --fake-whisper
```

## Convenciones
- Los servicios en `app/services/` no importan FastAPI: se prueban por separado.
- Datos pesados (transcripción, señales) en archivos aparte; `project.json` se mantiene pequeño.
- Mensajes para el usuario en español.
