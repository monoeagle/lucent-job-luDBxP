# Changelog

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
