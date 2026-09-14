"""
Cartographer — Centralized Logging Setup

Emits timestamped structured logs to stdout. To persist logs to a file, pipe the process output:
    python cartographer_gradio.py 2>&1 | tee logs/app.log

Log level is configurable via the CARTOGRAPHER_LOG_LEVEL environment variable (default: INFO).
"""
from __future__ import annotations

import logging
import os
import sys

_INITIALIZED = False


def setup_logger(name: str = "cartographer") -> logging.Logger:
    """
    Returns a configured logger that writes to stdout with timestamps.

    Level is controlled by the CARTOGRAPHER_LOG_LEVEL env var (default: INFO).
    To write to a file, pipe the process: python app.py 2>&1 | tee logs/app.log
    """
    global _INITIALIZED

    logger = logging.getLogger(name)
    log_level_str = os.getenv("CARTOGRAPHER_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    if not _INITIALIZED:
        logger.handlers.clear()

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        logger.propagate = False
        _INITIALIZED = True
        logger.info(f"Logging initialized (level={log_level_str}). Pipe to tee to save: python app.py 2>&1 | tee app.log")

    return logger


# Default application logger instance
logger = setup_logger("cartographer")
