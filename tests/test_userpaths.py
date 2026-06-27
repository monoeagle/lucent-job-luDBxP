"""AP-31 — per-user paths, dynamic port, legacy migration."""
import os
import socket

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


def test_pick_port_returns_preferred_when_free():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]
    assert userpaths.pick_port(free) == free


def test_pick_port_falls_back_when_occupied():
    occ = socket.socket()
    occ.bind(("127.0.0.1", 0))
    occ.listen()
    taken = occ.getsockname()[1]
    try:
        got = userpaths.pick_port(taken)
        assert got > 0 and got != taken
    finally:
        occ.close()


def test_pick_port_zero_is_free():
    assert userpaths.pick_port(0) > 0


def test_resolve_port_fixed():
    assert userpaths.resolve_port("8123", 5057) == 8123


def test_resolve_port_none_uses_preferred_when_free():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]
    assert userpaths.resolve_port(None, free) == free


def test_resolve_port_zero_is_dynamic():
    assert userpaths.resolve_port("0", 5057) > 0


def test_migrate_copies_when_target_missing(tmp_path):
    legacy = tmp_path / "old" / "config.json"
    legacy.parent.mkdir()
    legacy.write_text('{"x":1}', encoding="utf-8")
    user = tmp_path / "new" / "config.json"
    assert userpaths.migrate_legacy_config(str(user), str(legacy)) is True
    assert user.read_text(encoding="utf-8") == '{"x":1}'


def test_migrate_noop_when_target_exists(tmp_path):
    legacy = tmp_path / "old.json"
    legacy.write_text("OLD", encoding="utf-8")
    user = tmp_path / "new.json"
    user.write_text("KEEP", encoding="utf-8")
    assert userpaths.migrate_legacy_config(str(user), str(legacy)) is False
    assert user.read_text(encoding="utf-8") == "KEEP"


def test_migrate_noop_when_legacy_missing(tmp_path):
    user = tmp_path / "new.json"
    assert userpaths.migrate_legacy_config(str(user), str(tmp_path / "nope.json")) is False
    assert not user.exists()


def test_settings_default_path_is_per_user(tmp_path, monkeypatch):
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
    from core.settings import Settings
    s = Settings.load()
    s.set("default_connection", "sqlite:///x.db")
    s.save()
    assert (tmp_path / "config.json").exists()
    assert Settings.load().get("default_connection") == "sqlite:///x.db"


def test_log_default_dir_uses_userpaths_not_config(tmp_path, monkeypatch):
    # kein log_dir-Arg, kein LUCENT_LOG_DIR → muss über userpaths auflösen,
    # NICHT über ein (entferntes) config.LOG_DIR.
    monkeypatch.delenv("LUCENT_LOG_DIR", raising=False)
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "st"))
    from core import log as log_mod
    d = log_mod._resolve_dir(None)
    assert d == str(tmp_path / "st" / "luDBxP" / "logs")
