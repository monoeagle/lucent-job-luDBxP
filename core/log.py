"""Unified logging to stdout + a rotating file under the resolved log dir.

Configuration is resolved from explicit arguments first, then environment, then
config.py defaults:
  * directory : log_dir arg → LUCENT_LOG_DIR → config.LOG_DIR
  * level     : level arg   → LUCENT_LOG_LEVEL → (LUCENT_DEBUG ⇒ DEBUG) → config.LOG_LEVEL

LUCENT_LOG_DIR is the hook for a per-user log path (e.g. on a terminal server);
the full multi-user wiring lives in AP-31.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

import config

_TRUTHY = ("1", "true", "yes", "on")


def _resolve_dir(log_dir):
    if log_dir is None:
        log_dir = os.environ.get("LUCENT_LOG_DIR") or config.LOG_DIR
    return log_dir


def _resolve_level(level):
    if level is None:
        env = os.environ.get("LUCENT_LOG_LEVEL")
        if env:
            level = env
        elif os.environ.get("LUCENT_DEBUG", "").strip().lower() in _TRUTHY:
            level = "DEBUG"
        else:
            level = config.LOG_LEVEL
    if isinstance(level, str):
        resolved = logging.getLevelName(level.strip().upper())
        return resolved if isinstance(resolved, int) else logging.INFO
    return level


def init_logging(log_dir: str = None, level=None) -> logging.Logger:
    """Initialize unified logging to stdout and a rotating file.

    Re-applies cleanly on every call (existing handlers are replaced), so it is
    both reconfigurable and safe against duplicate handlers.
    """
    log_dir = _resolve_dir(log_dir)
    level = _resolve_level(level)
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("luDBxP")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    logger.info(
        "%s v%s — Logging aktiv (Level %s, Verzeichnis %s)",
        config.APP_NAME, config.APP_VERSION, logging.getLevelName(level), log_dir,
    )
    return logger
