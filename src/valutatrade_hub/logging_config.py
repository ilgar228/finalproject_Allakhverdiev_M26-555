"""Настройка логирования: формат, уровень, ротация."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import get_settings

_CONFIGURED = False


class _JsonFormatter(logging.Formatter):
    """Форматтер, сериализующий запись в JSON-строку."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # дополнительные поля, если переданы через extra=
        for key, value in record.__dict__.items():
            if key in payload or key.startswith("_"):
                continue
            if key in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "levelname", "levelno", "lineno",
                "module", "msecs", "message", "msg", "name", "pathname",
                "process", "processName", "relativeCreated", "stack_info",
                "thread", "threadName", "taskName",
            ):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    """Инициализирует корневой логгер приложения (идемпотентно)."""
    global _CONFIGURED
    logger = logging.getLogger("valutatrade")
    if _CONFIGURED:
        return logger

    settings = get_settings()
    level = getattr(logging, settings.log_level, logging.INFO)

    log_path: Path = settings.log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )

    if settings.log_format == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(levelname)s %(asctime)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False

    # параллельно — в stderr на уровне WARNING, чтобы видеть ошибки в консоли
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console)

    _CONFIGURED = True
    return logger


def get_logger(name: str = "valutatrade") -> logging.Logger:
    """Возвращает логгер приложения (при необходимости инициализирует)."""
    setup_logging()
    return logging.getLogger(name)