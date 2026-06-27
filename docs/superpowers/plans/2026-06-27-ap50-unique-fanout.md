# AP-50 — Unique-Constraints → korrekte Fan-out-Klassifikation: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen Join-Schritt nur dann als 1-N (`to_many`) klassifizieren, wenn die FK-haltende Kind-Seite *nicht* eindeutig ist — eine 1-1-Beziehung erzeugt damit keine falsche Fan-out-Warnung mehr.

**Architecture:** Eindeutigkeit wird beim Schema-Laden reflektiert (`Table.unique_constraints`), beim Graph-Bau pro FK in `JoinEdge.fk_unique` verdichtet und im Pathfinder als `to_many = absteigend AND NOT fk_unique` ausgewertet. `web/routes.py` braucht keine Änderung — die 1-N-Warnung ist von `to_many` getrieben.

**Tech Stack:** Python 3.14 (venv), SQLAlchemy (Reflection), NetworkX (Graph), pytest.

## Global Constraints

- **Layering:** `core/` darf NIE Flask importieren. Alle Änderungen liegen in `core/` + Tests.
- **Read-Only:** Es wird nur Schema-Metadaten gelesen; keine generierte SQL/Ausführung wird geändert.
- **Version Management:** Version nur via `sync_version.py`; Feature=minor → v0.36.0.
- **Sprache:** Code-Kommentare englisch (wie in `core/`), App-/Doku-Texte deutsch; Root-CHANGELOG `### Added` englisch, Mirror `### Hinzugefügt` deutsch.
- **Tests:** Baseline 234 passed, 1 skipped muss grün bleiben; neue Tests kommen hinzu.
- **Eindeutigkeits-Regel:** FK-Spalten sind kollektiv eindeutig ⇔ es existiert ein Eindeutigkeits-Set `U` (aus `table.unique_constraints` oder `table.primary_key`) mit `set(U) ⊆ set(fk_local_columns)`.
- **Bewusste Grenze:** Nur Unique-*Constraints* (kein Unique-*Index*; das ist AP-51). Implizite FKs → `fk_unique=False`.

---

### Task 1: Reflection von Unique-Constraints (Fixture + Model + Loader)

**Files:**
- Create: `tests/fixtures/onetoone_schema.sql`
- Modify: `tests/conftest.py`
- Modify: `core/model.py` (Table-Dataclass)
- Modify: `core/loaders/sqlalchemy_loader.py`
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Consumes: nichts.
- Produces:
  - `core.model.Table.unique_constraints: tuple[tuple[str, ...], ...]` (Default `()`), je innere Tuple = Spaltennamen einer Unique-Constraint.
  - pytest-Fixture `onetoone_url` (SQLite-URL) mit Tabellen `Person` (Parent), `Passport` (1-1: FK `PersonID` UNIQUE), `Orders` (1-N: FK `PersonID` nicht unique).

- [ ] **Step 1: Fixture-Schema anlegen**

Erstelle `tests/fixtures/onetoone_schema.sql`:

```sql
CREATE TABLE Person (
    PersonID INTEGER PRIMARY KEY,
    Name TEXT NOT NULL
);
CREATE TABLE Passport (
    PassportID INTEGER PRIMARY KEY,
    PersonID INTEGER NOT NULL UNIQUE REFERENCES Person(PersonID),
    Number TEXT NOT NULL
);
CREATE TABLE Orders (
    OrderID INTEGER PRIMARY KEY,
    PersonID INTEGER NOT NULL REFERENCES Person(PersonID),
    Total REAL NOT NULL
);
```

- [ ] **Step 2: conftest-Fixture ergänzen**

In `tests/conftest.py` nach der `inventory_nofk_url`-Fixture (Zeile 35) einfügen:

```python
@pytest.fixture
def onetoone_url(tmp_path) -> str:
    """SQLite URL with a 1-1 (Passport, UNIQUE FK) and a 1-N (Orders) child."""
    return _build_sqlite(tmp_path, "onetoone.db", "onetoone_schema.sql")
```

- [ ] **Step 3: Failing test schreiben (Loader reflektiert Unique-Constraints)**

In `tests/test_sqlalchemy_loader.py` ans Dateiende anhängen:

```python
def test_load_reflects_unique_constraints(onetoone_url):
    schema = SqlAlchemyLoader(onetoone_url).load()
    passport = schema.table("Passport")
    # inline UNIQUE on the FK column is reflected as a one-column unique set
    assert ("PersonID",) in passport.unique_constraints
    orders = schema.table("Orders")
    # the 1-N child has no unique set covering its FK column
    assert all("PersonID" not in u for u in orders.unique_constraints)
```

- [ ] **Step 4: Test laufen lassen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py::test_load_reflects_unique_constraints -v`
Expected: FAIL — `AttributeError: 'Table' object has no attribute 'unique_constraints'` (bzw. `TypeError` beim Table-Aufruf).

- [ ] **Step 5: Model-Feld ergänzen**

In `core/model.py` die `Table`-Dataclass (Zeilen 45–50) um ein Feld erweitern:

```python
@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    foreign_keys: tuple[ForeignKey, ...]
    primary_key: tuple[str, ...] = ()  # primary-key column names
    # Each inner tuple is the column names of one UNIQUE constraint (table-level
    # or inline). The primary key is held separately in `primary_key`.
    unique_constraints: tuple[tuple[str, ...], ...] = ()
```

- [ ] **Step 6: Loader reflektiert Unique-Constraints**

In `core/loaders/sqlalchemy_loader.py` im Tabellen-Loop (vor `tables.append(...)`, aktuell Zeile 67–68) die Unique-Constraints best-effort reflektieren und an `Table` übergeben:

```python
                pk = tuple(insp.get_pk_constraint(tname).get("constrained_columns", []))
                try:
                    uniques = tuple(
                        tuple(uc.get("column_names") or ())
                        for uc in insp.get_unique_constraints(tname)
                        if uc.get("column_names")
                    )
                except SQLAlchemyError:
                    uniques = ()
                tables.append(Table(tname, columns, tuple(fks), pk, uniques))
```

- [ ] **Step 7: Test laufen lassen — muss bestehen**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -v`
Expected: PASS (alle Loader-Tests inkl. dem neuen).

- [ ] **Step 8: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `235 passed, 1 skipped` (234 alt + 1 neu).

- [ ] **Step 9: Commit**

```bash
git add tests/fixtures/onetoone_schema.sql tests/conftest.py core/model.py core/loaders/sqlalchemy_loader.py tests/test_sqlalchemy_loader.py
git commit -m "feat: AP-50 reflect UNIQUE constraints into Table.unique_constraints"
```

---

### Task 2: Eindeutigkeit pro FK im Graph (`JoinEdge.fk_unique`)

**Files:**
- Modify: `core/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `core.model.Table.unique_constraints` (Task 1).
- Produces:
  - `core.graph.JoinEdge.fk_unique: bool` (Default `False`) — True, wenn die FK-Spalten der FK-haltenden Seite (`table_a`) kollektiv eindeutig sind.
  - Helfer `core.graph._columns_unique(table, columns) -> bool`.

- [ ] **Step 1: Failing test schreiben**

In `tests/test_graph.py` ans Dateiende anhängen:

```python
def _edge_with_holder(g, holder, other):
    """The JoinEdge on (holder, other) whose table_a is the FK holder."""
    joins = g[holder][other]["joins"]
    return next(j for j in joins if j.table_a == holder)


def test_join_edge_fk_unique_for_one_to_one(onetoone_url):
    g = build_graph(SqlAlchemyLoader(onetoone_url).load())
    # Passport holds a UNIQUE FK to Person → 1-1
    assert _edge_with_holder(g, "Passport", "Person").fk_unique is True


def test_join_edge_fk_not_unique_for_one_to_many(onetoone_url):
    g = build_graph(SqlAlchemyLoader(onetoone_url).load())
    # Orders holds a non-unique FK to Person → 1-N
    assert _edge_with_holder(g, "Orders", "Person").fk_unique is False
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_graph.py::test_join_edge_fk_unique_for_one_to_one -v`
Expected: FAIL — `AttributeError: 'JoinEdge' object has no attribute 'fk_unique'`.

- [ ] **Step 3: JoinEdge-Feld + Helfer + Verdrahtung**

In `core/graph.py` die `JoinEdge`-Dataclass (Zeilen 19–28) um ein Feld erweitern:

```python
@dataclass(frozen=True)
class JoinEdge:
    """One foreign key between two tables, as oriented column pairs.

    ``pairs`` holds ``(column_on_table_a, column_on_table_b)`` tuples — one for
    a single-column FK, several for a composite FK (all combined with AND).
    ``fk_unique`` is True when ``table_a``'s FK columns are collectively unique
    (the relationship is one-to-one, not one-to-many).
    """
    table_a: str
    table_b: str
    pairs: tuple[tuple[str, str], ...]
    fk_unique: bool = False
```

Den Eindeutigkeits-Helfer (nach den Imports, vor `_add_join_edge`) ergänzen:

```python
def _columns_unique(table, columns) -> bool:
    """True if ``columns`` on ``table`` are collectively unique: some unique set
    (a UNIQUE constraint or the primary key) is a subset of ``columns``."""
    target = set(columns)
    if not target:
        return False
    candidates = list(table.unique_constraints)
    if table.primary_key:
        candidates.append(table.primary_key)
    return any(set(u) <= target for u in candidates if u)
```

`_add_join_edge` um den `fk_unique`-Parameter erweitern (Zeilen 31–41):

```python
def _add_join_edge(g: nx.Graph, a: str, b: str,
                   pairs: tuple[tuple[str, str], ...], implied: bool,
                   fk_unique: bool = False) -> None:
    """Add or extend the (a, b) edge with one join option (one foreign key)."""
    option = JoinEdge(a, b, pairs, fk_unique)
    if g.has_edge(a, b):
        data = g[a][b]
        data["joins"] = data["joins"] + (option,)
        if not implied:
            data["implied"] = False  # a declared join makes the edge declared
    else:
        g.add_edge(a, b, joins=(option,), implied=implied)
```

In `build_graph` den deklarierten-FK-Loop (Zeilen 63–65) auf den Helfer umstellen; implizite FKs bleiben `fk_unique=False` (Default):

```python
    for table in schema.tables:
        for fk in table.foreign_keys:
            fk_unique = _columns_unique(table, fk.columns)
            _add_join_edge(g, table.name, fk.ref_table, fk.column_pairs,
                           False, fk_unique)
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `./venv/bin/python -m pytest tests/test_graph.py -v`
Expected: PASS (alle Graph-Tests inkl. der beiden neuen).

- [ ] **Step 5: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `237 passed, 1 skipped` (235 + 2 neu).

- [ ] **Step 6: Commit**

```bash
git add core/graph.py tests/test_graph.py
git commit -m "feat: AP-50 JoinEdge.fk_unique — flag one-to-one FKs at graph build"
```

---

### Task 3: Pathfinder-Kardinalität + Warnungs-Regression

**Files:**
- Modify: `core/pathfinder.py:67`
- Test: `tests/test_pathfinder.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `core.graph.JoinEdge.fk_unique` (Task 2).
- Produces: `JoinStep.to_many` ist `True` nur bei absteigendem Schritt mit *nicht* eindeutiger FK.

- [ ] **Step 1: Failing tests schreiben (Pathfinder)**

In `tests/test_pathfinder.py` ans Dateiende anhängen:

```python
@pytest.fixture
def oto_graph(onetoone_url):
    return build_graph(SqlAlchemyLoader(onetoone_url).load())


def test_one_to_one_step_is_not_to_many(oto_graph):
    # Person -> Passport descends, but Passport's FK is UNIQUE → 1-1, not 1-N
    paths = find_paths(oto_graph, "Person", "Passport")
    step = paths[0].steps[0]
    assert step.left_table == "Person" and step.right_table == "Passport"
    assert step.to_many is False


def test_one_to_many_step_still_to_many(oto_graph):
    # Person -> Orders descends with a non-unique FK → still 1-N
    paths = find_paths(oto_graph, "Person", "Orders")
    step = paths[0].steps[0]
    assert step.left_table == "Person" and step.right_table == "Orders"
    assert step.to_many is True
```

- [ ] **Step 2: Tests laufen lassen — `to_one` schlägt fehl**

Run: `./venv/bin/python -m pytest tests/test_pathfinder.py::test_one_to_one_step_is_not_to_many -v`
Expected: FAIL — `assert True is False` (heute liefert der absteigende Schritt `to_many=True`).

- [ ] **Step 3: `to_many` verfeinern**

In `core/pathfinder.py` Zeile 65–67 (Kommentar + Zuweisung) ersetzen:

```python
    # The chosen FK is held by chosen.table_a (the child side). Stepping a -> b
    # descends (one-to-many) when b is that FK holder — unless the FK columns are
    # themselves unique (chosen.fk_unique), which makes the step one-to-one.
    to_many = (chosen.table_a == b) and not chosen.fk_unique
```

- [ ] **Step 4: Tests laufen lassen — beide bestehen**

Run: `./venv/bin/python -m pytest tests/test_pathfinder.py -v`
Expected: PASS — inkl. der bestehenden `test_step_to_many_when_descending` / `test_step_to_one_when_ascending` (Inventory-FKs sind nicht unique → unverändert).

- [ ] **Step 5: API-Regression — 1-1 ohne 1-N-Warnung**

In `tests/test_api.py` ans Dateiende anhängen:

```python
def test_one_to_one_path_has_no_fanout_warning(client, onetoone_url):
    """A 1-1 join (UNIQUE FK) must not raise the 1-N fan-out warning."""
    resp = client.post("/api/joinpath", json={
        "connection_url": onetoone_url,
        "start": {"table": "Person", "column": "PersonID"},
        "target": {"table": "Passport", "column": "PassportID"},
        "filters": [],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert all("1-N" not in w for w in p["warnings"])


def test_one_to_many_path_still_warns(client, onetoone_url):
    """A 1-N join (non-unique FK) still raises the fan-out warning."""
    resp = client.post("/api/joinpath", json={
        "connection_url": onetoone_url,
        "start": {"table": "Person", "column": "PersonID"},
        "target": {"table": "Orders", "column": "OrderID"},
        "filters": [],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert any("1-N" in w and "Orders" in w for w in p["warnings"])
```

- [ ] **Step 6: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `241 passed, 1 skipped` (237 + 4 neu).

- [ ] **Step 7: Commit**

```bash
git add core/pathfinder.py tests/test_pathfinder.py tests/test_api.py
git commit -m "feat: AP-50 to_many=False for unique (one-to-one) FK steps"
```

---

### Task 4: Doku & Release v0.36.0

**Files:**
- Modify: `CLAUDE.md`
- Modify (via `sync_version.py`): `config.py`, `lucent-hub.yml`
- Modify: `CHANGELOG.md`, `luDBxP-docs/docs/entwicklung/changelog.md`
- Modify: `luDBxP-docs/docs/javascripts/icon-rail.js`, `luDBxP-docs/zensical.toml`

**Interfaces:**
- Consumes: fertige Implementierung aus Tasks 1–3.
- Produces: Release v0.36.0, konsistente Doku, gebaute Site.

- [ ] **Step 1: CLAUDE.md — Composite-FK/Fan-out-Notiz ergänzen**

In `CLAUDE.md` im Abschnitt „Bekannte Einschränkungen" direkt nach dem Composite-FK-Blockquote einen Satz ergänzen:

```
> **One-to-one detection (AP-50):** a descending FK whose child columns are themselves UNIQUE (constraint or PK) is treated as 1-1, not 1-N — no false fan-out warning. Uniqueness expressed *only* as a unique index is not yet detected (AP-51).
```

- [ ] **Step 2: Version bumpen (minor)**

Run:
```bash
./venv/bin/python sync_version.py --minor
./venv/bin/python -c "import config; print(config.APP_VERSION)"
```
Expected: `0.36.0`.

- [ ] **Step 3: Changelog (Root englisch) + Mirror (deutsch)**

In `CHANGELOG.md` ganz oben (vor `## [0.35.0]`) einfügen:

```markdown
## [0.36.0] — 2026-06-27

### Added
- One-to-one fan-out detection: a descending foreign key whose child columns
  carry a UNIQUE constraint (or are the primary key) is now classified as 1-1
  instead of 1-N, so the join-builder no longer raises a false fan-out warning
  for it.
```

In `luDBxP-docs/docs/entwicklung/changelog.md` ganz oben den deutschen, kondensierten Spiegel einfügen:

```markdown
## [0.36.0] — 2026-06-27

### Hinzugefügt
- 1-1-Erkennung: absteigende FK mit eindeutiger Kind-Spalte (UNIQUE/PK) gilt
  als 1-1 statt 1-N — keine falsche Fan-out-Warnung mehr.
```

- [ ] **Step 4: Badges + zensical nachziehen**

In `luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION='0.36.0'`, `TEST_COUNT='241'`, `TEST_DATE='2026-06-27'`.
In `luDBxP-docs/zensical.toml` Zeile 3: site_description-Ende von `· v0.35.0` auf `· v0.36.0`.

- [ ] **Step 5: Architektur-Diagramme prüfen**

Kein neues core-Modul/Endpoint (nur Felder + Logik in bestehenden Modulen) → `luDBxP-docs/mermaid-sources/referenz-architektur-*.mmd` brauchen i. d. R. keine Änderung. Kurz gegenprüfen, sonst unverändert lassen.

- [ ] **Step 6: Site bauen + gegenprüfen**

Run:
```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
```
Expected: Build ohne Fehler; danach in `luDBxP-docs/site/` gegenprüfen, dass `0.36.0` und `241` auftauchen:
```bash
grep -rl "0.36.0" luDBxP-docs/site/index.html luDBxP-docs/site/javascripts/icon-rail.js
```

- [ ] **Step 7: SDD-Final-Review**

Gesamten AP-Diff gegen die Spec prüfen: Layering (`core/` Flask-frei), Read-Only unverändert, Tests grün (241/1), keine Doku-Drift, bekannte Grenze (Unique-Index → AP-51) korrekt dokumentiert. Niemals weglassen.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: Release v0.36.0 — AP-50 1-1-Fan-out-Erkennung (Doku/Badges/Changelog/Site)"
```

- [ ] **Step 9: Push & gh-pages-Deploy — NUR auf Ansage des Nutzers**

Master-Push und der manuelle gh-pages-Deploy (Worktree, `.nojekyll` erhalten) erfolgen erst nach ausdrücklicher Freigabe. Nicht automatisch ausführen.

---

## Self-Review (durchgeführt)

**Spec-Coverage:** Reflection (Task 1: model+loader+Fixture), `JoinEdge.fk_unique`+Helfer mit Teilmengen-Regel (Task 2), `to_many`-Verfeinerung + Warnungs-Regression (Task 3), Doku/Release/Final-Review + bekannte Grenze (Task 4). Alle Spec-Abschnitte abgedeckt; Nicht-Ziele (kein 1-1-Chip, keine SQL-Änderung, keine Indizes) respektiert.

**Placeholder-Scan:** Keine TBD/TODO; jeder Code-Schritt enthält vollständigen Code; Befehle mit erwarteter Ausgabe.

**Type-Consistency:** `unique_constraints: tuple[tuple[str,...],...]` (Task 1) → `_columns_unique(table, columns)` + `JoinEdge.fk_unique: bool` (Task 2) → `chosen.fk_unique` in `to_many` (Task 3) durchgängig konsistent. Testzahlen kumulativ stimmig: 234 → 235 → 237 → 241.
