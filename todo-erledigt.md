# Erledigte Arbeitspakete — LucentTools DB Explorer

Abgeschlossene APs (umgehängt aus `todo.md`). Offene APs stehen in `todo.md`.

---

## AP-31 (Kern) — Multi-User-Basis: dynamischer Port + Pro-Nutzer-Pfade (v0.33.0)
- [x] **Neues `core/userpaths.py`** (pur, stdlib-only, kein Flask/`config`-Import): Pro-Nutzer-Pfade (XDG/`%LOCALAPPDATA%`, Slug `luDBxP`), `pick_port`/`resolve_port`, `migrate_legacy_config`
- [x] **Dynamischer Port pro Session:** ohne `LUCENT_PORT` erst 5057 (Hub), sonst freier Port; `LUCENT_PORT=<n>` fest, `=0` dynamisch; tatsächliche URL beim Start ausgegeben; Bind nur `127.0.0.1`
- [x] **Pro-Nutzer `config.json` + Logs** (`core/settings.py`/`core/log.py` umgestellt; Overrides `LUCENT_CONFIG_DIR`/`LUCENT_LOG_DIR`); App-Verzeichnis-`config.json` wird einmalig übernommen
- [x] **`run.sh`/`run.ps1`** brechen bei belegtem Port nicht mehr ab → `app.py` wählt freien Port
- [x] TDD (13 neue userpaths-Tests, 220 grün); Controller-verifiziert (2 Instanzen: 5057-Fallback, fester/dynamischer Port, Migration, nur 127.0.0.1); SDD mit Per-Task-Reviews + Final-Review (opus)
- [ ] **Offen (eigene Scheiben):** lokaler WSGI-Server (waitress), Idle-Shutdown/sauberer Stop, shared read-only venv / signierte run.ps1 / Betriebs-Doku

---

## AP-45 — Ergebnis-Hilfen Teil 2: Spaltenkopf-Aktionen + DISTINCT-Filterwerte (v0.32.0)
- [x] **`/api/distinct`** (read-only): `SELECT DISTINCT col FROM table WHERE col IS NOT NULL ORDER BY col`,
      spalten-validiert gegen das reflektierte Schema, begrenzt auf `config.DISTINCT_LIMIT`,
      best-effort (leere Liste bei jedem Fehler — wie `/api/orphan_check`)
- [x] **`/api/joinpath/run`** liefert zusätzlich **`columns_meta`** (Tabelle/Spalte je Ausgabespalte
      in Selektionsreihenfolge) → eindeutiges Spalten→Quell-Mapping auch bei gleichnamigen Spalten
- [x] **Spaltenkopf-Menü** in `renderJoinResult` (`th.th-actionable`): Sortieren ASC/DESC (legt
      ORDER-BY-Zeile an, baut neu), Als Filter (füllt Filterzeile vor, fokussiert Wertfeld),
      Spalte entfernen (nur Zusatzspalten; Start/Ziel-Anker deaktiviert)
- [x] **Filter-Wertfeld** mit `<datalist>` aus `/api/distinct` (`_updateFilterValueField` +
      `_loadFilterDistinct`, Cache je (Tabelle,Spalte)); Freitext bleibt möglich
- [x] 5 neue API-Tests (TDD: rot→grün), **205 grün** (1 skipped); Playwright-verifiziert
      (12 UI-Checks: Menü, Sortieren, Als-Filter, DISTINCT-Liste, Anker-Schutz, Spalte-entfernen)

## AP-49 — Analyzer-Feinschliff + ANSI-Fix (v0.31.0)
- [x] Eingabe-Textbox per Default größer (`#an_sql` min-height 17rem), weiterhin nur vertikal verstellbar
- [x] read-only-Hinweis als grünes Badge (`.an-readonly`), abgesetzt neben „Analysieren"
- [x] **Fix:** ANSI-Escape-Codes (`_ANSI_RE`) aus `parse_error` entfernt — kein `□[4m…`-Müll mehr
- [x] Parsefehler-Layout: Label + mehrzeiliger Fehler/SQL-Ausschnitt im `.an-parse-error`-Block (pre-wrap)
- [x] Regressionstest (parse_error ANSI-frei), 200 grün; Playwright-verifiziert (Höhe 272px, Badge, sauberer Fehler)

## AP-48 — SQL-Analyzer: größere Eingabe + Tippfehler-Lint (v0.30.0)
- [x] Eingabe-Textbox größer (~14 Zeilen, volle Breite) und **nur vertikal** verstellbar (`resize: vertical`, CSS `#an_sql`)
- [x] Lint `SUSPICIOUS_ALIAS`: Alias mit Edit-Distanz ≤1 zu LEFT/RIGHT/INNER/OUTER/FULL/CROSS → „möglicher Tippfehler im Join-Typ" (fängt `LEFTI`, das sqlglot als Alias schluckt)
- [x] Grenze dokumentiert: sqlglot bleibt tolerant; echte Syntaxfehler (fehlendes `"`) werden gefangen, nicht jeder Tippfehler ist einer
- [x] 2 Tests, 199 grün; Playwright-verifiziert (resize=vertical, LEFTI-Warnung sichtbar)

## AP-47 — Pfad-Auswahl-Indikator + Waisen-Chip pro Join-Typ (v0.29.0)
- [x] Pfad-Liste: `[*]`/`[ ]` statt Bullets (`_markActivePath`), aktiver Pfad hervorgehoben; aktualisiert beim Wechsel
- [x] read-only Endpoint `/api/orphan_check`: je Schritt NOT-EXISTS-Probe links/rechts → `{left_orphans,right_orphans}`
- [x] Frontend: datengetriebener Chip `⚠ LEFT/RIGHT/FULL` pro Join-Schritt (gecacht je Pfad, Reset bei frischem Build) + best-effort Option-Tönung
- [x] 2 API-Tests (Flags + Text-Mode-leer), 197 grün; Playwright-verifiziert (Marker wandert, Chips matchen Backend-Flags)

## AP-46 — Detailkarten folgen der Join-Builder-Auswahl (v0.28.0)
- [x] `#uml_area` initial versteckt (CSS `display:none`) → Graph zentriert wenn nichts gewählt
- [x] `_updateUmlAreaVisibility()`: zeigt Area bei Auswahl/Karten, sonst versteckt; CY.resize() bei Sichtbarkeitswechsel
- [x] Frischer Build öffnet Start+Ziel-Karten (auch bei Dropdown-Auswahl, nicht nur Graph-Doppelklick) + markiert Spalten (`_updateUmlMarks`)
- [x] Verdrahtet in showUmlCard/_updateGraphNodeMarkers/clearSelectionAndCards/drawGraph
- [x] Playwright-verifiziert (leer=versteckt, Build=2 Karten Cluster/OperatingSystem + markierte Spalten, Reset=versteckt)

## AP-44 — Join-Builder kompakter + Ergebnis-Hilfen (v0.27.0)
- [x] Zwei Button-Zeilen → eine (`.jb-controls`); 1-N-Info als absolute Kachel oben rechts (keine eigene Zeile); engere Row-Abstände + kompakteres SQL-Feld → mehr Tabellenhöhe
- [x] NULL-Zellen hervorgehoben (`.null-cell`) — Outer-Join-/Waisen-Zeilen sofort sichtbar
- [x] Statuszeile: Zeilen · Join-Typ · Fan-out (z. B. „8 Zeilen · LEFT · ⚠ 1-N")
- [x] Playwright-verifiziert (eine Steuer-Zeile, Kachel absolut top-right, 2 NULL-Zellen, Info-Text)
- [ ] Folge-Scheibe **AP-45**: Spaltenkopf-Aktionen (Sort/Filter/Spalte entfernen) + Filter-Dropdown mit echten DISTINCT-Werten (neues read-only Endpoint)

## AP-43 — Lesbares mehrzeiliges SQL-Layout (v0.26.0)
- [x] `core/sqlgen.py`: eine Spalte/Zeile, jeder JOIN eigene Zeile mit `ON`/`AND` darunter, `=` ausgerichtet (Composite-Keys via ljust-Padding)
- [x] WHERE mehrzeilig (`WHERE …` / `  AND …`); ORDER BY/LIMIT unverändert
- [x] Copy/Anzeige-Variante (`sql_inline`) endet mit `;` (paste-and-run); ausgeführtes `sql` ohne — Run-Endpoint verifiziert (10 Zeilen)
- [x] Soft-Wrap-Bedenken geklärt: Umbruch war rein visuell (echte `\n` bleiben); neues Format macht lange Zeilen ohnehin überflüssig
- [x] 10 Format-Test-Assertions angepasst + Semikolon-Test; 195 grün; Playwright (Format + kein H-Scroll + Copy mit `;`)

## AP-42 — Join-Builder-Politur (v0.24.1–v0.25.0)
- [x] Verbose Fan-out-Warntext pro Ast entfernt (Richtung steht als N-1/1-N-Chip am Join)
- [x] Eine kompakte Kachel „1-N kann Zeilen vervielfachen (Fan-out)" unter der Pfadliste, nur bei vorhandenem 1-N
- [x] SQL-Fenster `white-space: pre-wrap` + `overflow-wrap` → kein H-Scroll; Copy/Paste behält echte Zeilenumbrüche (Playwright: 5 Newlines, JOINs intakt)
- [x] Ziel-Knoten amber/gold (#f3b305) statt rot + dunkle Schrift (v0.24.2); Endpunkte voll eingefärbt (v0.24.1)
- [x] Demo-CMDB um Waisen ergänzt, damit Outer Joins sichtbar werden (INNER 4 → LEFT 5)

## AP-41 — Join-Typ pro Schritt + Start/Ziel-Color-Fix (v0.24.0)
- [x] `core/sqlgen.py`: `generate_sql(join_types=…)` — pro Schritt INNER/LEFT/RIGHT/FULL (`_JOIN_KEYWORDS`); ungültiger Typ → ValueError; Default INNER
- [x] `/api/joinpath` + `/api/joinpath/run` nehmen `join_types` (positionsweise); read-only-Ausführung bleibt parametrisiert
- [x] Frontend: pro Join-Station ein Dropdown (`#jb_join_types`) über der SQL; Änderung → `runBuild(true)` mit `join_types`; Reset bei frischem Build
- [x] **Fix:** Graph färbt Start grün / Ziel rot auch beim Bauen über Dropdowns (GRAPH_SEL aus Formular gespiegelt) — passend zur AP-40-Legende
- [x] Analyzer erkennt Outer Joins bereits korrekt (LEFT/RIGHT/FULL/CROSS) — kein Handlungsbedarf
- [x] +4 Tests (3 sqlgen + 1 api), 194 grün; Playwright-verifiziert (LEFT JOIN im SQL, Start/Ziel-Marker)

## AP-40 — Graph-Legende + Fix überlagernde Marker (v0.23.0)
- [x] Kleine Legende oben links im Schema-Graph (blau=Analyzer gelesen/Joins, rot=geschrieben, orange=Join-Pfad, N-1/1-N=Richtung, grün/rot Rahmen=Start/Ziel)
- [x] `clearGraphHighlights()` — Join-Pfad- und Analyzer-Marker wechselseitig exklusiv; blaue Spur verschwindet beim Join-Bauen (und umgekehrt); auch „Auswahl zurücksetzen" räumt alles
- [x] Playwright-verifiziert (nach Join-Bauen: analyze-Marker 0, hl-Kanten vorhanden; Legende sichtbar)

## AP-39 — SQL-Analyzer vertieft (Struktur/Klauseln/Graph/Lints/Komplexität) (v0.22.0)
- [x] `core/sqlanalyze.py`: Klausel-/Strukturextraktion aus AST — `columns`, `joins` (kind+ON), `edges`, `filters`, `group_by`, `having`, `order_by`, `distinct`, `limit`, `structure`-Zähler
- [x] Komplexitäts-Score (gewichtet: Joins/Subqueries/CTEs/UNION/Window/Aggregate/CASE) + Note A–E
- [x] Statische Lints ohne DB: `SELECT_STAR`, `LEADING_WILDCARD` (LIKE '%…'), `FUNC_ON_COLUMN`
- [x] `/api/analyze` liefert alle neuen Felder; Frontend-Panel mit Sektionen (Spalten/Joins/Filter/Sortierung/Gruppierung/Struktur/Komplexität)
- [x] Schema-Graph zeichnet die JOIN-Kanten des Statements (`analyze-edge`), nicht nur Knoten-Färbung
- [x] read-only — nie ausgeführt; 10 neue Tests, 190 grün; Playwright-verifiziert (Panel + Graph-Kanten)
- [ ] Spätere Scheiben (Roadmap): AP-40 Indexanalyse (Loader-Index-Reflection), AP-41 EXPLAIN-Plan (opt-in, read-only)

## AP-38 — Kopierbares, lauffähiges SQL (Werte eingesetzt) (v0.21.0)
- [x] `core/sqlgen.py`: `GeneratedSQL.sql_inline` — Filterwerte als Literale (Zahlen roh, Strings `'…'` mit `''`-Escaping, führende Nullen & LIKE als String); `_inline_literal`/`_looks_numeric`
- [x] `:p0` + `params` bleiben die parametrisierte read-only-Ausführungsschiene
- [x] `/api/joinpath` liefert `sql` **und** `sql_inline`
- [x] UI zeigt/kopiert `sql_inline` (Copy-Icon übernimmt den Box-Text); Execution unverändert über Body
- [x] 8 neue Tests (7 sqlgen inline + 1 api), 180 grün; Playwright: Box `= 1`, Clipboard ohne `:p0`

## AP-37 — Start ⇄ Ziel tauschen (v0.20.0)
- [x] ⇄-Knopf neben den Ziel-Dropdowns; tauscht Start/Ziel (Tabelle + Spalte)
- [x] Spiegelt Graph-Marker (`sel-source`/`sel-target`) und baut bei vorhandenem Pfad neu
- [x] Fan-out-Doku um Beispiel 3 erweitert (langen Pfad lesen → verkürzen oder Filter auf Viele-Seite)
- [x] Playwright-verifiziert (Swap tauscht Werte korrekt, kein Console-Error)

## AP-36 — Fan-out-Richtung pro Join sichtbar (v0.19.0)
- [x] `/api/joinpath` liefert pro Pfad ein `steps`-Feld (`left`/`right`/`to_many`)
- [x] Pfad-Liste: Richtungs-Chip pro Join — grün `N-1` (sicher) / gelb `1-N` (Fan-out)
- [x] Schema-Graph: hervorgehobene Kanten tragen Richtungs-Label (`N-1`/`1-N`) + Farbe
- [x] Referenzseite „Fan-out-Warnung (1-N)" mit durchgerechneten Beispielen + Abschnitt „Warum beide Richtungen warnen"
- [x] Test `test_joinpath_steps_carry_direction`; Playwright-verifiziert (Chips + CY-Kantenlabels)

## AP-E01 — Core-Domänenmodell
- [x] `core/model.py`: Schema, Table, Column, ForeignKey, View — typisiertes Domänenmodell

## AP-E02 — SchemaLoader-ABC + Stub-Loader
- [x] `core/schema_loader.py`: abstrakte `SchemaLoader`-Basisklasse
- [x] Stub-Loader: `manual_loader.py`, `schemaspy_loader.py`, `ddl_loader.py`

## AP-E03 — SQLAlchemy-Live-Reflection-Loader
- [x] `core/loaders/sqlalchemy_loader.py`: Live-Reflection über SQLAlchemy `inspect()`
- [x] Engine-Disposal auf Fehler-Pfad; Engine-Caching vermieden (read-only)

## AP-E04 — FK-Graph (NetworkX)
- [x] `core/graph.py`: `build_graph()` → NetworkX `DiGraph` mit join-Kanten
- [x] FK-Kanten tragen `from_col`/`to_col`-Metadaten

## AP-E05 — Pathfinder (k-kürzeste Pfade, BFS)
- [x] `core/pathfinder.py`: `find_paths()` mit deterministischem k-Pfad-BFS
- [x] Filter-Einwebung: Filter-Tabellen als Join-Baum einweben (keine Duplikat-Tabellen)

## AP-E06 — SQL-Generator (read-only, parametrisiert)
- [x] `core/sqlgen.py`: `generate_sql()` → SELECT … JOIN mit `?`-Platzhaltern
- [x] Werte nie direkt in SQL-String eingebettet

## AP-E07 — Implizite FKs (SchemaSpy-Heuristik)
- [x] `core/implied.py`: `guess_implicit_fks()` — Spaltenname-vs-PK-Heuristik
- [x] Nur typkompatible Kandidaten; im Graph als gestrichelte Kanten

## AP-E08 — Flask-API + Flask-Factory
- [x] `app.py`: App-Factory-Pattern
- [x] `web/routes.py`: `/api/schema`, `/api/joinpath`, `/api/graph`, `/api/data`, `/api/connect`, `/api/connections/*`
- [x] 400-Fehler bei fehlenden Feldern / ungültiger Connection; defensiv gehärtet

## AP-E09 — Filter-UI
- [x] Tabelle / Spalte / Operator / Wert / AND-Verknüpfung verdrahtet
- [x] Filter-Zeilen dynamisch hinzufügen/entfernen

## AP-E10 — Graph-Visualisierung (Cytoscape.js)
- [x] Cytoscape.js 3.30.2 lokal gebundelt (`web/static/lib/`)
- [x] Schema-Graph mit FK-Kanten; Join-Pfad-Highlight; gestrichelte Kanten für implizite FKs
- [x] Verschiebbarer Graph-Splitter

## AP-E11 — 3-Panel-Layout + Detail-Sub-Tabs
- [x] Objekt-Browser (links) · Tabs-Bereich (Mitte) · Graph-Panel (rechts)
- [x] Detail-Sub-Tabs: Join-Builder, Filter, Datenvorschau, DDL, Info
- [x] Sidebar-Tabs: Tools, Info

## AP-E12 — Datenvorschau
- [x] `core/datapreview.py`: `fetch_rows()` — erste 100 Zeilen jeder Tabelle/View
- [x] HTML-Tabelle in Detail-Sub-Tab

## AP-E13 — Views-Support
- [x] Views werden wie Tabellen geladen und im Objekt-Browser angezeigt
- [x] Join-Pfade können Views als Zwischenstationen verwenden

## AP-E14 — Verbindungs-Manager (Multi-DB)
- [x] Formular: DB-Typ (SQLite/PostgreSQL/MySQL/MSSQL), Host, Port, Name, User, Passwort
- [x] `core/connection.py`: `build_url()` → SQLAlchemy-Connection-URL
- [x] `core/settings.py`: Verbindungen persistent ohne Passwort speichern

## AP-E15 — run.sh-Menü + run.ps1
- [x] `run.sh`: interaktives Menü (start/stop/status/demo/logs) + direkte Flags (`--start`, `--demo`)
- [x] `run.ps1`: gleiches Menü für Windows PowerShell

## AP-E16 — Demo-CMDB
- [x] `sample_data/build_demo_db.py`: portable Demo-CMDB mit Diamond-Pfaden, zusammengesetzten FKs, Selbstreferenz, isolierten Tabellen
- [x] `sample_data/demo_cmdb.db` (mit FK-Constraints)
- [x] `sample_data/demo_cmdb_nofk.db` (ohne FK-Constraints, für implizite-FK-Tests)

## AP-E17 — Projektposter (A0)
- [x] `tools/make_poster.py`: A0-Poster-Generator (Matplotlib)
- [x] `mail/LucentDBExplorer-Projektposter-A0.pdf` + `.jpg`

## AP-E18 — Dokumentation (Zensical)
- [x] `luDBxP-docs/`: vollständige Zensical-Doku (Grundlagen, Referenz, Entwicklung, Projekt)
- [x] Architektur-Diagramme (Mermaid, lokal gerendert)
- [x] Datenmodell, UseCases, Testing, Projektstruktur, Changelog

## AP-E19 — AppImage
- [x] `build/LucentDBExplorer-0.1.0-x86_64.AppImage`: portables Linux-AppImage
- [x] `build/appimage/LucentDBExplorer.AppDir/`: AppDir-Struktur mit AppRun-Script

## AP-1 — Interaktive Pfad-Auswahl direkt im Graph (UML-Tabellenkarte)
- [x] Doppelklick auf Cytoscape-Knoten → UML-Tabellenkarte im Graph-Panel einblenden (Spalten, Typen, PK-Badge)
- [x] Erste Spaltenwahl = Quelle, zweite Spaltenwahl (andere Tabelle) = Ziel; visuelle Markierung
- [x] Bei vollständiger Quelle+Ziel: `/api/joinpath` automatisch aufrufen
- [x] Graph-Highlight des berechneten Join-Pfads (rote Kanten/Knoten)
- [x] Join-Builder-Tab öffnet sich automatisch und füllt Start-/Ziel-Felder + Spalten-Selects (Zweiweg-Sync Graph ↔ Join-Builder)
- [x] Statuszeile im Graph-Panel zeigt aktuelle Quelle/Ziel-Auswahl + „Auswahl zurücksetzen"-Button
- [x] Betroffen: `web/static/js/app.js` (Graph-Interaktion, UML-Karte, Join-Builder-Sync)

## AP-2 — „Verbinden" liefert „failed to fetch" (untersucht + entschärft)
- [x] Systematisch reproduziert (Playwright, beide Verbinden-Wege): bei laufendem Server fehlerfrei — **kein Code-Bug**
- [x] Root Cause: nicht erreichbarer Dev-Server (beim Session-Handoff gestoppt) → `fetch()` wirft die rohe Meldung „Failed to fetch"
- [x] Defense-in-depth-Fix: `postJSON` fängt den Netzwerkfehler ab und zeigt „Server nicht erreichbar — läuft LucentTools DB Explorer? Starte die App mit bash run.sh …" statt „Failed to fetch"
- [x] Verifiziert via Playwright (`route.abort`): klare Meldung statt „Failed to fetch"; 81 Tests grün

## AP-4 — Mehrere SELECT-Spalten
- [x] „Weitere Spalten +"-Bereich im Join-Builder (Tabelle.Spalte-Zeilen, analog Filter)
- [x] `extra_selects` an `/api/joinpath`; Validierung gegen `schema.has_column`
- [x] Pro Join-Pfad: SELECT = Start + Ziel + Zusatzspalten, deren Tabelle auf *diesem* Pfad liegt (jedes SQL bleibt gültig)
- [x] Tests (sqlgen 3 Selections; API: erscheint im SQL / off-path weggelassen / unbekannte Spalte 400)

## AP-5 — Tabellarischer Ausgabebereich im Join-Builder (v0.2.0)
- [x] Ergebnis-Container `#join_result` unter dem generierten SELECT
- [x] Pfad-Klick zeigt SQL **und** führt es read-only aus → Ergebnistabelle (Spalten + Zeilen, NULL kursiv)
- [x] Neuer Endpoint `POST /api/joinpath/run` (gleiche Join-Parameter + `path_index`); SQL serverseitig via `generate_sql`, kein client-SQL
- [x] `core/datapreview.py::execute_select()` — parametrisiertes read-only SELECT, harte Zeilen-Obergrenze (200)
- [x] DRY: `_parse_joinpath_params` + `_make_path_gen` von `api_joinpath` und Run-Endpoint geteilt
- [x] 3 neue API-Tests (Spalten/Zeilen, Zeilen-Cap, unbekannte Spalte 400); 109 Tests grün

## AP-9 — Ergebnisliste unter dem Join-Builder maximieren (v0.3.1)
- [x] Fixe `max-height: 320px` entfernt; `#join_result` füllt den vertikalen Restplatz (`flex: 1`, eigener Scroll)
- [x] Join-Builder-Panel als Flex-Spalte, auf `panel[data-tab=joinbuilder]` beschränkt (Detail-Tabs unberührt)
- [x] Verifiziert (Playwright): `max-height:none`, `flex-grow:1`, Tabelle bis ~13 px an die Panel-Unterkante

## AP-6 — Ausgabe-Steuerung: Zeilen-Auswahl + Aktualisieren (v0.3.0)
- [x] Zeilen-Auswahl 200 / 400 / Alle (`#jb_rows`) im Ergebnisbereich
- [x] „Aktualisieren"-Button (`#jb_refresh`): liest Formular neu (Sortierung/Spalten), behält gewählten Pfad
- [x] `/api/joinpath/run` nimmt `max_rows`, klemmt auf `config.MAX_RESULT_ROWS` (5000); „Alle" = bis Obergrenze; Antwort liefert `row_cap`
- [x] Info-Zeile „N Zeilen (begrenzt auf …)"; Graph-Pfad bleibt stabil (Sortierung/Spalten ändern den Pfad nicht)
- [x] 2 neue API-Tests (max_rows-Cap + row_cap); 111 Tests grün

## AP-7 — Feiner Graph-Zoom + Zoom-Slider (v0.3.0)
- [x] Mausrad-Zoom feinstufig (`wheelSensitivity` 0.2), Zoom-Grenzen 10 %–400 %
- [x] Vertikaler Zoom-Slider mit %-Anzeige (`#zoom_ctrl`) am rechten Graph-Rand
- [x] Beidseitige Synchronisation (Scrollen ↔ Slider) via `CY.on("zoom", …)` + Slider-`input`

## AP-8 — Fix „Auswahl zurücksetzen" bereinigt Graph + Karten (v0.3.0)
- [x] Button löscht jetzt Pfad-Highlight (`hl`) und schließt UML-Karten (`#uml_cards`)
- [x] Interner Selektions-Reset (neue Auswahl) lässt Karten bewusst stehen
- [x] Verifiziert (Playwright): 5 hl-Elemente + 1 Karte vor Reset → 0/0 nach Reset

## AP-3 — SQL-Optionen-Paket (Join-Builder)
- [x] DISTINCT (Checkbox)
- [x] ORDER BY (Tabelle.Spalte + ASC/DESC, mehrere; pro Pfad auf Pfad-Tabellen gefiltert)
- [x] LIMIT (Zahlenfeld; nur positive Ganzzahl)
- [x] WHERE-Erweiterungen: IS NULL / IS NOT NULL (kein Wert), IN (n parametrisierte Werte), BETWEEN (2 Werte)
- [x] UI rendert Wertfelder je Operator dynamisch; read-only + Named-Placeholder
- [x] 20 neue Tests (sqlgen + API); 106 Tests grün

## AP-11 — Composite Foreign Keys voll unterstützt (v0.5.0)
- [x] `ForeignKey` trägt alle Spaltenpaare (`column_pairs`; Properties `columns`/`ref_columns`/`is_composite`); `ForeignKey.single()` für einspaltige FKs
- [x] Loader: ein `ForeignKey` pro Constraint (composite intakt) statt Zerlegung pro Spalte
- [x] FK-Graph: `JoinEdge`-Objekte je FK — separate FKs bleiben alternative Join-Optionen (nicht verschmolzen)
- [x] Pathfinder `JoinStep.column_pairs` (deterministisch orientiert); SQL-Generator emittiert `ON … AND …` über alle Paare
- [x] DDL-Ansicht + `/api/schema` (FK als `columns`/`ref_columns`-Listen) + `app.js`-Anzeige angepasst
- [x] Tests: composite joint alle Paare (sqlgen-Unit + Demo-CMDB end-to-end), Mehrfach-FK bleibt alternativ (Regressionsschutz), API-Format; 112 grün
- [x] Doku: CLAUDE.md „Bekannte Einschränkungen" + Zensical `referenz/datenmodell.md`

## AP-10 — Gespeicherte Verbindungen in der Topbar (v0.6.0)
- [x] Dropdown `#topbar_conn` in der Topbar (neben „Verbinden") listet die gespeicherten Verbindungen
- [x] Auswahl verbindet direkt (`connectSaved` → `/api/connect`); passwortlos sofort, sonst Verbindungs-Tab vorbefüllt + Hinweis
- [x] Zweiweg-Sync: beide Picker (Topbar + Verbindungs-Tab) teilen die Liste (`refreshSavedConnections`) und spiegeln die Auswahl (`syncConnSelectors`)
- [x] Verbindungswechsel setzt UI zurück (Detail-Tabs, Graph-Highlight, UML-Karten, Schema) — über bestehendes `doConnect`/`drawGraph`
- [x] Frontend `index.html`/`app.js`/`app.css`; `/api/connections`-API unverändert (war bereits vorhanden)
- [x] Tests: DOM-Picker + connect-from-saved-Round-Trip (114 grün); UI im echten Browser verifiziert (Playwright/Chromium, Screenshot)

## AP-20 — Copy-Icon am SELECT (v0.10.0)
- [x] Copy-Icon (inline-SVG) oben rechts in der Ecke des generierten SELECT (`.sql-wrap`/`#sql_copy`)
- [x] Klick → SELECT in die Zwischenablage (`navigator.clipboard.writeText`); kurzes „copied"-Feedback; Event-Delegation (überlebt Re-Render)
- [x] Im Browser verifiziert (Playwright: Clipboard-Inhalt == SELECT)

## AP-21 — Kosmetik: gleiche Höhe Schema-Graph-Balken & Tab-Linie (v0.10.0)
- [x] `.panelhead` und `.tabbar` exakt gleich hoch (gemeinsame `min-height: 34px` + `box-sizing: border-box`)
- [x] Im Browser verifiziert (Playwright: panelhead == tabbar == 34px, Differenz 0)

## AP-13 — UI-Politur (v0.7.0)
- [x] Suchfeld `#obj_search` über dem Objekt-Browser filtert Tabellen/Views live nach Namen (`applyObjectFilter`, überlebt `renderSidebar`)
- [x] Linker Splitter `#splitter_left` macht die Sidebar-Breite verschiebbar (`--sidebar-width`, analog Graph-Splitter)
- [x] „Neu anordnen"-Button im Graph-Panel (`runGraphLayout`); cose-Abstände skalieren für dichte Schemas (> 12 Knoten) hoch (weniger Überlappung)
- [x] Frontend `index.html`/`app.js`/`app.css`; im Browser verifiziert (Playwright: Filter, Splitter 240→392px, Re-Layout), 115 Tests grün

## AP-15 (Teil 2, Linux) — `run.sh` abbruchsicher + idempotent (v0.12.0)
- [x] **Parität zu `run.ps1`:** Prereq-Check pro Schritt, durchgängige Status-Helfer (`_ok`/`_warn`/`_info`/`_hdr`/`_fail` waren schon da, jetzt im ganzen Setup-Pfad genutzt)
- [x] **venv-Integrität statt nur `[ -d ]`** (`venv_healthy`: `python -c import sys`); halbes/kaputtes venv wird automatisch neu gebaut (Stamp dabei invalidiert)
- [x] **Echter Paket-Vollständigkeits-Check:** `pip check` **plus** `importlib.metadata`-Prüfung jeder `requirements.txt`-Distribution; atomarer Stamp (erst nach Erfolg)
- [x] **NO-CDN adaptiv:** `--no-index`-Dry-Run-Probe gegen `wheels/`; offline wenn plattform-kompatibel, sonst **lauter** Online-Fallback (kein stilles Nachladen). win_amd64/cp314-Wheels greifen auf Linux nicht → Online; schaltet automatisch auf offline, sobald ein Linux-Wheelhouse vorliegt
- [x] **Port-/Instanz-Check** (`ss`/`lsof`) vor App-Start; **`|| true` entfernt** → App-Exit-Code wird durchgereicht; **robustes Menü** (Subshell-Isolierung); **`--debug`-Flag** (= `-DebugMode`)
- [x] **Bug gefunden+gefixt:** leeres venv galt via vacuous `pip check` fälschlich als „vollständig" → Install übersprungen, App-Crash. (Gleiche Schwäche in `run.ps1` → **AP-35** vorgemerkt.)
- [x] Verifiziert auf Linux: idempotenter Lauf · Port belegt (sauberer Abbruch) · kaputtes/leeres venv (Self-Heal + Online-Fallback, manylinux-Wheels) · 118 Tests grün via `run.sh --tests`
- [ ] **Linux-Doc-Schuld (gebündelt):** Zensical-Site-Rebuild (siehe AP-16-Rest)

## AP-33 — Logging sauber gemacht (v0.13.0)
- [x] **Rotation:** `RotatingFileHandler` (`config.LOG_MAX_BYTES` ≈ 1 MB · `LOG_BACKUP_COUNT` 5) statt unbegrenzter `app.log`
- [x] **Level konfigurierbar:** `LUCENT_LOG_LEVEL`; `LUCENT_DEBUG` ⇒ DEBUG; sonst `config.LOG_LEVEL` (INFO)
- [x] **Logpfad konfigurierbar:** `LUCENT_LOG_DIR` überschreibt `config.LOG_DIR` — Hook für Pro-Nutzer-Pfad
- [x] **Abdeckung:** Startup-Zeile (App/Version/Level/Pfad) + **Request-Logging** (Methode·Pfad·Status·Dauer) via `after_request` in `web/`
- [x] **Idempotent + reconfigurierbar** (Handler-Ersatz statt Early-Return); Layering gewahrt (`core/log.py` Flask-frei)
- [x] Test-first: 7 neue Tests in `tests/test_log.py`; **125 Tests grün**. Betroffen: `core/log.py`, `web/__init__.py`, `config.py`
- [ ] **An AP-31 übergeben:** volle Terminal-Server-Verdrahtung des Pro-Nutzer-Logpfads (z. B. `%LOCALAPPDATA%`) — hier nur der ENV-Hook gebaut

## AP-12 — MS SQL Server real testbar (Backend v0.9.0 · Abschluss v0.16.0)
- [x] **Backend (v0.9.0):** ODBC Driver 18 als Default + `Encrypt`/`TrustServerCertificate` in der URL (`_mssql_query`); klare Treiber-Fehlermeldung (`_odbc_driver_hint`); Setup-Doku
- [x] **System-ODBC (Linux-Devbox):** `msodbcsql18` + ODBC Driver 18 registriert; MSSQL via **rootless podman** (SQL Server 2022) — Docker/containerd-Konflikt umgangen
- [x] **Integrationstest real grün** (`tests/test_mssql_integration.py`, `LUCENT_MSSQL_TEST_URL`): provisioniert Parent/Child + FK, reflektiert via App-Loader, prüft die FK-Kante; skippt sauber ohne ENV. Voller Pfad ODBC 18 → pyodbc → SQLAlchemy → Core-Modell verifiziert
- [x] **UI-Felder (v0.16.0):** Verbindungs-Tab hat für MSSQL Tri-State-Dropdowns Verschlüsselung/Server-Zertifikat-vertrauen (Standard/ja/nein); `formParams` reicht durch; persistiert in `_CONN_FIELDS`. Test-first (Persistenz-Test), Playwright-verifiziert: ohne „vertrauen" Cert-Fehler, mit „ja" verbindet → 5 Tabellen aus `master` reflektiert. 138 grün
- [x] **Einschränkung „MSSQL nur gegen SQLite getestet" aufgehoben**

## AP-29 — SQL-Dialekt umschalten (v0.15.0)
- [x] **Dialect-Schicht** in `core/sqlgen.py` (hand-gerollt, keine neue Dependency): 5 Dialekte SQLite/PostgreSQL/MySQL/MSSQL/Oracle
- [x] **Identifier-Quoting** je Dialekt (`"…"` / `` `…` `` / `[…]`) mit Escaping (schließendes Zeichen verdoppeln); `dialect_for(db_type)`-Resolver, SQLite-Fallback
- [x] **Zeilenlimit** je Dialekt: `LIMIT n` · `SELECT TOP n …` (MSSQL) · `FETCH FIRST n ROWS ONLY` (Oracle)
- [x] **Web:** `/api/joinpath` akzeptiert `dialect`; Default aus der Verbindung abgeleitet (`_dialect_from_url`). **Ausführung** (`/api/joinpath/run`) nutzt den Dialekt der echten Verbindung → generiertes SQL läuft immer. UI-Dropdown in der Optionszeile, re-rendert bei Änderung
- [x] **Verhaltensänderung:** Identifier werden jetzt immer quotiert (auch SQLite-Default); bestehende `test_sqlgen`/`test_api`-Assertions nachgezogen
- [x] Test-first: `tests/test_sqlgen_dialect.py` (12 Tests); **137 grün**. Playwright-verifiziert (SQLite/MSSQL/Oracle/MySQL-Ausgabe + Ausführung). Betroffen: `core/sqlgen.py`, `web/routes.py`, `web/static/js/app.js`
- [x] sqlglot **nicht** nötig (Unterschiede klein & bounded) — für AP-25 (Analyzer/Parsing) aufgehoben

## AP-17 — Delivery-Verzeichnis bereinigen · VERWORFEN (2026-06-26)
- [x] **Gestrichen:** Auslieferung läuft über **GitHub-Releases** (`tools/build_release.py` → bereinigtes ZIP ohne Dev-/KI-Spuren; Releases v0.11.2/v0.11.3). Ein separates Delivery-Verzeichnis ist damit obsolet.

## AP-22 — Implizite FKs standardmäßig aktivieren? · ENTSCHIEDEN: NEIN (2026-06-26)
- [x] **Default bleibt OFF (opt-in).** Begründung: das Tool lebt von korrekten, vertrauenswürdigen Join-Pfaden; Default-ON würde geratene Beziehungen mit echten FKs vermischen. Implizite FKs bleiben bewusste Opt-in-Entscheidung (Checkbox `include_implied`, im Graph gestrichelt-lila abgehoben).

## AP-24 — Session-KPIs erheben & dokumentieren? · ENTSCHIEDEN (2026-06-26)
- [x] **Erfüllt:** KPI-Erhebung ist etablierte Handoff-Konvention (`docs/session-kennzahlen.md`, Schema aus `.pattern/session-handoff-kpi.pattern`).
- [x] **Dev-intern:** bleibt im Entwickler-Repo, **nicht** in der öffentlichen Zensical-Site (enthält Modell-/Token-/Subagenten-Infos).
- [ ] **Laufend:** fehlende Sessions (Session 4 Windows + aktuelle Linux-Sessions) beim **nächsten Handoff** nachtragen.

## AP-14 — Python-3.14-Readiness (v0.4.0 Windows · v0.14.0 Linux/AppImage)
- [x] **Windows (v0.4.0):** alle 5 C-Ext als cp314-win_amd64-Wheels ins Wheelhouse; `run.ps1`/`run.sh` auf 3.14 gegated; 3.14.6 via winget; offline-Setup ✓
- [x] **Linux/AppImage (v0.14.0):** Python 3.14.6 **user-lokal via `uv`** (kein Root); alle 5 C-Ext als **cp314-manylinux**-Wheels auf PyPI → venv-Neubau rein aus Wheels, **125 Tests grün** auf 3.14
- [x] **AppImage gegen 3.14 gebaut & verifiziert:** HTTP 200, bundelt 3.14.6 standalone (direkt geprüft); via projekteigenem `run.sh --appimage` (dogfoodt AP-15-Adaptiv-Install)
- [x] **AppRun-Fix — versions-bewusstes Update:** kopierte App bisher nur beim Erststart → führte stillen Alt-Code aus (real: 0.1.0 statt gebauter Version); jetzt Code-Refresh bei Versionswechsel, Nutzerdaten (`config.json`/`Logs/`) bleiben (`.app_version`-Stamp)
- [x] **AppRun-Fix — Browser:** öffnet bevorzugt Chrome/Chromium statt `xdg-open`-Default (Firefox)
- [x] **`run.sh`-Fix:** `re.split(...,1)` → `maxsplit=1` (3.14-DeprecationWarning)
- [ ] **Optional (offen):** explizite Lock-/Constraints-Datei mit exakten Versionen (requirements.txt hat nur `>=`)

## AP-23 — Join-Builder-Maske vereinheitlicht (v0.11.0)
- [x] Alle Dropdowns gleiche Breite (`--jb-ctrl-w: 150px`), alle Steuerelemente gleiche Höhe (`--jb-ctrl-h: 30px`); Start/Ziel/Filter/Sortier-/Spalten-Zeilen fluchten (Einrückung `padding-left`)
- [x] Alle Aktions-Buttons gleich groß (`min-width: 140px`, einheitliche Höhe/Rand); Zeilen-Löschbuttons (`.f-del`/`.ob-del`/`.c-del`) als einheitliche kleine Quadrate
- [x] Inline-Styles aus `app.js` entfernt (Margins/Breiten zentral ins CSS); Aktions- und Optionsleiste in zwei klare Zeilen aufgeteilt; Label „Weitere Spalten +" → „Spalten +"
- [x] Wertfelder je Operator (`=`, `IN`, `BETWEEN` zwei Boxen, `IS NULL` ohne) bleiben einheitlich ausgerichtet
- [x] `web/static/js/app.js` + `web/static/css/app.css`; im Browser verifiziert (Playwright, Demo-CMDB, Screenshots), 118 Tests grün
- [x] **Politur (gleiche Runde):** Copy-Icon liegt jetzt *in* der SELECT-Box statt im pre-Default-Margin auf dem Rand (`.sql_out { margin:0 }`, Abstand auf `.sql-wrap`, Icon-Inset 10/12px)
- [x] **Politur:** Default-Graphbreite `--graph-width` 50vw → 38vw, damit das mittlere Panel mehr Platz hat
- [x] **Politur:** Graph zentriert/füllt zuverlässig — Fenster-Resize-Autofit (`setupGraphAutofit`), kleineres Fit-Padding (`GRAPH_FIT_PAD=16`), engeres `componentSpacing` (FK-lose Einzelknoten dehnen die Bounding-Box nicht mehr auf)

## AP-16 — Graph entzerren: minimale Linienkreuzungen (v0.11.0)
- [x] Layout von force-directed `cose` auf **hierarchisches dagre** (Sugiyama, layered) umgestellt — der FK-Graph ist gerichtet, dagre minimiert Kantenkreuzungen
- [x] `dagre` 0.8.5 **lokal gebündelt** unter `web/static/lib/` (NO-CDN: kein Laufzeit-CDN; `<script>` cytoscape → dagre → app). `runGraphLayout` treibt **`window.dagre` direkt** (Graph bauen, `dagre.layout`, Knotenpositionen setzen) — der Adapter `cytoscape-dagre` wurde evaluiert und wieder **entfernt** (ungenutzt)
- [x] **Sicherheits-Audit der Lib** (auf Wunsch): kein `fetch`/XHR/WebSocket/EventSource/sendBeacon, kein `eval`/`Function()`/Blob/Worker, keine externen String-URLs (nur Doku-Kommentare), `require` nur Browserify-intern — reine lokale Layout-Berechnung
- [x] Parameter: `rankdir:"BT"` (referenzierte Tabellen oben), `ranker:"network-simplex"`, adaptive `nodesep`/`ranksep`; deterministisch → „Neu anordnen" setzt nach manuellem Ziehen zurück
- [x] **Entscheidung gerade vs. geknickte Kanten:** Routing rang-überspringender Kanten über dagres Knickpunkte (`curve-style:segments`) erreicht **0 Kreuzungen**, lässt die Verbindungen aber als Zickzack schlechter aussehen → **verworfen**. Bewusst **gerade Linien** mit **1 Kreuzung** (`Cluster→Host × Datacenter→Network`, topologiebedingte transitive Kante) — bessere Lesbarkeit (Nutzerwunsch)
- [x] Verifiziert (Playwright, Demo-CMDB): Kreuzungen **6 (Grid-Fallback) → 1** (Polylinien-Schnitt-Zähler), keine Konsolen-/Page-Fehler, sauberes Schichten-Layout; 118 Tests grün
- [ ] **Linux-Rest:** AP-Diagramm + Zensical-Site neu bauen (Konvention: nur Linux)

## AP-26 — Audit-Sessions: unerwünschtes Verhalten ausschließen (v0.11.0)
- [x] **Audit-Prozess + Checkliste** in `docs/audits/README.md`: Kriterien (kein Netzwerk/`eval`/`Function()`/Blob/Worker/externe URLs/Storage/DOM-Inject; `require` nur bundle-intern; NO-CDN; dokumentierte Globals)
- [x] **Auslöser** festgelegt: vor jedem Lib-Einbinden + stichprobenartig bei KI-Code; Ergebnis verpflichtend als datierte Datei `docs/audits/YYYY-MM-DD-<thema>.md`
- [x] **Reproduzierbar:** drei ripgrep-Snippets dokumentiert und gegen den Ist-Stand validiert (`dagre.min.js` → 0 Treffer, Template → 0 CDN-Referenzen)
- [x] **Doku-Ort entschieden:** `docs/audits/` (entwicklerintern, **nicht** ins Delivery — AP-17); öffentliche Site nur neutrale Aussage ohne KI-Bezug
- [x] **Erster Record:** `docs/audits/2026-06-26-dagre-cytoscape-dagre.md` (dagre/cytoscape-dagre, AP-16) — Ergebnis unbedenklich
- [ ] **Optional offen:** neutrale Sicherheits-Notiz auf der Zensical-Site (alle Assets lokal, kein CDN, kein Laufzeit-Netzwerk) — beim nächsten Linux-Doku-Build mitnehmen

## AP-18 — Verknüpfen mehrerer Tabellen (Status geprüft) (v0.11.0)
- [x] **Ergebnis: bereits voll implementiert.** `core/pathfinder.find_paths` erzeugt Multi-Station-Pfade (beliebig viele Zwischentabellen) via `nx.shortest_simple_paths`; `core/sqlgen.generate_sql` emittiert `FROM tables[0]` + ein `JOIN` je Step → N Tabellen = N-1 JOINs
- [x] **Filter-Tabellen** werden zusätzlich als Pfad-Zweige eingewebt (nächster erreichbarer Anker, deterministisch) — weitere Join-Stationen ohne Duplikat-Tabellen
- [x] **Verifiziert** (gegen Demo-CMDB): 7-Tabellen-Join `Network→Datacenter→Host→VirtualMachine→VMDisk→Datastore→Replication` (6 JOINs) + Filter-Weaving-Beispiel; bestehende Tests decken es ab (`test_sqlgen::test_basic_select_join` = 3 Tabellen/2 JOINs, `test_pathfinder`/`test_demo_db_cases` = Filter-Weaving)
- [x] **Abgrenzung dokumentiert** (`luDBxP-docs/docs/referenz/usecases.md`, UC-1): beliebig viele Zwischentabellen ja; eine Abfrage hat aber genau **eine** Start- und **eine** Ziel-Tabelle — mehrere unabhängige Ziele sind nicht vorgesehen
- [ ] **Linux-Rest:** Zensical-Site mit der UC-1-Ergänzung neu bauen (Konvention: nur Linux)

## AP-28 (UI-Fix) — Join-Builder: Contentbereich scrollt nicht mehr (v0.11.1)
- [x] Join-Builder-Panel auf feste Viewport-Höhe (`height: 100%` + `overflow: hidden`) statt `min-height: 100%` → Formular/Filter/SELECT bleiben fix, kein Außenscroll der `.tabpanels`
- [x] `#join_result` ist der **einzige** Scroller (`min-height: 0` statt 200px → kann im festen Panel schrumpfen/scrollen)
- [x] Verifiziert (Playwright, 1400×900): `.tabpanels`/Panel kein Overflow, `#join_result` scrollt (client ~202px); Detail-Tabs unberührt (Regel bleibt auf `[data-tab=joinbuilder]` beschränkt)
- [x] Betroffen: `web/static/css/app.css`

## AP-32 (UI-Fix) — Zoom-%-Slider waagerecht in die Graph-Kopfzeile (v0.11.2)
- [x] Slider aus absoluter Position **über** dem Graphen in die Panel-Kopfzeile (`.panelhead`) verschoben — **waagerecht**, links neben „Neu anordnen" (neue `.panelhead-tools`-Gruppe)
- [x] CSS: `#zoom_ctrl` von vertikal/absolut (writing-mode, box/shadow, `position:absolute`) auf `inline-flex` row; `#zoom_slider` horizontal (110×12px); `orient="vertical"` aus dem Markup entfernt
- [x] `app.js` unverändert nötig (Slider-IDs/Logik gleich); Kopfzeilen-Höhe bleibt 34px (AP-21 unberührt)
- [x] Verifiziert (Playwright): Slider in Kopfzeile, links vom Button, **keine** Graph-Überlappung; Zoom funktioniert (Slider 250 → CY-Zoom 250%); 118 Tests grün
- [x] Betroffen: `web/templates/index.html`, `web/static/css/app.css`

## AP-27 — Insights: Ort & Einbindung geklärt (v0.11.2)
- [x] **Bestandsaufnahme:** vorhandene 2 Insights folgen bereits einheitlichem Schema (`YYYY-MM-DD-<slug>.md`, Überschrift `# Insight YYYY-MM-DD — <Titel> (Session N)`, nummerierte Erkenntnisse) — bestätigt, keine Vereinheitlichung nötig
- [x] **Doku-Ort entschieden:** Insights bleiben entwicklerintern in `docs/insights/` (neben `handoffs/`, `audits/`), **nicht** im Delivery (AP-17) und **nicht** auf der öffentlichen Zensical-Site
- [x] **Index + Prozess** angelegt: `docs/insights/README.md` (Zweck, Konvention/Namensschema, Wann-schreiben, Index der Insights)
- [x] **Abgrenzung definiert** (Tabelle in README): Insight = *Warum*/Erkenntnis/Entscheidung (intern, Prozess-/KI-Bezug erlaubt) vs. öffentliche Doku = *Was*/*Wie benutze ich es* (`referenz/`/`grundlagen/`/`entwicklung/`, nie Prozess/KI)
- [x] **Überführung dokumentiert:** reife Insights können *neutralisiert* (ohne KI-Bezug) in die Site wandern; Original bleibt intern
- [x] Betroffen: `docs/insights/README.md` (neu)

## Server-Deployment-Fixes (PowerShell 5.1) (v0.11.1–v0.11.3)
Beim ersten Server-Test (Windows PowerShell **5.1**) aufgetretene Blocker behoben:
- [x] **run.ps1 reines ASCII + UTF-8-BOM** (v0.11.2-Fix): Em-Dashes `—` ohne BOM → PS 5.1 las als cp1252, zerlegte UTF-8-Bytes falsch → „unexpected )/}". Jetzt ASCII + BOM (PS 5.1 **und** 7)
- [x] **Start-Abbruch behoben** (v0.11.3): Flask-Dev-Server-Warnung („This is a development server…") geht auf stderr; unter `$ErrorActionPreference='Stop'` wertete PS 5.1 das als Fehler und brach den Start ab → in `Start-App` lokal auf `Continue` gesetzt (try/finally)
- [x] **Debug-Schalter**: `run.ps1 -DebugMode` setzt `LUCENT_DEBUG=1`; `app.py` liest die Variable → Flask-Debug (interaktiver Debugger + Reloader); Hilfe (`.PARAMETER`/`.EXAMPLE`) ergänzt
- [x] **app.py** zusätzlich `threaded=True` (gleichzeitige Requests); verifiziert: HTTP 200; 118 Tests grün
- [x] Betroffen: `app.py`, `run.ps1`
