# Changelog

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
