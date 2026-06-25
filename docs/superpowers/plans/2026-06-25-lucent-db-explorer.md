# Lucent DB Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Flask-Web-Tool, das aus einem reflektierten DB-Schema einen FK-Graphen baut, den kürzesten Join-Pfad zwischen zwei Spalten (plus Filter-Tabellen) findet und daraus read-only SQL generiert.

**Architecture:** Saubere Schichtung — `core/` (Domänenlogik, kennt kein Flask) und `web/` (Flask-Adapter). Loader reflektiert eine Live-DB via SQLAlchemy zu einem `Schema`-Dataclass-Modell. `graph.py` baut daraus einen ungerichteten NetworkX-Graphen (Knoten=Tabelle, Kante=FK). `pathfinder.py` findet *k*-kürzeste Pfade + webt Filter-Tabellen ein. `sqlgen.py` rendert deterministisches SQL. Flask-Blueprint exponiert `/api/schema` und `/api/joinpath`; ein Jinja-Formular ist die UI.

**Tech Stack:** Python 3.10+, Flask, SQLAlchemy (Reflection), NetworkX, pytest. Frontend: Jinja2 + vanilla JS/CSS, alle Libs lokal gebundelt (keine CDN).

## Global Constraints

- **Keine CDNs:** Jede JS/CSS/Font-Dependency lokal nach `web/static/{lib,css,js}/` bundeln; HTML-Referenzen relativ. (Globale Konvention)
- **Read-only by design:** Das Tool führt NIEMALS SQL aus. Kein Execution-Pfad, kein DB-Write, kein Result-Grid in v1.
- **Keine SQL-Injection im generierten Text:** Filterwerte als parametrisierte Named-Placeholder generieren, Werte separat ausweisen — nie roh konkatenieren.
- **Schichtregel:** `core/` importiert KEIN Flask. `web/` ruft `core/` auf, nie umgekehrt.
- **Version nur via `sync_version.py`** ändern, nie `config.py` manuell.
- **Sprache:** Code + Kommentare Englisch; Docstrings Google-Style Englisch; UI-Texte DE/EN via `strings.py`; Doku Deutsch.
- **Naming:** Dateien `snake_case`, Klassen `PascalCase`.
- **v1-Loader:** nur `sqlalchemy_loader` voll (SQLite + Postgres). `manual_loader`, `schemaspy_loader`, `ddl_loader` nur Interface-Stubs (`raise NotImplementedError`).
- **App-Identität:** `name=luDBxP`, `display_name="Lucent DB Explorer"`, Web-Port `5057` (vor erstem Hub-Start gegen Hub-Registry prüfen), `APP_VERSION="0.1.0"`.

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `config.py` | Konstanten, Pfade, `APP_VERSION`, GUI/Port-Konstanten |
| `config.json` | Runtime-Settings (Default-Connection-String, Sprache) |
| `strings.py` | i18n DE/EN |
| `core/settings.py` | JSON-Config-Persistence (Singleton) |
| `core/log.py` | Unified Logging |
| `core/model.py` | Dataclasses: `Column`, `ForeignKey`, `Table`, `Schema` |
| `core/schema_loader.py` | ABC `SchemaLoader` mit `load() -> Schema` |
| `core/loaders/sqlalchemy_loader.py` | Live-DB-Reflection (v1) |
| `core/loaders/{manual,schemaspy,ddl}_loader.py` | Stubs |
| `core/graph.py` | `build_graph(Schema) -> nx.Graph` |
| `core/pathfinder.py` | `find_paths(...) -> list[JoinPath]`; `JoinPath`/`JoinStep` Dataclasses |
| `core/sqlgen.py` | `generate_sql(JoinPath, selects, filters) -> GeneratedSQL` |
| `web/__init__.py` | `create_app()` Factory |
| `web/routes.py` | Blueprint: `/`, `/api/schema`, `/api/joinpath` |
| `web/templates/index.html` | Formular-UI |
| `web/static/{css,js}/` | lokale Assets |
| `app.py` | Entry-Point (`create_app().run`) |
| `tests/conftest.py` | Fixture: temp SQLite-DB + reflektiertes `Schema` |
| `tests/fixtures/inventory_schema.sql` | CMDB-artiges Schema mit FKs |
| `run.sh`, `sync_version.py`, `pytest.ini`, `lucent-hub.yml`, `requirements*.txt`, `CLAUDE.md`, `CHANGELOG.md`, `README.md`, `.gitignore` | Projekt-Gerüst |

**Build-Reihenfolge (Abhängigkeiten):** `model` → `schema_loader`(ABC) → `sqlalchemy_loader` → `graph` → `pathfinder` → `sqlgen` → `web`. Projekt-Gerüst (Task 1) zuerst, damit Tests laufen.

---

## Task 1: Projekt-Gerüst & Test-Harness

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore`, `config.py`, `config.json`, `core/__init__.py`, `core/loaders/__init__.py`, `web/__init__.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/fixtures/inventory_schema.sql`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nichts
- Produces: `pytest`-lauffähiges Projekt; Fixture `sqlite_engine` (SQLAlchemy `Engine` auf temp-SQLite mit geladenem Inventar-Schema) und `inventory_url` (str, `sqlite:///…`-URL der Fixture-DB).

- [ ] **Step 1: `requirements*.txt` + `pytest.ini` + `.gitignore` anlegen**

`requirements.txt`:
```
Flask>=3.0
SQLAlchemy>=2.0
networkx>=3.0
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=7.0
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

`.gitignore`:
```
venv/
.venv/
__pycache__/
*.py[cod]
*.egg-info/
Logs/
*.db
.req_stamp
.idea/
.vscode/
.DS_Store
```

- [ ] **Step 2: `config.py` + `config.json` anlegen**

`config.py`:
```python
"""App constants, paths, and version."""
import os

APP_NAME = "Lucent DB Explorer"
APP_SLUG = "luDBxP"
APP_VERSION = "0.1.0"  # NUR via sync_version.py ändern!
APP_AUTHOR = "Tobias Philipp / Lucent Trails"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "Logs")
CONFIG_JSON = os.path.join(BASE_DIR, "config.json")

WEB_HOST = "127.0.0.1"
WEB_PORT = 5057  # vor Hub-Start gegen Registry prüfen

# k-kürzeste Join-Pfade, die maximal zurückgegeben werden
MAX_JOIN_PATHS = 5
```

`config.json`:
```json
{
  "language": "de",
  "default_connection": ""
}
```

- [ ] **Step 3: Leere Package-`__init__.py` anlegen**

Lege leere Dateien an: `core/__init__.py`, `core/loaders/__init__.py`, `web/__init__.py`, `tests/__init__.py`.
(`web/__init__.py` wird in Task 7 mit `create_app` gefüllt — vorerst leer.)

- [ ] **Step 4: Fixture-Schema `tests/fixtures/inventory_schema.sql` anlegen**

```sql
CREATE TABLE OperatingSystems (
    OSID INTEGER PRIMARY KEY,
    OS_Family TEXT NOT NULL
);
CREATE TABLE VMwareCluster (
    ClusterID INTEGER PRIMARY KEY,
    ClusterName TEXT NOT NULL
);
CREATE TABLE Networks (
    NetworkID INTEGER PRIMARY KEY,
    VLAN INTEGER NOT NULL
);
CREATE TABLE VirtualMachines (
    VMID INTEGER PRIMARY KEY,
    NetworkID INTEGER NOT NULL REFERENCES Networks(NetworkID),
    OSID INTEGER NOT NULL REFERENCES OperatingSystems(OSID),
    ClusterID INTEGER NOT NULL REFERENCES VMwareCluster(ClusterID)
);
```

- [ ] **Step 5: `tests/conftest.py` mit Engine-Fixture anlegen**

```python
"""Shared pytest fixtures: a temp SQLite DB loaded from the inventory schema."""
import os
import pytest
from sqlalchemy import create_engine, text


def _schema_sql() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "fixtures", "inventory_schema.sql"), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture
def inventory_url(tmp_path) -> str:
    """File-based SQLite URL so SQLAlchemy reflection sees the schema."""
    db_path = tmp_path / "inventory.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    with engine.begin() as conn:
        # PRAGMA so SQLite reports foreign keys during reflection
        for statement in _schema_sql().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))
    engine.dispose()
    return url


@pytest.fixture
def sqlite_engine(inventory_url):
    engine = create_engine(inventory_url)
    yield engine
    engine.dispose()
```

- [ ] **Step 6: Smoke-Test schreiben**

`tests/test_smoke.py`:
```python
from sqlalchemy import inspect


def test_fixture_has_foreign_keys(sqlite_engine):
    insp = inspect(sqlite_engine)
    assert set(insp.get_table_names()) == {
        "OperatingSystems", "VMwareCluster", "Networks", "VirtualMachines",
    }
    fks = insp.get_foreign_keys("VirtualMachines")
    assert len(fks) == 3
```

- [ ] **Step 7: Test laufen lassen (muss zuerst fehlschlagen, dann grün)**

Run: `python -m venv venv && ./venv/bin/pip install -r requirements-dev.txt && ./venv/bin/python -m pytest tests/test_smoke.py -v`
Expected: PASS (2 Assertions). Falls die FK-Reflection leer ist, prüfen, dass die SQLite-DB **file-based** ist (nicht `:memory:`) — Reflection braucht eine echte Datei.

- [ ] **Step 8: Commit**

```bash
git add requirements*.txt pytest.ini .gitignore config.py config.json core/ web/ tests/
git commit -m "chore: Projekt-Gerüst + pytest-Fixture (SQLite-Inventar-Schema)"
```

---

## Task 2: Domänenmodell (`core/model.py`)

**Files:**
- Create: `core/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: nichts
- Produces:
  ```python
  @dataclass(frozen=True)
  class Column: name: str; type: str
  @dataclass(frozen=True)
  class ForeignKey: column: str; ref_table: str; ref_column: str
  @dataclass(frozen=True)
  class Table: name: str; columns: tuple[Column, ...]; foreign_keys: tuple[ForeignKey, ...]
  @dataclass(frozen=True)
  class Schema:
      tables: tuple[Table, ...]
      def table(self, name: str) -> Table        # KeyError wenn unbekannt
      def has_column(self, table: str, column: str) -> bool
  ```

- [ ] **Step 1: Failing test schreiben**

`tests/test_model.py`:
```python
import pytest
from core.model import Column, ForeignKey, Table, Schema


def _sample() -> Schema:
    return Schema(tables=(
        Table("Networks", (Column("NetworkID", "INTEGER"), Column("VLAN", "INTEGER")), ()),
        Table("VirtualMachines",
              (Column("VMID", "INTEGER"), Column("NetworkID", "INTEGER")),
              (ForeignKey("NetworkID", "Networks", "NetworkID"),)),
    ))


def test_table_lookup_returns_table():
    assert _sample().table("Networks").name == "Networks"


def test_table_lookup_unknown_raises():
    with pytest.raises(KeyError):
        _sample().table("Nope")


def test_has_column():
    s = _sample()
    assert s.has_column("Networks", "VLAN") is True
    assert s.has_column("Networks", "Ghost") is False
    assert s.has_column("Ghost", "VLAN") is False
```

- [ ] **Step 2: Test laufen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_model.py -v`
Expected: FAIL (`ModuleNotFoundError: core.model`)

- [ ] **Step 3: `core/model.py` implementieren**

```python
"""Schema domain model: plain immutable dataclasses, no Flask/SQLAlchemy deps."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    type: str


@dataclass(frozen=True)
class ForeignKey:
    column: str       # local column on the owning table
    ref_table: str
    ref_column: str


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    foreign_keys: tuple[ForeignKey, ...]


@dataclass(frozen=True)
class Schema:
    tables: tuple[Table, ...]

    def table(self, name: str) -> Table:
        for t in self.tables:
            if t.name == name:
                return t
        raise KeyError(name)

    def has_column(self, table: str, column: str) -> bool:
        try:
            t = self.table(table)
        except KeyError:
            return False
        return any(c.name == column for c in t.columns)
```

- [ ] **Step 4: Test laufen — muss grün sein**

Run: `./venv/bin/python -m pytest tests/test_model.py -v`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add core/model.py tests/test_model.py
git commit -m "feat(core): Schema-Domänenmodell (Column/ForeignKey/Table/Schema)"
```

---

## Task 3: Loader-Interface + Stubs (`core/schema_loader.py`, `core/loaders/*`)

**Files:**
- Create: `core/schema_loader.py`, `core/loaders/manual_loader.py`, `core/loaders/schemaspy_loader.py`, `core/loaders/ddl_loader.py`
- Test: `tests/test_loader_interface.py`

**Interfaces:**
- Consumes: `core.model.Schema`
- Produces:
  ```python
  class SchemaLoader(ABC):
      @abstractmethod
      def load(self) -> Schema: ...
  # Stubs: ManualLoader, SchemaSpyLoader, DdlLoader — load() raises NotImplementedError
  ```

- [ ] **Step 1: Failing test schreiben**

`tests/test_loader_interface.py`:
```python
import pytest
from core.schema_loader import SchemaLoader
from core.loaders.manual_loader import ManualLoader
from core.loaders.schemaspy_loader import SchemaSpyLoader
from core.loaders.ddl_loader import DdlLoader


def test_cannot_instantiate_abstract_loader():
    with pytest.raises(TypeError):
        SchemaLoader()  # abstract


@pytest.mark.parametrize("cls", [ManualLoader, SchemaSpyLoader, DdlLoader])
def test_stub_loaders_raise_not_implemented(cls):
    loader = cls()
    with pytest.raises(NotImplementedError):
        loader.load()
```

- [ ] **Step 2: Test laufen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_loader_interface.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: ABC + Stubs implementieren**

`core/schema_loader.py`:
```python
"""Loader contract: every schema source implements load() -> Schema."""
from abc import ABC, abstractmethod
from core.model import Schema


class SchemaLoader(ABC):
    @abstractmethod
    def load(self) -> Schema:
        """Read a schema source and return the domain Schema."""
```

`core/loaders/manual_loader.py`:
```python
"""Stub: manual JSON/YAML schema definition (later iteration)."""
from core.schema_loader import SchemaLoader
from core.model import Schema


class ManualLoader(SchemaLoader):
    def load(self) -> Schema:
        raise NotImplementedError("Manual JSON/YAML loader is planned for a later version.")
```

`core/loaders/schemaspy_loader.py`:
```python
"""Stub: SchemaSpy metadata import (later iteration)."""
from core.schema_loader import SchemaLoader
from core.model import Schema


class SchemaSpyLoader(SchemaLoader):
    def load(self) -> Schema:
        raise NotImplementedError("SchemaSpy import is planned for a later version.")
```

`core/loaders/ddl_loader.py`:
```python
"""Stub: SQL DDL file parser (later iteration)."""
from core.schema_loader import SchemaLoader
from core.model import Schema


class DdlLoader(SchemaLoader):
    def load(self) -> Schema:
        raise NotImplementedError("SQL DDL parser is planned for a later version.")
```

- [ ] **Step 4: Test laufen — muss grün sein**

Run: `./venv/bin/python -m pytest tests/test_loader_interface.py -v`
Expected: PASS (4 Tests: 1 abstract + 3 parametrisiert)

- [ ] **Step 5: Commit**

```bash
git add core/schema_loader.py core/loaders/ tests/test_loader_interface.py
git commit -m "feat(core): SchemaLoader-ABC + Stub-Loader (manual/schemaspy/ddl)"
```

---

## Task 4: SQLAlchemy-Loader (`core/loaders/sqlalchemy_loader.py`)

**Files:**
- Create: `core/loaders/sqlalchemy_loader.py`
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Consumes: `core.model.{Schema,Table,Column,ForeignKey}`, `core.schema_loader.SchemaLoader`, Fixture `inventory_url`
- Produces:
  ```python
  class SqlAlchemyLoader(SchemaLoader):
      def __init__(self, connection_url: str) -> None
      def load(self) -> Schema   # raises ConnectionError on bad URL/unreachable DB
  ```

- [ ] **Step 1: Failing test schreiben**

`tests/test_sqlalchemy_loader.py`:
```python
import pytest
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader


def test_load_reflects_tables_and_columns(inventory_url):
    schema = SqlAlchemyLoader(inventory_url).load()
    names = {t.name for t in schema.tables}
    assert names == {"OperatingSystems", "VMwareCluster", "Networks", "VirtualMachines"}
    assert schema.has_column("Networks", "VLAN")


def test_load_reflects_foreign_keys(inventory_url):
    schema = SqlAlchemyLoader(inventory_url).load()
    vm = schema.table("VirtualMachines")
    fk_targets = {(fk.column, fk.ref_table, fk.ref_column) for fk in vm.foreign_keys}
    assert ("NetworkID", "Networks", "NetworkID") in fk_targets
    assert ("OSID", "OperatingSystems", "OSID") in fk_targets
    assert ("ClusterID", "VMwareCluster", "ClusterID") in fk_targets


def test_bad_url_raises_connection_error():
    with pytest.raises(ConnectionError):
        SqlAlchemyLoader("sqlite:////nonexistent/path/that/cannot/exist.db").load()
```

- [ ] **Step 2: Test laufen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Loader implementieren**

```python
"""Live-DB schema loader via SQLAlchemy reflection (SQLite + Postgres for v1)."""
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

from core.model import Column, ForeignKey, Table, Schema
from core.schema_loader import SchemaLoader


class SqlAlchemyLoader(SchemaLoader):
    def __init__(self, connection_url: str) -> None:
        self._url = connection_url

    def load(self) -> Schema:
        try:
            engine = create_engine(self._url)
            insp = inspect(engine)
            tables = []
            for tname in insp.get_table_names():
                columns = tuple(
                    Column(col["name"], str(col["type"]))
                    for col in insp.get_columns(tname)
                )
                fks = []
                for fk in insp.get_foreign_keys(tname):
                    # SQLAlchemy returns parallel lists for composite keys;
                    # v1 models each column pair as its own ForeignKey edge.
                    for local, remote in zip(
                        fk["constrained_columns"], fk["referred_columns"]
                    ):
                        fks.append(ForeignKey(local, fk["referred_table"], remote))
                tables.append(Table(tname, columns, tuple(fks)))
            engine.dispose()
            return Schema(tuple(tables))
        except SQLAlchemyError as exc:
            raise ConnectionError(f"Could not reflect schema: {exc}") from exc
```

- [ ] **Step 4: Test laufen — muss grün sein**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -v`
Expected: PASS (3 Tests). Falls `test_bad_url_raises_connection_error` durchfällt: SQLite legt fehlende Dateien an — der Pfad `/nonexistent/...` ist nicht beschreibbar, daher wirft `inspect`/Reflection. Falls die DB doch angelegt wird, leeres Schema-Reflection ist ok — Test ggf. auf unerreichbare Postgres-URL umstellen.

- [ ] **Step 5: Commit**

```bash
git add core/loaders/sqlalchemy_loader.py tests/test_sqlalchemy_loader.py
git commit -m "feat(core): SQLAlchemy-Live-Reflection-Loader"
```

---

## Task 5: FK-Graph (`core/graph.py`)

**Files:**
- Create: `core/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `core.model.Schema`, `networkx`
- Produces:
  ```python
  def build_graph(schema: Schema) -> networkx.Graph
  # Knoten: Tabellenname (str). Kante (a,b) Attribut "joins":
  #   tuple[tuple[str,str,str,str], ...] mit (left_table, left_col, right_table, right_col).
  #   Mehrere FKs zwischen denselben zwei Tabellen sammeln sich in diesem Tuple.
  ```

- [ ] **Step 1: Failing test schreiben**

`tests/test_graph.py`:
```python
from core.graph import build_graph
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader


def test_graph_nodes_are_tables(inventory_url):
    g = build_graph(SqlAlchemyLoader(inventory_url).load())
    assert set(g.nodes) == {
        "OperatingSystems", "VMwareCluster", "Networks", "VirtualMachines",
    }


def test_graph_has_fk_edges_with_join_columns(inventory_url):
    g = build_graph(SqlAlchemyLoader(inventory_url).load())
    assert g.has_edge("VirtualMachines", "Networks")
    joins = g["VirtualMachines"]["Networks"]["joins"]
    # normalize to a set of frozensets so edge direction doesn't matter
    pairs = {frozenset(((lt, lc), (rt, rc))) for (lt, lc, rt, rc) in joins}
    assert frozenset((("VirtualMachines", "NetworkID"), ("Networks", "NetworkID"))) in pairs


def test_isolated_table_is_still_a_node(inventory_url):
    # VMwareCluster has no outgoing FK but is referenced — must still be a node
    g = build_graph(SqlAlchemyLoader(inventory_url).load())
    assert "VMwareCluster" in g.nodes
```

- [ ] **Step 2: Test laufen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_graph.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: `core/graph.py` implementieren**

```python
"""Build an undirected NetworkX graph from a Schema's foreign keys.

Nodes are table names; each edge carries a "joins" tuple of
(left_table, left_col, right_table, right_col) describing how to join the
two tables. The graph is undirected because a join works in both directions.
"""
import networkx as nx

from core.model import Schema


def build_graph(schema: Schema) -> nx.Graph:
    g = nx.Graph()
    for table in schema.tables:
        g.add_node(table.name)
    for table in schema.tables:
        for fk in table.foreign_keys:
            edge = (table.name, fk.column, fk.ref_table, fk.ref_column)
            if g.has_edge(table.name, fk.ref_table):
                existing = g[table.name][fk.ref_table]["joins"]
                g[table.name][fk.ref_table]["joins"] = existing + (edge,)
            else:
                g.add_edge(table.name, fk.ref_table, joins=(edge,))
    return g
```

- [ ] **Step 4: Test laufen — muss grün sein**

Run: `./venv/bin/python -m pytest tests/test_graph.py -v`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add core/graph.py tests/test_graph.py
git commit -m "feat(core): FK-Graph-Aufbau (NetworkX, Join-Spalten auf Kanten)"
```

---

## Task 6: Pathfinder (`core/pathfinder.py`)

**Files:**
- Create: `core/pathfinder.py`
- Test: `tests/test_pathfinder.py`

**Interfaces:**
- Consumes: `networkx.Graph` aus `build_graph`, `config.MAX_JOIN_PATHS`
- Produces:
  ```python
  @dataclass(frozen=True)
  class JoinStep: left_table: str; left_col: str; right_table: str; right_col: str
  @dataclass(frozen=True)
  class JoinPath:
      tables: tuple[str, ...]    # in Join-Reihenfolge, beginnend mit base table
      steps: tuple[JoinStep, ...]
  class NoPathError(Exception): ...

  def find_paths(graph, start_table, target_table,
                 filter_tables=(), k=MAX_JOIN_PATHS) -> list[JoinPath]
  # - kürzeste-zuerst, deterministischer Tie-Break (lexikografische Tabellensequenz)
  # - jede filter_table, die nicht im Pfad liegt, wird über kürzesten Verbindungspfad eingewoben
  # - raises NoPathError wenn start/target (oder eine filter_table) nicht verbunden sind
  ```

- [ ] **Step 1: Failing test schreiben**

`tests/test_pathfinder.py`:
```python
import pytest
from core.graph import build_graph
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.pathfinder import find_paths, NoPathError


@pytest.fixture
def graph(inventory_url):
    return build_graph(SqlAlchemyLoader(inventory_url).load())


def test_direct_path_networks_to_vm(graph):
    paths = find_paths(graph, "Networks", "VirtualMachines")
    assert paths[0].tables == ("Networks", "VirtualMachines")
    step = paths[0].steps[0]
    assert {step.left_table, step.right_table} == {"Networks", "VirtualMachines"}


def test_two_hop_networks_to_cluster(graph):
    # Networks -> VirtualMachines -> VMwareCluster
    paths = find_paths(graph, "Networks", "VMwareCluster")
    assert paths[0].tables == ("Networks", "VirtualMachines", "VMwareCluster")


def test_determinism(graph):
    a = find_paths(graph, "Networks", "VMwareCluster")
    b = find_paths(graph, "Networks", "VMwareCluster")
    assert [p.tables for p in a] == [p.tables for p in b]


def test_filter_table_is_woven_in(graph):
    # Start/target on the Networks<->Cluster axis, filter forces OperatingSystems in
    paths = find_paths(graph, "Networks", "VMwareCluster",
                       filter_tables=("OperatingSystems",))
    assert "OperatingSystems" in paths[0].tables


def test_no_path_raises():
    import networkx as nx
    g = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    with pytest.raises(NoPathError):
        find_paths(g, "A", "B")
```

- [ ] **Step 2: Test laufen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_pathfinder.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: `core/pathfinder.py` implementieren**

```python
"""Find join paths between two tables, weaving in required filter tables.

Shortest-first with a deterministic tie-break (lexicographic table sequence)
so identical input always yields identical SQL. Returns up to k candidates.
"""
from dataclasses import dataclass

import networkx as nx

import config


class NoPathError(Exception):
    """Raised when no join path connects the requested tables."""


@dataclass(frozen=True)
class JoinStep:
    left_table: str
    left_col: str
    right_table: str
    right_col: str


@dataclass(frozen=True)
class JoinPath:
    tables: tuple[str, ...]
    steps: tuple[JoinStep, ...]


def _join_step(graph: nx.Graph, a: str, b: str) -> JoinStep:
    """Pick the first join pair for edge (a,b), oriented a -> b deterministically."""
    joins = graph[a][b]["joins"]
    # deterministic: sort the candidate join tuples, take the first
    lt, lc, rt, rc = sorted(joins)[0]
    if lt == a:
        return JoinStep(lt, lc, rt, rc)
    return JoinStep(rt, rc, lt, lc)


def _to_join_path(graph: nx.Graph, node_seq: list[str]) -> JoinPath:
    steps = tuple(
        _join_step(graph, node_seq[i], node_seq[i + 1])
        for i in range(len(node_seq) - 1)
    )
    return JoinPath(tuple(node_seq), steps)


def _shortest_between(graph: nx.Graph, a: str, b: str) -> list[str]:
    try:
        return nx.shortest_path(graph, a, b)
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise NoPathError(f"No join path between {a} and {b}") from exc


def find_paths(graph, start_table, target_table,
               filter_tables=(), k=config.MAX_JOIN_PATHS):
    if start_table not in graph or target_table not in graph:
        raise NoPathError(f"Unknown table: {start_table} or {target_table}")

    # k shortest simple paths, shortest first, deterministic tie-break
    try:
        raw = list(nx.shortest_simple_paths(graph, start_table, target_table))
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise NoPathError(
            f"No join path between {start_table} and {target_table}"
        ) from exc
    raw.sort(key=lambda seq: (len(seq), seq))  # length then lexicographic
    candidates = raw[:k]

    results = []
    for node_seq in candidates:
        seq = list(node_seq)
        # weave in filter tables not already on the path
        for ftable in filter_tables:
            if ftable in seq:
                continue
            # connect ftable to the nearest node already in seq
            best = None
            for node in seq:
                try:
                    conn = nx.shortest_path(graph, node, ftable)
                except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                    raise NoPathError(
                        f"Filter table {ftable} is not connected"
                    ) from exc
                if best is None or (len(conn), conn) < (len(best), best):
                    best = conn
            # append the connecting hops (skip the first, already in seq)
            for node in best[1:]:
                if node not in seq:
                    seq.append(node)
        results.append(_to_join_path(graph, seq))
    return results
```

- [ ] **Step 4: Test laufen — muss grün sein**

Run: `./venv/bin/python -m pytest tests/test_pathfinder.py -v`
Expected: PASS (5 Tests)

- [ ] **Step 5: Commit**

```bash
git add core/pathfinder.py tests/test_pathfinder.py
git commit -m "feat(core): Pathfinder (k-kürzeste Pfade + Filter-Einwebung, deterministisch)"
```

---

## Task 7: SQL-Generator (`core/sqlgen.py`)

**Files:**
- Create: `core/sqlgen.py`
- Test: `tests/test_sqlgen.py`

**Interfaces:**
- Consumes: `core.pathfinder.{JoinPath,JoinStep}`
- Produces:
  ```python
  @dataclass(frozen=True)
  class Filter: table: str; column: str; op: str; value: object  # op in {=,!=,<,>,<=,>=,LIKE}
  @dataclass(frozen=True)
  class Selection: table: str; column: str
  @dataclass(frozen=True)
  class GeneratedSQL: sql: str; params: dict[str, object]

  def generate_sql(path: JoinPath, selects: tuple[Selection, ...],
                   filters: tuple[Filter, ...] = ()) -> GeneratedSQL
  # SELECT der gewählten Spalten, FROM base table, JOIN je Step mit ON,
  # WHERE aus Filtern mit named placeholders (:p0, :p1, ...).
  ```

- [ ] **Step 1: Failing test schreiben**

`tests/test_sqlgen.py`:
```python
from core.pathfinder import JoinPath, JoinStep
from core.sqlgen import generate_sql, Selection, Filter


def _path():
    return JoinPath(
        tables=("Networks", "VirtualMachines", "VMwareCluster"),
        steps=(
            JoinStep("Networks", "NetworkID", "VirtualMachines", "NetworkID"),
            JoinStep("VirtualMachines", "ClusterID", "VMwareCluster", "ClusterID"),
        ),
    )


def test_basic_select_join():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID")))
    assert "SELECT" in g.sql
    assert "FROM Networks" in g.sql
    assert "JOIN VirtualMachines ON Networks.NetworkID = VirtualMachines.NetworkID" in g.sql
    assert "JOIN VMwareCluster ON VirtualMachines.ClusterID = VMwareCluster.ClusterID" in g.sql
    assert g.params == {}


def test_filter_uses_named_placeholder():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "=", 7),))
    assert "WHERE VirtualMachines.OSID = :p0" in g.sql
    assert g.params == {"p0": 7}
    # value must never be inlined
    assert "= 7" not in g.sql


def test_determinism():
    a = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),))
    b = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),))
    assert a.sql == b.sql
```

- [ ] **Step 2: Test laufen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_sqlgen.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: `core/sqlgen.py` implementieren**

```python
"""Render a JoinPath + selections + filters into read-only SQL text.

Never executes anything. Filter values become named placeholders (:p0, :p1, …)
returned separately in `params`, so callers can show parameterized SQL and the
generated string is never a string-concatenation injection vector.
"""
from dataclasses import dataclass

from core.pathfinder import JoinPath

_ALLOWED_OPS = {"=", "!=", "<", ">", "<=", ">=", "LIKE"}


@dataclass(frozen=True)
class Selection:
    table: str
    column: str


@dataclass(frozen=True)
class Filter:
    table: str
    column: str
    op: str
    value: object


@dataclass(frozen=True)
class GeneratedSQL:
    sql: str
    params: dict


def generate_sql(path: JoinPath, selects, filters=()) -> GeneratedSQL:
    if not selects:
        raise ValueError("At least one selection is required.")

    select_cols = ", ".join(f"{s.table}.{s.column}" for s in selects)
    base = path.tables[0]
    lines = [f"SELECT {select_cols}", f"FROM {base}"]

    for step in path.steps:
        on = f"{step.left_table}.{step.left_col} = {step.right_table}.{step.right_col}"
        lines.append(f"JOIN {step.right_table} ON {on}")

    params: dict = {}
    if filters:
        clauses = []
        for i, flt in enumerate(filters):
            if flt.op not in _ALLOWED_OPS:
                raise ValueError(f"Unsupported operator: {flt.op}")
            key = f"p{i}"
            clauses.append(f"{flt.table}.{flt.column} {flt.op} :{key}")
            params[key] = flt.value
        lines.append("WHERE " + " AND ".join(clauses))

    return GeneratedSQL(sql="\n".join(lines), params=params)
```

- [ ] **Step 4: Test laufen — muss grün sein**

Run: `./venv/bin/python -m pytest tests/test_sqlgen.py -v`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add core/sqlgen.py tests/test_sqlgen.py
git commit -m "feat(core): SQL-Generator (read-only, parametrisierte Filter)"
```

---

## Task 8: Flask-App + API (`web/__init__.py`, `web/routes.py`, `app.py`)

**Files:**
- Create: `web/routes.py`, `app.py`
- Modify: `web/__init__.py` (von leer zu `create_app`-Factory)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: alle `core/`-Module, `config.{WEB_HOST,WEB_PORT}`
- Produces:
  ```python
  # web/__init__.py
  def create_app() -> flask.Flask
  # Endpunkte (JSON):
  #   POST /api/schema   body {connection_url}      -> {tables:[{name,columns:[...]}]} | 400 {error}
  #   POST /api/joinpath body {connection_url, start:{table,column},
  #                            target:{table,column}, filters:[{table,column,op,value}]}
  #                      -> {paths:[{tables, sql, params}]} | 400 {error}
  ```

- [ ] **Step 1: Failing test schreiben**

`tests/test_api.py`:
```python
import pytest
from web import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_schema_endpoint_returns_tables(client, inventory_url):
    resp = client.post("/api/schema", json={"connection_url": inventory_url})
    assert resp.status_code == 200
    names = {t["name"] for t in resp.get_json()["tables"]}
    assert "VirtualMachines" in names


def test_joinpath_endpoint_returns_sql(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [],
    })
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]
    assert paths
    assert "SELECT" in paths[0]["sql"]
    assert "VirtualMachines" in paths[0]["tables"]


def test_joinpath_no_connection_returns_400(client):
    resp = client.post("/api/joinpath", json={
        "connection_url": "sqlite:////nope/x.db",
        "start": {"table": "A", "column": "x"},
        "target": {"table": "B", "column": "y"},
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()
```

- [ ] **Step 2: Test laufen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_api.py -v`
Expected: FAIL (`ImportError: cannot import name 'create_app'`)

- [ ] **Step 3: `web/routes.py` implementieren**

```python
"""HTTP API: reflect a schema and compute join-path SQL. Read-only."""
from flask import Blueprint, jsonify, render_template, request

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.graph import build_graph
from core.pathfinder import find_paths, NoPathError
from core.sqlgen import generate_sql, Selection, Filter

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.post("/api/schema")
def api_schema():
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    try:
        schema = SqlAlchemyLoader(url).load()
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(tables=[
        {"name": t.name, "columns": [c.name for c in t.columns]}
        for t in schema.tables
    ])


@bp.post("/api/joinpath")
def api_joinpath():
    data = request.get_json(silent=True) or {}
    try:
        schema = SqlAlchemyLoader(data["connection_url"]).load()
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    except KeyError:
        return jsonify(error="connection_url is required"), 400

    graph = build_graph(schema)
    start = data["start"]
    target = data["target"]
    filters = tuple(
        Filter(f["table"], f["column"], f["op"], f["value"])
        for f in data.get("filters", [])
    )
    filter_tables = tuple(f.table for f in filters)
    selects = (Selection(start["table"], start["column"]),
               Selection(target["table"], target["column"]))
    try:
        paths = find_paths(graph, start["table"], target["table"], filter_tables)
    except NoPathError as exc:
        return jsonify(error=str(exc)), 400

    out = []
    for p in paths:
        gen = generate_sql(p, selects, filters)
        out.append({"tables": list(p.tables), "sql": gen.sql, "params": gen.params})
    return jsonify(paths=out)
```

- [ ] **Step 4: `web/__init__.py` als Factory implementieren**

```python
"""Flask application factory."""
from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    from web.routes import bp
    app.register_blueprint(bp)
    return app
```

- [ ] **Step 5: `app.py` Entry-Point + Minimal-Template anlegen**

`app.py`:
```python
"""Lucent DB Explorer — entry point."""
import config
from web import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=config.WEB_HOST, port=config.WEB_PORT)
```

`web/templates/index.html` (Minimal-Platzhalter, damit `GET /` rendert — volle UI in Task 9):
```html
<!doctype html>
<html lang="de">
<head><meta charset="utf-8"><title>Lucent DB Explorer</title></head>
<body><h1>Lucent DB Explorer</h1></body>
</html>
```

- [ ] **Step 6: Test laufen — muss grün sein**

Run: `./venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS (3 Tests)

- [ ] **Step 7: Commit**

```bash
git add web/ app.py tests/test_api.py
git commit -m "feat(web): Flask-Factory + /api/schema + /api/joinpath"
```

---

## Task 9: Frontend-Formular (`web/templates/index.html`, `web/static/`)

**Files:**
- Modify: `web/templates/index.html`
- Create: `web/static/css/app.css`, `web/static/js/app.js`
- Test: `tests/test_index_page.py`

**Interfaces:**
- Consumes: `/api/schema`, `/api/joinpath` (aus Task 8)
- Produces: serverseitig nur die gerenderte Seite; JS ruft die JSON-APIs. Keine neuen Python-Schnittstellen.

- [ ] **Step 1: Failing test schreiben**

`tests/test_index_page.py`:
```python
import pytest
from web import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_renders_form_and_local_assets(client):
    html = client.get("/").get_data(as_text=True)
    assert "Lucent DB Explorer" in html
    assert 'id="connection_url"' in html
    # assets must be local, never a CDN
    assert "/static/js/app.js" in html
    assert "http://" not in html and "https://" not in html
```

- [ ] **Step 2: Test laufen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_index_page.py -v`
Expected: FAIL (Form-Marker fehlen im Minimal-Template)

- [ ] **Step 3: `index.html` ausbauen**

```html
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lucent DB Explorer</title>
  <link rel="stylesheet" href="/static/css/app.css">
</head>
<body>
  <h1>Lucent DB Explorer</h1>
  <section>
    <label>Connection-URL
      <input type="text" id="connection_url" placeholder="sqlite:///inventory.db">
    </label>
    <button id="btn_load">Schema laden</button>
  </section>

  <section id="builder" hidden>
    <label>Start <select id="start_table"></select>.<select id="start_col"></select></label>
    <label>Ziel <select id="target_table"></select>.<select id="target_col"></select></label>
    <div id="filters"></div>
    <button id="btn_add_filter">Filter +</button>
    <button id="btn_build">Join-Pfad bauen</button>
  </section>

  <section id="result" hidden>
    <ul id="path_list"></ul>
    <pre id="sql_out"></pre>
  </section>

  <script src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: `app.css` + `app.js` anlegen**

`web/static/css/app.css`:
```css
body { font-family: system-ui, sans-serif; max-width: 880px; margin: 2rem auto; padding: 0 1rem; }
section { margin: 1rem 0; }
pre { background: #1A1A2E; color: #eaeaea; padding: 1rem; overflow-x: auto; }
label { display: block; margin: .5rem 0; }
```

`web/static/js/app.js`:
```javascript
"use strict";
let SCHEMA = { tables: [] };

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || "Fehler");
  return data;
}

function fillTableSelects() {
  const opts = SCHEMA.tables.map((t) => `<option>${t.name}</option>`).join("");
  for (const id of ["start_table", "target_table"]) {
    document.getElementById(id).innerHTML = opts;
  }
  fillColumns("start_table", "start_col");
  fillColumns("target_table", "target_col");
}

function fillColumns(tableSel, colSel) {
  const tname = document.getElementById(tableSel).value;
  const t = SCHEMA.tables.find((x) => x.name === tname);
  document.getElementById(colSel).innerHTML =
    (t ? t.columns : []).map((c) => `<option>${c}</option>`).join("");
}

document.getElementById("btn_load").addEventListener("click", async () => {
  const url = document.getElementById("connection_url").value;
  try {
    SCHEMA = await postJSON("/api/schema", { connection_url: url });
    fillTableSelects();
    document.getElementById("builder").hidden = false;
  } catch (e) { alert(e.message); }
});

document.getElementById("start_table").addEventListener("change", () =>
  fillColumns("start_table", "start_col"));
document.getElementById("target_table").addEventListener("change", () =>
  fillColumns("target_table", "target_col"));

document.getElementById("btn_build").addEventListener("click", async () => {
  const url = document.getElementById("connection_url").value;
  const body = {
    connection_url: url,
    start: { table: start_table.value, column: start_col.value },
    target: { table: target_table.value, column: target_col.value },
    filters: [],
  };
  try {
    const data = await postJSON("/api/joinpath", body);
    const list = document.getElementById("path_list");
    list.innerHTML = data.paths
      .map((p, i) => `<li><a href="#" data-i="${i}">${p.tables.join(" → ")}</a></li>`)
      .join("");
    const show = (i) => { document.getElementById("sql_out").textContent = data.paths[i].sql; };
    list.querySelectorAll("a").forEach((a) =>
      a.addEventListener("click", (ev) => { ev.preventDefault(); show(+a.dataset.i); }));
    show(0);
    document.getElementById("result").hidden = false;
  } catch (e) { alert(e.message); }
});
```

- [ ] **Step 5: Test laufen — muss grün sein**

Run: `./venv/bin/python -m pytest tests/test_index_page.py -v`
Expected: PASS

- [ ] **Step 6: Manueller End-to-End-Check**

Run: `./venv/bin/python app.py` und im Browser `http://127.0.0.1:5057` öffnen. Connection-URL einer SQLite-Test-DB eingeben → „Schema laden" → Start/Ziel wählen → „Join-Pfad bauen" → SQL erscheint.
Expected: Pfad `Networks → VirtualMachines → VMwareCluster` + generiertes SELECT.

- [ ] **Step 7: Commit**

```bash
git add web/templates/index.html web/static/ tests/test_index_page.py
git commit -m "feat(web): Formular-UI (lokale Assets, Schema-Laden + Pfad-Bau)"
```

---

## Task 10: Projekt-Abschluss-Dateien (`run.sh`, `lucent-hub.yml`, `sync_version.py`, Doku)

**Files:**
- Create: `run.sh`, `lucent-hub.yml`, `sync_version.py`, `strings.py`, `core/settings.py`, `core/log.py`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`
- Test: `tests/test_sync_version.py`

**Interfaces:**
- Consumes: `config.APP_VERSION`
- Produces: `sync_version.py` CLI (`--patch/--minor/--major/--set X.Y.Z`), das `config.py APP_VERSION` + `lucent-hub.yml version` aktualisiert.

- [ ] **Step 1: Failing test für `sync_version` schreiben**

`tests/test_sync_version.py`:
```python
import re
import sync_version


def test_bump_patch():
    assert sync_version.bump("0.1.0", "patch") == "0.1.1"


def test_bump_minor():
    assert sync_version.bump("0.1.3", "minor") == "0.2.0"


def test_bump_major():
    assert sync_version.bump("1.2.3", "major") == "2.0.0"


def test_set_explicit_validates():
    assert sync_version.bump("0.1.0", "set", "3.4.5") == "3.4.5"
```

- [ ] **Step 2: Test laufen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_sync_version.py -v`
Expected: FAIL (`ModuleNotFoundError: sync_version`)

- [ ] **Step 3: `sync_version.py` implementieren**

```python
"""Version sync: bump config.APP_VERSION and lucent-hub.yml in lockstep.

Usage: python sync_version.py --patch | --minor | --major | --set X.Y.Z
NEVER edit config.py APP_VERSION manually.
"""
import re
import sys

import config

_VER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def bump(current: str, kind: str, explicit: str = "") -> str:
    if kind == "set":
        if not _VER_RE.match(explicit):
            raise ValueError(f"Invalid version: {explicit}")
        return explicit
    major, minor, patch = (int(x) for x in current.split("."))
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "major":
        return f"{major + 1}.0.0"
    raise ValueError(f"Unknown bump kind: {kind}")


def _write(new_version: str) -> None:
    import os
    cfg = os.path.join(config.BASE_DIR, "config.py")
    with open(cfg, encoding="utf-8") as fh:
        text = fh.read()
    text = re.sub(r'APP_VERSION = "[^"]+"', f'APP_VERSION = "{new_version}"', text)
    with open(cfg, "w", encoding="utf-8") as fh:
        fh.write(text)
    hub = os.path.join(config.BASE_DIR, "lucent-hub.yml")
    if os.path.exists(hub):
        with open(hub, encoding="utf-8") as fh:
            htext = fh.read()
        htext = re.sub(r'version: "[^"]+"', f'version: "{new_version}"', htext)
        with open(hub, "w", encoding="utf-8") as fh:
            fh.write(htext)


def main(argv: list[str]) -> None:
    flag = argv[1] if len(argv) > 1 else ""
    mapping = {"--patch": "patch", "--minor": "minor", "--major": "major"}
    if flag in mapping:
        new = bump(config.APP_VERSION, mapping[flag])
    elif flag == "--set" and len(argv) > 2:
        new = bump(config.APP_VERSION, "set", argv[2])
    else:
        print("Usage: sync_version.py --patch|--minor|--major|--set X.Y.Z")
        return
    _write(new)
    print(f"Version: {config.APP_VERSION} -> {new}")


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Test laufen — muss grün sein**

Run: `./venv/bin/python -m pytest tests/test_sync_version.py -v`
Expected: PASS (4 Tests)

- [ ] **Step 5: `strings.py`, `core/settings.py`, `core/log.py` anlegen**

`strings.py`:
```python
"""UI text internationalization (DE/EN)."""
_STRINGS = {
    "app_title":   {"de": "Lucent DB Explorer", "en": "Lucent DB Explorer"},
    "btn_load":    {"de": "Schema laden",        "en": "Load schema"},
    "btn_build":   {"de": "Join-Pfad bauen",     "en": "Build join path"},
    "lbl_start":   {"de": "Start",               "en": "Start"},
    "lbl_target":  {"de": "Ziel",                "en": "Target"},
    "err_no_path": {"de": "Keine Join-Verbindung gefunden",
                    "en": "No join path found"},
}
_lang = "de"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in ("de", "en") else "de"


def t(key: str) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        return f"[{key}]"
    return entry.get(_lang, entry.get("de", f"[{key}]"))
```

`core/settings.py`:
```python
"""Runtime settings persisted as JSON (singleton-style load/save)."""
import json
import os

import config

_DEFAULTS = {"language": "de", "default_connection": ""}


class Settings:
    def __init__(self, data: dict, path: str):
        self._data = data
        self._path = path

    @classmethod
    def load(cls, path: str = config.CONFIG_JSON) -> "Settings":
        data = dict(_DEFAULTS)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                data.update(json.load(fh))
        return cls(data, path)

    def get(self, key: str):
        return self._data.get(key, _DEFAULTS.get(key))

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
```

`core/log.py`:
```python
"""Unified logging to stdout + a rotating file under LOG_DIR."""
import logging
import os

import config


def init_logging(log_dir: str = config.LOG_DIR) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("luDBxP")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)
    file_handler = logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    return logger
```

- [ ] **Step 6: `run.sh` + `lucent-hub.yml` anlegen**

`run.sh` (chmod +x):
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

VENV=venv
PY=python3
STAMP=.req_stamp

pick_python() {
  for v in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$v" >/dev/null 2>&1; then PY="$v"; return; fi
  done
}

setup_venv() {
  pick_python
  [ -d "$VENV" ] || "$PY" -m venv "$VENV"
  NEW_HASH="$(md5sum requirements.txt | cut -d' ' -f1)"
  if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$NEW_HASH" ]; then
    ./"$VENV"/bin/pip install -r requirements.txt
    echo "$NEW_HASH" > "$STAMP"
  fi
}

case "${1:-}" in
  --setup-venv) setup_venv ;;
  --version)    ./"$VENV"/bin/python -c "import config; print(config.APP_VERSION)" ;;
  --clean)      rm -rf "$VENV" "$STAMP"; setup_venv ;;
  --skip-setup) ./"$VENV"/bin/python app.py ;;
  *)            setup_venv; ./"$VENV"/bin/python app.py ;;
esac
```

`lucent-hub.yml`:
```yaml
name: luDBxP
display_name: "Lucent DB Explorer"
version: "0.1.0"
description: "Visueller Join-Pfad-Builder: vom FK-Graphen zum read-only SQL."
theme_color: "#2E6FAE"
category: "Datenbank"
type: "web"
port: 5057   # vor erstem Hub-Start gegen Registry prüfen

run_command: "bash run.sh --skip-setup"

setup:
  command: "bash run.sh --setup-venv"
  check: "venv"
  label: "Python-Umgebung einrichten"
```

- [ ] **Step 7: `CHANGELOG.md`, `README.md`, `CLAUDE.md` anlegen**

`CHANGELOG.md`:
```markdown
# Changelog

## [0.1.0] — 2026-06-25
### Added
- FK-Graph aus Live-DB-Reflection (SQLAlchemy, SQLite + Postgres).
- Join-Pfad-Builder (k-kürzeste Pfade, deterministischer Tie-Break).
- Filterobjekte (WHERE über erreichbare Tabellen).
- Read-only SQL-Generierung mit parametrisierten Platzhaltern.
- Flask-Web-UI mit lokal gebundelten Assets.
```

`README.md` (Kurzfassung):
```markdown
# Lucent DB Explorer

Visueller Join-Pfad-Builder. Liest ein DB-Schema per Reflection, baut einen
FK-Graphen und generiert aus Start-/Ziel-Spalte (+ Filtern) read-only SQL.

## Start
```bash
bash run.sh            # Setup + Start (http://127.0.0.1:5057)
bash run.sh --version
```

## Tests
```bash
./venv/bin/python -m pytest
```
```

`CLAUDE.md`: nach `CLAUDE_md.pattern` anlegen — Projektname „Lucent DB Explorer", Stack Flask/SQLAlchemy/NetworkX, Schichtregel (`core/` ohne Flask), Read-only-Constraint, keine CDNs.

- [ ] **Step 8: Volle Test-Suite + Commit**

Run: `./venv/bin/python -m pytest -v`
Expected: ALLE Tests grün.

```bash
chmod +x run.sh
git add run.sh lucent-hub.yml sync_version.py strings.py core/settings.py core/log.py CHANGELOG.md README.md CLAUDE.md tests/test_sync_version.py
git commit -m "chore: Projekt-Abschluss (run.sh, hub.yml, sync_version, i18n, Doku)"
```

---

## Self-Review

**1. Spec-Coverage** (jede Spec-Sektion → Task):
- §1 Scope / read-only → Task 4–8, Global Constraints ✓
- §2 Architektur/Struktur → Task 1 (Gerüst) + jeweilige Modul-Tasks ✓
- §3 Datenfluss → Task 4 (Loader) → 5 (Graph) → 6 (Pathfinder) → 7 (SQL) → 8 (API) → 9 (UI) ✓
- §4 Mehrere Pfade / Tie-Break → Task 6 (`find_paths`, `shortest_simple_paths` + Sort) ✓
- §5 Fehler/Sicherheit → Task 4 (`ConnectionError`), 6 (`NoPathError`), 7 (Named-Placeholder), 8 (400-Handling) ✓
- §6 Testing/Fixture → Task 1 (Fixture) + Tests in jedem Task ✓
- §7 Querschnitt (Assets lokal, i18n, sync_version, run.sh) → Task 9 (lokale Assets, Test verbietet `http(s)://`) + Task 10 ✓
- §8 Offene Punkte (Port, Connection-Handling) → in config/hub als Kommentar + UI-Feld ✓

**2. Placeholder-Scan:** Keine „TBD/TODO/später ausfüllen" in Code-Steps; CLAUDE.md verweist bewusst auf vorhandenes `CLAUDE_md.pattern` (kein Code, daher Beschreibung statt Vollabdruck zulässig).

**3. Typ-Konsistenz:** `Schema/Table/Column/ForeignKey` (Task 2) konsistent in 3–5 genutzt. `JoinPath/JoinStep` (Task 6) konsistent in 7. `Selection/Filter/GeneratedSQL` (Task 7) konsistent in 8. `find_paths`/`generate_sql`/`build_graph`/`create_app`-Signaturen über Tasks identisch. `bump()` in Task 10 Test & Impl identisch.

Hinweis: Im Frontend (Task 9) sind v1 noch keine Filter-Eingabefelder verdrahtet (Buttons existieren, `filters: []`); Filter-Logik ist backend-vollständig und getestet. Das ist eine bewusste, ehrliche v1-Scheibe — Filter-UI ist der erste Folge-Task nach v1.
