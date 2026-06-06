"""Centralized logging configuration.

Logs go to BOTH the terminal (journald picks this up) and a rotating file,
so no error is ever lost even if the Telegram error channel is unreachable.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from app.config import config

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_configured = False


def setup_logging() -> None:
    """Configure root logging once at startup (idempotent)."""
    global _configured
    if _configured:
        return

    level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(_FORMAT)

    # Terminal / journald
    stream = logging.StreamHandler(stream=sys.stdout)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    # Rotating file (best-effort — never crash startup if the dir is read-only)
    try:
        os.makedirs(config.LOG_DIR, exist_ok=True)
        path = os.path.join(config.LOG_DIR, config.LOG_FILE)
        file_handler = RotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except Exception as exc:  # pragma: no cover - filesystem edge case
        root.warning("File logging disabled: %s", exc)

    # Quiet down noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    _configured = True
