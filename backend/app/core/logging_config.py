"""Logging estructurado: JSON a stdout vía la librería estándar `logging`.

No se usa `structlog` ni `python-json-logger` como dependencia nueva — con un único
formatter propio alcanza para lo que se necesita hoy (que Docker capture stdout línea
por línea, ya parseable como JSON por cualquier agregador futuro sin tocar código de
aplicación). Ver docs/specs/fase_07_spec.md §3.4 y ROADMAP "Logging estructurado".
"""

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime

# Contexto por-request, seteado por el middleware de request_id en app/main.py.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Atributos estándar de LogRecord — cualquier otra clave presente en __dict__ se
# considera "extra" pasado explícitamente por el caller (ej. logger.info(..., extra={...}))
# y se incluye tal cual en el JSON de salida.
_STANDARD_LOG_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "taskName",
    "request_id",
}


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Reemplaza los handlers del logger raíz por uno que emite JSON a stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
