# AP-52: Multi-Schema-Reflection (ein wählbares Schema)

**Datum:** 2026-06-27
**Status:** Design abgenommen

## Ziel

Tabellen aus einem **wählbaren** Datenbank-Schema reflektieren und join-/abfragbar
machen — heute reflektiert der Loader nur das Default-Schema, sodass Tabellen in
anderen Schemas (häufig auf PostgreSQL/MSSQL) unsichtbar sind. Es ist immer
**genau ein** Schema aktiv; die erzeugte SQL wird schema-qualifiziert, damit sie
unabhängig vom `search_path` läuft.

## Motivation / verifizierter Ist-Zustand

„Tabellenname" ist heute überall die Identität: `graph`-Knoten = `table.name`,
`pathfinder` arbeitet auf diesen Strings, `sqlgen` nutzt `dialect.quote(table)`,
`datapreview` quotet einen Namen aus einer Allow-List, die API trägt
`{table, column}`, das Frontend nutzt `tableByName(name)`. Der Loader ruft
`get_table_names()` / `get_view_names()` **ohne** `schema=` auf → nur das
Default-Schema.

Weil immer nur **ein** Schema aktiv ist, treten **keine Namenskollisionen** auf.
Deshalb bleibt die Identität „bare name" gültig und Model/Graph/Pathfinder müssen
**nicht** geändert werden. Das gewählte Schema ist ein **Request-Parameter**, der
durch Reflection und SQL-Erzeugung fließt — keine Schema-Identität im Model.

## Architektur / Datenfluss

```
Frontend Schema-Dropdown (aus /api/schemas)
   → jeder reflektierende API-Call trägt optional "schema"
   → SqlAlchemyLoader.load(schema) reflektiert dieses Schema (bare Namen)
   → sqlgen / datapreview qualifizieren FROM/JOIN/Spalten als schema.table
```

Read-Only-Constraint und Layering (`core/` Flask-frei) bleiben unberührt.
`core/model.py`, `core/graph.py`, `core/pathfinder.py` werden **nicht** geändert.

## Komponenten / Änderungen

### 1. Loader: schema-Parameter + Schema-Listing
- `core/loaders/sqlalchemy_loader.py`: `load(self, schema=None)` reicht `schema=`
  an **alle** Inspector-Aufrufe durch (`get_table_names`, `get_view_names`,
  `get_columns`, `get_foreign_keys`, `get_pk_constraint`,
  `get_unique_constraints`, `get_indexes`, `get_view_definition`). `schema=None`
  = heutiges Default-Verhalten (unverändert).
- Neue reine Funktion, die die verfügbaren Schemas listet und bekannte
  System-Schemas herausfiltert: `list_schemas(connection_url) -> tuple[str, ...]`
  (nutzt `inspect(engine).get_schema_names()`; filtert `information_schema`,
  `pg_catalog`, `sys`, `INFORMATION_SCHEMA` u. ä.).

### 2. SQL-Qualifizierung
- `core/sqlgen.py`:
  - `Dialect.qualify_schema(schema, table)` rendert `quote(schema).quote(table)`.
  - `generate_sql(..., schema="")`: bei nicht-leerem `schema` wird **jede**
    Tabellenreferenz (FROM, JOIN, qualifizierte Spalten in SELECT/WHERE/ORDER BY)
    schema-qualifiziert. Leeres `schema` → **exakt** heutige Ausgabe (keine
    Regression an bestehenden Tests).
- `core/datapreview.py`: optionaler `schema`-Parameter; qualifiziert das Objekt
  als `"<schema>"."<object>"` (dialekt-neutral mit `"`-Quoting wie bisher), wenn
  gesetzt.

### 3. API
- Neuer Endpoint **`GET/POST /api/schemas`**: nimmt `connection_url`, liefert
  `{"schemas": [...]}` via `list_schemas`.
- Bestehende reflektierende Endpoints nehmen optional `schema` entgegen und
  reichen es an `SqlAlchemyLoader(...).load(schema)` **und** (wo SQL erzeugt wird)
  an `generate_sql(..., schema=...)` / `datapreview(..., schema=...)` weiter:
  `/api/schema`, `/api/graph`, `/api/joinpath`, `/api/joinpath/run`, `/api/data`,
  `/api/distinct`, `/api/orphan_check`.

### 4. Frontend
- `web/static/js/app.js`: ein Schema-Dropdown, befüllt aus `/api/schemas` nach
  erfolgreicher Verbindung. Wechsel → re-reflektieren (Schema in alle nachfolgenden
  Requests aufnehmen). Default-Auswahl = leer (Default-Schema, heutiges Verhalten).
- Session-Level — **keine** Persistenz pro gespeicherter Verbindung.

## Tests (SQLite via ATTACH)

SQLite stellt Schemas über `ATTACH DATABASE` bereit; `get_schema_names()` liefert
`main` + die angehängten. Neue Fixture (`tests/fixtures/` + conftest), die eine
zweite SQLite-DB mit einer eigenen Tabelle anhängt:

- **Loader:** `load(schema="<attached>")` reflektiert die Tabelle(n) des
  angehängten Schemas; `load()` (default) sieht sie nicht.
- **`list_schemas`:** enthält das angehängte Schema; bekannte System-Schemas
  gefiltert.
- **`/api/schemas`:** Endpoint liefert die Schema-Liste.
- **sqlgen:** mit `schema="s"` erzeugt FROM/JOIN als `"s"."t"`; ohne `schema`
  **unverändert** (bestehende sqlgen-Tests bleiben grün).
- **datapreview:** mit `schema` korrekt qualifiziert.
- **API-Integration:** ein joinpath-Request mit `schema` liefert qualifizierte
  SQL und 200.

## Doku / Release

- Version **minor** via `sync_version.py --minor` → v0.38.0.
- CHANGELOG (englisch) + Mirror (deutsch).
- Badges (`icon-rail.js`) + `zensical.toml`.
- `CLAUDE.md`: neue Schema-Wahl-Fähigkeit + Endpoint dokumentieren.
- Architektur-Diagramm `luDBxP-docs/mermaid-sources/referenz-architektur-3.mmd`
  um das neue `/api/schemas`-Endpoint ergänzen (Komponenten/Endpoints-Karte).
- Site-Build + SDD-Final-Review. Push/gh-pages nur auf Nutzer-Ansage.

## Nicht-Ziele (bewusste Grenzen → spätere AP)

- **Kein** gleichzeitiges Reflektieren mehrerer Schemas und **keine**
  Cross-Schema-Joins (erforderte qualifizierte Identität in Model/Graph/Pathfinder).
- **Keine** Persistenz der Schemawahl pro gespeicherter Verbindung.
- Keine Änderung an Model/Graph/Pathfinder, an der Read-Only-Ausführung oder an
  der Fan-out-/Uniqueness-Logik.
