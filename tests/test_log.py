"""AP-33 — Logging: rotation, configurable level/dir, request logging."""
import logging
from logging.handlers import RotatingFileHandler

import pytest

import config
from core import log as log_mod


@pytest.fixture(autouse=True)
def _reset_logger():
    """Each test starts from a clean luDBxP logger so init_logging re-applies."""
    logger = logging.getLogger("luDBxP")
    for h in list(logger.handlers):
        logger.removeHandler(h)
    logger.setLevel(logging.WARNING)
    yield
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)


def test_uses_rotating_file_handler(tmp_path):
    logger = log_mod.init_logging(log_dir=str(tmp_path))
    rfhs = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rfhs) == 1
    assert rfhs[0].maxBytes == config.LOG_MAX_BYTES
    assert rfhs[0].backupCount == config.LOG_BACKUP_COUNT


def test_level_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LUCENT_LOG_LEVEL", "DEBUG")
    logger = log_mod.init_logging(log_dir=str(tmp_path))
    assert logger.level == logging.DEBUG


def test_lucent_debug_implies_debug_level(tmp_path, monkeypatch):
    monkeypatch.delenv("LUCENT_LOG_LEVEL", raising=False)
    monkeypatch.setenv("LUCENT_DEBUG", "1")
    logger = log_mod.init_logging(log_dir=str(tmp_path))
    assert logger.level == logging.DEBUG


def test_default_level_is_info(tmp_path, monkeypatch):
    monkeypatch.delenv("LUCENT_LOG_LEVEL", raising=False)
    monkeypatch.delenv("LUCENT_DEBUG", raising=False)
    logger = log_mod.init_logging(log_dir=str(tmp_path))
    assert logger.level == logging.INFO


def test_log_dir_from_env(tmp_path, monkeypatch):
    target = tmp_path / "userlogs"
    monkeypatch.setenv("LUCENT_LOG_DIR", str(target))
    logger = log_mod.init_logging()
    logger.info("hello")
    assert (target / "app.log").exists()


def test_idempotent_no_duplicate_handlers(tmp_path):
    log_mod.init_logging(log_dir=str(tmp_path))
    first = len(logging.getLogger("luDBxP").handlers)
    log_mod.init_logging(log_dir=str(tmp_path))
    second = len(logging.getLogger("luDBxP").handlers)
    assert first == second == 2  # one stream + one rotating file handler


def test_request_is_logged(tmp_path, monkeypatch, caplog, inventory_url):
    monkeypatch.setenv("LUCENT_LOG_DIR", str(tmp_path))
    from web import create_app
    client = create_app().test_client()
    with caplog.at_level(logging.INFO, logger="luDBxP"):
        client.post("/api/schema", json={"connection_url": inventory_url})
    line = " ".join(r.getMessage() for r in caplog.records)
    assert "POST" in line and "/api/schema" in line and "200" in line
