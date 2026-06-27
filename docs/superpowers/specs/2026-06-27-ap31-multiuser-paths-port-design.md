# AP-31 — Kern-Scheibe: Pro-Nutzer-Pfade + dynamischer Port

**Datum:** 2026-06-27
**Status:** Design freigegeben → bereit für Implementierungsplan
**Umfang:** Kern-Scheibe von AP-31 (Terminal-Server-Tauglichkeit). Plattform-neutral,
voll auf Linux testbar. Robustheit (waitress, Idle-Shutdown) und Deployment-Layer
sind bewusst nicht Teil dieser Scheibe (siehe §8).

## 1 · Ziel & Problem

Auf einem (RDS-)Terminal-Server mit mehreren gleichzeitigen Nutzern bricht die App
heute, weil:

1. **Fester Port 5057** auf geteiltem `127.0.0.1`-Loopback → die zweite Instanz kann
   nicht binden; ein fremder Browser erreicht die fremde Instanz (keine Isolation).
2. **Gemeinsame `config.json` + `Logs/`** im App-Verzeichnis → Nutzer überschreiben
   sich gegenseitig; auf einem read-only App-Verzeichnis (Program Files) schlägt das
   Schreiben sogar fehl.

Diese Scheibe behebt die **Pflicht-Basis**: dynamische Port-Wahl pro Session und
Pro-Nutzer-Datenpfade. Damit laufen mehrere Nutzer kollisionsfrei nebeneinander.

**Erfolgskriterien:**
- Zwei Instanzen auf derselben Maschine starten beide erfolgreich (zweite weicht auf
  einen freien Port aus) und melden je ihre URL.
- `config.json` + Logs liegen pro Nutzer im OS-Standardpfad; das App-Verzeichnis wird
  nicht mehr beschrieben.
- Bestehende gespeicherte Verbindungen gehen nicht verloren (einmalige Migration).
- Volle Test-Suite grün; neue Unit-Tests für Pfad-/Port-Auflösung.

## 2 · Architektur (Ansatz A)

Layering-Regel des Projekts: `web/` → `core/` → `config.py` (nur Konstanten).
`config.py` darf **nicht** `core/` importieren (Zyklus, da `core/settings.py` `config`
importiert). Daher lebt die gesamte Auflösungslogik in einem neuen **puren** Modul
`core/userpaths.py`, das den App-Slug als Parameter erhält (kein `config`-Import).

```
app.py            ── Port-Wahl + URL-Ausgabe + Migrationsaufruf ─┐
core/settings.py  ── Default-config.json-Pfad ──────────────────┤→ core/userpaths.py (pur)
core/log.py       ── Log-Verzeichnis ───────────────────────────┘
config.py         ── Konstanten: APP_SLUG, WEB_PORT, WEB_HOST, LEGACY_CONFIG_JSON
```

`core/userpaths.py` importiert nur `os`, `sys`, `socket`, `shutil` — kein Flask, kein
`config`. Damit voll isoliert unit-testbar.

## 3 · Modul-API `core/userpaths.py`

Der App-Slug wird stets vom Aufrufer übergeben (`config.APP_SLUG == "luDBxP"`); das
Modul hält selbst **keine** Slug-Konstante (vermeidet Divergenz zu `config`).

```python
def user_config_dir(app_slug: str) -> str
    """Pro-Nutzer-Config-Verzeichnis (wird angelegt). Reihenfolge:
       LUCENT_CONFIG_DIR → Windows %LOCALAPPDATA%\\<slug> → $XDG_CONFIG_HOME/<slug>
       → ~/.config/<slug>."""

def user_config_file(app_slug: str, filename: str = "config.json") -> str
    """Vollständiger Pfad zur Pro-Nutzer-Config-Datei (Verzeichnis wird angelegt)."""

def user_log_dir(app_slug: str) -> str
    """Pro-Nutzer-Log-Verzeichnis (wird angelegt). Reihenfolge:
       LUCENT_LOG_DIR → Windows %LOCALAPPDATA%\\<slug>\\Logs
       → $XDG_STATE_HOME/<slug>/logs → ~/.local/state/<slug>/logs."""

def pick_port(preferred: int, host: str = "127.0.0.1") -> int
    """preferred == 0 → freien Port vom OS. preferred > 0 → preferred versuchen;
       ist er belegt, einen freien Port zurückgeben. (Kurzes TOCTOU-Fenster bis
       app.run() bindet — bewusst akzeptiert.)"""

def migrate_legacy_config(user_file: str, legacy_file: str) -> bool
    """Wenn user_file fehlt und legacy_file existiert → kopieren. True wenn migriert."""
```

**Pfad-Konventionen (Slug `luDBxP` auf allen OSen):**

| | Windows | Linux/mac |
|---|---|---|
| Config | `%LOCALAPPDATA%\luDBxP\config.json` | `$XDG_CONFIG_HOME/luDBxP/config.json` bzw. `~/.config/luDBxP/config.json` |
| Logs | `%LOCALAPPDATA%\luDBxP\Logs\` | `$XDG_STATE_HOME/luDBxP/logs/` bzw. `~/.local/state/luDBxP/logs/` |

Env-Overrides `LUCENT_CONFIG_DIR` / `LUCENT_LOG_DIR` haben Vorrang. Plattformweiche
über `os.name == "nt"`; Windows-Fallback `~\AppData\Local`, wenn `%LOCALAPPDATA%` fehlt.

## 4 · Port-Wahl + URL-Ausgabe (`app.py`)

```
forced = os.environ.get("LUCENT_PORT")
if forced is None:        port = userpaths.pick_port(config.WEB_PORT)   # 5057 bevorzugt, sonst frei
elif forced == "0":       port = userpaths.pick_port(0)                 # immer frei
else:                     port = int(forced)                            # fester Port, kein Fallback
print(f"LucentTools DB Explorer läuft auf http://{config.WEB_HOST}:{port}")  # + ins Log
app.run(host=config.WEB_HOST, port=port, debug=debug, use_reloader=debug, threaded=True)
```

- Bind bleibt ausschließlich `127.0.0.1` (kein `0.0.0.0`).
- Lokal/über den Hub bleibt es bei 5057 (bookmarkbar); auf RDS weicht jede weitere
  Instanz auf einen freien Port aus. Die tatsächliche URL wird immer ausgegeben.

## 5 · Migration (einmalig, verlustfrei)

In `app.py` (nur im `__main__`-Pfad, damit `create_app`/Tests unberührt bleiben):

```
user_cfg = userpaths.user_config_file(config.APP_SLUG)
if userpaths.migrate_legacy_config(user_cfg, config.LEGACY_CONFIG_JSON):
    log.info("config.json aus App-Verzeichnis übernommen → %s", user_cfg)
```

Logs werden nicht migriert (starten am neuen Ort neu; alte Dateien bleiben liegen).

## 6 · Änderungen an bestehenden Dateien

- **`config.py`**: `WEB_PORT = 5057` (= bevorzugt), `WEB_HOST` bleiben. Neu
  `LEGACY_CONFIG_JSON = os.path.join(BASE_DIR, "config.json")` (nur Migrationsquelle).
  `CONFIG_JSON` und `LOG_DIR` (feste App-Pfade) **entfallen**.
- **`core/settings.py`**: `load(path=None)` Default → `userpaths.user_config_file(config.APP_SLUG)`.
- **`core/log.py`**: Log-Verzeichnis → `userpaths.user_log_dir(config.APP_SLUG)`; der
  `LUCENT_LOG_DIR`-Check lebt jetzt in `userpaths` (eine Quelle der Wahrheit).
- **`app.py`**: Port-Wahl, URL-Ausgabe, Migrationsaufruf.
- **`run.sh` / `run.ps1` / `lucent-hub.yml`**: keine Änderung nötig (starten `app.py`;
  Port/URL-Logik liegt in `app.py`). `WEB_PORT=5057` bleibt der Hub-reservierte Port.

## 7 · Test-Plan (alles auf Linux grün)

**Neu `tests/test_userpaths.py`:**
- `user_config_file`/`user_log_dir` respektieren `LUCENT_CONFIG_DIR`/`LUCENT_LOG_DIR`.
- Linux-Default via gepatchtem `HOME`/`XDG_CONFIG_HOME`/`XDG_STATE_HOME`.
- Verzeichnis existiert nach dem Aufruf.
- `pick_port(5057)`: gibt 5057 zurück wenn frei; belegt der Test 5057 mit einem Socket,
  kommt ein **anderer, freier** Port (> 0, ≠ 5057) zurück.
- `pick_port(0)`: liefert einen freien Port.
- `migrate_legacy_config`: kopiert nur, wenn Ziel fehlt und Quelle existiert; sonst No-op.

**Angepasst:**
- `tests/test_api.py` (3 Stellen): statt `monkeypatch.setattr(config, "CONFIG_JSON", …)`
  jetzt `monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))`.
- `tests/test_log.py`: auf die `userpaths`-Auflösung anpassen, falls es `config.LOG_DIR`
  direkt referenziert (sonst unverändert; `LUCENT_LOG_DIR`/`log_dir`-Arg bleiben gültig).

**Manuelle Verifikation:** App starten → URL-Banner erscheint; `config.json` landet im
Pro-Nutzer-Pfad; zweite Instanz bei belegtem 5057 startet auf freiem Port.

## 8 · Bewusste Spec-Abweichungen (diese Scheibe lässt aus)

- **waitress / lokaler WSGI-Server** — OUT (Robustheits-Layer). Flask-Dev-Server mit
  `threaded=True` bleibt.
- **Idle-Shutdown / sauberer Stop** — OUT (gehört zum AP-34-Tray-Lifecycle).
- **Session-Token in der URL** — DEFERRED (laut Spec „optional"; read-only mindert das
  Risiko, dass ein fremder Nutzer einen Port errät).
- **Windows-`%LOCALAPPDATA%`-Zweig** — implementiert, aber auf der Linux-Dev-Maschine
  nur per Logik testbar (kein Windows-Live-Lauf hier).
- **Shared read-only venv / signierte `run.ps1` / Betriebs-Doku** — OUT (Deployment-Layer).

## 9 · Risiken

- **TOCTOU bei `pick_port`**: minimales Zeitfenster zwischen Port-Ermittlung und
  `app.run()`-Bind; akzeptiert (Spec sieht das so vor).
- **Migration**: nur Kopie bei fehlendem Ziel — kein Überschreiben, kein Datenverlust.
- **Verhaltensänderung**: `config.json`/Logs ziehen vom App-Verzeichnis in den
  Nutzer-Pfad um. Migration fängt die Verbindungen ab; Logs starten neu (unkritisch).
