# AP-31 (Rest, Scheibe 1) — waitress als WSGI-Server: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Den produktiven App-Start vom Werkzeug-Dev-Server auf den waitress-WSGI-Server umstellen; der Debug-Modus behält den Dev-Server mit Auto-Reload.

**Architecture:** Die Server-Wahl wird in `app.py` in eine pur testbare Funktion `run_server(app, host, port, debug)` herausgezogen. `debug=True` → `app.run(... use_reloader=True ...)` (Werkzeug); `debug=False` → `waitress.serve(app, host=..., port=...)`. `import waitress` erfolgt nur in `app.py` (Layering: `core/` bleibt server-/Flask-frei).

**Tech Stack:** Python 3.14 (venv), Flask, waitress (neu), pytest.

## Global Constraints

- **Layering:** `core/` darf NIE Flask/Server importieren. waitress wird ausschließlich in `app.py` importiert (innerhalb `run_server`).
- **NO-CDN / Offline:** Alle Dependencies bleiben offline-installierbar. waitress ist `py3-none-any` (plattformneutral) → muss ins `wheels/`-Wheelhouse, damit der Offline-Install (Linux + Windows) strikt offline bleibt.
- **Version Management:** Version nur via `sync_version.py` ändern, nie von Hand. Feature → `--minor` → v0.35.0.
- **Sprache:** Code-Kommentare/Doku auf dem im Projekt etablierten Stand (deutsch in der App-Doku, englisch im Root-CHANGELOG `### Added`).
- **Dependency-Floor:** `waitress>=3.0`.
- **Tests:** Baseline 232 passed, 1 skipped muss grün bleiben; neue Tests kommen hinzu.

---

### Task 1: waitress-Dependency + Wheelhouse

**Files:**
- Modify: `requirements.txt`
- Create: `wheels/waitress-*-py3-none-any.whl` (per pip download)

**Interfaces:**
- Consumes: nichts.
- Produces: `import waitress` und `from waitress import serve` sind im venv verfügbar (Voraussetzung für Task 2).

- [ ] **Step 1: waitress zu requirements.txt hinzufügen**

In `requirements.txt` nach der `Pillow>=10`-Zeile ergänzen:

```
waitress>=3.0         # AP-31: produktiver WSGI-Server (pure Python, Win+Linux)
```

- [ ] **Step 2: waitress-Wheel ins Wheelhouse laden**

Run:
```bash
./venv/bin/pip download waitress --no-deps -d wheels/
```
Expected: Eine Datei `wheels/waitress-<version>-py3-none-any.whl` entsteht (pure-Python, plattformneutral). Kontrolle:
```bash
ls wheels/waitress-*.whl
```

- [ ] **Step 3: waitress ins venv installieren**

Run:
```bash
./venv/bin/pip install --no-index --find-links wheels/ waitress
```
Expected: `Successfully installed waitress-<version>` (offline aus dem Wheelhouse).

- [ ] **Step 4: Import + Suite verifizieren**

Run:
```bash
./venv/bin/python -c "import waitress; print(waitress.__version__)"
./venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expected: waitress-Version wird gedruckt; `232 passed, 1 skipped`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt wheels/waitress-*.whl
git commit -m "build: AP-31 waitress als Dependency + Offline-Wheel"
```

---

### Task 2: `run_server()`-Weiche + Verdrahtung (TDD)

**Files:**
- Create: `tests/test_app_server.py`
- Modify: `app.py` (neue Funktion `run_server`; `__main__`-Block ruft sie statt `app.run` direkt)

**Interfaces:**
- Consumes: `import waitress` aus Task 1.
- Produces: `app.run_server(app, host, port, debug)` — bei `debug=False` ruft es `waitress.serve(app, host=host, port=port)`; bei `debug=True` ruft es `app.run(host=host, port=port, debug=True, use_reloader=True, threaded=True)`.

- [ ] **Step 1: Failing test schreiben**

Erstelle `tests/test_app_server.py`:

```python
"""AP-31: die Server-Weiche in app.run_server wählt waitress vs. Dev-Server."""
import waitress

import app as app_module


class FakeApp:
    """Minimaler App-Stub: zeichnet auf, ob/wie .run() gerufen wurde."""

    def __init__(self):
        self.run_called = False
        self.run_kwargs = None

    def run(self, **kwargs):
        self.run_called = True
        self.run_kwargs = kwargs


def test_run_server_production_uses_waitress(monkeypatch):
    captured = {}
    monkeypatch.setattr(waitress, "serve",
                        lambda app, **kw: captured.update(app=app, kw=kw))
    fake = FakeApp()

    app_module.run_server(fake, "127.0.0.1", 5057, debug=False)

    assert captured["app"] is fake
    assert captured["kw"] == {"host": "127.0.0.1", "port": 5057}
    assert fake.run_called is False


def test_run_server_debug_uses_dev_server(monkeypatch):
    serve_calls = {"n": 0}
    monkeypatch.setattr(waitress, "serve",
                        lambda *a, **k: serve_calls.__setitem__("n", serve_calls["n"] + 1))
    fake = FakeApp()

    app_module.run_server(fake, "127.0.0.1", 5057, debug=True)

    assert fake.run_called is True
    assert fake.run_kwargs.get("use_reloader") is True
    assert serve_calls["n"] == 0
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run:
```bash
./venv/bin/python -m pytest tests/test_app_server.py -v
```
Expected: FAIL — `AttributeError: module 'app' has no attribute 'run_server'`.

- [ ] **Step 3: `run_server` implementieren und `__main__` verdrahten**

In `app.py` nach `app = create_app()` (Zeile 9) und vor dem `if __name__ == "__main__":`-Block die Funktion einfügen:

```python


def run_server(app, host, port, debug):
    """AP-31: Server-Weiche. Normalbetrieb → waitress (Prod-WSGI-Server);
    Debug → Werkzeug-Dev-Server mit Auto-Reload (waitress kann kein Reload)."""
    if debug:
        app.run(host=host, port=port, debug=True, use_reloader=True, threaded=True)
    else:
        from waitress import serve
        serve(app, host=host, port=port)
```

Im `__main__`-Block den direkten `app.run(...)`-Aufruf (aktuell Zeile 30–31) ersetzen durch:

```python
    run_server(app, config.WEB_HOST, port, debug)
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run:
```bash
./venv/bin/python -m pytest tests/test_app_server.py -v
```
Expected: PASS (2 passed).

- [ ] **Step 5: Volle Suite grün**

Run:
```bash
./venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expected: `234 passed, 1 skipped` (232 alt + 2 neu).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_server.py
git commit -m "feat: AP-31 waitress als WSGI-Server (Debug behält Dev-Server)"
```

---

### Task 3: Doku, Version-Bump & Release

**Files:**
- Modify: `CLAUDE.md` (AP-31-„Offen"-Zeile; „How to Run")
- Modify (via `sync_version.py`): `config.py`, `lucent-hub.yml`
- Modify: `CHANGELOG.md` + Mirror `luDBxP-docs/docs/entwicklung/changelog.md`
- Modify: `luDBxP-docs/zensical.toml`, `luDBxP-docs/docs/javascripts/icon-rail.js`
- Modify (falls relevant): `luDBxP-docs/mermaid-sources/referenz-architektur-*.mmd`

**Interfaces:**
- Consumes: fertige Implementierung aus Task 2.
- Produces: Release v0.35.0, konsistente Doku, gebauter Site-Stand.

- [ ] **Step 1: CLAUDE.md nachziehen**

In `CLAUDE.md` im Abschnitt „Per-Nutzer-Pfade & Port (AP-31 …)" die „Offen"-Zeile anpassen — waitress ist erledigt, nur noch Idle-Shutdown offen:

```
- **Offen (Rest von AP-31):** Idle-Shutdown/sauberer Stop (lokaler WSGI-Server via waitress erledigt), Deployment-Packaging via AppImage.
```

Im Abschnitt „How to Run" einen Satz ergänzen:

```
Normalbetrieb läuft auf dem waitress-WSGI-Server; `--debug` nutzt den Werkzeug-Dev-Server mit Auto-Reload.
```

- [ ] **Step 2: Version bumpen (minor)**

Run:
```bash
./venv/bin/python sync_version.py --minor
./venv/bin/python -c "import config; print(config.APP_VERSION)"
```
Expected: `0.35.0`.

- [ ] **Step 3: Changelog (Root, englisch) + Mirror (deutsch)**

In `CHANGELOG.md` einen `## [0.35.0]`-Block mit `### Added` (englisch, Volltext) ergänzen:

```markdown
### Added
- Production WSGI server: the app now serves via **waitress** in normal
  operation; `--debug` keeps the Werkzeug dev server with auto-reload.
```

In `luDBxP-docs/docs/entwicklung/changelog.md` den deutschen, kondensierten Spiegel-Eintrag unter `### Hinzugefügt` ergänzen:

```markdown
### Hinzugefügt
- waitress als WSGI-Server im Normalbetrieb (Debug behält Dev-Server mit Auto-Reload).
```

- [ ] **Step 4: Badges + zensical-Version nachziehen**

In `luDBxP-docs/docs/javascripts/icon-rail.js` `APP_VERSION` auf `0.35.0`, `TEST_COUNT` auf `234`, `TEST_DATE` auf `2026-06-27` setzen.
In `luDBxP-docs/zensical.toml` die `site_description` von `… · v0.34.1` auf `… · v0.35.0` ändern.

- [ ] **Step 5: Architektur-Diagramme prüfen**

Kein neues core-Modul/Endpoint (nur `app.py`-interne Änderung) → `referenz-architektur-*.mmd` brauchen i. d. R. **keine** Änderung. Kurz gegenprüfen, ob waitress irgendwo im Stack-Diagramm erwähnt werden soll; falls ja, in `-1.mmd`/`-3.mmd` ergänzen, sonst unverändert lassen.

- [ ] **Step 6: Site bauen + gegenprüfen**

Run:
```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
```
Expected: Build ohne Fehler; danach `luDBxP-docs/site/index.html` inhaltlich gegenprüfen (Version v0.35.0, Test-Zahl 234 sichtbar).

- [ ] **Step 7: SDD-Final-Review**

Den gesamten Diff dieser AP gegen die Spec prüfen (Layering eingehalten, NO-CDN/Offline intakt, Tests grün, Doku ohne Drift). Niemals weglassen.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: Release v0.35.0 — waitress-WSGI-Server (AP-31), Doku/Badges/Changelog/Site"
```

- [ ] **Step 9: Push & gh-pages-Deploy — NUR auf Ansage des Nutzers**

Master-Push und der manuelle gh-pages-Deploy (Worktree-Verfahren, `.nojekyll` erhalten) erfolgen erst nach ausdrücklicher Freigabe. Nicht automatisch ausführen.

---

## Self-Review (durchgeführt)

**Spec-Coverage:** waitress-Weiche (Task 2), Dependencies+Wheelhouse (Task 1), Debug-Fork (Task 2), Tests (Task 2), Doku/Release inkl. SDD-Review (Task 3) — alle Spec-Abschnitte abgedeckt. Idle-Shutdown bleibt korrekt out-of-scope.

**Placeholder-Scan:** Keine TBD/TODO; alle Code-Schritte enthalten konkreten Code; Release-Schritte mit exakten Pfaden/Befehlen.

**Type-Consistency:** `run_server(app, host, port, debug)` ist in Interfaces, Implementierung und Test identisch signiert; `waitress.serve(app, host=, port=)` und `app.run(..., use_reloader=True)` durchgängig konsistent.
