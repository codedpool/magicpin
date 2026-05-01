"""
Structured JSON logger.

Usage:
    from core.logging import logger
    logger.info("composed message", extra={"conv_id": "...", "latency_ms": 1234})
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

from core.settings import settings


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for easy parsing."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
                  + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Attach any extra fields passed via logger.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            payload["_serialization_error"] = True
            return json.dumps({"level": "ERROR", "msg": "log serialization failed"})


class PlainFormatter(logging.Formatter):
    """Human-readable single-line format for local dev."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )


def _make_logger() -> logging.Logger:
    log = logging.getLogger("vera")
    log.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    log.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter() if settings.LOG_FORMAT == "json" else PlainFormatter()
    )
    log.addHandler(handler)
    log.propagate = False
    return log


logger = _make_logger()
