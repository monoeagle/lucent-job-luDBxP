# AP-31 Kern-Scheibe (Pro-Nutzer-Pfade + dynamischer Port) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mehrere Nutzer können die App kollisionsfrei auf einer Maschine betreiben — dynamische Port-Wahl pro Session und Pro-Nutzer-`config.json`/Logs statt App-Verzeichnis.

**Architecture:** Ein neues, pures Stdlib-Modul `core/userpaths.py` löst Pro-Nutzer-Pfade (OS-Standard), einen freien Port und die einmalige Migration auf. Konsumenten (`core/settings.py`, `core/log.py`, `app.py`) rufen es; `config.py` bleibt reine Konstanten. Layering bleibt `web → core → config`.

**Tech Stack:** Python 3.10+ (venv 3.14), Flask (nur in `app.py`/`web/`), pytest. `core/userpaths.py` nutzt ausschließlich Stdlib (`os`, `socket`, `shutil`).

## Global Constraints

- **Python ≥ 3.10**; Tests laufen mit `./venv/bin/python -m pytest` (venv = Python 3.14 via uv).
- **`core/` darf niemals Flask importieren.** `core/userpaths.py` nutzt nur Stdlib (`os`, `socket`, `shutil`) und importiert **nicht** `config` (kein Zyklus — App-Slug kommt als Parameter).
- **Keine neue Third-Party-Dependency** (waitress/WSGI ist bewusst OUT).
- **Bind ausschließlich an `127.0.0.1`** (kein `0.0.0.0`).
- **Pro-Nutzer-Verzeichnisname = Slug `luDBxP`** auf allen OSen.
- **Version je AP** via `./venv/bin/python sync_version.py --minor` (hier 0.32.1 → 0.33.0); jede AP **ohne KI-Signatur** committen; Release berührt mehr als `sync_version.py` (CHANGELOG + Mirror, Roadmap/todo, CLAUDE.md, Site-Build, gh-pages-Deploy).
- Diese Scheibe lässt **bewusst aus** (Spec §8): waitress, Idle-Shutdown/Stop, Session-Token, shared venv / signierte run.ps1 / Betriebs-Doku. Der Windows-`%LOCALAPPDATA%`-Zweig wird implementiert, aber hier nur per Logik (nicht live) getestet.

---

### Task 1: `core/userpaths.py` — Pro-Nutzer-Pfade (config + logs)

**Files:**
- Create: `core/userpaths.py`
- Test: `tests/test_userpaths.py`

**Interfaces:**
- Produces: `user_config_dir(app_slug: str) -> str`, `user_config_file(app_slug: str, filename: str = "config.json") -> str`, `user_log_dir(app_slug: str) -> str`. Alle legen das Verzeichnis an. Overrides: `LUCENT_CONFIG_DIR`, `LUCENT_LOG_DIR`.

- [ ] **Step 1: Failing tests schreiben**

`tests/test_userpaths.py`:
```python
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
```

- [ ] **Step 2: Test läuft → schlägt fehl**

Run: `./venv/bin/python -m pytest tests/test_userpaths.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.userpaths'`

- [ ] **Step 3: Modul implementieren**

`core/userpaths.py`:
```python
"""Per-user data locations and dynamic port selection (AP-31 core slice).

Pure stdlib module — no Flask, no `config` import (the app slug is passed in),
so it stays free of the web layer and import cycles. Resolves OS-standard
per-user paths for config + logs, picks a free TCP port, and migrates a legacy
app-directory config.json once.
"""
import os
import shutil
import socket


def _app_base(app_slug, *, kind):
    """OS base directory for this app's per-user data.

    kind is "config" or "state" (state = logs). On Windows both map to
    %LOCALAPPDATA%\\<slug>; on POSIX they follow the XDG base-dir spec.
    """
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(root, app_slug)
    if kind == "config":
        root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config")
    else:
        root = os.environ.get("XDG_STATE_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "state")
    return os.path.join(root, app_slug)


def user_config_dir(app_slug):
    """Per-user config directory (created). LUCENT_CONFIG_DIR overrides."""
    d = os.environ.get("LUCENT_CONFIG_DIR") or _app_base(app_slug, kind="config")
    os.makedirs(d, exist_ok=True)
    return d


def user_config_file(app_slug, filename="config.json"):
    """Full path to the per-user config file (directory created)."""
    return os.path.join(user_config_dir(app_slug), filename)


def user_log_dir(app_slug):
    """Per-user log directory (created). LUCENT_LOG_DIR overrides."""
    d = os.environ.get("LUCENT_LOG_DIR")
    if not d:
        base = _app_base(app_slug, kind="state")
        d = os.path.join(base, "Logs" if os.name == "nt" else "logs")
    os.makedirs(d, exist_ok=True)
    return d
```

- [ ] **Step 4: Test läuft → grün**

Run: `./venv/bin/python -m pytest tests/test_userpaths.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add core/userpaths.py tests/test_userpaths.py
git commit -m "feat: AP-31 core/userpaths — per-user config/log dirs (XDG/LOCALAPPDATA)"
```

---

### Task 2: `core/userpaths.py` — Port-Wahl (`pick_port` + `resolve_port`)

**Files:**
- Modify: `core/userpaths.py` (Funktionen anhängen)
- Test: `tests/test_userpaths.py` (Tests anhängen)

**Interfaces:**
- Produces: `pick_port(preferred: int, host: str = "127.0.0.1") -> int` (preferred wenn bindbar, sonst freier Port; `preferred == 0` → immer frei). `resolve_port(forced, preferred: int, host: str = "127.0.0.1") -> int` (forced = `LUCENT_PORT`-Wert: `None`/"" → `pick_port(preferred)`; "0" → freier Port; "<n>" → fester int n).

- [ ] **Step 1: Failing tests anhängen**

Ans Ende von `tests/test_userpaths.py`:
```python
import socket  # noqa: E402  (am Dateianfang zu den Imports ziehen ist auch ok)


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
```

- [ ] **Step 2: Test läuft → schlägt fehl**

Run: `./venv/bin/python -m pytest tests/test_userpaths.py -q`
Expected: FAIL — `AttributeError: module 'core.userpaths' has no attribute 'pick_port'`

- [ ] **Step 3: Implementieren (an `core/userpaths.py` anhängen)**

```python
def _port_free(port, host):
    """True if `port` can be exclusively bound on `host`."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def pick_port(preferred, host="127.0.0.1"):
    """Return `preferred` if bindable on `host`, else a free OS-assigned port.
    `preferred == 0` always yields a free port. (A tiny TOCTOU window remains
    until the server actually binds — accepted for this tool.)"""
    if preferred and _port_free(preferred, host):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def resolve_port(forced, preferred, host="127.0.0.1"):
    """Resolve the listen port from a LUCENT_PORT value `forced`:
    None/"" → pick_port(preferred); "0" → free port; "<n>" → fixed int n."""
    if forced is None or str(forced).strip() == "":
        return pick_port(preferred, host)
    forced = str(forced).strip()
    if forced == "0":
        return pick_port(0, host)
    return int(forced)
```

- [ ] **Step 4: Test läuft → grün**

Run: `./venv/bin/python -m pytest tests/test_userpaths.py -q`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add core/userpaths.py tests/test_userpaths.py
git commit -m "feat: AP-31 userpaths.pick_port/resolve_port — dynamic port selection"
```

---

### Task 3: `core/userpaths.py` — Migration (`migrate_legacy_config`)

**Files:**
- Modify: `core/userpaths.py` (Funktion anhängen)
- Test: `tests/test_userpaths.py` (Tests anhängen)

**Interfaces:**
- Produces: `migrate_legacy_config(user_file: str, legacy_file: str) -> bool` (kopiert legacy→user nur wenn user fehlt und legacy existiert; True wenn kopiert).

- [ ] **Step 1: Failing tests anhängen**

Ans Ende von `tests/test_userpaths.py`:
```python
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
```

- [ ] **Step 2: Test läuft → schlägt fehl**

Run: `./venv/bin/python -m pytest tests/test_userpaths.py -q`
Expected: FAIL — `AttributeError: module 'core.userpaths' has no attribute 'migrate_legacy_config'`

- [ ] **Step 3: Implementieren (an `core/userpaths.py` anhängen)**

```python
def migrate_legacy_config(user_file, legacy_file):
    """One-time copy legacy_file → user_file, only when user_file is absent and
    legacy_file exists. Returns True if a copy happened (never overwrites)."""
    if os.path.exists(user_file) or not os.path.exists(legacy_file):
        return False
    os.makedirs(os.path.dirname(user_file), exist_ok=True)
    shutil.copy2(legacy_file, user_file)
    return True
```

- [ ] **Step 4: Test läuft → grün**

Run: `./venv/bin/python -m pytest tests/test_userpaths.py -q`
Expected: PASS (13 passed)

- [ ] **Step 5: Commit**

```bash
git add core/userpaths.py tests/test_userpaths.py
git commit -m "feat: AP-31 userpaths.migrate_legacy_config — one-time config.json takeover"
```

---

### Task 4: `config.py` + `core/settings.py` auf Pro-Nutzer-config.json umstellen

**Files:**
- Modify: `config.py:11-12`
- Modify: `core/settings.py:1-6,21-37`
- Modify: `tests/test_api.py:41-43,55-58,73-78`

**Interfaces:**
- Consumes: `core.userpaths.user_config_file` (Task 1), `config.APP_SLUG`, neu `config.LEGACY_CONFIG_JSON`.

- [ ] **Step 1: Failing test schreiben (Settings nutzt Pro-Nutzer-Pfad)**

Ans Ende von `tests/test_userpaths.py`:
```python
def test_settings_default_path_is_per_user(tmp_path, monkeypatch):
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
    from core.settings import Settings
    s = Settings.load()
    s.set("default_connection", "sqlite:///x.db")
    s.save()
    assert (tmp_path / "config.json").exists()
    assert Settings.load().get("default_connection") == "sqlite:///x.db"
```

- [ ] **Step 2: Test läuft → schlägt fehl**

Run: `./venv/bin/python -m pytest tests/test_userpaths.py::test_settings_default_path_is_per_user -q`
Expected: FAIL — Datei landet im alten `config.CONFIG_JSON`-Pfad, nicht in `tmp_path` (AssertionError: not exists).

- [ ] **Step 3: `config.py` umstellen**

Ersetze in `config.py` die Zeilen 11–12:
```python
LOG_DIR = os.path.join(BASE_DIR, "Logs")
CONFIG_JSON = os.path.join(BASE_DIR, "config.json")
```
durch:
```python
LOG_DIR = os.path.join(BASE_DIR, "Logs")  # entfällt in Task 5
# AP-31: Daten liegen jetzt pro Nutzer (core/userpaths). Der alte App-Verzeichnis-
# Pfad bleibt nur als einmalige Migrationsquelle erhalten.
LEGACY_CONFIG_JSON = os.path.join(BASE_DIR, "config.json")
```

- [ ] **Step 4: `core/settings.py` umstellen**

Imports oben (nach `import config`) ergänzen:
```python
from core import userpaths
```
Default-Pfad in `load()` (Zeile 32) ersetzen:
```python
        path = path or userpaths.user_config_file(config.APP_SLUG)
```
Docstring-Zeile „defaults to config.CONFIG_JSON" → „defaults to the per-user config.json (core/userpaths, honours LUCENT_CONFIG_DIR)".

- [ ] **Step 5: `tests/test_api.py` (3 Stellen) auf Env-Override umstellen**

In `test_connections_save_list_delete_without_password`, `test_mssql_connection_persists_encrypt_and_trust` und `test_connect_from_saved_sqlite_round_trip` jeweils ersetzen:
```python
    import config
    monkeypatch.setattr(config, "CONFIG_JSON", str(tmp_path / "settings.json"))
```
durch:
```python
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
```

- [ ] **Step 6: Volle Suite läuft → grün**

Run: `./venv/bin/python -m pytest -q`
Expected: PASS (alle bisher grünen + neue userpaths-Tests; 1 skipped MSSQL)

- [ ] **Step 7: Commit**

```bash
git add config.py core/settings.py tests/test_api.py tests/test_userpaths.py
git commit -m "feat: AP-31 per-user config.json via userpaths (settings + tests)"
```

---

### Task 5: `core/log.py` auf Pro-Nutzer-Log-Verzeichnis umstellen

**Files:**
- Modify: `config.py` (Zeile `LOG_DIR = …` entfernen)
- Modify: `core/log.py:1-23`

**Interfaces:**
- Consumes: `core.userpaths.user_log_dir` (Task 1), `config.APP_SLUG`.

- [ ] **Step 1: Failing test schreiben (Default-Log-Dir ist Pro-Nutzer, ohne config.LOG_DIR)**

Ans Ende von `tests/test_userpaths.py`:
```python
def test_log_default_dir_uses_userpaths_not_config(tmp_path, monkeypatch):
    # kein log_dir-Arg, kein LUCENT_LOG_DIR → muss über userpaths auflösen,
    # NICHT über ein (entferntes) config.LOG_DIR.
    monkeypatch.delenv("LUCENT_LOG_DIR", raising=False)
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "st"))
    from core import log as log_mod
    d = log_mod._resolve_dir(None)
    assert d == str(tmp_path / "st" / "luDBxP" / "logs")
```

- [ ] **Step 2: Test läuft → schlägt fehl**

Run: `./venv/bin/python -m pytest tests/test_userpaths.py::test_log_default_dir_uses_userpaths_not_config -q`
Expected: FAIL — `_resolve_dir(None)` liefert `config.LOG_DIR` (App-Verzeichnis), nicht den XDG-State-Pfad.

- [ ] **Step 3: `config.py` — `LOG_DIR` entfernen**

Lösche in `config.py` die Zeile:
```python
LOG_DIR = os.path.join(BASE_DIR, "Logs")  # entfällt in Task 5
```

- [ ] **Step 4: `core/log.py` umstellen**

Import ergänzen (nach `import config`):
```python
from core import userpaths
```
`_resolve_dir` (Zeilen 20–23) ersetzen:
```python
def _resolve_dir(log_dir):
    if log_dir is None:
        # LUCENT_LOG_DIR + OS-Standardpfad werden in userpaths aufgelöst (AP-31).
        log_dir = userpaths.user_log_dir(config.APP_SLUG)
    return log_dir
```
Modul-Docstring-Zeile 5 „→ config.LOG_DIR" ändern zu „→ per-user log dir (core/userpaths, honours LUCENT_LOG_DIR)".

- [ ] **Step 5: Volle Suite läuft → grün**

Run: `./venv/bin/python -m pytest -q`
Expected: PASS (inkl. unveränderter `tests/test_log.py`; 1 skipped)

- [ ] **Step 6: Commit**

```bash
git add config.py core/log.py tests/test_userpaths.py
git commit -m "feat: AP-31 per-user log dir via userpaths (drop config.LOG_DIR)"
```

---

### Task 6: `app.py` verdrahten — dynamischer Port + URL-Ausgabe + Migration

**Files:**
- Modify: `app.py` (vollständig)

**Interfaces:**
- Consumes: `core.userpaths.resolve_port`, `core.userpaths.user_config_file`, `core.userpaths.migrate_legacy_config`, `config.WEB_PORT`, `config.WEB_HOST`, `config.APP_SLUG`, `config.APP_NAME`, `config.LEGACY_CONFIG_JSON`.

- [ ] **Step 1: `app.py` ersetzen**

```python
"""LucentTools DB Explorer - entry point."""
import logging
import os

import config
from core import userpaths
from web import create_app

app = create_app()  # initialisiert auch das Logging (core.log.init_logging)

if __name__ == "__main__":
    logger = logging.getLogger("luDBxP")

    # AP-31: vorhandene App-Verzeichnis-config.json einmalig pro Nutzer übernehmen.
    user_cfg = userpaths.user_config_file(config.APP_SLUG)
    if userpaths.migrate_legacy_config(user_cfg, config.LEGACY_CONFIG_JSON):
        logger.info("config.json aus App-Verzeichnis übernommen → %s", user_cfg)

    # Debug optional via Umgebungsvariable (run.ps1 -DebugMode setzt sie).
    debug = os.environ.get("LUCENT_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

    # AP-31: Port pro Session. Ohne LUCENT_PORT erst 5057 versuchen, sonst freien
    # Port; LUCENT_PORT=<n> erzwingt einen festen Port, =0 immer dynamisch.
    port = userpaths.resolve_port(os.environ.get("LUCENT_PORT"),
                                  config.WEB_PORT, config.WEB_HOST)
    url = f"http://{config.WEB_HOST}:{port}"
    logger.info("%s läuft auf %s", config.APP_NAME, url)
    print(f"\n  ▸ {config.APP_NAME} — {url}\n", flush=True)

    app.run(host=config.WEB_HOST, port=port,
            debug=debug, use_reloader=debug, threaded=True)
```

- [ ] **Step 2: Import-Sanity (kein Syntax-/Importfehler)**

Run: `./venv/bin/python -c "import app; print('import ok')"`
Expected: `import ok` (lädt `app` ohne den Server zu starten)

- [ ] **Step 3: Manuelle Verifikation — URL-Ausgabe + Pro-Nutzer-config + Port-Fallback**

Run (Terminal A):
```bash
LUCENT_CONFIG_DIR=/tmp/lu_a LUCENT_LOG_DIR=/tmp/lu_a/logs ./venv/bin/python app.py
```
Expected: Banner `▸ LucentTools DB Explorer — http://127.0.0.1:5057`. Im Browser eine Verbindung speichern → `/tmp/lu_a/config.json` entsteht.

Run (Terminal B, während A läuft):
```bash
LUCENT_CONFIG_DIR=/tmp/lu_b ./venv/bin/python app.py
```
Expected: Banner mit **abweichendem, freiem Port** (nicht 5057), eigener Prozess startet. Danach beide mit Strg+C beenden.

- [ ] **Step 4: Volle Suite läuft → grün (Regression)**

Run: `./venv/bin/python -m pytest -q`
Expected: PASS (1 skipped)

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: AP-31 app entry — dynamic port, URL banner, per-user config migration"
```

---

### Task 7: Release & Doku (Definition of Done)

**Files:**
- Modify: `config.py`/`lucent-hub.yml` (über `sync_version.py`), `CHANGELOG.md`, `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/projekt/roadmap.md`, `todo.md`, `todo-erledigt.md`, `CLAUDE.md`, `luDBxP-docs/zensical.toml`

**Interfaces:** keine (Doku/Release).

- [ ] **Step 1: Version-Bump (minor)**

Run: `./venv/bin/python sync_version.py --minor`
Expected: `Version: 0.32.1 -> 0.33.0`

- [ ] **Step 2: CHANGELOG (Haupt + Mirror)**

Oben in `CHANGELOG.md` und `luDBxP-docs/docs/entwicklung/changelog.md` einfügen (Mirror mit deutscher Überschrift „### Hinzugefügt"):
```markdown
## [0.33.0] — 2026-06-27
### Added
- **AP-31 (Kern) — Multi-User-Basis:** dynamische Port-Wahl pro Session (5057 bevorzugt,
  sonst freier Port; `LUCENT_PORT` erzwingt fest/`0`=dynamisch) und Pro-Nutzer-Datenpfade
  (config.json + Logs im OS-Nutzerverzeichnis, Slug `luDBxP`; `LUCENT_CONFIG_DIR`/`LUCENT_LOG_DIR`
  als Overrides). Neues pures Modul `core/userpaths.py`; vorhandene App-Verzeichnis-`config.json`
  wird einmalig übernommen; die tatsächliche URL wird beim Start ausgegeben. Bind weiterhin nur
  `127.0.0.1`. (Robustheit/Deployment — waitress, Idle-Shutdown, Packaging — bleibt offen.)
```

- [ ] **Step 3: `CLAUDE.md` — Logging/Pfad-Abschnitt nachziehen**

Den Logging-Abschnitt ergänzen: `LUCENT_CONFIG_DIR` (Pro-Nutzer-config.json) + `LUCENT_PORT` dokumentieren; den Satz „full terminal-server wiring is AP-31" zu „Pro-Nutzer-Pfade + dynamischer Port seit AP-31-Kern (v0.33.0); Rest (waitress/Idle/Deployment) offen" ändern.

- [ ] **Step 4: Roadmap + todo nachziehen**

In `luDBxP-docs/docs/projekt/roadmap.md` den AP-31-Eintrag der **offenen** APs auf „(Kern erledigt v0.33.0 — Rest: waitress/Idle-Shutdown/Deployment)" ergänzen und einen erledigten Eintrag „AP-31 (Kern) — Pro-Nutzer-Pfade + dynamischer Port — v0.33.0" hinzufügen. In `todo.md`/`todo-erledigt.md` die erledigten Kern-Checkboxen umhängen (Port-Wahl, Pro-Nutzer-config/Logs).

- [ ] **Step 5: zensical-Badge + Site bauen**

`luDBxP-docs/zensical.toml` `site_description` `v0.32.1` → `v0.33.0`. Dann:
Run: `cd luDBxP-docs && .venv-docs/bin/python build_docs.py --no-mermaid`
Expected: `✓ Build fertig`

- [ ] **Step 6: Commit (ohne KI-Signatur)**

```bash
git add -A
git commit -m "docs: AP-31 (Kern) Release v0.33.0 — Pro-Nutzer-Pfade + dynamischer Port (Changelog/Roadmap/CLAUDE/Site)"
```

- [ ] **Step 7: Push + gh-pages-Deploy**

```bash
git push origin master
WT=$(mktemp -d)/ghp
git worktree add "$WT" gh-pages
rsync -a --delete --exclude='.git' --exclude='.nojekyll' luDBxP-docs/site/ "$WT"/
test -f "$WT/.nojekyll" || touch "$WT/.nojekyll"
git -C "$WT" add -A
git -C "$WT" commit -m "docs: Site-Deploy v0.33.0 — AP-31 Kern (Pro-Nutzer-Pfade + dynamischer Port)"
git -C "$WT" push origin gh-pages
git worktree remove "$WT"
```
Expected: master + gh-pages aktualisiert.

---

## Self-Review

**Spec-Coverage:** §2 Architektur → Task 1–6. §3 Modul-API → Task 1/2/3. §4 Port+URL → Task 2 (resolve_port) + Task 6 (app.py). §5 Migration → Task 3 + Task 6. §6 config/settings/log → Task 4/5. §7 Test-Plan → Tasks 1–5 (Unit) + Task 6 (manuell). §8 Abweichungen → Global Constraints. Release (DoD) → Task 7. Keine Lücke.

**Platzhalter:** keine — jeder Code-Schritt enthält vollständigen Code, jede Test-/Run-Zeile einen konkreten Befehl + erwartete Ausgabe.

**Typ-Konsistenz:** `user_config_file(app_slug)`, `user_log_dir(app_slug)`, `pick_port(preferred, host)`, `resolve_port(forced, preferred, host)`, `migrate_legacy_config(user_file, legacy_file)` — in Definition (Task 1–3) und Nutzung (Task 4–6) identisch. `config.APP_SLUG`, `config.WEB_PORT`, `config.WEB_HOST`, `config.LEGACY_CONFIG_JSON` durchgängig gleich benannt.
