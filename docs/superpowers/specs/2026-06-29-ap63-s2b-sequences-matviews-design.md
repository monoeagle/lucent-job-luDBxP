# AP-63·Stufe 2b — Sequences + Materialized Views als Sidebar-Kategorien — Design

**Datum:** 2026-06-29
**Status:** Spec (genehmigt im Brainstorming)
**Aufwand:** S–M (zwei weitere read-only Objekt-Kategorien auf dem in AP-63·S2 etablierten Muster; SQLAlchemy-nativ, echte Reflektion nur PG/Oracle → skip-guarded)
**Vorgänger:** AP-63·S2 (Trigger-Kategorie, v0.53.0) etablierte das neue-Objekt-Kategorie-Muster. Konzept: `docs/concepts/2026-06-28-sidebar-object-categories.md` (Stufe 2).

## Ziel

**Sequences** und **Materialized Views** als je eigene read-only Sidebar-Kategorie reflektieren + anzeigen, auf dem Muster von AP-63·S2 (Model → Loader → Endpoint → Sidebar-Kategorie → Detail). Display-only; nimmt nicht an Join-Pfaden teil.

**Gestaffelt (bewusst):**
- **Diese Scheibe:** Sequences (nur Name) + Materialized Views (Spalten + Definition, **kein** Daten-Tab). SQLAlchemy-nativ; echte Werte nur gegen PG/Oracle (skip-guarded), andere Engines → `()`.
- **Folge:** Matview-Daten-Vorschau (Daten-Tab, braucht Allowlist-Anpassung); Sequenz-Details (start/increment via Katalog-SQL).

## Code-Befunde (Ist-Stand verifiziert)

- **SQLAlchemy-Inspector** hat nativ `get_sequence_names(schema=None)`, `get_materialized_view_names(schema=None)`, `get_view_definition(name, schema=None)`, `get_columns(name, schema=None)`. Auf SQLite liefern Sequence-/Matview-Listen `[]`.
- **`core/model.py`**: `View(name, columns, definition)` passt strukturell exakt für Matviews; `Schema(tables, views=(), triggers=())` — neue Felder am Ende anfügen (Default `()`), wie bei AP-63·S1/S2.
- **Loader (`core/loaders/sqlalchemy_loader.py`)**: baut `views` via `get_view_names` + `get_columns` + `get_view_definition`; `_reflect_triggers(engine)` (AP-63·S2) ist das Muster für eine separate Reflektion. Importe: `View`, `Schema` vorhanden; `Sequence` ergänzen.
- **`/api/schema` (`web/routes.py`)**: serialisiert `views=[{name,columns,definition}]` + `triggers=[…]`. Ergänzungspunkt.
- **Sidebar (`renderSidebar`)**: Kategorien als `<h3>Name (N)</h3>` + `objList(items, kind)`; AP-63·S2 fügte die conditional „Trigger"-Kategorie (nur N>0) ein. `openDetail(kind, name)` hat einen `hasData`-Flag (table/view → Daten-Tab; trigger → keiner).
- **Skip-Guard-Muster:** `tests/test_mssql_integration.py` nutzt `os.environ.get("LUCENT_MSSQL_TEST_URL")` + `pytest.mark.skipif`. Für PG analog `LUCENT_PG_TEST_URL`.

## 1. Reflection (Loader)

Nach dem Views-Block in `load()`, vor dem `Schema(...)`-Return:
```python
try:
    sequences = tuple(Sequence(n) for n in insp.get_sequence_names(schema=schema))
except (SQLAlchemyError, NotImplementedError):
    sequences = ()
matviews = []
try:
    mv_names = insp.get_materialized_view_names(schema=schema)
except (SQLAlchemyError, NotImplementedError):
    mv_names = []
for mvname in mv_names:
    try:
        mvcols = tuple(Column(c["name"], str(c["type"])) for c in insp.get_columns(mvname, schema=schema))
    except SQLAlchemyError:
        mvcols = ()
    try:
        mvdef = insp.get_view_definition(mvname, schema=schema) or ""
    except (SQLAlchemyError, NotImplementedError):
        mvdef = ""
    matviews.append(View(mvname, mvcols, mvdef))
```
- `Schema(...)`-Return um `sequences` + `tuple(matviews)` erweitern (Reihenfolge = Model-Feldreihenfolge).
- `Sequence` aus `core.model` importieren.
- **Read-only**, rein Inspector-Reflektion. SQLite → leer.

## 2. Model (`core/model.py`, pur)

```python
@dataclass(frozen=True)
class Sequence:
    name: str
```
`Schema` um zwei Felder erweitern (am Ende, Default `()`):
```python
sequences: tuple[Sequence, ...] = ()
materialized_views: tuple[View, ...] = ()   # Matviews reusen das View-Shape
```

## 3. Endpoint (`/api/schema`, `web/routes.py`)

Ergänzen:
```python
sequences=[{"name": s.name} for s in schema.sequences],
materialized_views=[
    {"name": mv.name,
     "columns": [{"name": c.name, "type": c.type} for c in mv.columns],
     "definition": mv.definition}
    for mv in schema.materialized_views
],
```

## 4. Sidebar (`web/static/js/app.js::renderSidebar`)

Nach der Trigger-Kategorie, vor `<div class="sidebar-bottom">`, zwei conditional Kategorien (nur N>0):
```javascript
((SCHEMA.sequences && SCHEMA.sequences.length)
  ? `<h3>Sequences (${SCHEMA.sequences.length})</h3>` +
    `<ul class="objlist">${objList(SCHEMA.sequences, "sequence")}</ul>` : "") +
((SCHEMA.materialized_views && SCHEMA.materialized_views.length)
  ? `<h3>Materialized Views (${SCHEMA.materialized_views.length})</h3>` +
    `<ul class="objlist">${objList(SCHEMA.materialized_views, "matview")}</ul>` : "") +
```
Klick-Handler ist generisch (`openDetail(li.dataset.kind, li.dataset.name)`).

## 5. Detail (`openDetail`, neue Zweige)

- **`kind==="sequence"`**: `defHtml = `<h2>Sequenz: ${esc(s.name)}</h2><p class="hint">nur Name reflektiert</p>``; `sqlText = ""`. Lookup `(SCHEMA.sequences||[]).find(x => x.name === name)`.
- **`kind==="matview"`**: wie der View-Zweig — Spalten-Tabelle (`colRows(mv.columns, false)`) + `sqlText = mv.definition`. Lookup `(SCHEMA.materialized_views||[]).find(x => x.name === name)`. Überschrift „Materialized View: <name>".
- **`hasData`** bleibt `kind === "table" || kind === "view"` → für `sequence`/`matview` **kein** Daten-Subtab (display-only).
- Alle dynamischen Werte via `esc`. Read-only; keine Join-Teilnahme.

## 6. Tests

**CI — Endpoint-Serialisierung (monkeypatch, ohne PG):** in `tests/test_api.py` `SqlAlchemyLoader.load` so monkeypatchen, dass es ein konstruiertes `Schema` mit einer `Sequence("seq_orders")` und einer matview-`View("mv_sales", (Column("total","INTEGER"),), "SELECT …")` liefert; `POST /api/schema` → `sequences`/`materialized_views` korrekt serialisiert (Namen/Spalten/Definition).

**CI — Leer-Pfad:** Loader gegen `inventory_url` (SQLite) → `schema.sequences == ()` **und** `schema.materialized_views == ()`; `/api/schema` liefert `sequences == []` und `materialized_views == []`.

**Live PG — skip-guarded:** neue `tests/test_pg_integration.py` (`_PG_URL = os.environ.get("LUCENT_PG_TEST_URL")`, `pytestmark = pytest.mark.skipif(not _PG_URL, …)`): legt eine Sequenz + eine Materialized View an, reflektiert via `SqlAlchemyLoader`, findet beide in `schema.sequences`/`materialized_views` (Matview mit Spalten), räumt auf. Dokumentiert in der `CLAUDE.md`-„How to Test"-Sektion (wie MSSQL/Oracle).

**Browser-Smoke (ohne PG, via `page.route`):** Playwright fängt die `/api/schema`-Antwort ab und injiziert `sequences:[{name:"seq_demo"}]` + `materialized_views:[{name:"mv_demo",columns:[{name:"x",type:"INTEGER"}],definition:"SELECT 1 AS x"}]` in die JSON-Antwort → Sidebar zeigt „Sequences"- und „Materialized Views"-Kategorien; `mv_demo` öffnen → Spalte `x` im Detail; `seq_demo` öffnen → „Sequenz: seq_demo". App-Neustart vor Smoke.

## 7. Scope-Cuts (bewusst)

- **Display-only** — kein Daten-Tab/Daten-Vorschau (auch Matviews; Daten-Preview = Folge-AP, bräuchte `fetch_rows`-Allowlist-Anpassung).
- **Sequenzen nur Name** (kein start/increment/min/max via Katalog-SQL).
- Echte Reflektion nur PG/Oracle; SQLite/MSSQL → `()`. Keine Join-Pfad-Teilnahme.
- PG/Oracle-Trigger-Reflektion (Fast-Follow aus S2) bleibt separat.

## 8. Release / Doku (nach Implementierung)

- `sync_version.py --minor` (Feature) + icon-rail `APP_VERSION`/`TEST_COUNT`.
- Roadmap: AP-63·S2b → erledigt (Sequences/Matviews); AP-63·S3 (Procedures/Functions) bleibt offen; PG/Oracle-Trigger als Rest-Fast-Follow.
- CLAUDE.md „Bekannte Einschränkungen": Sequences/Matview-Kategorien (read-only, PG/Oracle) als Tier notieren; „How to Test" um `LUCENT_PG_TEST_URL` ergänzen; Kennzahlen-Seite mitziehen.
- Changelog EN + DE-Mirror, zensical, Site-Build, gh-pages.
- Deutsch / NO-CDN / SDD-Final-Review nicht weglassen.
