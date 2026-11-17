"""Cola de trabajos en segundo plano.

Un solo worker a la vez: con 8 GB de RAM y CPU compartida, transcribir y renderizar
en paralelo saturaría la máquina. Los jobs informan progreso en project.json.
"""
from __future__ import annotations

import logging
import threading
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

log = logging.getLogger("elmariana.jobs")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="elmariana-job")
_active: dict[str, Future] = {}
_lock = threading.Lock()


def submit(key: str, fn: Callable[..., Any], *args: Any, on_error: Callable[[Exception], None] | None = None) -> bool:
    """Encola `fn`. Devuelve False si ya hay un job con la misma clave en curso."""
    with _lock:
        fut = _active.get(key)
        if fut is not None and not fut.done():
            return False

        def _run() -> Any:
            try:
                return fn(*args)
            except Exception as exc:  # se registra y se reporta al proyecto
                log.error("Job %s falló: %s\n%s", key, exc, traceback.format_exc())
                if on_error:
                    try:
                        on_error(exc)
                    except Exception:  # pragma: no cover
                        log.exception("on_error falló")
                return None

        _active[key] = _executor.submit(_run)
        return True


def is_running(key: str) -> bool:
    with _lock:
        fut = _active.get(key)
        return fut is not None and not fut.done()


def wait(key: str, timeout: float | None = None) -> None:
    """Usado en pruebas."""
    with _lock:
        fut = _active.get(key)
    if fut is not None:
        fut.result(timeout=timeout)
