# AP-31 (Rest, Scheibe 1): waitress als WSGI-Server

**Datum:** 2026-06-27
**Status:** Design abgenommen
**Vorgänger:** `2026-06-27-ap31-multiuser-paths-port-design.md` (AP-31-Kern: Per-Nutzer-Pfade + dynamischer Port)

## Ziel

Den produktiven Start der App vom Werkzeug-**Entwicklungsserver** (`app.run()`)
auf den **waitress**-WSGI-Server umstellen. Der Debug-Modus behält den
Dev-Server inklusive Auto-Reload.

**Out of scope (spätere AP):** Idle-Shutdown / Selbst-Herunterfahren nach
Inaktivität. Deployment-Packaging ist über den AppImage-Build (`run.sh`) bereits
abgedeckt.

## Motivation

`app.run(...)` startet den Werkzeug-Dev-Server. Der ist fürs Entwickeln gedacht
(druckt selbst die „development server"-Warnung), nicht für Dauerbetrieb.
waitress ist ein reiner WSGI-Produktionsserver:

- **Pure Python**, identisch auf Windows und Linux (anders als gunicorn = Unix-only)
  → passt zum Windows-RDS-Ziel des Projekts.
- Wheel ist `py3-none-any` (plattformneutral) → kein `win_amd64`-Bruch im
  Offline-Wheelhouse, NO-CDN-/Offline-Pfad bleibt intakt.
- Fester Thread-Pool + Verbindungs-Queue → vorhersehbares Verhalten bei
  mehreren gleichzeitigen Requests (parallele Schema-Reflection + UI-Calls).

Bei einem lokalen `127.0.0.1`-Single-User-Tool ist der Lastgewinn gering; der
reale Nutzen ist Sauberkeit/Korrektheit (kein Dev-Server-Banner, vorhersehbares
Multi-Request-Verhalten) und ein klarer Dev-/Prod-Schalter.

## Architektur

### Server-Weiche in `app.py`

Die Server-Wahl wird in eine kleine, pur testbare Funktion herausgezogen:

```python
def run_server(app, host, port, debug):
    """Normalbetrieb → waitress; Debug → Werkzeug-Dev-Server mit Auto-Reload."""
    if debug:
        app.run(host=host, port=port, debug=True, use_reloader=True, threaded=True)
    else:
        from waitress import serve
        serve(app, host=host, port=port)
```

Der `__main__`-Block bleibt sonst unverändert: Legacy-Config-Migration,
Debug-Flag aus `LUCENT_DEBUG`, `userpaths.resolve_port(...)`, das URL-Print
(`▸ <APP_NAME> — http://host:port`) und das Logging laufen **vor**
`run_server(...)`, damit die URL weiterhin sofort erscheint.

`import waitress` erfolgt **nur innerhalb** von `run_server` (bzw. im
`app.py`-`__main__`-Pfad) — `core/` bleibt server-/Flask-frei (Layering-Regel).

### Dependencies

- `requirements.txt`: `waitress>=3.0` ergänzen.
- `wheels/`-Wheelhouse: waitress-Wheel (`*.whl`, `py3-none-any`) aufnehmen,
  damit der Offline-Install (Linux **und** Windows) weiter strikt offline läuft.

### Saubere Stops (unverändert)

waitress reagiert von sich aus sauber auf SIGTERM/SIGINT. Der bestehende
Tray-Stop (`launcher/core.py`: `terminate()` → `kill()`) und `Strg+C` im
Terminal funktionieren ohne Änderung. Threads: waitress-Default (Pool=4),
kein Config-Knopf (YAGNI).

## Tests

Neue Datei `tests/test_app_server.py`:

- `run_server(..., debug=False)` ruft `waitress.serve` mit `(app, host, port)`
  auf und ruft `app.run` **nicht** (Monkeypatch beider Aufrufe; `serve` wird
  gepatcht, sodass nichts real bindet).
- `run_server(..., debug=True)` ruft `app.run` mit `use_reloader=True` auf und
  ruft `waitress.serve` **nicht**.

Bestehende Suite (232 passed, 1 skipped) bleibt grün; `test_smoke.py` deckt die
App-Erzeugung weiter ab.

## Doku / Release

- `CLAUDE.md`: AP-31-„Offen"-Zeile auf „nur noch Idle-Shutdown offen"
  reduzieren; „How to Run" um den Hinweis Prod=waitress / Debug=Dev-Server
  ergänzen.
- Version-Bump **minor** (Feature) via `sync_version.py --minor` → v0.35.0.
- Übliche Release-Kette: Changelog + Doc-Mirror, Badges, Architektur-Diagramme,
  Site-Build, gh-pages-Deploy (gemäß `ludbxp-release-deploy-steps`).
- SDD-Final-Review nicht weglassen.

## Risiken / offene Punkte

- waitress loggt eigene Startmeldungen nicht über die App-`after_request`-Schicht
  — akzeptabel; das eigene URL-Print bleibt die maßgebliche Startanzeige.
- Idle-Shutdown bleibt bewusst offen (separate AP).
