# AP-66·Stufe 1 — Views → referenzierte Routinen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sichtbar machen, welche Views (in ihrer Definition) reflektierte Stored Procedures/Functions/Packages aufrufen — Diagnose für „nicht über reine Join/FK-Lineage migrierbare" Views.

**Architecture:** Neues pures Modul `core/viewdeps.py` extrahiert per sqlglot-AST die Funktionsaufruf-Namen aus dem View-Definitionstext und gleicht sie gegen die reflektierte `schema.routines`-Namensmenge ab. Der Loader füllt ein neues `View.routines`-Feld; Route + Frontend zeigen es (View-Detail-Abschnitt + Sidebar-Badge). Read-only, keine Routinen-Ausführung.

**Tech Stack:** Python/sqlglot (AST), pytest (volle CI-Unit-Abdeckung — kein DB nötig), Flask-Route, vanilla JS.

## Global Constraints

- **Read-only:** keine Ausführung/Auflösung von Routinen; nur Anzeige der Namen.
- **Layering:** `core/` importiert nie Flask; `core/viewdeps.py` ist pur (nur sqlglot).
- **Nur bestätigte Treffer:** ausschließlich gegen `schema.routines` gematchte Namen — keine Confidence-Stufen, keine „möglich, nicht reflektiert"-Treffer.
- **Built-ins ausgeschlossen:** SQL-Built-ins parsen als getypte sqlglot-Knoten (nicht `exp.Anonymous`) und fallen automatisch raus.
- **Model-Erweiterung = Trailing-Feld mit `()`-Default** (`View.routines`).
- **`_reflect_routines` genau einmal aufrufen** (Ergebnis im finalen `Schema(...)` wiederverwenden, nicht doppelt reflektieren).
- **Sprache:** Deutsch (Commits/Doku/UI). **No CDN.**
- **Version-Bump nur via `sync_version.py`**, Ziel **v0.57.0** (`--minor`).
- **Tests:** `./venv/bin/python -m pytest` (venv = Python 3.14).

---

### Task 1: Core-Extraktion — `core/viewdeps.py`

**Files:**
- Create: `core/viewdeps.py`
- Test: `tests/test_viewdeps.py`

**Interfaces:**
- Consumes: `sqlglot` (bereits Projekt-Dependency, s. `core/sqlanalyze.py`).
- Produces: `referenced_routines(definition: str, known_routine_names, dialect=None) -> tuple[str, ...]` —
  sortierte, deduplizierte kanonische Routinennamen (Original-Schreibweise aus `known_routine_names`),
  die in der View-Definition als Funktionsaufruf vorkommen. `()` bei Parse-Fehler/leer/kein Match.

- [ ] **Step 1: Write the failing tests** in `tests/test_viewdeps.py`:

```python
from core.viewdeps import referenced_routines


def test_plain_function_call_matched():
    out = referenced_routines("SELECT calc_total(x) FROM t", {"calc_total"})
    assert out == ("calc_total",)


def test_builtin_not_matched():
    # COUNT/UPPER parsen als getypte sqlglot-Knoten, nicht als Anonymous.
    out = referenced_routines("SELECT COUNT(x), UPPER(y) FROM t", {"count", "upper"})
    assert out == ()


def test_case_insensitive_returns_canonical():
    out = referenced_routines("SELECT myfn(x) FROM t", {"MYFN"}, dialect="oracle")
    assert out == ("MYFN",)


def test_package_qualified_call_matches_package():
    out = referenced_routines("SELECT pkg.fn(x) FROM dual", {"PKG"}, dialect="oracle")
    assert out == ("PKG",)


def test_schema_package_qualified_matches_package():
    out = referenced_routines("SELECT myschema.pkg.fn(x) FROM dual", {"PKG"}, dialect="oracle")
    assert out == ("PKG",)


def test_dedup_and_sorted():
    out = referenced_routines("SELECT b_fn(x), a_fn(y), b_fn(z) FROM t", {"a_fn", "b_fn"})
    assert out == ("a_fn", "b_fn")


def test_no_match_returns_empty():
    assert referenced_routines("SELECT a, b FROM t", {"calc_total"}) == ()


def test_empty_definition_returns_empty():
    assert referenced_routines("", {"calc_total"}) == ()
    assert referenced_routines("   ", {"calc_total"}) == ()


def test_empty_known_names_returns_empty():
    assert referenced_routines("SELECT calc_total(x) FROM t", set()) == ()


def test_parse_error_returns_empty():
    # Unparsebarer Müll → () statt Exception.
    assert referenced_routines("]]] not sql (((", {"calc_total"}) == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_viewdeps.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.viewdeps'`

- [ ] **Step 3: Implement `core/viewdeps.py`**

```python
"""Extract user-routine references from a view definition (read-only, sqlglot).

A view that calls a stored procedure/function — or an Oracle package routine —
holds part of its data logic outside plain join/FK lineage. This module finds
which *reflected* routines a view definition references: it parses the SQL and
matches function-call names (and package qualifiers) against the known routine
names. No DB access, no execution.
"""
from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

# This project's dialect names → sqlglot's (mirrors core.sqlanalyze).
_SQLGLOT_DIALECT = {
    "sqlite": "sqlite",
    "postgresql": "postgres",
    "mysql": "mysql",
    "mssql": "tsql",
    "oracle": "oracle",
}


def referenced_routines(definition, known_routine_names, dialect=None):
    """Return the reflected routine names referenced by a view definition.

    Args:
        definition: raw view definition SQL (may be empty).
        known_routine_names: iterable of reflected routine names (ground truth).
        dialect: this project's dialect name (e.g. "oracle"); mapped to sqlglot.

    Returns:
        Sorted, de-duplicated tuple of the canonical names (original casing from
        known_routine_names) referenced as function calls in the definition.
        Empty on empty definition, empty known set, parse failure, or no match.
    """
    if not definition or not definition.strip():
        return ()
    canon = {n.upper(): n for n in known_routine_names}
    if not canon:
        return ()
    try:
        tree = parse_one(definition, read=_SQLGLOT_DIALECT.get(dialect or ""))
    except SqlglotError:
        return ()
    if tree is None:
        return ()

    hits = set()
    for call in tree.find_all(exp.Anonymous):
        candidates = {call.name}
        # Package-qualified call (PKG.FN(...) / SCHEMA.PKG.FN(...)): the qualifier
        # lives on the parent Dot's left side. Collect every identifier there so
        # the package name can match a reflected package routine.
        parent = call.parent
        if isinstance(parent, exp.Dot):
            for ident in parent.left.find_all(exp.Identifier):
                candidates.add(ident.name)
        for cand in candidates:
            if cand and cand.upper() in canon:
                hits.add(canon[cand.upper()])
    return tuple(sorted(hits))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_viewdeps.py -v`
Expected: PASS (all 10).

- [ ] **Step 5: Commit**

```bash
git add core/viewdeps.py tests/test_viewdeps.py
git commit -m "feat(viewdeps): View→Routine-Extraktion via sqlglot, Abgleich gegen reflektierte Routinen (AP-66·S1)"
```

---

### Task 2: Model `View.routines` + Loader-Verdrahtung

**Files:**
- Modify: `core/model.py` (`class View`)
- Modify: `core/loaders/sqlalchemy_loader.py` (`load()` — Import, View-/Matview-Schleifen, `Schema(...)`-Return)
- Test: `tests/test_model.py`, `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Consumes: `referenced_routines(definition, known_routine_names, dialect)` (Task 1).
- Produces: `View(name, columns, definition="", routines=())` — neues Trailing-Feld
  `routines: tuple[str, ...] = ()`. Loader füllt es für Views + Matviews.

- [ ] **Step 1: Write the failing model test** in `tests/test_model.py` (ans Dateiende):

```python
def test_view_routines_default_empty_and_positional():
    from core.model import View, Column
    v = View("v", (Column("a", "INT"),), "SELECT a FROM t")
    assert v.routines == ()
    v2 = View("v2", (), "SELECT fn() FROM t", ("FN",))
    assert v2.routines == ("FN",)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_model.py::test_view_routines_default_empty_and_positional -v`
Expected: FAIL — `TypeError: __init__() takes ... positional arguments but 4 were given`

- [ ] **Step 3: Add the field** in `core/model.py` `class View`:

```python
@dataclass(frozen=True)
class View:
    name: str
    columns: tuple[Column, ...]
    definition: str = ""
    routines: tuple[str, ...] = ()   # referenzierte (reflektierte) Routinennamen
```

- [ ] **Step 4: Run model test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_model.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing loader-seam test** in `tests/test_sqlalchemy_loader.py` (ans Dateiende).
Verifiziert, dass der Loader `View.routines` befüllt, und dass SQLite (keine Routinen) leer bleibt:

```python
def test_loader_views_have_empty_routines_on_sqlite(inventory_url):
    schema = SqlAlchemyLoader(inventory_url).load()
    # SQLite hat keine Stored Routines → keine View referenziert welche.
    assert all(v.routines == () for v in schema.views)
```

(Hinweis: `inventory_url` enthält die View `VMNetworks` — dieser Test ist nach Task 3 ein
reiner Regressionsschutz für die Verdrahtung; er ist bereits grün, sobald der Default `()` greift,
und bleibt grün, wenn die Verdrahtung korrekt ist.)

- [ ] **Step 6: Wire the loader** in `core/loaders/sqlalchemy_loader.py::load()`.

(a) Import erweitern (oben):
```python
from core.viewdeps import referenced_routines
```

(b) **Vor** der View-Schleife (direkt nach dem Tabellen-Loop, vor `views = []` bei ~Z.252)
Routinen einmal reflektieren + Namensmenge + Dialektname bilden:
```python
            routines = _reflect_routines(engine, schema)
            routine_names = frozenset(r.name for r in routines)
            dname = getattr(getattr(engine, "dialect", None), "name", "")
            views = []
```

(c) View-Schleife: `View(...)` um das Routinen-Arg erweitern (Z.262):
```python
                views.append(View(vname, vcols, definition,
                                  referenced_routines(definition, routine_names, dname)))
```

(d) Matview-Schleife: ebenso (Z.286):
```python
                matviews.append(View(mvname, mvcols, mvdef,
                                     referenced_routines(mvdef, routine_names, dname)))
```

(e) `Schema(...)`-Return (Z.287–290): die schon reflektierten `routines` **wiederverwenden**
statt `_reflect_routines` erneut aufzurufen:
```python
            return Schema(tuple(tables), tuple(views), _reflect_triggers(engine, schema),
                          sequences, tuple(matviews),
                          routines,
                          _reflect_synonyms(engine, schema))
```

- [ ] **Step 7: Run loader + model + viewdeps tests**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py tests/test_model.py tests/test_viewdeps.py -q`
Expected: PASS (inkl. `test_loader_views_have_empty_routines_on_sqlite`).

- [ ] **Step 8: Commit**

```bash
git add core/model.py core/loaders/sqlalchemy_loader.py tests/test_model.py tests/test_sqlalchemy_loader.py
git commit -m "feat(loader): View.routines via referenced_routines befüllen (AP-66·S1)"
```

---

### Task 3: Route — `routines` in `/api/schema`

**Files:**
- Modify: `web/routes.py` (`api_schema` — `views`- und `materialized_views`-Arrays)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `schema.views[..].routines` / `schema.materialized_views[..].routines` (Task 2).
- Produces: `/api/schema`-JSON: jedes View- und Matview-Objekt trägt `"routines": [...]`.

- [ ] **Step 1: Write the failing test** in `tests/test_api.py` (ans Dateiende):

```python
def test_schema_view_exposes_referenced_routines(client, inventory_url, monkeypatch):
    import web.routes as routes_mod
    from core.model import Schema, View, Column

    fake = Schema(
        tables=(),
        views=(View("v_uses_fn", (Column("a", "INT"),), "SELECT fn(a) FROM t", ("FN",)),),
    )
    monkeypatch.setattr(routes_mod.SqlAlchemyLoader, "load", lambda self, schema=None: fake)
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    v = next(x for x in data["views"] if x["name"] == "v_uses_fn")
    assert v["routines"] == ["FN"]


def test_schema_view_routines_empty_on_sqlite(client, inventory_url):
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    assert all(v["routines"] == [] for v in data["views"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "referenced_routines or view_routines_empty" -v`
Expected: FAIL — `KeyError: 'routines'`.

- [ ] **Step 3: Add serialization** in `web/routes.py` `api_schema`.

`views`-Array (nach `"definition": v.definition,`):
```python
        views=[{
            "name": v.name,
            "columns": [{"name": c.name, "type": c.type} for c in v.columns],
            "definition": v.definition,
            "routines": list(v.routines),
        } for v in schema.views],
```

`materialized_views`-Array (nach `"definition": mv.definition`):
```python
        materialized_views=[
            {"name": mv.name,
             "columns": [{"name": c.name, "type": c.type} for c in mv.columns],
             "definition": mv.definition,
             "routines": list(mv.routines)}
            for mv in schema.materialized_views
        ],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "routines" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(api): View.routines in /api/schema serialisieren (AP-66·S1)"
```

---

### Task 4: Frontend — View-Detail-Abschnitt + Sidebar-Badge

**Files:**
- Modify: `web/static/js/app.js` (`objList` ~Z.160; `openDetail` View-Zweig ~Z.348 + Matview-Zweig ~Z.341)
- Test: Manueller Playwright-Smoke (System-`python3`, `page.route`-Injektion).

**Interfaces:**
- Consumes: `SCHEMA.views[..].routines`, `SCHEMA.materialized_views[..].routines` (Task 3).

- [ ] **Step 1: Sidebar-Badge in `objList`.** Aktuell:
```javascript
  const objList = (items, kind) => items.map((o) =>
    `<li data-kind="${kind}" data-name="${escAttr(o.name)}">${esc(o.name)}</li>`).join("");
```
Ersetzen durch (Badge „ƒ" nur wenn `o.routines` nicht leer; generisch, andere Kinds tragen kein `routines`):
```javascript
  const objList = (items, kind) => items.map((o) => {
    const usesRtn = o.routines && o.routines.length;
    const badge = usesRtn
      ? ` <span class="rtn-badge" title="${escAttr("nutzt Routinen: " + o.routines.join(", "))}">ƒ</span>`
      : "";
    return `<li data-kind="${kind}" data-name="${escAttr(o.name)}">${esc(o.name)}${badge}</li>`;
  }).join("");
```

- [ ] **Step 2: View-Detail-Abschnitt.** Im View-Zweig von `openDetail` (der finale `else`-Zweig,
der `SCHEMA.views.find(...)` nutzt) den Routinen-Abschnitt ergänzen. Aktuell etwa:
```javascript
  } else {
    const v = SCHEMA.views.find((x) => x.name === name);
    defHtml = `<h2>View: ${esc(v.name)}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(v.columns, false)}</tbody></table>`;
    sqlText = v.definition;
  }
```
Erweitern um den Abschnitt (nur bei vorhandenen Routinen):
```javascript
  } else {
    const v = SCHEMA.views.find((x) => x.name === name);
    const rtnHtml = (v.routines && v.routines.length)
      ? `<h3>Verwendet Routinen</h3><ul>` +
        v.routines.map((r) => `<li>${esc(r)}</li>`).join("") + `</ul>`
      : "";
    defHtml = `<h2>View: ${esc(v.name)}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(v.columns, false)}</tbody></table>` + rtnHtml;
    sqlText = v.definition;
  }
```

- [ ] **Step 3: Matview-Detail-Abschnitt.** Im Matview-Zweig (`kind === "matview"`) analog `rtnHtml`
aus `mv.routines` bilden und an `defHtml` anhängen:
```javascript
  } else if (kind === "matview") {
    const mv = (SCHEMA.materialized_views || []).find((x) => x.name === name);
    const rtnHtml = (mv.routines && mv.routines.length)
      ? `<h3>Verwendet Routinen</h3><ul>` +
        mv.routines.map((r) => `<li>${esc(r)}</li>`).join("") + `</ul>`
      : "";
    defHtml = `<h2>Materialized View: ${esc(mv.name)}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(mv.columns, false)}</tbody></table>` + rtnHtml;
    sqlText = mv.definition;
  }
```

- [ ] **Step 4: App neu starten + Browser-Smoke.** App-Neustart nötig (JS ist live, aber sicher neu laden);
die App läuft ggf. schon auf 5057, sonst `bash run.sh --skip-setup`.
Neues `scratchpad/smoke_view_routines.py` (modelliert nach `scratchpad/smoke_seq_matview.py`):
`page.route`-Injektion einer `/api/schema`-Antwort mit einer View `{name, columns, definition, routines:["FN"]}`
und einer View ohne Routinen. Prüfen:
- Sidebar: das View-Item mit Routinen trägt das „ƒ"-Badge (`.rtn-badge`), das andere nicht.
- View-Detail (Klick): Abschnitt „Verwendet Routinen" mit „FN" sichtbar; bei der View ohne Routinen kein Abschnitt.
Run: `python3 scratchpad/smoke_view_routines.py` → Erwartet `PASS`.

- [ ] **Step 5: Commit** (nur `app.js`; Smoke bleibt untracked in scratchpad):

```bash
git add web/static/js/app.js
git commit -m "feat(ui): View-Detail 'Verwendet Routinen' + Sidebar-ƒ-Badge (AP-66·S1)"
```

(Optionales CSS für `.rtn-badge` — ein dezentes Inline-Styling reicht; falls ein `web/assets`/`static`-CSS
existiert, eine kleine Regel ergänzen. Am echten Code prüfen, wo Badges wie `.badge` definiert sind, und
konsistent stylen.)

---

### Task 5: Release v0.57.0 + Doku (am Code geprüft)

**Files:**
- Modify: via `sync_version.py`; Changelog (EN + DE-Mirror), Roadmap-Prosa + `.mmd`, `architektur.md` (+ `referenz-architektur-1.mmd`), `datenmodell.md`, `oberflaeche.md`, Kennzahlen, `zensical.toml`, Site, gh-pages.

**Interfaces:** keine (Release/Doku).

- [ ] **Step 1: Version-Bump**

```bash
./venv/bin/python sync_version.py --minor   # → v0.57.0
```

- [ ] **Step 2: Doku am echten Code geprüft nachziehen** (grep-belegt):
  - **Changelog EN + DE-Mirror:** v0.57.0 — Views zeigen referenzierte (reflektierte) Routinen; Diagnose für Migration.
  - **Roadmap-Prosa + Diagramme** (`roadmap.md`, `projekt-roadmap-1.mmd` Gantt, `entwicklung-arbeitspakete-1.mmd` Board): AP-66·S1 als erledigt, **einzeln enumeriert** (kein Sammeleintrag).
  - **`architektur.md`-Prosa + `referenz-architektur-1.mmd`** (core-Modulkarte): neues Modul **`core/viewdeps.py`** aufnehmen.
  - **`datenmodell.md`:** `View.routines`-Feld.
  - **`oberflaeche.md`:** View-Detail-Abschnitt „Verwendet Routinen" + Sidebar-ƒ-Badge.
  - **Kennzahlen** (`kennzahlen.md`): Version v0.57.0, Commits/Tests/Coverage **frisch erheben**
    (`git rev-list --count HEAD`, `pytest`, `pytest --cov=core --cov=web --cov=launcher --cov=config --cov=app`),
    Karten + Tabelle + **Per-Modul-Balken** (core/web/launcher/GUI — die sind hartkodiert, je Release prüfen).
  - **`zensical.toml`** Versionsstring.
  - Mit `grep` gegenprüfen, dass `architektur.md`/`datenmodell.md` `core/viewdeps.py` bzw. `View.routines` nennen.

- [ ] **Step 3: Site bauen + verifizieren**

```bash
bash luDBxP-docs/run_luDBxP_docs.sh --build
```
grep: `v0.57.0` in gebauter Site; `viewdeps`/`View.routines` in Referenz; Gantt-SVG zeigt AP-66·S1.

- [ ] **Step 4: Voll-Suite + Commit + Deploy**

```bash
./venv/bin/python -m pytest -q   # grün
git add -A
git commit -m "release: v0.57.0 — AP-66·S1 (Views→referenzierte Routinen)"
# FF-Merge nach master + Push + gh-pages-Worktree-Deploy (etabliertes Muster)
```

---

## Self-Review

**1. Spec coverage:**
- `core/viewdeps.py::referenced_routines` (sqlglot, Anonymous + Package-Qualifier, Built-ins raus, case-insensitiv, kanonisch, dedup/sort, ()-Fallbacks) → Task 1 ✓
- `View.routines` Trailing-Feld → Task 2 ✓
- Loader: Routinen vor View-Schleife einmal reflektieren, Views+Matviews füllen, `routines` im Schema-Return wiederverwenden → Task 2 ✓
- Route `routines` in views + materialized_views → Task 3 ✓
- Frontend View-/Matview-Detail-Abschnitt + Sidebar-Badge → Task 4 ✓
- Tests: viewdeps-Unit (CI) + Loader-Naht + Route-Naht + JS-Smoke → Task 1/2/3/4 ✓
- Release/Doku inkl. neues core-Modul in Architektur + Per-Modul-Balken → Task 5 ✓
- Read-only / nur bestätigte Treffer / Built-ins raus → Task 1 (Design der Extraktion) ✓

**2. Placeholder scan:** Extraktionscode, Tests, JS konkret. Der „am echten Code prüfen"-Hinweis (Task 4 CSS `.rtn-badge`) betrifft bestehendes Styling, keine zu erfindende Logik.

**3. Type consistency:** `referenced_routines(definition, known_routine_names, dialect=None) -> tuple[str,...]` identisch in Task 1 (def) und Task 2 (Aufruf); `View(name, columns, definition="", routines=())` konsistent in Task 2/3; JS liest `o.routines`/`v.routines`/`mv.routines` einheitlich, passend zur Route-Serialisierung `"routines": list(...)`.
