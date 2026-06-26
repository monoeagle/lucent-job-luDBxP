# Erledigte Arbeitspakete — Lucent DB Explorer

Abgeschlossene APs (umgehängt aus `todo.md`). Offene APs stehen in `todo.md`.

---

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
- [x] Defense-in-depth-Fix: `postJSON` fängt den Netzwerkfehler ab und zeigt „Server nicht erreichbar — läuft Lucent DB Explorer? Starte die App mit bash run.sh …" statt „Failed to fetch"
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
