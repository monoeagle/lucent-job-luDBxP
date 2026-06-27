# AP-51 — Unique-Index als Uniqueness-Quelle: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine FK-Spalte, die nur über einen (voll-spaltigen, nicht-partiellen) Unique-Index eindeutig ist, als 1-1 erkennen — und damit die bewusste Grenze von AP-50 schließen.

**Architecture:** Der Loader reflektiert zusätzlich `get_indexes` und legt die qualifizierenden Unique-Index-Spaltensets in `Table.unique_indexes` ab. `graph._columns_unique` zieht dieses Feld als weitere Eindeutigkeits-Quelle heran (gleiche Teilmengen-Regel). `JoinEdge.fk_unique`, `pathfinder` und `web/routes.py` bleiben unverändert.

**Tech Stack:** Python 3.14 (venv), SQLAlchemy (Reflection), NetworkX (Graph), pytest.

## Global Constraints

- **Layering:** `core/` darf NIE Flask importieren. Alle Änderungen liegen in `core/` + Tests.
- **Read-Only:** nur Schema-Metadaten lesen; keine Änderung an generierter SQL/Ausführung/Pathfinder-Orientierung/Frontend.
- **Version Management:** Version nur via `sync_version.py`; Feature=minor → v0.37.0.
- **Sprache:** Code-Kommentare englisch; CHANGELOG-Root `### Added` englisch, Mirror `### Hinzugefügt` deutsch.
- **Eindeutigkeits-Regel:** FK-Spalten kollektiv eindeutig ⇔ es existiert ein Set `U` (aus `unique_constraints`, `unique_indexes` oder `primary_key`) mit `set(U) ⊆ set(fk_local_columns)`.
- **Unique-Index-Qualifikation:** ein Index zählt nur, wenn `unique` truthy **und** `column_names` ohne `None` (keine Expression-Indizes) **und** nicht partiell (kein `*_where`-Key in `dialect_options`).
- **Tests:** Baseline 241 passed, 1 skipped muss grün bleiben; neue Tests kommen hinzu.

---

### Task 1: Reflection von Unique-Indizes (Fixture + Model + Loader)

**Files:**
- Create: `tests/fixtures/uniqueindex_schema.sql`
- Modify: `tests/conftest.py`
- Modify: `core/model.py` (Table-Dataclass)
- Modify: `core/loaders/sqlalchemy_loader.py`
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Consumes: `core.model.Table` (mit `unique_constraints` aus AP-50).
- Produces:
  - `core.model.Table.unique_indexes: tuple[tuple[str, ...], ...]` (Default `()`).
  - pytest-Fixture `uniqueindex_url` mit `Parent` (PK), `Profile` (FK `ParentID`, eindeutig nur via voll Unique-Index → 1-1) und `Note` (FK `ParentID`, nur partieller Unique-Index → bleibt 1-N).

- [ ] **Step 1: Fixture-Schema anlegen**

Erstelle `tests/fixtures/uniqueindex_schema.sql`:

```sql
CREATE TABLE Parent (
    ParentID INTEGER PRIMARY KEY,
    Label TEXT NOT NULL
);
CREATE TABLE Profile (
    ProfileID INTEGER PRIMARY KEY,
    ParentID INTEGER NOT NULL REFERENCES Parent(ParentID),
    Bio TEXT
);
CREATE UNIQUE INDEX ux_profile_parent ON Profile(ParentID);
CREATE TABLE Note (
    NoteID INTEGER PRIMARY KEY,
    ParentID INTEGER NOT NULL REFERENCES Parent(ParentID),
    Body TEXT
);
CREATE UNIQUE INDEX ux_note_parent_partial ON Note(ParentID) WHERE Body IS NOT NULL;
```

- [ ] **Step 2: conftest-Fixture ergänzen**

In `tests/conftest.py` nach der `onetoone_url`-Fixture einfügen:

```python
@pytest.fixture
def uniqueindex_url(tmp_path) -> str:
    """SQLite URL: Profile is 1-1 via a UNIQUE INDEX only; Note's only unique
    index is partial (WHERE ...) → must not count → stays 1-N."""
    return _build_sqlite(tmp_path, "uniqueindex.db", "uniqueindex_schema.sql")
```

- [ ] **Step 3: Failing test schreiben (Loader reflektiert Unique-Indizes, partiell ausgeschlossen)**

In `tests/test_sqlalchemy_loader.py` ans Dateiende anhängen:

```python
def test_load_reflects_unique_indexes(uniqueindex_url):
    schema = SqlAlchemyLoader(uniqueindex_url).load()
    profile = schema.table("Profile")
    # full, non-partial unique index on the FK column is reflected
    assert ("ParentID",) in profile.unique_indexes
    note = schema.table("Note")
    # the only unique index on Note is partial → must be excluded
    assert all("ParentID" not in idx for idx in note.unique_indexes)
```

- [ ] **Step 4: Test laufen lassen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py::test_load_reflects_unique_indexes -v`
Expected: FAIL — `AttributeError: 'Table' object has no attribute 'unique_indexes'`.

- [ ] **Step 5: Model-Feld ergänzen**

In `core/model.py` die `Table`-Dataclass nach `unique_constraints` (Zeile 53) erweitern:

```python
    unique_constraints: tuple[tuple[str, ...], ...] = ()
    # Column names of UNIQUE indexes (full-column, non-partial). Kept separate
    # from `unique_constraints`: a unique index is not a declared constraint.
    unique_indexes: tuple[tuple[str, ...], ...] = ()
```

- [ ] **Step 6: Loader reflektiert qualifizierende Unique-Indizes**

In `core/loaders/sqlalchemy_loader.py` direkt nach dem `uniques`-Block (vor `tables.append(...)`, aktuell Zeile 75–76) ergänzen und den `Table`-Aufruf erweitern:

```python
                except SQLAlchemyError:
                    uniques = ()
                try:
                    uidx = tuple(
                        tuple(idx["column_names"])
                        for idx in insp.get_indexes(tname)
                        if idx.get("unique")
                        and idx.get("column_names")
                        and None not in idx["column_names"]
                        and not any(k.endswith("_where")
                                    for k in (idx.get("dialect_options") or {}))
                    )
                except SQLAlchemyError:
                    uidx = ()
                tables.append(Table(tname, columns, tuple(fks), pk, uniques, uidx))
```

(Die alte `tables.append(Table(tname, columns, tuple(fks), pk, uniques))`-Zeile entfällt — ersetzt durch die Variante mit `uidx`.)

- [ ] **Step 7: Test laufen lassen — muss bestehen**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -v`
Expected: PASS (alle Loader-Tests inkl. dem neuen).

- [ ] **Step 8: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `242 passed, 1 skipped` (241 + 1 neu).

- [ ] **Step 9: Commit**

```bash
git add tests/fixtures/uniqueindex_schema.sql tests/conftest.py core/model.py core/loaders/sqlalchemy_loader.py tests/test_sqlalchemy_loader.py
git commit -m "feat: AP-51 reflect qualifying UNIQUE indexes into Table.unique_indexes"
```

---

### Task 2: `_columns_unique` zieht Unique-Indizes heran (+ Composite-Carry-over)

**Files:**
- Modify: `core/graph.py:34-43` (`_columns_unique`)
- Test: `tests/test_graph.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `core.model.Table.unique_indexes` (Task 1); bestehende Helfer `_edge_with_holder` (`tests/test_graph.py`), `client`-Fixture (`tests/test_api.py`).
- Produces: `_columns_unique` erkennt Eindeutigkeit auch über `table.unique_indexes`; `JoinEdge.fk_unique`/`to_many` werden dadurch für index-eindeutige FKs `True`/`False`.

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_graph.py` zuerst den Import ergänzen (oben bei den bestehenden Imports):

```python
from core.graph import build_graph, _columns_unique
from core.model import Table
```

(Die bestehende `from core.graph import build_graph`-Zeile durch die obige ersetzen.)

Dann ans Dateiende anhängen — Unit-Tests des Helfers (decken Composite-Carry-over + Index-Quelle ab) und zwei Graph-Integrationstests:

```python
def test_columns_unique_composite_constraint_covered():
    # composite UNIQUE constraint covering exactly the FK columns → unique
    t = Table("X", (), (), unique_constraints=(("a", "b"),))
    assert _columns_unique(t, ("a", "b")) is True


def test_columns_unique_composite_superset_not_covered():
    # the unique set has MORE columns than the FK → FK columns alone not unique
    t = Table("X", (), (), unique_constraints=(("a", "b", "c"),))
    assert _columns_unique(t, ("a", "b")) is False


def test_columns_unique_via_unique_index():
    # uniqueness sourced from a unique index, not a constraint
    t = Table("X", (), (), unique_indexes=(("a",),))
    assert _columns_unique(t, ("a",)) is True


def test_join_edge_fk_unique_via_index(uniqueindex_url):
    g = build_graph(SqlAlchemyLoader(uniqueindex_url).load())
    # Profile is unique on its FK only through a UNIQUE INDEX → 1-1
    assert _edge_with_holder(g, "Profile", "Parent").fk_unique is True


def test_partial_unique_index_does_not_count(uniqueindex_url):
    g = build_graph(SqlAlchemyLoader(uniqueindex_url).load())
    # Note's only unique index is partial (WHERE ...) → not unique → 1-N
    assert _edge_with_holder(g, "Note", "Parent").fk_unique is False
```

In `tests/test_api.py` ans Dateiende anhängen (End-to-End: Index-Eindeutigkeit unterdrückt die Fan-out-Warnung):

```python
def test_index_unique_path_has_no_fanout_warning(client, uniqueindex_url):
    """A 1-1 join whose uniqueness comes from a UNIQUE INDEX must not warn 1-N."""
    resp = client.post("/api/joinpath", json={
        "connection_url": uniqueindex_url,
        "start": {"table": "Parent", "column": "ParentID"},
        "target": {"table": "Profile", "column": "ProfileID"},
        "filters": [],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert all("1-N" not in w for w in p["warnings"])
```

- [ ] **Step 2: Tests laufen lassen — Index/Composite-Fälle schlagen fehl**

Run: `./venv/bin/python -m pytest tests/test_graph.py::test_columns_unique_via_unique_index tests/test_graph.py::test_join_edge_fk_unique_via_index -v`
Expected: FAIL — `assert False is True` (Unique-Indizes werden noch nicht herangezogen).

- [ ] **Step 3: `_columns_unique` um Unique-Indizes erweitern**

In `core/graph.py` die `_columns_unique`-Funktion (Zeilen 34–43) ersetzen:

```python
def _columns_unique(table, columns) -> bool:
    """True if ``columns`` on ``table`` are collectively unique: some unique set
    (a UNIQUE constraint, a qualifying UNIQUE index, or the primary key) is a
    subset of ``columns``."""
    target = set(columns)
    if not target:
        return False
    candidates = list(table.unique_constraints) + list(table.unique_indexes)
    if table.primary_key:
        candidates.append(table.primary_key)
    return any(set(u) <= target for u in candidates if u)
```

- [ ] **Step 4: Tests laufen lassen — bestehen**

Run: `./venv/bin/python -m pytest tests/test_graph.py tests/test_api.py -v`
Expected: PASS (neue Tests grün; bestehende AP-50-Tests unverändert grün).

- [ ] **Step 5: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `248 passed, 1 skipped` (242 + 6 neu).

- [ ] **Step 6: Commit**

```bash
git add core/graph.py tests/test_graph.py tests/test_api.py
git commit -m "feat: AP-51 _columns_unique honors UNIQUE indexes (+ composite coverage tests)"
```

---

### Task 3: Doku & Release v0.37.0

**Files:**
- Modify: `CLAUDE.md`
- Modify (via `sync_version.py`): `config.py`, `lucent-hub.yml`
- Modify: `CHANGELOG.md`, `luDBxP-docs/docs/entwicklung/changelog.md`
- Modify: `luDBxP-docs/docs/javascripts/icon-rail.js`, `luDBxP-docs/zensical.toml`

**Interfaces:**
- Consumes: fertige Implementierung aus Tasks 1–2.
- Produces: Release v0.37.0, konsistente Doku, gebaute Site.

- [ ] **Step 1: CLAUDE.md — AP-50-Grenze auf erledigt umschreiben**

In `CLAUDE.md` die AP-50-Notiz im Abschnitt „Bekannte Einschränkungen" anpassen. Den Satzteil „Uniqueness expressed *only* as a unique index is not yet detected (AP-51)." ersetzen durch:

```
Uniqueness backed by a UNIQUE index (full-column, non-partial) is detected too (AP-51); only partial and expression unique indexes are deliberately ignored.
```

- [ ] **Step 2: Version bumpen (minor)**

Run:
```bash
./venv/bin/python sync_version.py --minor
./venv/bin/python -c "import config; print(config.APP_VERSION)"
```
Expected: `0.37.0`.

- [ ] **Step 3: Changelog (Root englisch) + Mirror (deutsch)**

In `CHANGELOG.md` ganz oben (vor `## [0.36.0]`) einfügen:

```markdown
## [0.37.0] — 2026-06-27

### Added
- One-to-one detection now also recognizes uniqueness backed by a UNIQUE
  index (full-column, non-partial), not just UNIQUE constraints and primary
  keys — so a descending FK that is unique only through an index no longer
  raises a false fan-out warning. Partial and expression unique indexes are
  deliberately ignored.
```

In `luDBxP-docs/docs/entwicklung/changelog.md` ganz oben einfügen:

```markdown
## [0.37.0] — 2026-06-27

### Hinzugefügt
- 1-1-Erkennung berücksichtigt jetzt auch Unique-Indizes (voll-spaltig,
  nicht-partiell) — nicht nur UNIQUE-Constraints/PK. Partielle und
  Expression-Indizes bleiben bewusst ausgeschlossen.
```

- [ ] **Step 4: Badges + zensical nachziehen**

In `luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION='0.37.0'`, `TEST_COUNT='248'`, `TEST_DATE='2026-06-27'`.
In `luDBxP-docs/zensical.toml` Zeile 3: site_description-Ende von `· v0.36.0` auf `· v0.37.0`.

- [ ] **Step 5: Architektur-Diagramme prüfen**

Kein neues core-Modul/Endpoint (nur ein Feld + Loader-/Helfer-Logik) → `luDBxP-docs/mermaid-sources/referenz-architektur-*.mmd` brauchen i. d. R. keine Änderung. Kurz gegenprüfen, sonst unverändert lassen.

- [ ] **Step 6: Site bauen + gegenprüfen**

Run:
```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
```
Expected: Build ohne Fehler; danach gegenprüfen, dass `0.37.0` und `248` auftauchen:
```bash
grep -rl "0.37.0" luDBxP-docs/site/index.html luDBxP-docs/site/javascripts/icon-rail.js
```

- [ ] **Step 7: SDD-Final-Review**

Gesamten AP-Diff gegen die Spec prüfen: Layering (`core/` Flask-frei), Read-Only unverändert, Tests grün (248/1), partielle/Expression-Indizes korrekt ausgeschlossen, keine Doku-Drift. Niemals weglassen.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: Release v0.37.0 — AP-51 Unique-Index als Uniqueness-Quelle (Doku/Badges/Changelog/Site)"
```

- [ ] **Step 9: Push & gh-pages-Deploy — NUR auf Ansage des Nutzers**

Master-Push und der manuelle gh-pages-Deploy (Worktree, `.nojekyll` erhalten) erfolgen erst nach ausdrücklicher Freigabe. Nicht automatisch ausführen.

---

## Self-Review (durchgeführt)

**Spec-Coverage:** Reflection inkl. partiell/Expression-Ausschluss (Task 1: model+loader+Fixture), `_columns_unique` mit Index-Quelle + Composite-Carry-over (Task 2: Unit- + Graph- + API-Tests), Doku/Release/Final-Review + Grenz-Umschreibung (Task 3). Alle Spec-Abschnitte abgedeckt; Nicht-Ziele (kein Indizes-Feature, partiell/Expression ignoriert, keine SQL-/Pathfinder-Änderung) respektiert. Pathfinder braucht keinen Code (Wirkung fließt über `_columns_unique`) — kein eigener Task.

**Placeholder-Scan:** Keine TBD/TODO; jeder Code-Schritt enthält vollständigen Code; Befehle mit erwarteter Ausgabe.

**Type-Consistency:** `unique_indexes: tuple[tuple[str,...],...]` (Task 1) → in `_columns_unique`-Kandidatenliste (Task 2) → über `fk_unique`/`to_many` (unverändert aus AP-50) konsistent. Testzahlen kumulativ stimmig: 241 → 242 → 248.
