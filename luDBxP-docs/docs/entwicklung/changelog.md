# Changelog

## [0.14.0] — 2026-06-26
### Geändert
- **AP-14 (Teil 2, Linux) — Python-3.14-AppImage:** venv und AppImage laufen jetzt
  gegen **Python 3.14.6** (user-lokal via `uv`, kein Root; alle 5 C-Extensions als
  **cp314-manylinux**-Wheels → venv rein aus Wheels, 125 Tests grün). AppImage
  gegen 3.14 gebaut & verifiziert (HTTP 200, bundelt 3.14.6).
- **AppImage-Fixes (`run.sh` AppRun):** **versions-bewusstes App-Update** (Code wird
  bei Versionswechsel erneuert, Nutzerdaten `config.json`/`Logs/` bleiben — vorher
  lief stiller Alt-Code weiter, real 0.1.0 statt der gebauten Version); **Browser**
  öffnet bevorzugt Chrome/Chromium statt `xdg-open`-Default.
### Behoben
- **`run.sh` unter Python 3.14:** `re.split(..., 1)` (positionsbasiertes `maxsplit`)
  löste einen DeprecationWarning aus → `maxsplit=1`.

## [0.13.0] — 2026-06-26
### Geändert
- **AP-33 — Logging sauber gemacht:** `core/log.py` rotiert jetzt (`RotatingFileHandler`,
  ~1 MB × 5) statt unbegrenzter `app.log`; Level via `LUCENT_LOG_LEVEL`
  (`LUCENT_DEBUG` ⇒ DEBUG), Logpfad via `LUCENT_LOG_DIR` (Pro-Nutzer-Hook;
  volle Terminal-Server-Verdrahtung bleibt AP-31). `init_logging` ist idempotent
  + reconfigurierbar (Handler-Ersatz) mit Startup-Zeile. Neu: **Request-Logging**
  (Methode · Pfad · Status · Dauer) in der `web/`-App-Factory — Layering gewahrt
  (`core/log.py` bleibt Flask-frei). 125 Tests grün (7 neue, test-first).

## [0.12.0] — 2026-06-26

### Geändert

- **AP-15 (Teil 2, Linux) — `run.sh` abbruchsicher + idempotent (Parität zu
  `run.ps1`):** Der Linux-Launcher heilt sich nach abgebrochenen Läufen selbst.
  Jeder Schritt prüft seine Vorbedingungen und meldet seinen Status
  (`_ok`/`_warn`/`_info`/`_hdr`/`_fail`):
  - **venv-Integrität statt nur Existenz** (`venv_healthy`: `python -c import sys`);
    ein halbes/kaputtes venv wird automatisch neu gebaut.
  - **Echter Paket-Vollständigkeits-Check:** `pip check` **plus** Vorhandensein
    jeder in `requirements.txt` gelisteten Distribution (`importlib.metadata`) —
    fängt sowohl abgebrochene Installs als auch ein frisch gebautes, leeres venv.
  - **Atomarer Stamp:** `.req_stamp` wird erst **nach** erfolgreichem Install
    geschrieben; ein abgebrochener Install wiederholt sich beim nächsten Lauf.
  - **Port-/Instanz-Check** vor App-Start (5057 belegt via `ss`/`lsof` → klare
    Abbruch-Meldung statt Crash).
  - **Robustes Menü:** ein fehlgeschlagener Schritt beendet das Menü nicht mehr
    (Subshell-Isolierung, bash-Pendant zum try/catch).
  - **Exit-Codes nicht mehr verschluckt:** das `|| true` in `do_start`/
    `do_skip_setup` entfernt; der App-Exit-Code wird sauber durchgereicht.
  - **`--debug`-Flag** (Pendant zu `run.ps1 -DebugMode`, setzt `LUCENT_DEBUG=1`).
- **AP-15 / NO-CDN auf Linux (adaptiv):** Installation versucht zuerst **strikt
  offline** aus `wheels/` (`--no-index`-Dry-Run-Probe, kein Netz). Deckt das
  Wheelhouse die Plattform ab → Offline-Install; sonst — z. B. die gebundelten
  `win_amd64`/cp314-Wheels auf Linux — **lauter** Fallback auf Online-pip (kein
  stilles Nachladen). Schaltet automatisch auf offline, sobald ein passendes
  Linux-Wheelhouse vorliegt.

### Behoben

- **Leeres venv galt fälschlich als „vollständig":** `pip check` allein ist auf
  einem frisch gebauten, paketleeren venv vacuously grün — in Kombination mit
  einem noch passenden `.req_stamp` wäre der Install übersprungen worden (App
  hätte beim Import gecrasht). Der Vollständigkeits-Check prüft jetzt zusätzlich
  das tatsächliche Vorhandensein der Requirements. **Hinweis:** dieselbe latente
  Schwäche steckt in `run.ps1` (Windows) — dort zur Behebung vorgemerkt (Skript
  ist signiert, separate Session).

## [0.10.0] — 2026-06-26

### Hinzugefügt

- **AP-20 — Copy-Icon am SELECT:** In der oberen rechten Ecke des generierten
  SELECT sitzt ein Copy-Icon; ein Klick kopiert das SQL in die Zwischenablage
  (`navigator.clipboard`) mit kurzem „kopiert"-Feedback.

### Behoben

- **AP-21 — Kosmetik:** Der „Schema-Graph"-Balken (`.panelhead`) und die Tab-Linie
  (`.tabbar`) haben jetzt exakt dieselbe Höhe (gemeinsame `min-height` +
  `box-sizing`), vorher war der Graph-Balken minimal höher.

## [0.9.0] — 2026-06-26

### Geändert

- **AP-12 (Backend) — MS SQL Server: ODBC-Treiber & Verschlüsselung
  konfigurierbar, klare Treiber-Fehlermeldung:** `build_url` nutzt jetzt
  standardmäßig den aktuellen **ODBC Driver 18 for SQL Server** (überschreibbar
  per `driver`) und unterstützt optionale `Encrypt`/`TrustServerCertificate`-
  Parameter — nichts Unsicheres wird per Default angenommen. Fehlt der ODBC-
  Treiber, meldet die App das klar (AP-2-Stil) statt einer rohen pyodbc-Exception
  (`_odbc_driver_hint`: IM002 / „no default driver" / „Can't open lib"). Installations-
  Doku ergänzt. 118 Tests grün. (Realer Integrationstest gegen eine MSSQL-Instanz
  und UI-Felder für Encrypt/Trust folgen separat.)

## [0.8.0] — 2026-06-26

### Geändert

- **AP-15 (Teil 1, Windows) — `run.ps1` abbruchsicher + idempotent:** Der
  Windows-Launcher heilt sich nach abgebrochenen Läufen selbst. Jeder Schritt
  prüft seine Vorbedingungen (Python, venv-Integrität per Funktionstest,
  Paket-Vollständigkeit per `pip check`, freier Port) und zieht nur Fehlendes
  nach; der Requirements-Stamp wird erst nach erfolgreichem Install geschrieben
  (atomar). **NO-CDN / nur lokale Sourcen:** Installation strikt `--no-index`
  aus `wheels\` mit `--dry-run`-Vorabprüfung — fehlt ein Wheel, steigt das Setup
  mit Protokoll (welche Pakete fehlen) aus, **ohne etwas zu installieren oder
  online nachzuladen**. Neu außerdem: durchgängige Status-Ausgaben, Port-Check
  vor App-Start (5057 belegt → klare Meldung) und ein gegen Einzelfehler robustes
  Menü. Verifiziert: idempotenter Lauf, fehlender Stamp, fehlendes Wheel, belegter
  Port. (`run.sh`/Linux-Parität folgt separat.)

## [0.7.0] — 2026-06-26

### Hinzugefügt

- **AP-13 — UI-Politur:** Drei Verbesserungen in Objekt-Browser und Graph-Panel:
  (1) **Suchfeld** über dem Objekt-Browser filtert die Tabellen-/View-Listen live
  nach Namen; (2) **linker Splitter** macht die Sidebar-Breite per Drag verschiebbar
  (analog zum Graph-Splitter, via `--sidebar-width`); (3) **„Neu anordnen"-Button**
  im Graph-Panel würfelt das cose-Layout neu, dessen Abstände jetzt für dichte
  Schemas (> 12 Knoten) hochskalieren, damit Knoten weniger überlappen. Reines
  Frontend (`index.html`/`app.js`/`app.css`). Im Browser verifiziert (Playwright);
  115 Tests grün.

## [0.6.0] — 2026-06-26

### Hinzugefügt

- **AP-10 — Gespeicherte Verbindungen in der Topbar:** Neues Dropdown in der
  Topbar (neben „Verbinden") listet die in `config.json` gespeicherten
  Verbindungen; eine Auswahl verbindet sofort — passwortlose Verbindungen
  (SQLite oder Server ohne Auth) direkt, sonst öffnet sich der Verbindungs-Tab
  vorbefüllt zum Ergänzen des Passworts. Beide Verbindungs-Picker (Topbar +
  Verbindungs-Tab) teilen dieselbe Liste und spiegeln die Auswahl. Ein
  Verbindungswechsel setzt den UI-Zustand zurück (Detail-Tabs schließen,
  Graph-Highlight/UML-Karten leeren, Schema neu laden). Reines Frontend
  (`index.html`/`app.js`/`app.css`); die `/api/connections`-API blieb unverändert.
  Im Browser verifiziert (Playwright/Chromium); 114 Tests grün.

## [0.5.0] — 2026-06-26

### Geändert

- **AP-11 — Composite Foreign Keys voll unterstützt:** Mehrspaltige FKs werden
  nicht mehr nur auf dem ersten Spaltenpaar gejoint. Ein FK trägt jetzt alle
  `(lokal, referenziert)`-Spaltenpaare (`ForeignKey.column_pairs`, mit Properties
  `columns`/`ref_columns`/`is_composite`); der Join-Pfad-Generator emittiert
  `JOIN … ON a.x = b.x AND a.y = b.y`. Zwei **separate** einspaltige FKs zwischen
  denselben Tabellen bleiben weiterhin alternative Join-Wege (nicht mit AND
  verschmolzen). Betroffen: Loader, FK-Graph (`JoinEdge`), Pathfinder
  (`JoinStep.column_pairs`), SQL-Generator, DDL-Ansicht und `/api/schema`
  (FKs jetzt als `columns`/`ref_columns`-Listen, Frontend angepasst). 112 Tests grün.

## [0.4.0] — 2026-06-26

### Geändert

- **AP-14 — Python-3.14-Readiness (Windows):** Das Offline-Wheelhouse (`wheels/`)
  wurde von der CPython-3.12- auf die **3.14-ABI** umgestellt. Die fünf
  kompilierten Wheels (SQLAlchemy, psycopg2-binary, pyodbc, greenlet, MarkupSafe)
  liegen jetzt als `cp314-win_amd64` vor — identische Paketversionen, nur neuer
  ABI-Tag; die `py3-none-any`-Wheels bleiben versionsunabhängig. Die Launcher
  `run.ps1` (Offline-Gate) und `run.sh` (Präferenzreihenfolge) verlangen bzw.
  bevorzugen jetzt Python 3.14; `wheels/README.md` entsprechend aktualisiert.
  Verifiziert: venv mit Python 3.14.6, Offline-Setup aus `wheels/`, `pip check`
  sauber, alle **111 Tests grün**, App startet (HTTP 200).

## [0.3.1] — 2026-06-26

### Geändert

- **AP-9 — Ergebnisliste maximiert**: Die Ergebnistabelle unter dem Join-Builder
  nutzt jetzt den vollen vertikalen Restplatz nach unten (fixe `max-height: 320px`
  entfernt). Das Join-Builder-Panel ist eine Flex-Spalte; `#join_result` wächst
  mit (`flex: 1`, eigener Scroll). Auf das Join-Builder-Panel beschränkt, sodass
  Detail-Tabs ihren normalen Fluss behalten.

## [0.3.0] — 2026-06-26

### Hinzugefügt

- **AP-6 — Ausgabe-Steuerung im Join-Builder**: Auswahl der Ausgabezeilen
  (200 / 400 / Alle) plus „Aktualisieren"-Button im Ergebnisbereich.
  `/api/joinpath/run` akzeptiert nun `max_rows`; der Wert wird serverseitig auf
  `config.MAX_RESULT_ROWS` (5000) geklemmt — „Alle" heißt „alle bis zur
  Obergrenze" zum Schutz der Oberfläche. Die Antwort liefert `row_cap`; die
  Info-Zeile zeigt „N Zeilen (begrenzt auf …)". „Aktualisieren" liest das
  Formular neu (geänderte Sortierungen/Spalten) und behält den gewählten Pfad;
  ein Zeilenwechsel führt nur das aktuelle SELECT neu aus. Der hervorgehobene
  Join-Pfad im Graphen bleibt stabil, da Sortierungen/Zusatzspalten auf die
  Pfad-Tabellen beschränkt sind.
- **AP-7 — Feiner Graph-Zoom + Slider**: Mausrad-Zoom feinstufig
  (`wheelSensitivity` 0.2 statt 1, Zoom-Grenzen 10 %–400 %) plus vertikaler
  Zoom-Slider mit Prozent-Anzeige am rechten Graph-Rand, beidseitig
  synchronisiert (Scrollen ↔ Slider).

### Behoben

- **AP-8 — „Auswahl zurücksetzen"**: Der Button bereinigt jetzt zusätzlich den
  hervorgehobenen Join-Pfad im Graphen (`hl`) und schließt die UML-Karten
  darunter (`#uml_cards`) — vorher blieb beides stehen. Der interne
  Auswahl-Reset (neue Selektion starten) lässt die Karten bewusst bestehen.

## [0.2.0] — 2026-06-26

### Hinzugefügt

- **AP-5 — Tabellarischer Ausgabebereich im Join-Builder**: Beim Wählen eines
  Join-Pfads wird das generierte SELECT angezeigt **und** ausgeführt; die
  zurückgelieferten Zeilen erscheinen als Tabelle unter dem SQL. Neuer
  read-only Endpoint `POST /api/joinpath/run`: das SELECT wird **serverseitig**
  aus den validierten Join-Parametern erzeugt (kein client-geliefertes SQL),
  parametrisiert ausgeführt und auf max. 200 Zeilen begrenzt
  (`core.datapreview.execute_select`). Gemeinsame Pfad-/SQL-Bau-Logik in
  `_parse_joinpath_params` + `_make_path_gen` (von beiden Endpoints geteilt).

## [0.1.0] — 2026-06-25

### Hinzugefügt

- **FK-Graph** aus Live-DB-Reflection (SQLAlchemy, SQLite + PostgreSQL).
- **Join-Pfad-Builder** (k-kürzeste Pfade, deterministischer Tie-Break).
- **Filterobjekte** (WHERE über erreichbare Tabellen).
- **Read-only SQL-Generierung** mit parametrisierten Platzhaltern.
- **Flask-Web-UI** mit lokal gebundelten Assets.
- **Portable Demo-CMDB** (`sample_data/`): SQLite-DB + reproduzierbarer Generator,
  deckt mehrdeutige Pfade (Diamant), zusammengesetzte FKs, Graph-Sonderfälle
  (Selbstreferenz, Mehrfach-FK, isolierte Tabelle) und realistische Daten ab;
  inkl. Integrationstests pro Fall.
- **Interaktives Menü** in `run.sh` (ohne Argument) plus `run.ps1` für Windows mit
  identischem Menü; Flags (`--skip-setup` etc.) bleiben Hub-kompatibel.
- **Filter-UI**: „Filter +" fügt Filterzeilen hinzu (Tabelle · Spalte · Operator ·
  Wert · Entfernen); mehrere Filter werden mit UND verknüpft und an die
  bestehende, getestete Backend-Filterlogik (parametrisiertes WHERE) gesendet.
- **Graph-Visualisierung**: neuer `/api/graph`-Endpoint (Knoten/Kanten) und eine
  interaktive Schema-Graph-Ansicht mit Cytoscape.js (lokal gebundelt, kein CDN).
  Der gewählte Join-Pfad wird im Graph farblich hervorgehoben; die
  joinpath-Antwort liefert die konkreten Pfad-Kanten.
- **Implizite (geratene) Foreign Keys**: optionale Heuristik (Spaltenname trifft
  einspaltigen Primärschlüssel einer anderen Tabelle, kompatibler Typ).
  Per Checkbox einschaltbar; gefundene Beziehungen erscheinen im Graph
  gestrichelt und ermöglichen Join-Pfade auch ohne deklarierte FKs. Neue
  FK-lose Demo-DB (`demo_cmdb_nofk.db`) zum Ausprobieren.
- **Verbindungs-Manager** (Tools → Verbindungen): strukturiertes Formular mit
  Datenbank-Typ-Auswahl (SQLite, PostgreSQL, MySQL/MariaDB, MS SQL Server) und
  passenden Feldern. Das Backend baut die SQLAlchemy-URL (`core.connection.build_url`)
  und testet die Verbindung (`/api/connect`). Benannte Verbindungen speicherbar
  in `config.json` (ohne Passwort).

### Geändert

- **Info-Bereich** in der Sidebar ans untere Ende gesetzt; zeigt App-Metadaten und
  Technologie-Stack via `GET /api/info`.
- **3-Panel-Layout** (wie ein minimalistischer SQL Developer): Objekt-Browser links,
  Tab-Bereich Mitte, Schema-Graph rechts mit eigenem Scrolling.
- **Views** werden reflektiert; `/api/schema` liefert Spalten + SQL-Definition.
- **Detail-Tabs**: „Definition", „Daten" (Vorschau erste 100 Zeilen via `/api/data`),
  „SQL" (rekonstruiertes DDL).
- **UX**: Connection-URL aus `default_connection` vorbelegt — Demo-DB direkt startbereit.

### Bekannte Einschränkungen

- **Composite Foreign Keys**: Schemas mit Mehrspaltigen FKs werden in v1 nur auf der
  ersten Spalte gejoint; einspaltigen FKs sind vollständig unterstützt.
- **Datenbank-Backends**: PostgreSQL-Support ist implementiert, aber in der
  automatisierten Testsuite nur gegen SQLite abgedeckt.
