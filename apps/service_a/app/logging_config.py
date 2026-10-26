from __future__ import annotations

import logging
import os
import sys

_LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def configure_logging() -> None:
    """Send the app's own logs to stdout alongside uvicorn's access logs."""
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = _LOG_LEVELS.get(level_name, logging.INFO)

    app_logger = logging.getLogger("app")
    if not any(getattr(h, "_entra_app_handler", False) for h in app_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        setattr(handler, "_entra_app_handler", True)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        app_logger.addHandler(handler)

    app_logger.setLevel(level)
    app_logger.propagate = False

    if level_name not in _LOG_LEVELS:
        app_logger.warning("Unknown LOG_LEVEL=%r; using INFO", level_name)
