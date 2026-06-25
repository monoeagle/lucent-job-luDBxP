"""Unified logging to stdout + an append-only file under LOG_DIR."""
import logging
import os

import config


def init_logging(log_dir: str = config.LOG_DIR) -> logging.Logger:
    """Initialize unified logging to stdout and file.

    Args:
        log_dir: Directory for log files (defaults to config.LOG_DIR).

    Returns:
        The configured Logger instance.
    """
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("luDBxP")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)
    file_handler = logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    return logger
