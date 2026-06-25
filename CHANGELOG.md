# Changelog

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

### Changed
- UX: Connection-URL wird aus `default_connection` (config.json) vorbefüllt —
  standardmäßig die mitgelieferte Demo-DB, sodass „Schema laden" sofort
  funktioniert. Verdrahtet `core/settings.py` in die Index-Route.
- UX: Leere Connection-URL liefert eine klare Meldung statt der internen
  SQLAlchemy-„Could not parse URL"-Fehlermeldung.
