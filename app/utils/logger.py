"""Shared logger configuration."""

import logging
import os
from app.config import settings


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # avoid duplicate handlers on reload

    logger.setLevel(settings.LOG_LEVEL)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        os.makedirs(settings.LOG_DIR, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(settings.LOG_DIR, "app.log"))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass  # file logging optional, e.g. read-only environments

    return logger
