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
