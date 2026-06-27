# AP-51: Unique-Index als Uniqueness-Quelle (+ Composite-Test-Carry-over)

**Datum:** 2026-06-27
**Status:** Design abgenommen
**Vorgänger:** AP-50 (`2026-06-27-ap50-unique-fanout-design.md`) — Unique-Constraints → 1-1-Fan-out-Erkennung. AP-51 schließt deren bewusste Grenze.

## Ziel

Die Eindeutigkeits-Erkennung der Fan-out-Klassifikation um eine zweite Quelle
erweitern: **Unique-Indizes**. AP-50 erkennt nur `UNIQUE`-*Constraints* und den
PK; eine FK-Spalte, die ausschließlich über `CREATE UNIQUE INDEX` eindeutig ist
(auf manchen Postgres-/MSSQL-Setups die Form, in der inline-`UNIQUE` reflektiert
wird), wird heute fälschlich als 1-N behandelt. AP-51 behebt das.

Zusätzlich: der aus dem AP-50-Final-Review übernommene **Composite-Unique-Test**
wird nachgezogen.

## Motivation / verifizierter Ist-Zustand

`core/graph._columns_unique` zieht aktuell `table.unique_constraints` und
`table.primary_key` als Eindeutigkeits-Kandidaten heran. Auf SQLite (Test-Backend)
gilt nachgewiesen:

- Ein reiner `CREATE UNIQUE INDEX` erscheint **nicht** in
  `insp.get_unique_constraints(...)`, aber in `insp.get_indexes(...)` mit
  `unique=1`. → von AP-50 nicht erfasst, von AP-51 erfasst.
- **Partielle** Unique-Indizes tragen `dialect_options['…_where']` und
  garantieren *keine* globale Eindeutigkeit → dürfen NICHT als eindeutig zählen.
- **Expression**-Indizes liefern `None` in `column_names` → dürfen NICHT zählen.

## Zuschnitt (bewusst minimal)

- Nur Unique-*Indizes* als zusätzliche Uniqueness-Quelle. **Kein** Indizes-Feature,
  **keine** Perf-Hinweise.
- Keine Änderung an Pathfinder, `web/routes.py`, Frontend oder generierter SQL.
- Read-Only-Constraint und Layering (`core/` Flask-frei) unberührt.

## Architektur / Datenfluss

Gleiche Kette wie AP-50, eine zusätzliche Quelle beim Laden:

```
loader: get_unique_constraints  +  get_indexes (unique, voll-spaltig, nicht partiell)
   → model.Table (unique_constraints | unique_indexes)
   → graph._columns_unique (Teilmengen-Regel über alle Quellen)
   → graph.JoinEdge.fk_unique  →  pathfinder.to_many   (unverändert)
```

## Komponenten / Änderungen

### 1. `core/model.py`
`Table` bekommt ein **getrenntes** Feld (ehrliche Benennung — Constraints ≠ Indizes):
```python
unique_indexes: tuple[tuple[str, ...], ...] = ()
```
Je innere Tuple = Spaltennamen eines voll-spaltigen, nicht-partiellen
Unique-Index. Als letztes Feld mit Default `()` → abwärtskompatibel.

### 2. `core/loaders/sqlalchemy_loader.py`
Zusätzlich zu `get_unique_constraints` auch `insp.get_indexes(tname)` best-effort
reflektieren. Ein Index zählt als Eindeutigkeits-Quelle **nur**, wenn alle drei
Bedingungen gelten:
- `idx.get("unique")` ist truthy, **und**
- `column_names` ist nicht leer und enthält kein `None` (keine Expression-Indizes),
  **und**
- der Index ist nicht partiell: kein Schlüssel endet auf `_where` in
  `idx.get("dialect_options", {})`.

Fehler beim Reflektieren dürfen die Reflektion nicht abbrechen (try/except
`SQLAlchemyError` → `()`, analog zu `unique_constraints`). Die so gewonnenen
Spaltentupel werden als `unique_indexes` an `Table` übergeben. Andere Loader
(`manual`, `ddl`, `schemaspy`) liefern den Default `()`.

### 3. `core/graph.py`
`_columns_unique` berücksichtigt zusätzlich `table.unique_indexes` als
Kandidaten — gleiche Teilmengen-Regel `set(U) ⊆ set(fk_local_columns)`:
```python
candidates = list(table.unique_constraints) + list(table.unique_indexes)
if table.primary_key:
    candidates.append(table.primary_key)
return any(set(u) <= target for u in candidates if u)
```
`JoinEdge.fk_unique`, `build_graph`, `pathfinder` und `web/routes.py` bleiben
unverändert.

## Tests

### Neue Fixture `tests/fixtures/uniqueindex_schema.sql`
- `Parent` (PK).
- `Profile`: FK `ParentID`, eindeutig **nur** via `CREATE UNIQUE INDEX` (kein
  UNIQUE-Constraint) → muss als 1-1 erkannt werden.
- `Note`: FK `ParentID` mit nicht-eindeutigem Index → bleibt 1-N.
- Ein **partieller** Unique-Index (`… WHERE …`) auf einer Spalte, der **nicht**
  als eindeutig zählen darf.

### Neue conftest-Fixture
`uniqueindex_url` (analog `onetoone_url`), gebaut aus dem neuen Schema-File.

### Tests
- **Loader:** `unique_indexes` enthält das voll-spaltige Index-Set; der partielle
  Index ist **nicht** enthalten.
- **Graph:** `_edge_with_holder(g, "Profile", "Parent").fk_unique is True`
  (Index-basiert); `Note`→`Parent` `fk_unique is False`.
- **Pathfinder:** absteigend in `Profile` → `to_many is False`; in `Note` →
  `to_many is True`.
- **Carry-over (Composite-Unique, aus AP-50-Review):** in `tests/test_graph.py`
  ein Fall mit zusammengesetzter FK, die genau durch ein zusammengesetztes
  Unique-Set (Constraint **oder** Index) abgedeckt ist → `fk_unique True`; eine
  Teil-Abdeckung (Unique-Set ist *Obermenge* der FK-Spalten) → `fk_unique False`.

### Regression
Bestehende AP-50-Tests (`onetoone`-Fixture, Inventory) bleiben unverändert grün.

## Doku / Release

- Version **minor** via `sync_version.py --minor` → v0.37.0.
- CHANGELOG (englisch) + Mirror (deutsch).
- Badges (`icon-rail.js`: APP_VERSION/TEST_COUNT/TEST_DATE) + `zensical.toml`.
- `CLAUDE.md`: die AP-50-Notiz „… Uniqueness expressed only as a unique index is
  not yet detected (AP-51)" auf erledigt umschreiben (Unique-Indizes werden jetzt
  erkannt; nur partielle/Expression-Indizes bleiben bewusst ausgeschlossen).
- Architektur-Diagramme: kein neues Modul/Endpoint → i. d. R. unverändert, kurz
  gegenprüfen.
- Site-Build + SDD-Final-Review. Push/gh-pages nur auf Nutzer-Ansage.

## Nicht-Ziele

- Kein Indizes-Feature, keine Perf-Hinweise (eigene spätere AP).
- Partielle und Expression-Unique-Indizes zählen bewusst **nicht** als
  Eindeutigkeits-Garantie.
- Keine Änderung an generierter SQL, Pathfinder-Orientierung, Frontend oder
  Read-Only-Ausführung.
