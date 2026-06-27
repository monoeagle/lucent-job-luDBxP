# Changelog

## [0.25.0] — 2026-06-27
### Changed
- **AP-42 — Join-builder polish:** the verbose per-branch fan-out warning text ("branch X is
  1-N (descending) — may multiply rows") is **gone** — direction already shows as an **N-1/1-N
  chip** on each join. Instead, one compact tile under the path list: "**1-N** may multiply rows
  (fan-out)", only when a path has a 1-N step. Saves noticeable space.
- **SQL box now wraps** instead of scrolling horizontally (`white-space: pre-wrap`). The wrap is
  purely **visual** — copy/paste yields the statement with its real line breaks, so it stays runnable.

## [0.24.2] — 2026-06-27
### Changed
- **Target node now amber/gold** instead of red: red was still too close to the orange path
  fill. Target = **amber (#f3b305) with dark text**, clearly distinct from start (green) and
  path (orange). Legend adjusted (so "target" is now also clearly different from "Analyzer:
  written"/red).

## [0.24.1] — 2026-06-27
### Fixed
- **Target hard to read in the graph:** the red target **ring** blended into the orange path
  fill. Endpoints are now **fully coloured** — start green, target red, intermediate orange —
  so they stand out clearly. Legend adjusted to filled squares.

## [0.24.0] — 2026-06-27
### Added
- **AP-41 — Per-step join type:** the join-builder now lets you pick the type **per join
  station** — **INNER** (default), **LEFT**, **RIGHT**, **FULL**. One dropdown per step above
  the SQL output; changing one rebuilds SQL **and** result. So e.g. start rows without a match
  are no longer dropped (LEFT instead of INNER). `sqlgen`/`/api/joinpath` + `/api/joinpath/run`
  accept `join_types` (positional; read-only execution stays parameterised). The **SQL Analyzer**
  already detected outer joins correctly (LEFT/RIGHT/FULL/CROSS).
### Fixed
- **Graph markers didn't match the legend:** building via the dropdowns left start/target
  uncoloured (all nodes the same). The graph now marks **start green / target red** (rings)
  even without click-selection — matching the legend. 194 tests green, 1 skipped.

## [0.23.0] — 2026-06-27
### Added
- **AP-40 — Graph legend** (small, top-left of the schema graph): explains the highlights —
  blue = Analyzer (read/joins), red = Analyzer (written), orange = join path, N-1/1-N = join
  direction, green/red ring = start/target.
### Fixed
- **Overlapping graph markers:** the join-builder path and the analyzer markers are now
  **mutually exclusive** — the blue analyzer trace disappears as soon as a join path is built
  (and vice versa). Previously blue nodes/edges lingered next to the orange path. Verified via
  Playwright. 190 tests green, 1 skipped.

## [0.22.0] — 2026-06-27
### Added
- **AP-39 — SQL Analyzer: structure/clause analysis, graph drawing, lints, complexity:**
  the analyzer now reads the sqlglot AST far more deeply (beyond type + read/written tables).
  New in the panel: **columns**, **joins** (type + ON), **filters (WHERE)**, **GROUP BY/HAVING**,
  **ORDER BY**, **DISTINCT/LIMIT**, a **structure counter** (tables/joins/subqueries/CTEs/UNION/
  window/aggregate/CASE) and a weighted **complexity score** (grade A–E). The **schema graph now
  draws the statement's JOIN edges** (not only colours the nodes). Extra schema-free static lints:
  `SELECT_STAR`, `LEADING_WILDCARD` (LIKE '%…'), `FUNC_ON_COLUMN`. Still **read-only — never executed**.
  `/api/analyze` returns the new fields. 190 tests green, 1 skipped.

## [0.21.0] — 2026-06-27
### Added
- **AP-38 — Copyable, runnable SQL (values inlined):** the SQL display and copy icon now
  produce **directly runnable** SQL — filter values are inlined as literals (numbers bare,
  strings single-quoted with `''` escaping; leading zeros and LIKE operands stay strings).
  A SELECT pasted into an external SQL editor runs as-is, without filling in `:p0` bind
  variables. The **parameterised** form (`:p0` + `params`) stays the internal read-only
  **execution** path (injection-safe); `/api/joinpath` returns both as `sql` and `sql_inline`.
  180 tests green, 1 skipped.

## [0.20.0] — 2026-06-27
### Added
- **AP-37 — Swap start ⇄ target:** new **⇄ button** next to the target dropdowns swaps
  start and target (table + column), mirrors the graph markers, and rebuilds immediately
  if a path was already shown. Handy because the **warning-free direction is often the
  reverse** (ascending toward a parent never fans out).
- **Docs:** fan-out page extended with **Example 3** (reading a long path → shorten the
  chain *or* filter the "many"-side table; rule of thumb + ⇄ hint).

## [0.19.0] — 2026-06-27
### Added
- **AP-36 — Per-join fan-out direction made visible:** every join step of a path now
  carries a **direction chip** — green `N-1` (ascending, safe) or amber `1-N`
  (descending, can multiply rows) — both in the **path list** and as a **label on the
  highlighted edge** in the schema graph. Makes it obvious that a path is a *mix* of
  N-1 and 1-N steps rather than "all descending". `/api/joinpath` now returns a per-path
  `steps` field (`left`/`right`/`to_many`) for this; the existing `.path-warn` box stays.
  172 tests green, 1 skipped.
- **Docs:** new reference page **Fan-out warning (1-N)** with worked examples, including a
  section explaining why both join directions warn while one step is still N-1.

## [0.18.0] — 2026-06-27
### Added
- **AP-25 — Read-only SQL-Statement-Analyzer:** New **SQL Analyzer** tab lets users
  paste any SQL statement; it is parsed by **sqlglot** (bundled locally, no CDN) and
  **never executed** against any database. Shows statement type (SELECT/INSERT/UPDATE/
  DELETE/DDL), read and written tables, and structural/schema warnings:
  `WRITE_STATEMENT`, `NO_WHERE` (UPDATE/DELETE without WHERE), `CARTESIAN_JOIN`
  (multi-table FROM without JOIN condition); with an active connection also
  `UNKNOWN_TABLE` and `UNKNOWN_COLUMN` (case-insensitive, schema-aware).
  Involved tables are highlighted in the schema graph (`analyze-read` / `analyze-write`
  CSS classes). Works with and without a database connection. 165 Tests grün, 1 skipped.

## [0.17.0] — 2026-06-27
### Added
- **AP-30 — N-1-Stern (Auto-Weaving, Fan-out-Warnung):** Select-/ORDER-BY-/Filter-
  Tabellen werden automatisch in den Join-Baum gewebt — stilles Verwerfen entfällt.
  Fehlende Tabellen (unerreichbar im FK-Graphen) lösen einen `NoPathError` aus.
  Absteigende (1-N) Join-Äste erzeugen eine **nicht-blockierende Fan-out-Warnung**
  pro Pfad (`warnings`-Feld in `/api/joinpath`); das Frontend zeigt diese als
  `.path-warn`-Box direkt am betroffenen Pfad an. 144 Tests grün, 1 skipped.

## [0.16.0] — 2026-06-27
### Added
- **AP-12 (Abschluss) — MSSQL-Verschlüsselungsfelder in der UI:** Im Verbindungs-Tab
  gibt es für **MS SQL Server** jetzt zwei Tri-State-Dropdowns **Verschlüsselung**
  (`Encrypt`) und **Server-Zertifikat vertrauen** (`TrustServerCertificate`), je
  **Standard / ja / nein**. „Standard" lässt den Parameter weg (nichts Unsicheres
  wird angenommen). Die Werte werden mit gespeicherten Verbindungen persistiert
  (`_CONN_FIELDS`, kein Secret) und beim Laden wiederhergestellt.
- **AP-12 real verifiziert:** Optionaler, skip-guardeter Integrationstest
  (`tests/test_mssql_integration.py`) gegen **SQL Server 2022** — provisioniert
  ein Schema mit FK und prüft die Reflection. Treiber `msodbcsql18` (ODBC Driver 18)
  + Instanz lokal eingerichtet; End-to-End im Browser bestätigt (ohne „vertrauen"
  scheitert die Verbindung am selbst-signierten Zertifikat, mit „ja" verbindet sie).

## [0.15.0] — 2026-06-26
### Added
- **AP-29 — SQL-Dialekt umschalten:** Der Join-Builder hat ein **Dialekt-Dropdown**
  (SQLite · PostgreSQL · MySQL · MSSQL · Oracle); das generierte read-only SELECT
  wird dialekt-treu gerendert:
  - **Identifier-Quoting** je Dialekt: `"x"` (SQLite/PG/Oracle), `` `x` `` (MySQL),
    `[x]` (MSSQL) — mit korrektem Escaping (schließendes Zeichen verdoppelt).
  - **Zeilenlimit** je Dialekt: `LIMIT n` (SQLite/PG/MySQL), `SELECT TOP n …`
    (MSSQL), `FETCH FIRST n ROWS ONLY` (Oracle).
  - Default-Dialekt aus der aktiven Verbindung abgeleitet; bei Änderung wird das
    SQL neu gerendert.
  - **Anzeige vs. Ausführung getrennt:** Das angezeigte SQL nutzt den gewählten
    Dialekt (zum Kopieren), die **Ausführung** (`/api/joinpath/run`) nutzt den
    Dialekt der *echten* Verbindung — generiertes SQL läuft also immer.
  - Umgesetzt als kleine `Dialect`-Schicht in `core/sqlgen.py` (keine neue
    Abhängigkeit); test-first, 12 neue Tests; **137 Tests grün**.
### Changed
- **Identifier werden jetzt immer quotiert** (auch im SQLite-Default): aus
  `SELECT VirtualMachine.VMID` wird `SELECT "VirtualMachine"."VMID"`. Korrekt und
  reserved-word-/case-sicher; Ausführung gegen SQLite unverändert gültig.

## [0.14.0] — 2026-06-26
### Changed
- **AP-14 (Teil 2, Linux) — Python-3.14-AppImage:** Der Linux-Pfad von AP-14 ist
  abgeschlossen — venv und AppImage laufen jetzt gegen **Python 3.14.6**:
  - **3.14 user-lokal** via `uv` beschafft (kein Root); alle 5 C-Extensions
    (sqlalchemy, greenlet, markupsafe, psycopg2-binary, pyodbc) liegen als
    **cp314-manylinux**-Wheels auf PyPI vor → venv-Neubau rein aus Wheels,
    **125 Tests grün** auf 3.14.
  - **AppImage gegen 3.14 gebaut & verifiziert** (HTTP 200; bundelt 3.14.6
    standalone, direkt geprüft).
- **AppImage-Fixes (`run.sh` AppRun):**
  - **Versions-bewusstes App-Update:** Der AppRun kopierte den App-Code bisher
    nur beim Erststart und aktualisierte nie → eine neuere AppImage führte stillen
    Alt-Code aus (real beobachtet: 0.1.0 statt der gebauten Version). Jetzt wird
    der Code bei Versionswechsel erneuert, **Nutzerdaten** (`config.json`, `Logs/`)
    bleiben erhalten (`.app_version`-Stamp).
  - **Browser:** AppRun öffnet bevorzugt **Chrome/Chromium** statt des
    Default-Browsers (vorher `xdg-open` → ggf. Firefox).
### Fixed
- **`run.sh` unter Python 3.14:** `re.split(..., 1)` löste einen
  `DeprecationWarning` aus (positionsbasiertes `maxsplit`) → auf `maxsplit=1`
  umgestellt.

## [0.13.0] — 2026-06-26
### Changed
- **AP-33 — Logging sauber gemacht:** `core/log.py` heilt das bisher minimale
  Logging (fix INFO, unbegrenzte Datei) zu einem konfigurierbaren, rotierenden
  Setup:
  - **Rotation:** `RotatingFileHandler` (`config.LOG_MAX_BYTES` ≈ 1 MB,
    `config.LOG_BACKUP_COUNT` = 5) statt unbegrenzt wachsender `app.log`.
  - **Level konfigurierbar:** `LUCENT_LOG_LEVEL` (DEBUG/INFO/…); `LUCENT_DEBUG`
    impliziert DEBUG; sonst `config.LOG_LEVEL` (INFO).
  - **Logpfad konfigurierbar:** `LUCENT_LOG_DIR` überschreibt `config.LOG_DIR` —
    der Hook für einen **Pro-Nutzer-Logpfad** (volle Terminal-Server-Verdrahtung
    bleibt AP-31).
  - **Idempotent + reconfigurierbar:** Handler werden bei jedem `init_logging`
    sauber ersetzt (keine Duplikate); Startup-Zeile mit App/Version/Level/Pfad.
  - **Request-Logging:** `web/`-App-Factory loggt jede Anfrage (Methode · Pfad ·
    Status · Dauer) via `after_request` — deutlich höhere Abdeckung. Layering
    gewahrt: `core/log.py` bleibt Flask-frei, der Hook liegt in `web/`.
  - 125 Tests grün (7 neue in `tests/test_log.py`, test-first).

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
