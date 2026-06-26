# Changelog

## [0.12.0] — 2026-06-26
### Changed
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

### Fixed
- **Leeres venv galt fälschlich als „vollständig":** `pip check` allein ist auf
  einem frisch gebauten, paketleeren venv vacuously grün — in Kombination mit
  einem noch passenden `.req_stamp` wäre der Install übersprungen worden (App
  hätte beim Import gecrasht). Der Vollständigkeits-Check prüft jetzt zusätzlich
  das tatsächliche Vorhandensein der Requirements. **Hinweis:** dieselbe latente
  Schwäche steckt in `run.ps1` (Windows) — dort zur Behebung vorgemerkt (Skript
  ist signiert, separate Session).

## [0.10.0] — 2026-06-26
### Added
- **AP-20 — Copy-Icon am SELECT:** In der oberen rechten Ecke des generierten
  SELECT sitzt ein Copy-Icon; ein Klick kopiert das SQL in die Zwischenablage
  (`navigator.clipboard`) mit kurzem „kopiert"-Feedback.

### Fixed
- **AP-21 — Kosmetik:** Der „Schema-Graph"-Balken (`.panelhead`) und die Tab-Linie
  (`.tabbar`) haben jetzt exakt dieselbe Höhe (gemeinsame `min-height` +
  `box-sizing`), vorher war der Graph-Balken minimal höher.

## [0.9.0] — 2026-06-26
### Changed
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
### Changed
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
### Added
- **AP-13 — UI-Politur:** Drei Verbesserungen in Objekt-Browser und Graph-Panel:
  (1) **Suchfeld** über dem Objekt-Browser filtert die Tabellen-/View-Listen live
  nach Namen; (2) **linker Splitter** macht die Sidebar-Breite per Drag verschiebbar
  (analog zum Graph-Splitter, via `--sidebar-width`); (3) **„Neu anordnen"-Button**
  im Graph-Panel würfelt das cose-Layout neu, dessen Abstände jetzt für dichte
  Schemas (> 12 Knoten) hochskalieren, damit Knoten weniger überlappen. Reines
  Frontend (`index.html`/`app.js`/`app.css`). Im Browser verifiziert (Playwright);
  115 Tests grün.

## [0.6.0] — 2026-06-26
### Added
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
### Changed
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
### Changed
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
### Changed
- **AP-9 — Ergebnisliste maximiert:** Die Ergebnistabelle unter dem Join-Builder
  nutzt jetzt den vollen vertikalen Restplatz nach unten (fixe `max-height: 320px`
  entfernt). Das Join-Builder-Panel ist eine Flex-Spalte; `#join_result` wächst
  mit (`flex: 1`, eigener Scroll). Auf das Join-Builder-Panel beschränkt, sodass
  Detail-Tabs ihren normalen Fluss behalten.

## [0.3.0] — 2026-06-26
### Added
- **AP-6 — Ausgabe-Steuerung im Join-Builder:** Auswahl der Ausgabezeilen
  (200 / 400 / Alle) plus „Aktualisieren"-Button im Ergebnisbereich.
  `/api/joinpath/run` akzeptiert nun `max_rows`; der Wert wird serverseitig
  auf `config.MAX_RESULT_ROWS` (5000) geklemmt — „Alle" heißt „alle bis zur
  Obergrenze" zum Schutz der Oberfläche. Die Antwort liefert `row_cap`; die
  Info-Zeile zeigt „N Zeilen (begrenzt auf …)". „Aktualisieren" liest das
  Formular neu (geänderte Sortierungen/Spalten) und behält den gewählten Pfad;
  ein Zeilenwechsel führt nur das aktuelle SELECT neu aus. Der hervorgehobene
  Join-Pfad im Graphen bleibt dabei stabil — Sortierungen/Zusatzspalten sind
  auf die Pfad-Tabellen beschränkt und ändern den Pfad nicht.
- **AP-7 — Feiner Graph-Zoom + Slider:** Mausrad-Zoom feinstufig
  (`wheelSensitivity` 0.2 statt 1, Zoom-Grenzen 10 %–400 %). Neuer vertikaler
  Zoom-Slider mit Prozent-Anzeige am rechten Graph-Rand, beidseitig
  synchronisiert (Scrollen ↔ Slider).

### Fixed
- **AP-8 — „Auswahl zurücksetzen":** Der Button bereinigt jetzt zusätzlich den
  hervorgehobenen Join-Pfad im Graphen (`hl`-Klassen) und schließt die
  UML-Karten darunter (`#uml_cards`) — vorher blieb beides stehen. Die interne
  Auswahl-Zurücksetzung (neue Selektion starten) lässt die Karten bewusst
  bestehen.

## [0.2.0] — 2026-06-26
### Added
- Join-Builder: tabellarischer **Ausgabebereich** unter dem generierten SELECT.
  Beim Wählen eines Join-Pfads wird das SQL angezeigt **und** ausgeführt; die
  zurückgelieferten Zeilen erscheinen als Tabelle (`#join_result`). Neuer
  read-only Endpoint `POST /api/joinpath/run`: das SELECT wird **serverseitig**
  aus den (validierten) Join-Parametern erzeugt (kein client-geliefertes SQL),
  parametrisiert ausgeführt und auf max. 200 Zeilen begrenzt
  (`core.datapreview.execute_select`). DRY-Refaktorierung der gemeinsamen
  Pfad-/SQL-Bau-Logik (`_parse_joinpath_params`, `_make_path_gen`).

## [0.1.0] — 2026-06-25
### Added
- FK-Graph aus Live-DB-Reflection (SQLAlchemy, SQLite + Postgres).
- Join-Pfad-Builder (k-kürzeste Pfade, deterministischer Tie-Break).
- Filterobjekte (WHERE über erreichbare Tabellen).
- Read-only SQL-Generierung mit parametrisierten Platzhaltern.
- Flask-Web-UI mit lokal gebundelten Assets.
- Portable Demo-CMDB (`sample_data/`): SQLite-DB + reproduzierbarer Generator,
  deckt mehrdeutige Pfade (Diamant), zusammengesetzte FKs, Graph-Sonderfälle
  (Selbstreferenz, Mehrfach-FK, isolierte Tabelle) und realistische Daten ab;
  inkl. Integrationstests pro Fall.
- Interaktives Menü in `run.sh` (ohne Argument) plus `run.ps1` für Windows mit
  identischem Menü; Flags (`--skip-setup` etc.) bleiben Hub-kompatibel.
- Filter-UI: „Filter +" fügt Filterzeilen hinzu (Tabelle · Spalte · Operator ·
  Wert · Entfernen); mehrere Filter werden mit UND verknüpft und an die
  bestehende, getestete Backend-Filterlogik (parametrisiertes WHERE) gesendet.
- Graph-Visualisierung: neuer `/api/graph`-Endpoint (Knoten/Kanten) und eine
  interaktive Schema-Graph-Ansicht mit Cytoscape.js (lokal gebundelt, keine
  CDN). Der gewählte Join-Pfad wird im Graph farblich hervorgehoben; die
  joinpath-Antwort liefert dazu die konkreten Pfad-Kanten.
- Implizite (geratene) Foreign Keys: optionale Heuristik (Spaltenname trifft
  einspaltige Primärschlüssel-Spalte einer anderen Tabelle, kompatibler Typ).
  Per Checkbox einschaltbar; gefundene Beziehungen erscheinen im Graph
  gestrichelt und ermöglichen Join-Pfade auch ohne deklarierte FKs. Loader/
  Modell führen jetzt Primärschlüssel-Infos. Neue FK-lose Demo-DB
  (`demo_cmdb_nofk.db`) zum Ausprobieren.

### Added
- Verbindungs-Manager (Tools → Verbindungen): strukturiertes Formular mit
  Datenbank-Typ-Auswahl (SQLite, PostgreSQL, MySQL/MariaDB, MS SQL Server) und
  passenden Feldern (Host/Port/DB/Benutzer/Passwort bzw. Dateipfad). Das
  Backend baut die SQLAlchemy-URL (`core.connection.build_url`) und testet die
  Verbindung (`/api/connect`). Passwort-Feld versteckt; die echte URL liegt in
  einem versteckten Feld, die Topbar zeigt sie maskiert. Benannte Verbindungen
  sind in `config.json` speicherbar (`/api/connections`, ohne Passwort).
  Treiber: psycopg2-binary, PyMySQL, pyodbc (MSSQL braucht zusätzlich System-
  ODBC: unixODBC + msodbcsql).

### Changed
- Info-Bereich in der Sidebar ans untere Ende gesetzt; die Info-Seite zeigt
  jetzt App-Metadaten (Name, Version, Ersteller) und den Technologie-Stack
  mit Versionen (Python/Flask/SQLAlchemy/NetworkX/Cytoscape.js) über den neuen
  `GET /api/info`-Endpoint, plus die Verbindungs-Übersicht.
- Layout-Feinschliff: senkrechte Trennlinie zwischen Hauptbereich und Graph
  ist per Drag verschiebbar; der Graph-Bereich ist standardmäßig 1/3 der
  Breite (Cytoscape skaliert beim Ziehen mit). Sidebar bekommt Kategorien
  „Tools" (Join-Builder) und „Info" (Übersicht: URL, Anzahl Tabellen/Views/FKs).
- Detail-Tabs haben jetzt Unter-Tabs „Definition" (Struktur), „Daten"
  (read-only Vorschau der ersten 100 Zeilen über den neuen `/api/data`-
  Endpoint) und „SQL" (rekonstruiertes CREATE-DDL bzw. View-Definition).
  Hinweis: Die Datenvorschau führt erstmals eine Abfrage aus — strikt
  read-only (`SELECT … LIMIT`), Objektname gegen das Schema validiert.
- UI-Redesign zum 3-Panel-Layout (wie ein minimalistischer SQL Developer):
  Objekt-Browser links (Tabellen + Views), Tab-Bereich in der Mitte mit festem
  „Join-Builder"-Tab plus dynamisch öffenbaren, schließbaren Detail-Tabs für
  Tabellen/Views, und der Schema-Graph als festes Panel rechts mit eigenem
  Scrolling (scrollt nicht mehr mit der Seite). Tabellen-Detail zeigt Spalten
  (Typ, PK) und Foreign Keys; View-Detail zeigt Spalten und die SQL-Definition.
- Views werden jetzt reflektiert; `/api/schema` liefert ein vollständiges
  Struktur-Format (Spalten mit Typ/PK, Foreign Keys, Views mit Definition).
  Demo-DBs enthalten zwei Beispiel-Views.
- UX: Connection-URL wird aus `default_connection` (config.json) vorbefüllt —
  standardmäßig die mitgelieferte Demo-DB, sodass „Schema laden" sofort
  funktioniert. Verdrahtet `core/settings.py` in die Index-Route.
- UX: Leere Connection-URL liefert eine klare Meldung statt der internen
  SQLAlchemy-„Could not parse URL"-Fehlermeldung.
