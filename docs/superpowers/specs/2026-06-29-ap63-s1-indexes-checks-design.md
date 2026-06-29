# AP-63·Stufe 1 — Indizes + Check-Constraints im Tabellen-Detail — Design

**Datum:** 2026-06-29
**Status:** Spec (genehmigt im Brainstorming)
**Aufwand:** S (read-only Reflection-Anreicherung, SQLite-CI-testbar, kein Dialekt-SQL, keine Sidebar-Kategorie)
**Vorgänger-Konzept:** `docs/concepts/2026-06-28-sidebar-object-categories.md` (Abschnitt „Stufe 1")

## Ziel

Im Tabellen-Detail (Sub-Tab „Definition") **alle Indizes** (Name, Spalten, unique) und **Check-Constraints** (Name, Ausdruck) read-only auflisten. Heute werden nur *unique* Indizes gelesen (intern für die 1-1-Erkennung) und gar nicht angezeigt; Check-Constraints werden nie gelesen. Etabliert „mehr DB-Objekte read-only reflektieren + anzeigen" risikoarm — ohne Dialekt-SQL, ohne neue Sidebar-Kategorie.

## Code-Befunde (Ist-Stand verifiziert)

- **`core/model.py`**: `Table` trägt `primary_key`, `unique_constraints`, `unique_indexes` (gefilterte Spalten-Tupel, für 1-1), `comment`. Reine frozen Dataclasses, kein SQLAlchemy/Flask.
- **`core/loaders/sqlalchemy_loader.py:80–91`**: liest heute via `insp.get_indexes(tname)` nur die **unique** Indizes in `uidx` (mit Guard gegen `None`-Spalten + partielle `_where`-Indizes). `insp.get_check_constraints(tname)` wird **nicht** aufgerufen.
- **Reflection verifiziert (SQLite via SQLAlchemy):** `get_indexes()` liefert je Index `{name, column_names, unique, dialect_options}`; `get_check_constraints()` liefert `[{sqltext, name}]` — inkl. **unbenannter** Inline-Checks (`name=None`). Beides funktioniert nativ inkl. SQLite → voll CI-testbar.
- **`/api/schema` (`web/routes.py:134–162`)**: serialisiert je Table `name/comment/columns/foreign_keys/ddl` — **nicht** Indizes/Checks.
- **UI `openDetail` (`web/static/js/app.js:290–342`)**: „Definition"-Subtab zeigt Spalten-Tabelle + „Foreign Keys"-Liste; „SQL"-Subtab zeigt `t.ddl`. Anreicherungs-Punkt = nach dem FK-Abschnitt.
- **Andere Loader** (`manual_loader`, `ddl_loader`, `schemaspy_loader`) konstruieren `Table(...)` — neue Felder mit Default `()` am **Ende** anfügen hält sie unberührt.

## 1. Model (`core/model.py`, pur)

Zwei neue frozen Dataclasses:
```python
@dataclass(frozen=True)
class Index:
    name: str
    columns: tuple[str, ...]
    unique: bool = False

@dataclass(frozen=True)
class CheckConstraint:
    name: str        # "" = unbenannt
    sqltext: str
```
Zwei neue `Table`-Felder, **am Ende** (nach `comment`), Default `()`:
```python
indexes: tuple[Index, ...] = ()
check_constraints: tuple[CheckConstraint, ...] = ()
```
`unique_indexes` bleibt **unverändert** (gefilterte 1-1-Sicht); `indexes` ist die vollständige Anzeige-Liste daneben (bewusst getrennt — unterschiedliche Zwecke).

## 2. Loader (`core/loaders/sqlalchemy_loader.py`)

Nach dem `uidx`-Block, vor dem `Table(...)`-Append:
```python
try:
    indexes = tuple(
        Index(idx.get("name") or "", tuple(idx["column_names"]), bool(idx.get("unique")))
        for idx in insp.get_indexes(tname, schema=schema)
        if idx.get("column_names") and None not in idx["column_names"]
    )
except SQLAlchemyError:
    indexes = ()
try:
    checks = tuple(
        CheckConstraint(cc.get("name") or "", cc.get("sqltext") or "")
        for cc in insp.get_check_constraints(tname, schema=schema)
    )
except (SQLAlchemyError, NotImplementedError):
    checks = ()
```
- An `Table(...)` als die zwei neuen Trailing-Argumente durchreichen (Reihenfolge = Model-Feldreihenfolge: `… tcomment, indexes, checks`).
- **Expression-/Funktions-Indizes** (`None` in `column_names`) werden übersprungen — gleicher Guard wie `uidx`; dokumentierte Mini-Einschränkung (kein sauberer Spalten-Display).
- Importe oben ergänzen: `Index, CheckConstraint` aus `core.model`.

## 3. Endpoint (`/api/schema`, `web/routes.py`)

Je Table-Dict ergänzen:
```python
"indexes": [
    {"name": ix.name, "columns": list(ix.columns), "unique": ix.unique}
    for ix in t.indexes
],
"check_constraints": [
    {"name": cc.name, "sqltext": cc.sqltext} for cc in t.check_constraints
],
```

## 4. UI (`web/static/js/app.js::openDetail`, Table-Zweig)

Nach dem FK-Abschnitt zwei genestete Abschnitte an `defHtml` anhängen:
- **Indizes** — `<h3>Indizes</h3>` + Liste; je Index `name · col1, col2` plus ein `unique`-Badge (`<span class="badge">unique</span>`) wenn `ix.unique`; leer → `<p class='hint'>keine Indizes</p>`. Namenlose Indizes („" ) als „(unbenannt)".
- **Check-Constraints** — `<h3>Check-Constraints</h3>` + Liste; je Check `name: sqltext` (Name „(unbenannt)" falls leer); leer → `<p class='hint'>keine Check-Constraints</p>`.
- Alle Werte via `esc`. Reine Definition-Anzeige; `t.ddl` (SQL-Subtab) unverändert.

## 5. Demo-DB + Tests

**`sample_data/build_demo_db.py`** minimal erweitern (für CI-Abdeckung, ohne bestehende Tests zu stören):
- Ein **inline-Check**: `VMDisk.SizeGB INTEGER NOT NULL CHECK (SizeGB > 0)`.
- Ein **benannter, nicht-unique Index**: `CREATE INDEX ix_host_cluster ON Host(ClusterID);` (im `_SCHEMA`-String nach den CREATE TABLEs).
- Nach der Änderung die **volle Suite** laufen (Spalten-/Struktur-Tests in `test_demo_db_cases.py` dürfen nicht brechen — Spaltenzahl/Namen bleiben gleich).

**Tests:**
- **Loader** (`tests/test_sqlalchemy_loader.py` o. `tests/test_demo_db_cases.py`): gegen die Demo → `schema.table("Host").indexes` enthält `Index("ix_host_cluster", ("ClusterID",), False)`; `schema.table("VMDisk").check_constraints` enthält einen Check, dessen `sqltext` `SizeGB` referenziert.
- **Konstruiertes SQLite** (eigene Fixture o. inline): Tabelle mit unique-Index + **unbenanntem** Inline-Check → `Index(..., unique=True)` vorhanden; `CheckConstraint("", …)` (Name leer) vorhanden — belegt unique-Flag + unbenannten-Check-Pfad.
- **Endpoint** (`tests/test_api.py`): `/api/schema` gegen `demo_url` → das Host-Table-Dict hat `indexes` mit `ix_host_cluster`; VMDisk hat `check_constraints` nicht leer.
- **Browser-Smoke** (Playwright, System-python3): Demo verbinden → Tabelle `Host` öffnen → „Definition" zeigt einen „Indizes"-Abschnitt mit `ix_host_cluster`; Tabelle `VMDisk` zeigt einen „Check-Constraints"-Abschnitt. **App-Neustart** vor Smoke (Route/Python-Änderung).

## 6. Scope-Cuts (bewusst)

- **Nur Definition-Anzeige** — das rekonstruierte `table_ddl` (SQL-Subtab) bleibt unverändert (kein inline-CHECK/CREATE INDEX im DDL).
- **Keine Sidebar-Kategorie** — reine Anreicherung der bestehenden Detail-Ansicht.
- **Expression-/Funktions-Indizes** (Spalten = Ausdruck) werden übersprungen.
- Keine Teilnahme dieser Objekte an Join-Pfaden/SQL-Generierung.
- Stufe 2 (Sequences/Mat-Views/Triggers) + Stufe 3 (Procedures/Functions) bleiben separate APs.

## 7. Release / Doku (nach Implementierung)

- `sync_version.py --minor` (Feature) + icon-rail `APP_VERSION`/`TEST_COUNT`.
- Roadmap: AP-63·S1 → erledigt; AP-63·S2/S3 bleiben offen, namentlich.
- CLAUDE.md „Bekannte Einschränkungen": Detail-Anreicherung (Indizes/Checks) als read-only Tier notieren; Kennzahlen-Seite (hartkodiert) mitziehen.
- Changelog EN + DE-Mirror, zensical, Site-Build, gh-pages.
- Deutsch / NO-CDN / SDD-Final-Review nicht weglassen.
