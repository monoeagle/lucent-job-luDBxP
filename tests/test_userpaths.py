"""AP-31 — per-user paths, dynamic port, legacy migration."""
import os

from core import userpaths


def test_config_file_honors_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
    p = userpaths.user_config_file("luDBxP")
    assert p == str(tmp_path / "config.json")
    assert tmp_path.is_dir()


def test_config_dir_default_xdg(tmp_path, monkeypatch):
    monkeypatch.delenv("LUCENT_CONFIG_DIR", raising=False)
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    d = userpaths.user_config_dir("luDBxP")
    assert d == str(tmp_path / "cfg" / "luDBxP")
    assert os.path.isdir(d)


def test_log_dir_honors_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("LUCENT_LOG_DIR", str(tmp_path / "L"))
    d = userpaths.user_log_dir("luDBxP")
    assert d == str(tmp_path / "L")
    assert os.path.isdir(d)


def test_log_dir_default_xdg_state(tmp_path, monkeypatch):
    monkeypatch.delenv("LUCENT_LOG_DIR", raising=False)
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    d = userpaths.user_log_dir("luDBxP")
    assert d == str(tmp_path / "state" / "luDBxP" / "logs")
    assert os.path.isdir(d)
