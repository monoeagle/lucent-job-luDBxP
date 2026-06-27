# AP-34 — Kern: Tray-Icon-Launcher (Variante A, Python)

**Datum:** 2026-06-27
**Status:** Design freigegeben → bereit für Implementierungsplan
**Umfang:** Kern-Scheibe von AP-34. Plattformübergreifend (Python); die Launcher-Logik
ist auf Linux headless testbar. Das Live-Log-Fenster und die signierte Verteilung sind
bewusst nicht Teil dieser Scheibe (siehe §9).

## 1 · Ziel & Nutzen

Der Nutzer soll **ein Icon klicken** und die App startet — **ohne selbst ein venv
einzurichten**. Auf Windows (und Linux) läuft die App über ein **Tray-Icon**: beim Start
automatisch den Browser öffnen, im Tray Version/URL anzeigen, die URL erneut öffnen und die
App **sauber beenden** (was den Port freigibt — löst die AP-31-Notiz, dass ein Port bis
Prozessende belegt bleibt).

**Auslieferung per Skript (kein `.exe`-Bau):** Das „eine Icon" ist eine Verknüpfung auf
`run.ps1 -Action tray`. `run.ps1` **baut das venv beim ersten Start automatisch** (reuse der
bestehenden adaptiven `Ensure-Venv`-Logik, AP-15 — legt das venv an und installiert die
Pakete) und startet anschließend den Tray-Launcher **fensterlos** (`pythonw -m launcher`).
Der Tray-Launcher selbst ist reines Python (Variante A); Variante B (PowerShell/.NET
NotifyIcon) ist verworfen. PowerShell ist hier ausdrücklich erlaubt; das Hinzufügen der
`tray`-Action erfordert eine **Re-Signatur** der signierten `run.ps1` (akzeptiert).

**Erfolgskriterien:**
- **Ein Klick genügt:** beim ersten Start wird das venv automatisch erzeugt + Pakete
  installiert; danach öffnet sich die App. Spätere Starts gehen direkt durch.
- Tray-Icon mit Menü **Im Browser öffnen · Info · Beenden**.
- Beim Start öffnet sich der Standardbrowser automatisch, sobald der Server antwortet.
- **Beenden** stoppt den App-Prozess → der Port wird frei.
- Kein dauerhaftes Konsolenfenster im Normalbetrieb (der Tray-Prozess läuft via `pythonw`;
  das `run.ps1`-Fenster zeigt nur beim erstmaligen venv-Aufbau kurz den Fortschritt und
  schließt dann).
- Launcher-Logik durch Tests + Controller-E2E auf Linux verifiziert; volle Suite grün.

## 2 · Architektur (Ansatz A1)

Neues App-Layer-Paket `launcher/` (peer zu `web/`, `app.py`; nutzt `config` +
`core.userpaths`; **kein** Web-Import — `app.py` wird als Kindprozess gestartet, nicht
in-process). Die testbare Logik ist von der nicht-headless-testbaren GUI getrennt:

```
launcher/
  __init__.py
  core.py       # LauncherCore — Logik, KEIN pystray-Import (headless testbar)
  tray.py       # build_tray(core) — pystray + Pillow, dünne GUI-Schale
  __main__.py   # Einstieg: core.start() + Auto-Browser-Thread + Tray-Loop
tests/test_launcher.py
```

Kanonischer Start: `python -m launcher` (Windows fensterlos via `pythonw.exe`).

## 3 · `launcher/core.py` — `LauncherCore`

```python
LauncherCore(host=config.WEB_HOST, opener=webbrowser.open)

  start() -> str
      # Port wählen (userpaths.pick_port(config.WEB_PORT, host) — 5057 bevorzugt, sonst frei),
      # app.py als Kindprozess starten mit env[LUCENT_PORT]=<port>; port/url merken; url zurückgeben.
      # Windows: subprocess.Popen(..., creationflags=CREATE_NO_WINDOW). sys.executable = (python|pythonw).

  wait_until_ready(timeout=20.0, interval=0.3) -> bool
      # GET self.url via urllib (stdlib, kurzer Timeout) bis HTTP-Antwort 200 → True; sonst bei Ablauf False.

  open_browser() -> None        # self._opener(self.url)
  is_running() -> bool          # self._proc is not None and self._proc.poll() is None
  stop(timeout=5.0) -> None     # Kind terminieren (SIGTERM→kill-Fallback) → Port frei
  info() -> dict                # {"name","version","url","port","running"}
```

Der Launcher **wählt den Port selbst** (reused `userpaths.pick_port` aus AP-31) und gibt ihn
per `LUCENT_PORT` an `app.py`; dadurch kennt er URL/Port sofort (Auto-Browser + Info) und
**besitzt den Prozess** (Beenden). `opener` ist injizierbar → headless testbar. Der App-Pfad
ist `config.BASE_DIR/app.py`, gestartet mit `sys.executable`.

## 4 · Prozess- & „Beenden"-Mechanik

`start()` spawnt `[sys.executable, <BASE_DIR>/app.py]` mit `env[LUCENT_PORT]=port`. „Beenden"
ruft `core.stop()` → `Popen.terminate()`, wartet bis `timeout`, sonst `kill()`. Mit dem
Prozessende wird der Port vom OS freigegeben. Danach `icon.stop()` + Programmende. Kein
Server-seitiger Stop-Endpoint nötig. (TOCTOU zwischen `pick_port` und dem Bind in `app.py`:
kleines Fenster, akzeptiert wie in AP-31.)

## 5 · Auslieferung: ein Icon → venv-Bootstrap → versteckter Start

- **Windows:** Verknüpfung-Ziel `run.ps1 -Action tray`. Neue Action **`tray`** → `Do-Tray`:
  `Ensure-Venv` (legt das venv bei Bedarf an + installiert Pakete; bestehende AP-15-Logik) →
  Tray-Launcher fensterlos starten: `Start-Process $VenvPythonw -ArgumentList '-m','launcher'`
  (pythonw = ohne Konsole). Der Kindprozess `app.py` startet mit `CREATE_NO_WINDOW`.
  Das `run.ps1`-Fenster ist nur beim erstmaligen venv-Aufbau kurz sichtbar (Fortschritt) und
  schließt, sobald der Tray-Prozess läuft.
- **Linux:** neue `run.sh`-Action **`--tray`** → `ensure_venv` + `python -m launcher`.
- `$VenvPythonw` = `venv\Scripts\pythonw.exe` (analog zum vorhandenen `$VenvPy`).
- Die Erstellung der Desktop-/Startmenü-Verknüpfung (Ziel `run.ps1 -Action tray`) wird auf der
  Betriebsseite dokumentiert; das automatisierte Ausrollen der Verknüpfung bleibt die
  Deployment-Scheibe.
- **`run.ps1` wird modifiziert** (neue `tray`-Action) → Re-Signatur nötig (akzeptiert).

## 6 · Tray + Info + Icon (`launcher/tray.py`)

`build_tray(core) -> pystray.Icon` mit Menü:
- **Im Browser öffnen** (default) → `core.open_browser()`
- **Info** → `icon.notify(...)` mit Name/Version/URL/Port (Ballon-Notification)
- **Beenden** → `core.stop(); icon.stop()`

Icon: zur Laufzeit mit **Pillow** gezeichnet (64×64, Markenfarbe `#2E6FAE`, Glyph „DB") — kein
Binär-Asset im Repo, später durch ein echtes `.png`/`.ico` ersetzbar.

## 7 · Abhängigkeiten (NO-CDN)

`requirements.txt` += `pystray>=0.19`, `Pillow>=10`. Passende **Wheels in `wheels/`** für das
Windows-Ziel (cp314, analog zu den vorhandenen win_amd64-Wheels); die Linux-Dev-Umgebung zieht
aus PyPI. Da `Ensure-Venv`/`run.sh` aus `requirements.txt` installieren, werden die neuen Pakete
beim **ersten** Tray-Start automatisch mitinstalliert — der Nutzer tut nichts. `core.py`
importiert **kein** pystray/Pillow (nur Stdlib) → Tests laufen ohne GUI-Backend.

## 8 · Test- & Verifikationsplan

- **`tests/test_launcher.py`** (kein pystray-Import):
  - `start` setzt `env["LUCENT_PORT"]` = gewählter Port und ruft `Popen` mit dem app.py-Pfad
    (Popen gemockt; Port ist int > 0).
  - `wait_until_ready` → True gegen einen Stub-HTTP-Server (http.server, 200) / False bei Timeout
    auf einen geschlossenen Port (kurzer Timeout).
  - `open_browser` ruft den injizierten Opener mit `core.url`.
  - `stop` terminiert einen echten Dummy-Kindprozess (`sys.executable -c "import time;time.sleep(30)"`)
    → `poll()` danach nicht `None`.
  - `info` liefert `version == config.APP_VERSION`, `url`, `port`.
- **Controller-E2E (Linux, headless, ohne Tray):** `LauncherCore.start()` startet echtes `app.py`
  (freier Port, temp `LUCENT_CONFIG_DIR`/`LUCENT_LOG_DIR`) → `wait_until_ready()` True → HTTP 200 →
  `stop()` → Port frei. Verifiziert die gesamte Kern-Integration ohne GUI.
- **Tray-Icon/Notify** (pystray/Pillow): headless **nicht** verifizierbar → manuell auf einem
  Desktop bzw. unter Windows später; in dieser Scheibe nicht abnahmeblockierend.
- **`run.sh --tray`** (Bash): Aktion verdrahtet (`ensure_venv` + `python -m launcher`);
  Controller prüft `bash -n run.sh` + dass die Aktion `python -m launcher` aufruft.
- **`run.ps1 -Action tray`** (PowerShell): auf der Linux-Dev-Maschine **nicht** ausführbar;
  textuell hinzugefügt (Re-Signatur + Live-Test später unter Windows).

## 9 · Bewusste Spec-Abweichungen

- **Log-Fenster** (Tkinter Live-Tail von `app.log`) — OUT (eigene Folge-Scheibe).
- **Chrome bevorzugt** → **Standardbrowser** via `webbrowser` (Nutzerentscheidung).
- **Info „aktive Verbindung":** server-seitig existiert keine globale aktive Verbindung
  (read-only; die Verbindung wird im Browser/pro Tab gewählt) → Info zeigt Name/Version/URL/Port.
- **Tray-Icon** zur Laufzeit generiert (Pillow) statt mitgeliefertem Asset.
- **Kein `.exe`-/Freeze-Bau** (organisatorisch nicht möglich) → Auslieferung per Skript
  (`run.ps1`-venv-Bootstrap). Subprozess-Modell (kein In-Process-Server) ausreichend.
- **Variante B (PowerShell/.NET NotifyIcon)** verworfen — der Launcher ist Python; PowerShell
  dient nur als Bootstrap (`run.ps1 -Action tray`). Die `tray`-Action **modifiziert `run.ps1`**
  → Re-Signatur nötig (akzeptiert).
- **Automatisches Ausrollen** der Startmenü-/Desktop-Verknüpfung bleibt die Deployment-Scheibe;
  hier nur Launcher + `tray`-Action + Doku der Verknüpfung.

## 10 · Risiken

- **Headless-Test der GUI** nicht möglich → Kernlogik ist isoliert + getestet; Tray manuell/Windows.
- **pystray-Backend** (Linux: AppIndicator/X11) wird zur Laufzeit benötigt, aber nicht von Tests.
- **pythonw-stdout** verschwindet (kein Konsolenfenster) → der Launcher hängt **nicht** am
  Parsen von `app.py`-stdout; er kennt den Port selbst. Logs gehen weiter in `app.log`.
