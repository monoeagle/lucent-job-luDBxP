# Tier-2 — Tabellen-/Spaltenkommentare Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reflektierte Tabellen-/Spaltenkommentare aus der Ziel-DB lesen und im UI als Hover-Tooltip anzeigen.

**Architecture:** Kommentare sind reine Daten, die durch die bestehenden Schichten fließen: SQLAlchemy-Reflection liest sie → `core/model.py` trägt sie als Dataclass-Felder → `web/routes.py` serialisiert sie in `/api/schema` → `web/static/js/app.js` zeigt sie als `title`-Attribut. `core/` bleibt Flask-frei (Layering-Regel). Keine Änderung am generierten SQL.

**Tech Stack:** Python 3.14 (venv), Flask, SQLAlchemy 2.0.51, NetworkX, vanilla JS, pytest, Playwright (System-`python3`) für die JS-Sichtprüfung.

## Global Constraints

- Version-Bump **nur** via `./venv/bin/python sync_version.py --minor` (Feature → 0.39.0 → 0.40.0). `config.APP_VERSION` niemals von Hand editieren.
- `core/` darf **niemals** Flask importieren; `web/` ruft `core/`, nie umgekehrt.
- **Read-Only:** keine INSERT/UPDATE/DELETE/DDL; das generierte SQL bleibt unverändert (kein `sqlgen.py`-Touch).
- **No-CDN:** keine `<script src="https://…">` / `<link href="https://…">`. Keine neuen Frontend-Dependencies.
- Kommentar-Konvention: leerer String `""` bedeutet „kein Kommentar"; niemals `None`.
- Sprache der Doku/Commits: Deutsch.
- Tests laufen mit `./venv/bin/python -m pytest` (venv = Python 3.14).
- Verifiziertes Reflection-Verhalten (SQLAlchemy 2.0.51 / SQLite): `get_columns` enthält bei SQLite **keinen** `comment`-Key → immer `col.get("comment")`; `get_table_comment` wirft bei SQLite **`NotImplementedError`** → abfangen.

---

### Task 1: Model — `comment`-Felder

**Files:**
- Modify: `core/model.py:5-9` (`Column`), `core/model.py:45-56` (`Table`)
- Test: `tests/test_model.py`

**Interfaces:**
- Produces:
  - `Column(name: str, type: str, comment: str = "")`
  - `Table(name, columns, foreign_keys, primary_key=(), unique_constraints=(), unique_indexes=(), comment: str = "")`

- [ ] **Step 1: Write the failing test**

In `tests/test_model.py` anhängen:

```python
from core.model import Column, Table


def test_column_carries_comment_default_empty():
    assert Column("a", "INT").comment == ""
    assert Column("a", "INT", comment="fachliche Beschreibung").comment == "fachliche Beschreibung"


def test_table_carries_comment_default_empty():
    cols = (Column("a", "INT"),)
    assert Table("t", cols, ()).comment == ""
    assert Table("t", cols, (), comment="Auftragskopf").comment == "Auftragskopf"


def test_table_positional_constructor_still_works():
    # comment ist letztes Feld mit Default → bestehende positionsbasierte
    # Konstruktoren (name, cols, fks, pk, uniques, uidx) brechen nicht.
    cols = (Column("a", "INT"),)
    t = Table("t", cols, (), ("a",), (("a",),), (("a",),))
    assert t.primary_key == ("a",) and t.comment == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_model.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'comment'`

- [ ] **Step 3: Write minimal implementation**

In `core/model.py`, `Column` (Zeilen 5-9) erweitern:

```python
@dataclass(frozen=True)
class Column:
    name: str
    type: str
    comment: str = ""
```

In `core/model.py`, `Table` (Zeilen 45-56) um das letzte Feld erweitern (nach `unique_indexes`):

```python
    unique_indexes: tuple[tuple[str, ...], ...] = ()
    # Tabellenkommentar (COMMENT ON TABLE). Leerer String = kein Kommentar.
    comment: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_model.py -v`
Expected: PASS (alle, inkl. der 3 bestehenden Model-Tests)

- [ ] **Step 5: Commit**

```bash
git add core/model.py tests/test_model.py
git commit -m "feat: Tier-2 model — comment-Felder auf Column und Table"
```

---

### Task 2: Loader — Kommentare reflektieren (robust)

**Files:**
- Modify: `core/loaders/sqlalchemy_loader.py:58-92` (Spalten-Mapping + Tabellen-Append)
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Consumes: `Column(..., comment="")`, `Table(..., comment="")` aus Task 1.
- Produces: `SqlAlchemyLoader(url).load(schema=None)` füllt `Column.comment` aus `col.get("comment")` und `Table.comment` aus `get_table_comment(...)["text"]`; beide fallen robust auf `""` zurück.

- [ ] **Step 1: Write the failing tests**

In `tests/test_sqlalchemy_loader.py` anhängen:

```python
def _patch_loader(monkeypatch, fake_inspector):
    """Lässt SqlAlchemyLoader.load() gegen einen Fake-Inspector laufen."""
    import core.loaders.sqlalchemy_loader as mod

    class _DummyEngine:
        def dispose(self):
            pass

    monkeypatch.setattr(mod, "create_engine", lambda url: _DummyEngine())
    monkeypatch.setattr(mod, "inspect", lambda engine: fake_inspector)


class _FakeInspector:
    """Minimaler Inspector: eine Tabelle 't' mit kommentierter Spalte 'a'."""
    def __init__(self, table_comment):
        self._table_comment = table_comment  # dict, Exception-Klasse, oder None

    def get_table_names(self, schema=None):
        return ["t"]

    def get_columns(self, tname, schema=None):
        return [{"name": "a", "type": "INT", "comment": "Spalten-Notiz"},
                {"name": "b", "type": "TEXT", "comment": None}]

    def get_foreign_keys(self, tname, schema=None):
        return []

    def get_pk_constraint(self, tname, schema=None):
        return {"constrained_columns": []}

    def get_unique_constraints(self, tname, schema=None):
        return []

    def get_indexes(self, tname, schema=None):
        return []

    def get_table_comment(self, tname, schema=None):
        if isinstance(self._table_comment, type) and issubclass(self._table_comment, Exception):
            raise self._table_comment()
        return self._table_comment

    def get_view_names(self, schema=None):
        return []


def test_load_reflects_column_and_table_comments(monkeypatch):
    _patch_loader(monkeypatch, _FakeInspector({"text": "Tabellen-Notiz"}))
    schema = SqlAlchemyLoader("fake://").load()
    t = schema.table("t")
    assert t.comment == "Tabellen-Notiz"
    assert next(c for c in t.columns if c.name == "a").comment == "Spalten-Notiz"
    # comment None → leerer String, nie None
    assert next(c for c in t.columns if c.name == "b").comment == ""


def test_load_table_comment_not_implemented_falls_back_empty(monkeypatch):
    _patch_loader(monkeypatch, _FakeInspector(NotImplementedError))
    schema = SqlAlchemyLoader("fake://").load()
    assert schema.table("t").comment == ""


def test_load_sqlite_has_empty_comments(inventory_url):
    # SQLite kennt keine Kommentare: kein comment-Key, get_table_comment wirft
    # NotImplementedError → alles fällt sauber auf "" zurück, kein Crash.
    schema = SqlAlchemyLoader(inventory_url).load()
    for t in schema.tables:
        assert t.comment == ""
        assert all(c.comment == "" for c in t.columns)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -k "comment" -v`
Expected: FAIL — `test_load_reflects_column_and_table_comments` (Spalten-/Tabellenkommentar leer, da Loader sie noch nicht liest)

- [ ] **Step 3: Write minimal implementation**

In `core/loaders/sqlalchemy_loader.py`, das Spalten-Mapping (Zeilen 58-61) um den Kommentar erweitern:

```python
                columns = tuple(
                    Column(col["name"], str(col["type"]), col.get("comment") or "")
                    for col in insp.get_columns(tname, schema=schema)
                )
```

Direkt **vor** dem `tables.append(...)` (aktuell Zeile 92) den Tabellenkommentar robust holen:

```python
                try:
                    tcomment = (insp.get_table_comment(tname, schema=schema)
                                .get("text") or "")
                except (NotImplementedError, SQLAlchemyError):
                    tcomment = ""
                tables.append(Table(tname, columns, tuple(fks), pk, uniques, uidx, tcomment))
```

(Die bestehende `tables.append(...)`-Zeile durch die letzte Zeile oben ersetzen — `tcomment` als 7. Argument.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -v`
Expected: PASS (alle, inkl. der bestehenden Loader-Tests)

- [ ] **Step 5: Commit**

```bash
git add core/loaders/sqlalchemy_loader.py tests/test_sqlalchemy_loader.py
git commit -m "feat: Tier-2 loader — Spalten-/Tabellenkommentare reflektieren (robust ggü. SQLite)"
```

---

### Task 3: Route — Kommentare in `/api/schema` serialisieren

**Files:**
- Modify: `web/routes.py:129-148` (`api_schema`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Table.comment`, `Column.comment` aus Task 1/2.
- Produces: `/api/schema`-JSON: jedes Tabellen-Objekt hat `"comment": <str>`, jedes Spalten-Objekt hat `"comment": <str>`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_api.py` anhängen:

```python
def test_schema_endpoint_serializes_comments(client, monkeypatch):
    from core.model import Column, Table, Schema
    import web.routes as routes

    class _FakeLoader:
        def __init__(self, url):
            pass

        def load(self, schema=None):
            cols = (Column("a", "INT", comment="Spalten-Notiz"),)
            return Schema((Table("t", cols, (), comment="Tabellen-Notiz"),))

    monkeypatch.setattr(routes, "SqlAlchemyLoader", _FakeLoader)
    data = client.post("/api/schema", json={"connection_url": "fake://"}).get_json()
    table = data["tables"][0]
    assert table["comment"] == "Tabellen-Notiz"
    assert table["columns"][0]["comment"] == "Spalten-Notiz"


def test_schema_endpoint_comment_key_present_for_sqlite(client, inventory_url):
    # SQLite: keine Kommentare → Schlüssel vorhanden, Wert leer.
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    t = data["tables"][0]
    assert t["comment"] == ""
    assert all(c["comment"] == "" for c in t["columns"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "comment" -v`
Expected: FAIL — `KeyError: 'comment'` (Serialisierung kennt das Feld noch nicht)

- [ ] **Step 3: Write minimal implementation**

In `web/routes.py`, im `jsonify(...)` von `api_schema` (Zeilen 129-142) das Tabellen- und Spalten-Dict erweitern:

```python
    return jsonify(
        tables=[{
            "name": t.name,
            "comment": t.comment,
            "columns": [
                {"name": c.name, "type": c.type, "pk": c.name in t.primary_key,
                 "comment": c.comment}
                for c in t.columns
            ],
            "foreign_keys": [
                {"columns": list(fk.columns), "ref_table": fk.ref_table,
                 "ref_columns": list(fk.ref_columns)}
                for fk in t.foreign_keys
            ],
            "ddl": table_ddl(t),
        } for t in schema.tables],
```

(Views bleiben unverändert — out of scope.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS (alle)

- [ ] **Step 5: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat: Tier-2 route — Tabellen-/Spaltenkommentare in /api/schema serialisieren"
```

---

### Task 4: UI — Kommentare als Hover-Tooltip

**Files:**
- Modify: `web/static/js/app.js:206-210` (`colRows`), `:242` (Detail-Header `<h2>`), `:1073` (UML-Spalte), `:1076` (UML-Kartenkopf)
- Verify: Playwright-Snippet (System-`python3`)

**Interfaces:**
- Consumes: `c.comment` / `t.comment` aus dem `/api/schema`-JSON (Task 3). View-Spalten haben kein `comment` → `c.comment` ist `undefined` → Guard verhindert leeres `title`.

- [ ] **Step 1: `colRows` — Tooltip auf der Spaltenzeile (Detail-Tab, geteilt von Tabelle + View)**

`web/static/js/app.js:206-210` ersetzen durch:

```javascript
function colRows(columns, withPk) {
  return columns.map((c) => {
    const pk = withPk && c.pk ? ` <span class="badge">PK</span>` : "";
    const tip = c.comment ? ` title="${esc(c.comment)}"` : "";
    return `<tr${tip}><td>${esc(c.name)}${pk}</td><td>${esc(c.type)}</td></tr>`;
  }).join("");
}
```

- [ ] **Step 2: Detail-Header — Tabellenkommentar als Tooltip**

`web/static/js/app.js:242` (`defHtml = \`<h2>Tabelle: ${esc(t.name)}</h2>\` +`) ersetzen durch:

```javascript
    defHtml = `<h2${t.comment ? ` title="${esc(t.comment)}"` : ""}>Tabelle: ${esc(t.name)}</h2>` +
```

- [ ] **Step 3: UML-Spalte + Kartenkopf — Tooltips**

`web/static/js/app.js:1071-1076` ersetzen durch:

```javascript
  const colsHtml = t.columns.map((c) => {
    const pk = c.pk ? ` <span class="badge">PK</span>` : "";
    const tip = c.comment ? ` title="${esc(c.comment)}"` : "";
    return `<div class="uml-col"${tip} data-table="${esc(tableName)}" data-col="${esc(c.name)}">${esc(c.name)}${pk}<span class="uml-col-type">${esc(c.type)}</span></div>`;
  }).join("");

  const headTip = t.comment ? ` title="${esc(t.comment)}"` : "";
  card.innerHTML = `<div class="uml-card-head"${headTip}>${esc(tableName)}</div>${colsHtml}`;
```

- [ ] **Step 4: App starten und JS-Sichtprüfung mit Playwright**

App starten (Mittel der Wahl):

```bash
bash run.sh --tray
```

Playwright-Check (System-`python3`) — prüft die geteilte `colRows`-Funktion direkt im geladenen App-Kontext. Datei `scratchpad/verify_tier2.py`:

```python
import re, urllib.request
from playwright.sync_api import sync_playwright

# Port aus der Tray-/App-Ausgabe; Default 5057.
URL = "http://127.0.0.1:5057/"
urllib.request.urlopen(URL, timeout=5)  # App erreichbar?

with sync_playwright() as p:
    page = p.chromium.launch().new_page()
    page.goto(URL)
    page.wait_for_function("typeof colRows === 'function'")
    with_comment = page.evaluate(
        "colRows([{name:'a', type:'INT', pk:false, comment:'Fach-Notiz'}], true)")
    without = page.evaluate(
        "colRows([{name:'a', type:'INT', pk:false}], true)")
    assert 'title="Fach-Notiz"' in with_comment, with_comment
    assert "title=" not in without, without  # kein leeres title bei View-Spalten
    print("OK: colRows-Tooltip-Guard verifiziert")
```

Run: `python3 scratchpad/verify_tier2.py`
Expected: `OK: colRows-Tooltip-Guard verifiziert`

Zusätzlich visuell bestätigen: eine Tabelle öffnen (Detail-Tab) und in die UML ziehen — bei einer DB **mit** Kommentaren erscheint der Tooltip beim Hovern über Spalte/Kopf. Bei SQLite (keine Kommentare) erscheint korrekt **kein** Tooltip.

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: Tier-2 UI — Tabellen-/Spaltenkommentare als Hover-Tooltip (Liste + UML)"
```

---

### Task 5: Release & Doku

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`), `CHANGELOG.md`, `CLAUDE.md` (Einschränkungen-Block), Roadmap/Board/Gantt + Doc-Mirror unter `luDBxP-docs/`
- Reference: Release-/Deploy-Memory (`ludbxp-release-deploy-steps`), Handoff-Pattern

**Interfaces:**
- Consumes: fertige, getestete Tasks 1-4.

- [ ] **Step 1: Gesamte Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: alle bestehenden + neuen Tests PASS (2 skipped: MSSQL/Oracle-Live)

- [ ] **Step 2: Version bumpen (Feature → minor)**

```bash
./venv/bin/python sync_version.py --minor   # 0.39.0 → 0.40.0
```

- [ ] **Step 3: CHANGELOG-Eintrag**

In `CHANGELOG.md` oben einen `## v0.40.0`-Block ergänzen: „Tier-2: Tabellen-/Spaltenkommentare werden bei der Reflection gelesen und im UI (Detail-Liste + UML) als Hover-Tooltip angezeigt; generiertes SQL unverändert."

- [ ] **Step 4: CLAUDE.md — Einschränkungen aktualisieren**

Im „Bekannte Einschränkungen"-Block Tier-2 von „offener Kandidat" auf „erledigt" ziehen (Kommentare jetzt reflektiert; offen bleiben Tier-3 GROUP BY/Aggregate und Cross-Schema-Joins).

- [ ] **Step 5: Übersichten enumerieren + Doc-Mirror/Site**

Roadmap/Board/Gantt und Architektur-Diagramme nachziehen (Tier-2 als **eigenes**, namentliches Item — keine Sammel-Einträge), Doc-Mirror unter `luDBxP-docs/` aktualisieren, Site bauen und gerenderte Übersicht inhaltlich gegenprüfen (Render-Kodierung beachten: `&#45;` etc.). Exakte Mirror-/Build-/gh-pages-Schritte siehe Release-Memory `ludbxp-release-deploy-steps`.

- [ ] **Step 6: Final-Review + Commit + Push**

SDD-Final-Review nicht weglassen. Dann:

```bash
git add -A
git commit -m "docs: Release v0.40.0 — Tier-2 Tabellen-/Spaltenkommentare (Changelog/CLAUDE/Roadmap/Site)"
git push origin master
```

gh-pages-Deploy gemäß Release-Memory (manuelles gh-pages-Worktree-Deploy).

---

## Self-Review

**Spec-Abdeckung:**
- Model-Felder (Spec §1) → Task 1 ✓
- Loader-Reflection inkl. `col.get("comment")` + `get_table_comment().get("text")` + `try/except (NotImplementedError, SQLAlchemyError)` (Spec §2) → Task 2 ✓
- Serialisierung in `/api/schema` (Spec §3) → Task 3 ✓
- UI-Tooltips Liste + UML + Tabellen-Header (Spec §4) → Task 4 ✓
- Teststrategie: Model-Unit ✓ (T1), Fake-Inspector Positiv- + NotImplementedError-Pfad ✓ (T2), SQLite-Negativ-Pfad ✓ (T2/T3), Routes-Serialisierung gemockt ✓ (T3), JS via Playwright ✓ (T4). Live-Tests (optional/skip-guarded) bewusst weggelassen — „nice to have", nicht CI-tragend (Spec erlaubt das explizit).
- Out of Scope eingehalten: Views, SQL-Kommentare, neues CSS/Icons — keine Task berührt sie.
- Release-Konventionen (Version-Bump, Doku, Übersichten enumerieren) → Task 5 ✓

**Platzhalter-Scan:** keine TBD/TODO; jeder Code-Schritt zeigt vollständigen Code; jeder Test-Schritt zeigt Testcode + Run-Kommando + erwartetes Ergebnis.

**Typ-Konsistenz:** `comment: str = ""` durchgängig; `Column(name, type, comment="")` und `Table(..., comment="")` in T1 definiert, in T2/T3 identisch konsumiert; JSON-Key `"comment"` in T3 erzeugt und in T4 als `c.comment`/`t.comment` gelesen; `colRows` bleibt namens­gleich.
