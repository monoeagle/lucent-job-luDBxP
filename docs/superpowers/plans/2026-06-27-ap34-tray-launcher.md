# AP-34 Kern — Tray-Icon-Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein-Klick-Start: eine Verknüpfung auf `run.ps1 -Action tray` baut beim ersten Start das venv automatisch und startet einen fensterlosen Python-Tray-Launcher (Im Browser öffnen · Info · Beenden) mit Auto-Browser.

**Architecture:** Neues App-Layer-Paket `launcher/`: `core.py` (Stdlib-only, testbar — Port wählen via `userpaths.pick_port`, `app.py` als Kindprozess mit `LUCENT_PORT` starten, Readiness-Polling, sauberes Beenden = Port frei) + dünnes `tray.py` (pystray/Pillow) + `__main__.py`. Ausgeliefert über die bestehende adaptive `run.ps1`/`run.sh` (venv-Bootstrap), kein `.exe`-Bau.

**Tech Stack:** Python 3.10+ (venv 3.14), `pystray`+`Pillow` (Tray/Icon), Stdlib (`subprocess`, `urllib`, `webbrowser`, `threading`), pytest. Flask läuft im Kindprozess `app.py` (unverändert).

## Global Constraints

- **Python ≥ 3.10**; Tests mit `./venv/bin/python -m pytest` (venv = Python 3.14).
- **`launcher/core.py` ist Stdlib-only** und importiert **kein** `pystray`/`Pillow` (bleibt headless-testbar). Nur `launcher/tray.py`/`__main__.py` importieren die GUI-Pakete.
- **NO-CDN:** `pystray`/`Pillow` als **Wheels in `wheels/`** (Windows cp314 win_amd64). `run.ps1` installiert **strikt offline** aus `wheels\` (kein Online-Fallback) → die Wheels MÜSSEN vorhanden sein. `run.sh` fällt auf PyPI zurück (Linux-Dev).
- **Bind nur `127.0.0.1`** (geerbt über `app.py`).
- **Kein `.exe`/Freeze.** Auslieferung via `run.ps1 -Action tray` (Ensure-Venv → `pythonw -m launcher`). `run.ps1` wird modifiziert → **Re-Signatur** nötig (Maintainer unter Windows; auf der Linux-Dev-Maschine nicht ausführbar/-testbar).
- **Version je AP** via `./venv/bin/python sync_version.py --minor` (0.33.0 → 0.34.0); je AP **ohne KI-Signatur** committen; Release berührt mehr als `sync_version.py` (CHANGELOG+Mirror, Roadmap/todo, CLAUDE.md, Betriebsseite, Site-Build, gh-pages-Deploy).
- **Spec-Abweichungen (Spec §9):** Log-Fenster (Tkinter), Chrome-bevorzugt, Info „aktive Verbindung", automatisches Verknüpfungs-Ausrollen = OUT/deferred. Tray-GUI ist headless **nicht** verifizierbar (Kernlogik schon).

---

### Task 1: `launcher/core.py` — LauncherCore (testbarer Kern)

**Files:**
- Create: `launcher/__init__.py`
- Create: `launcher/core.py`
- Test: `tests/test_launcher.py`

**Interfaces:**
- Consumes: `config.BASE_DIR`, `config.WEB_HOST`, `config.WEB_PORT`, `config.APP_NAME`, `config.APP_VERSION`; `core.userpaths.pick_port(preferred, host)` (aus AP-31).
- Produces: `LauncherCore(host=config.WEB_HOST, opener=webbrowser.open)` mit `start() -> str`, `wait_until_ready(timeout=20.0, interval=0.3) -> bool`, `open_browser() -> None`, `is_running() -> bool`, `stop(timeout=5.0) -> None`, `info() -> dict`. Attribute `port`, `url`.

- [ ] **Step 1: Paket-Init anlegen**

`launcher/__init__.py`:
```python
"""AP-34 tray launcher package."""
```

- [ ] **Step 2: Failing tests schreiben**

`tests/test_launcher.py`:
```python
"""AP-34 — tray launcher core."""
import http.server
import socket
import subprocess
import sys
import threading

import config
from launcher.core import LauncherCore


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_start_picks_port_and_sets_lucent_port_env(monkeypatch):
    captured = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, env=None, **kw):
        captured["cmd"] = cmd
        captured["env"] = env
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    c = LauncherCore()
    url = c.start()
    assert c.port and c.port > 0
    assert captured["env"]["LUCENT_PORT"] == str(c.port)
    assert captured["cmd"][0] == sys.executable
    assert captured["cmd"][1].endswith("app.py")
    assert url == f"http://127.0.0.1:{c.port}"


def test_info_reports_version_url_port(monkeypatch):
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: type("P", (), {"poll": lambda self: None})())
    c = LauncherCore()
    c.start()
    info = c.info()
    assert info["version"] == config.APP_VERSION
    assert info["name"] == config.APP_NAME
    assert info["url"] == c.url and info["port"] == c.port


def test_open_browser_uses_injected_opener():
    calls = []
    c = LauncherCore(opener=lambda u: calls.append(u))
    c.url = "http://127.0.0.1:1234"
    c.open_browser()
    assert calls == ["http://127.0.0.1:1234"]


def test_wait_until_ready_true_against_stub_server():
    port = _free_port()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = LauncherCore()
        c.url = f"http://127.0.0.1:{port}"
        assert c.wait_until_ready(timeout=3) is True
    finally:
        srv.shutdown()


def test_wait_until_ready_false_on_closed_port():
    c = LauncherCore()
    c.url = f"http://127.0.0.1:{_free_port()}"   # nichts lauscht dort
    assert c.wait_until_ready(timeout=0.6, interval=0.1) is False


def test_stop_terminates_child():
    c = LauncherCore()
    c._proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    assert c.is_running() is True
    c.stop(timeout=5)
    assert c.is_running() is False
    assert c._proc.poll() is not None
```

- [ ] **Step 3: Test läuft → schlägt fehl**

Run: `./venv/bin/python -m pytest tests/test_launcher.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'launcher.core'`

- [ ] **Step 4: `launcher/core.py` implementieren**

```python
"""Tray launcher core (AP-34): own the app.py child process, pick the port,
poll for readiness, open the browser. Pure stdlib — no pystray/Pillow import,
so it stays headless-testable. The GUI shell (launcher/tray.py) drives this."""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

import config
from core import userpaths

_APP_PY = os.path.join(config.BASE_DIR, "app.py")
_CREATE_NO_WINDOW = 0x08000000  # Windows: no console for the child


class LauncherCore:
    """Owns the app.py child process; start/stop/info for the tray shell."""

    def __init__(self, host=config.WEB_HOST, opener=webbrowser.open):
        self.host = host
        self._opener = opener
        self.port = None
        self.url = None
        self._proc = None

    def start(self):
        """Pick a free port, spawn app.py with LUCENT_PORT set; return the URL."""
        self.port = userpaths.pick_port(config.WEB_PORT, self.host)
        self.url = f"http://{self.host}:{self.port}"
        env = dict(os.environ, LUCENT_PORT=str(self.port))
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        self._proc = subprocess.Popen([sys.executable, _APP_PY], env=env, **kwargs)
        return self.url

    def wait_until_ready(self, timeout=20.0, interval=0.3):
        """Poll self.url until the server answers (any HTTP status) or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(self.url, timeout=1):
                    return True
            except urllib.error.HTTPError:
                return True   # answered (e.g. 4xx) → it is up
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(interval)
        return False

    def open_browser(self):
        if self.url:
            self._opener(self.url)

    def is_running(self):
        return self._proc is not None and self._proc.poll() is None

    def stop(self, timeout=5.0):
        """Terminate the app process (frees the port). SIGTERM then kill."""
        if self._proc is None or self._proc.poll() is not None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()

    def info(self):
        return {"name": config.APP_NAME, "version": config.APP_VERSION,
                "url": self.url, "port": self.port, "running": self.is_running()}
```

- [ ] **Step 5: Test läuft → grün**

Run: `./venv/bin/python -m pytest tests/test_launcher.py -q`
Expected: PASS (6 passed)

- [ ] **Step 6: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: PASS (1 skipped MSSQL)

- [ ] **Step 7: Commit**

```bash
git add launcher/__init__.py launcher/core.py tests/test_launcher.py
git commit -m "feat: AP-34 launcher core — port handoff, readiness poll, clean stop"
```

> **Controller-Verifikation nach Task 1 (kein pytest, echtes app.py):** `LauncherCore.start()` mit temp `LUCENT_CONFIG_DIR` startet echtes `app.py`; `wait_until_ready()` True; `urlopen` 200; `stop()`; Port frei. (stdlib-only — pystray nicht nötig.)

---

### Task 2: Abhängigkeiten + GUI-Schale (`tray.py`, `__main__.py`)

**Files:**
- Modify: `requirements.txt`
- Modify: `wheels/` (Windows-Wheels für pystray/Pillow hinzufügen)
- Create: `launcher/tray.py`
- Create: `launcher/__main__.py`

**Interfaces:**
- Consumes: `LauncherCore` (Task 1), `config.APP_NAME`.
- Produces: `launcher.tray.make_icon_image(size=64) -> PIL.Image.Image`, `launcher.tray.build_tray(core) -> pystray.Icon`; `launcher.__main__.main()` (startet Kern + Auto-Browser-Thread + Tray-Loop).

- [ ] **Step 1: `requirements.txt` ergänzen**

Am Ende von `requirements.txt` anhängen:
```
pystray>=0.19         # AP-34: Tray-Icon
Pillow>=10            # AP-34: Tray-Icon-Bild
```

- [ ] **Step 2: Windows-Wheels ins Wheelhouse laden**

Run (lädt die Windows-cp314-Wheels für das Offline-Setup, ohne sie lokal zu installieren):
```bash
./venv/bin/pip download --only-binary=:all: --platform win_amd64 \
  --python-version 314 --implementation cp --abi cp314 \
  --dest wheels/ pystray Pillow
```
Expected: neue `.whl` in `wheels/` (u. a. `pystray-…-py3-none-any.whl`, `pillow-…-cp314-cp314-win_amd64.whl`, ggf. `six-…-py3-none-any.whl`).
Prüfen: `ls wheels/ | grep -Ei "pystray|pillow|six"`
**Falls das Pillow-cp314-win_amd64-Wheel (noch) nicht auf PyPI liegt:** STOP, als BLOCKED melden (Pillow-Version mit cp314-Wheels nötig) — nicht raten.

- [ ] **Step 3: Pakete lokal (Linux) installieren (für Import-Smoke)**

Run: `./venv/bin/pip install pystray Pillow`
Expected: erfolgreich installiert (aus PyPI; Linux-Wheels).

- [ ] **Step 4: `launcher/tray.py` implementieren**

```python
"""Tray GUI shell (AP-34): pystray icon + menu wired to LauncherCore.
Thin by design — all logic lives in launcher.core (headless-testable)."""
import pystray
from PIL import Image, ImageDraw

import config


def make_icon_image(size=64):
    """A simple branded tray icon (no bundled asset): brand square + 'DB'."""
    img = Image.new("RGBA", (size, size), (46, 111, 174, 255))  # #2E6FAE
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, size - 5, size - 5], outline=(255, 255, 255, 255), width=2)
    draw.text((14, 22), "DB", fill=(255, 255, 255, 255))
    return img


def build_tray(core):
    """Build the pystray.Icon with the Open/Info/Quit menu wired to `core`."""
    def on_open(icon, item):
        core.open_browser()

    def on_info(icon, item):
        i = core.info()
        icon.notify(f"{i['name']} v{i['version']}\n{i['url']}", "Info")

    def on_quit(icon, item):
        core.stop()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Im Browser öffnen", on_open, default=True),
        pystray.MenuItem("Info", on_info),
        pystray.MenuItem("Beenden", on_quit),
    )
    return pystray.Icon("luDBxP", make_icon_image(), config.APP_NAME, menu)
```

- [ ] **Step 5: `launcher/__main__.py` implementieren**

```python
"""Entry point: `python -m launcher` (Windows fensterlos via pythonw)."""
import threading

from launcher.core import LauncherCore
from launcher.tray import build_tray


def main():
    core = LauncherCore()
    core.start()

    def _open_when_ready():
        if core.wait_until_ready():
            core.open_browser()

    threading.Thread(target=_open_when_ready, daemon=True).start()
    build_tray(core).run()   # blockiert bis „Beenden"


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Import-/Bau-Smoke (headless, ohne Tray-Loop)**

Run: `./venv/bin/python -c "from launcher.tray import build_tray, make_icon_image; from launcher.core import LauncherCore; img=make_icon_image(); ic=build_tray(LauncherCore()); print('ok', img.size, len(ic.menu))"`
Expected: `ok (64, 64) 3` (Icon + 3-Punkte-Menü gebaut; `.run()` wird NICHT aufgerufen).
**Falls `import pystray` headless mit Backend-Fehler scheitert** (kein Display/AppIndicator): stattdessen nur Syntax prüfen — `./venv/bin/python -m py_compile launcher/tray.py launcher/__main__.py` (Exit 0) — und im Report vermerken, dass die GUI manuell/auf einem Desktop zu prüfen ist.

- [ ] **Step 7: Volle Suite grün (keine Regression)**

Run: `./venv/bin/python -m pytest -q`
Expected: PASS (1 skipped).

- [ ] **Step 8: Commit**

```bash
git add requirements.txt wheels/ launcher/tray.py launcher/__main__.py
git commit -m "feat: AP-34 tray shell + deps — pystray/Pillow icon, python -m launcher entry"
```

---

### Task 3: Start-Integration `run.sh --tray` + `run.ps1 -Action tray`

**Files:**
- Modify: `run.sh` (neue Action `--tray` + Dispatch + Hilfe)
- Modify: `run.ps1` (`tray` in ValidateSet, `$VenvPythonw`, `Do-Tray`, switch-Zweig)

**Interfaces:**
- Consumes: `launcher` (`python -m launcher`), bestehende `ensure_venv`/`Ensure-Venv`.

- [ ] **Step 1: `run.sh` — `do_tray` + Dispatch**

In `run.sh` bei den Actions (nach `do_skip_setup() { … }`) ergänzen:
```bash
do_tray()       { ensure_venv; "$VENV_PY" -m launcher; }
```
Im `case "${1:-MENU}"`-Block den Zweig hinzufügen (vor `--start|"")`):
```bash
  --tray)       do_tray ;;
```
In der `--help`-Usage-Zeile `--tray` ergänzen:
```bash
    echo "Usage: run.sh [--start|--tray|--setup-venv|--skip-setup|--clean|--tests|--demo-db|--version|--appimage] [--debug]"
```

- [ ] **Step 2: `run.sh` Syntax + Verdrahtung prüfen**

Run: `bash -n run.sh && grep -nE "do_tray\(\)|--tray\)" run.sh`
Expected: kein Syntaxfehler; `do_tray` ruft `"$VENV_PY" -m launcher`; `--tray)`-Dispatch vorhanden.

- [ ] **Step 3: `run.ps1` — `tray`-Action ergänzen**

a) ValidateSet erweitern (Zeile mit `[ValidateSet('menu', 'start', …)]`):
```powershell
    [ValidateSet('menu', 'start', 'tray', 'setup-venv', 'skip-setup', 'clean', 'tests', 'demo-db', 'version')]
```
b) Nach `$VenvPy  = Join-Path $Venv 'Scripts\python.exe'` ergänzen:
```powershell
$VenvPythonw = Join-Path $Venv 'Scripts\pythonw.exe'
```
c) Bei den Actions (nach `function Do-SkipSetup { … }`) ergänzen:
```powershell
function Do-Tray {
    Ensure-Venv
    # Tray fensterlos starten (pythonw = keine Konsole); app.py wird vom Launcher gestartet.
    Start-Process -FilePath $VenvPythonw -ArgumentList '-m', 'launcher' -WorkingDirectory $PSScriptRoot
}
```
d) Im `switch ($Action)` den Zweig hinzufügen (nach `'start' { Do-Start }`):
```powershell
    'tray'       { Do-Tray }
```

- [ ] **Step 4: `run.ps1` Konsistenz prüfen (auf Linux nicht ausführbar)**

Run: `grep -nE "'tray'|Do-Tray|VenvPythonw" run.ps1`
Expected: ValidateSet enthält `'tray'`; `$VenvPythonw` definiert; `Do-Tray` ruft `Start-Process … pythonw … -m launcher`; switch-Zweig `'tray' { Do-Tray }` vorhanden.
*(PowerShell ist auf der Linux-Dev-Maschine nicht ausführbar — Live-Test + Re-Signatur später unter Windows.)*

- [ ] **Step 5: Commit**

```bash
git add run.sh run.ps1
git commit -m "feat: AP-34 launch integration — run.sh --tray + run.ps1 -Action tray (venv-bootstrap)"
```

---

### Task 4: Release & Doku (Definition of Done)

**Files:**
- Modify: `config.py`/`lucent-hub.yml` (via `sync_version.py`), `CHANGELOG.md`, `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/projekt/roadmap.md`, `todo.md`, `todo-erledigt.md`, `CLAUDE.md`, `luDBxP-docs/docs/betrieb/terminalserver.md`, `luDBxP-docs/zensical.toml`

- [ ] **Step 1: Version-Bump (minor)**

Run: `./venv/bin/python sync_version.py --minor`
Expected: `Version: 0.33.0 -> 0.34.0`

- [ ] **Step 2: CHANGELOG (Haupt + Mirror)**

Oben in `CHANGELOG.md` und `luDBxP-docs/docs/entwicklung/changelog.md` (Mirror: `### Hinzugefügt`):
```markdown
## [0.34.0] — 2026-06-27
### Added
- **AP-34 (Kern) — Tray-Icon-Launcher:** Ein-Klick-Start ohne venv-Einrichtung durch den
  Nutzer. Eine Verknüpfung auf `run.ps1 -Action tray` (Linux: `run.sh --tray`) baut beim
  ersten Start das venv automatisch und startet einen **fensterlosen** Python-Tray-Launcher
  (`launcher/`): Tray-Menü **Im Browser öffnen · Info · Beenden**, Auto-Browser beim Start
  (pollt bis der Server antwortet), „Beenden" stoppt den App-Prozess → Port frei. Neue
  Pakete `pystray`/`Pillow` (als Wheels gebündelt). *Offen:* Live-Log-Fenster, automatisches
  Verknüpfungs-Ausrollen.
```

- [ ] **Step 3: `CLAUDE.md` — Start-Hinweis ergänzen**

Im Abschnitt „How to Run" eine Zeile ergänzen:
```markdown
bash run.sh --tray     # Tray-Icon-Launcher (startet App + Auto-Browser); Windows: run.ps1 -Action tray
```

- [ ] **Step 4: Roadmap + todo nachziehen**

In `luDBxP-docs/docs/projekt/roadmap.md`: AP-34 aus „Offene Arbeitspakete" entfernen und unter „Erledigte Arbeitspakete" ergänzen:
```markdown
- **AP-34 (Kern)** — Tray-Icon-Launcher (Python/pystray): Ein-Klick-Start über `run.ps1 -Action tray`/`run.sh --tray` (venv-Bootstrap), Tray-Menü Im-Browser-öffnen/Info/Beenden, Auto-Browser, sauberes Beenden (Port frei) — v0.34.0 *(Log-Fenster/Verknüpfungs-Ausrollen offen)*
```
In `todo.md`: die AP-34-Zeile aus der Offen-Liste im Kopf entfernen/anpassen. In `todo-erledigt.md` einen AP-34-Kern-Eintrag (erledigte Checkboxen: launcher/core+tray, run.sh/run.ps1 tray-Action, Auto-Browser, Beenden; offen: Log-Fenster) hinzufügen.

- [ ] **Step 5: Betriebsseite — Ein-Klick-Start ergänzen**

In `luDBxP-docs/docs/betrieb/terminalserver.md` einen Abschnitt nach „Start pro Nutzer" einfügen:
```markdown
## Ein-Klick-Start (Tray)

Statt einer Konsole kann pro Nutzer eine **Verknüpfung** angelegt werden, deren Ziel
`run.ps1 -Action tray` (Windows) bzw. `run.sh --tray` (Linux) ist. Beim **ersten** Klick wird
das venv automatisch eingerichtet (Fortschritt kurz sichtbar), danach startet ein **Tray-Icon**
fensterlos und der Browser öffnet sich automatisch. Tray-Menü: **Im Browser öffnen**, **Info**
(Version/URL/Port), **Beenden** (stoppt die App → Port frei). Spätere Starts gehen direkt durch.
```

- [ ] **Step 6: zensical-Badge + Site bauen**

`luDBxP-docs/zensical.toml` `site_description` `v0.33.0` → `v0.34.0`. Dann:
Run: `cd luDBxP-docs && .venv-docs/bin/python build_docs.py --no-mermaid`
Expected: `✓ Build fertig`

- [ ] **Step 7: Commit (ohne KI-Signatur)**

```bash
git add -A
git commit -m "docs: AP-34 (Kern) Release v0.34.0 — Tray-Icon-Launcher (Changelog/Roadmap/CLAUDE/Betrieb/Site)"
```

- [ ] **Step 8: Push + gh-pages-Deploy**

```bash
git push origin master
WT=$(mktemp -d)/ghp
git worktree add "$WT" gh-pages
rsync -a --delete --exclude='.git' --exclude='.nojekyll' luDBxP-docs/site/ "$WT"/
test -f "$WT/.nojekyll" || touch "$WT/.nojekyll"
git -C "$WT" add -A
git -C "$WT" commit -m "docs: Site-Deploy v0.34.0 — AP-34 Tray-Icon-Launcher"
git -C "$WT" push origin gh-pages
git worktree remove "$WT"
```

---

## Self-Review

**Spec-Coverage:** §2 Architektur → Task 1/2. §3 LauncherCore-API → Task 1. §4 Beenden/Port → Task 1 (`stop`). §5 Auslieferung (run.ps1/run.sh tray) → Task 3. §6 Tray/Info/Icon → Task 2. §7 Deps/Wheels → Task 2. §8 Tests/Verifikation → Task 1 (Unit + Controller-E2E) / Task 2 (Smoke) / Task 3 (Wiring). §9 Abweichungen → Global Constraints. Release/DoD → Task 4. Keine Lücke.

**Platzhalter:** keine — jeder Code-Schritt enthält vollständigen Code, jede Run-Zeile Befehl + erwartete Ausgabe; GUI-Headless-Risiko (Step Task2/6) + Pillow-Wheel-Risiko (Task2/2) mit konkretem Eskalationspfad benannt.

**Typ-Konsistenz:** `LauncherCore(host, opener)` mit `start()→str`, `wait_until_ready(timeout,interval)→bool`, `open_browser()`, `is_running()→bool`, `stop(timeout)`, `info()→dict` — in Definition (Task 1) und Nutzung (`tray.py`/`__main__.py`, Task 2) identisch. `build_tray(core)→pystray.Icon`, `make_icon_image(size)→Image` konsistent. `userpaths.pick_port(preferred, host)` wie in AP-31.
