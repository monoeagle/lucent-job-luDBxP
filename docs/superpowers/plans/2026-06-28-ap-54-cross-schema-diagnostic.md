# AP-54 — Cross-Schema-FK-Diagnose Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read-only sichtbar machen, ob die verbundene DB FKs über Schema-Grenzen hat — `referred_schema` ins Model tragen, daraus die Cross-Schema-Kanten ableiten und im Info/Übersicht-Panel anzeigen.

**Architecture:** `ForeignKey` bekommt ein `ref_schema`-Feld (Loader füllt es), `Schema.cross_schema_fks(current_schema)` leitet die Kantenliste ab, `/api/schema` serialisiert sie, und `openInfo()` rendert Count + Liste. `SCHEMA` im Frontend **ist** die `/api/schema`-Antwort (`app.js:1555`), daher liegt `cross_schema_fks` ohne Extra-Verdrahtung an `SCHEMA.cross_schema_fks`.

**Tech Stack:** Python 3.14 / SQLAlchemy (Model+Loader+Route), Vanilla JS (Render), pytest + Playwright-Smoke.

## Global Constraints

- **Read-only:** keine Join-/SQL-Änderung; nur Reflexion + Anzeige.
- **Layering:** `core/` importiert kein Flask.
- **NO CDN**, Texte Deutsch, Codes/Bezeichner englisch.
- **Rückwärtskompatibel:** `ref_schema` ist Default-Feld am Ende von `ForeignKey` → `ForeignKey(ref_table, pairs)` und `.single(...)` bleiben gültig.
- **`current_schema=""`** → jedes nicht-leere `ref_schema` zählt als cross-schema.
- **venv:** Python 3.14; Baseline `./venv/bin/python -m pytest -q` = **324 passed, 2 skipped**.
- **Smoke:** System-`python3` + Playwright, Server `http://127.0.0.1:5057`, Demo `sample_data/demo_cmdb.db`. JS/CSS live; **Python-Änderungen (Route) brauchen App-Neustart**, bevor der Browser-Smoke die neue Route sieht.
- **Version-Bump:** `sync_version.py --minor` (0.45.3 → 0.46.0) + icon-rail `APP_VERSION` + `TEST_COUNT`.

---

## File Structure

- `core/model.py` — `ForeignKey.ref_schema`; `Schema.cross_schema_fks()`.
- `core/loaders/sqlalchemy_loader.py:70` — `referred_schema` mitnehmen.
- `web/routes.py` — `cross_schema_fks` im `/api/schema`-JSON.
- `web/static/js/app.js` — `openInfo()` rendert Count + Kantenliste.
- `tests/test_model.py`, `tests/test_api.py` — Logik- + Route-Tests.
- `.superpowers/sdd/verify_xschema.py` — Browser-Smoke.

---

### Task 1: Core + Route — `ref_schema`, Diagnose, JSON

**Files:**
- Modify: `core/model.py` (`ForeignKey` ~Z.13-25; `Schema` ~Z.64+)
- Modify: `core/loaders/sqlalchemy_loader.py:70`
- Modify: `web/routes.py` (`api_schema` `jsonify`)
- Test: `tests/test_model.py`, `tests/test_api.py`

**Interfaces:**
- Produces: `ForeignKey(ref_table, column_pairs, ref_schema="")`; `Schema.cross_schema_fks(current_schema: str) -> tuple[dict, ...]` mit Keys `from_table, columns, to_schema, to_table, to_columns`; `/api/schema`-JSON-Feld `cross_schema_fks`.

- [ ] **Step 1: Failing Tests schreiben**

In `tests/test_model.py` anhängen:
```python
from core.model import ForeignKey, Table, Schema


def _tbl(name, fks):
    return Table(name, (), tuple(fks))


def test_foreign_key_ref_schema_defaults_empty():
    fk = ForeignKey("Product", (("ProductID", "ProductID"),))
    assert fk.ref_schema == ""


def test_cross_schema_fks_lists_foreign_schema_edge():
    fk = ForeignKey("Product", (("ProductID", "ProductID"),), "Production")
    sch = Schema((_tbl("SalesOrderDetail", [fk]),))
    edges = sch.cross_schema_fks("Sales")
    assert edges == ({
        "from_table": "SalesOrderDetail",
        "columns": ["ProductID"],
        "to_schema": "Production",
        "to_table": "Product",
        "to_columns": ["ProductID"],
    },)


def test_cross_schema_fks_excludes_same_schema():
    same = ForeignKey("Customer", (("CustomerID", "CustomerID"),), "Sales")
    none = ForeignKey("Customer", (("CustomerID", "CustomerID"),))  # ref_schema=""
    sch = Schema((_tbl("SalesOrderHeader", [same, none]),))
    assert sch.cross_schema_fks("Sales") == ()


def test_cross_schema_fks_empty_current_treats_any_ref_schema_as_cross():
    fk = ForeignKey("Product", (("ProductID", "ProductID"),), "Production")
    sch = Schema((_tbl("SalesOrderDetail", [fk]),))
    assert len(sch.cross_schema_fks("")) == 1
```

In `tests/test_api.py` anhängen (nutzt das bestehende `client`-Fixture + `inventory_url`):
```python
def test_schema_includes_cross_schema_fks_key(client, inventory_url):
    resp = client.post("/api/schema", json={"connection_url": inventory_url})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "cross_schema_fks" in data
    assert data["cross_schema_fks"] == []   # SQLite has no cross-schema FKs
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `./venv/bin/python -m pytest tests/test_model.py tests/test_api.py -q`
Expected: FAIL — `TypeError`/`AttributeError` (ForeignKey nimmt kein 3. Arg / `cross_schema_fks` fehlt) bzw. `KeyError: 'cross_schema_fks'`.

- [ ] **Step 3: `ForeignKey.ref_schema` ergänzen**

In `core/model.py`, `ForeignKey`-Dataclass, **nach** `column_pairs: tuple[tuple[str, str], ...]`:
```python
    ref_schema: str = ""   # Schema, auf das der FK zeigt, falls abweichend; "" = gleiches/unbekanntes Schema
```

- [ ] **Step 4: `Schema.cross_schema_fks()` ergänzen**

In `core/model.py`, `Schema`-Dataclass, als neue Methode:
```python
    def cross_schema_fks(self, current_schema: str) -> tuple[dict, ...]:
        """FK-Kanten, deren ref_schema gesetzt und != dem reflektierten Schema ist."""
        out = []
        for t in self.tables:
            for fk in t.foreign_keys:
                if fk.ref_schema and fk.ref_schema != current_schema:
                    out.append({
                        "from_table": t.name,
                        "columns": list(fk.columns),
                        "to_schema": fk.ref_schema,
                        "to_table": fk.ref_table,
                        "to_columns": list(fk.ref_columns),
                    })
        return tuple(out)
```

- [ ] **Step 5: Loader — `referred_schema` mitnehmen**

In `core/loaders/sqlalchemy_loader.py:70`, aus:
```python
                    fks.append(ForeignKey(fk["referred_table"], pairs))
```
wird:
```python
                    fks.append(ForeignKey(fk["referred_table"], pairs, fk.get("referred_schema") or ""))
```

- [ ] **Step 6: Route — `cross_schema_fks` serialisieren**

In `web/routes.py`, `api_schema`, im `jsonify(...)` (das `schema_name` ist dort schon vorhanden) ein Keyword ergänzen, z. B. direkt nach `views=[…]`:
```python
        cross_schema_fks=list(schema.cross_schema_fks(schema_name)),
```

- [ ] **Step 7: Tests laufen lassen, Erfolg bestätigen**

Run: `./venv/bin/python -m pytest tests/test_model.py tests/test_api.py -q`
Expected: PASS — alle neuen Tests grün.

- [ ] **Step 8: Volle Suite (Regression)**

Run: `./venv/bin/python -m pytest -q`
Expected: 324 + 5 neue = **329 passed, 2 skipped** (Zahl in Task 3 aus echter Ausgabe übernehmen).

- [ ] **Step 9: Commit**

```bash
git add core/model.py core/loaders/sqlalchemy_loader.py web/routes.py tests/test_model.py tests/test_api.py
git commit -m "feat: Cross-Schema-FK-Diagnose — ref_schema im Model + Schema.cross_schema_fks + /api/schema (AP-54 core)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: UI — Info/Übersicht-Panel zeigt Cross-Schema-FKs

**Files:**
- Modify: `web/static/js/app.js` (`openInfo`, `dbBlock` ~Z.212-220)
- Create: `.superpowers/sdd/verify_xschema.py`

**Interfaces:**
- Consumes (aus Task 1): `SCHEMA.cross_schema_fks` (Array aus `{from_table, columns, to_schema, to_table, to_columns}`; `SCHEMA` = `/api/schema`-Antwort).

- [ ] **Step 1: Failing Browser-Smoke schreiben**

Create `.superpowers/sdd/verify_xschema.py`:
```python
"""Browser smoke for AP-54: the Info/Übersicht panel shows a 'Cross-Schema-FKs'
row. SQLite has none → count 0, no edge list. A JS-injected fake edge verifies the
list-render path too."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5057/"
DB = "/home/meagle/Dokumente/_Projects/lucent-job-luDBxP/sample_data/demo_cmdb.db"
BOOT = """async (d)=>{const r=await postJSON('/api/connect',{db_type:'sqlite',filepath:d});setCurrentUrl(r.connection_url);await doConnect();return 1;}"""

results = []
def check(n, ok, d=""):
    results.append((n, ok)); print(("PASS" if ok else "FAIL"), n, ("- " + d) if d else "")

def launch(p):
    last = None
    for kw in ({"executable_path": "/usr/bin/chromium"}, {"executable_path": "/usr/bin/google-chrome"}, {}):
        try: return p.chromium.launch(headless=True, **kw)
        except Exception as e: last = e
    raise last

with sync_playwright() as p:
    b = launch(p); page = b.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(f"{m.text} [{m.location.get('url','')}]") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.evaluate(BOOT, DB)
    page.wait_for_function("SCHEMA && SCHEMA.tables && SCHEMA.tables.length > 0", timeout=8000)

    # /api/schema response carries the new key
    has_key = page.evaluate("Array.isArray(SCHEMA.cross_schema_fks)")
    check("SCHEMA.cross_schema_fks is an array", has_key)

    # empty case: Info panel shows the row with 0, no edge list
    page.evaluate("openInfo()")
    page.wait_for_selector("#tabpanels .detail", timeout=5000)
    txt = page.eval_on_selector("#tabpanels", "el => el.textContent")
    check("Info panel shows 'Cross-Schema-FKs' row", "Cross-Schema-FKs" in txt, txt[:0])

    # populated case: inject a fake edge, re-render, expect the edge string
    page.evaluate("""SCHEMA.cross_schema_fks = [{from_table:'Det', columns:['PID'], to_schema:'Prod', to_table:'Product', to_columns:['ProductID']}]; openInfo();""")
    page.wait_for_timeout(300)
    txt2 = page.eval_on_selector("#tabpanels", "el => el.textContent")
    check("edge list renders injected cross-schema edge",
          "Det.PID → Prod.Product.ProductID" in txt2, txt2[txt2.find('Cross'):][:80] if 'Cross' in txt2 else "")

    real = [e for e in errors if "favicon" not in e.lower()]
    check("no console errors (favicon ignored)", not real, "; ".join(real[:3]))
    b.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results)-len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
```

- [ ] **Step 2: Smoke laufen lassen, Fehlschlag bestätigen**

Voraussetzung: App nach Task 1 (Route-Änderung) **neu gestartet** (z. B. `LUCENT_PORT=5057 bash run.sh --skip-setup`), sonst liefert die laufende Route `cross_schema_fks` noch nicht.
Run: `python3 .superpowers/sdd/verify_xschema.py`
Expected: FAIL — „Info panel shows 'Cross-Schema-FKs' row" scheitert (Zeile fehlt noch).

- [ ] **Step 3: `openInfo` — Zeile + Kantenliste rendern**

In `web/static/js/app.js`, `openInfo`, im `dbBlock`-Aufbau nach der Zeile
```js
      `<tr><td>Deklarierte Foreign Keys</td><td>${fkCount}</td></tr>` +
```
einfügen:
```js
      `<tr><td>Cross-Schema-FKs</td><td>${(SCHEMA.cross_schema_fks || []).length}</td></tr>` +
```
Und direkt **vor** dem `panel.innerHTML = …`-Aufbau einen Kantenlisten-Block bauen:
```js
  const xfk = SCHEMA.cross_schema_fks || [];
  const xfkBlock = xfk.length
    ? `<h3>Cross-Schema-FKs</h3><ul class="objlist">` +
      xfk.map((e) =>
        `<li>${esc(e.from_table)}.${esc(e.columns.join(","))} → ` +
        `${esc(e.to_schema)}.${esc(e.to_table)}.${esc(e.to_columns.join(","))}</li>`).join("") +
      `</ul>`
    : "";
```
Diesen `xfkBlock` in den finalen `panel.innerHTML`-String nach dem `dbBlock` einfügen (vor dem schließenden `</div>`).

- [ ] **Step 4: Smoke laufen lassen, Erfolg bestätigen**

Run: `python3 .superpowers/sdd/verify_xschema.py`
Expected: `4/4 checks passed`.

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: Info-Panel zeigt Cross-Schema-FKs (Count + Kantenliste) (AP-54 ui)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Release v0.46.0 + Doku/Übersichten + Deploy

**Files:** `config.py`, `lucent-hub.yml` (sync_version); icon-rail.js (`APP_VERSION` + `TEST_COUNT`); `zensical.toml`; `CHANGELOG.md` + Mirror; `roadmap.md`/Gantt/Board; `oberflaeche.md`; Site.

- [ ] **Step 1: Version-Bump (MINOR)**

```bash
./venv/bin/python sync_version.py --minor   # 0.45.3 → 0.46.0
./venv/bin/python -m pytest -q 2>&1 | tail -1   # echte Testzahl für TEST_COUNT
```

- [ ] **Step 2: icon-rail + zensical**

`luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION` → `'0.46.0'`, `TEST_COUNT` → die neue passed-Zahl (TEST_DATE bleibt `2026-06-28`). `luDBxP-docs/zensical.toml`: `· v0.45.3` → `· v0.46.0`.

- [ ] **Step 3: Changelog (Root EN)**

In `CHANGELOG.md` oben:
```markdown
## [0.46.0] — 2026-06-28

### Added
- Cross-schema FK diagnostic (read-only): foreign keys that point to a different
  schema are now reflected (`referred_schema`) and surfaced in the Info/Übersicht
  panel as a „Cross-Schema-FKs" count plus the list of crossing edges
  (`table.col → schema.table.col`). Answers empirically whether a connected
  database uses cross-schema FKs — the decision gate for full cross-schema joins.
  No join/SQL change. (AP-54)
```

- [ ] **Step 4: Changelog-Mirror (DE)**

In `luDBxP-docs/docs/entwicklung/changelog.md` oben:
```markdown
## [0.46.0] — 2026-06-28

### Hinzugefügt
- Cross-Schema-FK-Diagnose (read-only): FKs, die auf ein anderes Schema zeigen,
  werden jetzt reflektiert (`referred_schema`) und im Info/Übersicht-Panel als
  „Cross-Schema-FKs"-Count plus Kantenliste (`Tabelle.Spalte → Schema.Tabelle.Spalte`)
  angezeigt. Beantwortet empirisch, ob eine DB Cross-Schema-FKs nutzt — das
  Entscheidungs-Gate für die volle Cross-Schema-Join-Stufe. Keine SQL-Änderung. (AP-54)
```

- [ ] **Step 5: roadmap.md — AP-54 von Offen → Erledigt**

(a) Versionslog: nach dem `**v0.45.3** … AP-60 …`-Block einfügen:
```markdown
**v0.46.0** (2026-06-28):

- **AP-54** — Cross-Schema-FK-Diagnose (read-only): `referred_schema` ins Model getragen, `Schema.cross_schema_fks()` leitet die Cross-Schema-Kanten ab, `/api/schema` liefert sie, das Info-Panel zeigt Count + Kantenliste. Entscheidungs-Gate für AP-57. **Aufwand S** — v0.46.0
```
(b) Den **AP-54-Bullet aus der „### Legacy-DB-Migration"-Offen-Liste entfernen** (er ist jetzt erledigt).

- [ ] **Step 6: Gantt + Board**

Gantt `projekt-roadmap-1.mmd`: in der erledigt-Sektion nach `AP-60 … f19 …` einfügen `AP-54 — Cross-Schema-FK-Diagnose          :done, f20, 2026-06-28, 1d` und die Sektionsüberschrift auf `v0.33.0–v0.46.0 (erledigt)` ziehen; den **AP-54-Eintrag aus der „Legacy-DB-Migration (geplant)"-Sektion entfernen**.
Board `entwicklung-arbeitspakete-1.mmd`: `M1` (AP-54) von der `class M1,M2,M3,M4 plan`-Zeile herausnehmen (→ `class M2,M3,M4 plan`) und `class M1 done` ergänzen.

- [ ] **Step 7: oberflaeche.md**

Im SQL-Analyzer-/Info-nahen Abschnitt einen Satz ergänzen: das Info/Übersicht-Panel zeigt jetzt zusätzlich „Cross-Schema-FKs" (Count + Kantenliste), read-only.

- [ ] **Step 8: Site bauen + gegenprüfen**

```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
cd luDBxP-docs/site && grep -o "v0.46.0" index.html | head -1 && grep -o "AP-54" images/mermaid/projekt-roadmap-1.svg | head -1
```

- [ ] **Step 9: SDD-Final-Review** (opus, über den Branch-Diff).

- [ ] **Step 10: Commit Doku/Version**

```bash
git add -A
git commit -m "docs: Release v0.46.0 — Cross-Schema-FK-Diagnose (AP-54)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 11: Merge + Deploy** (nach Freigabe): ff-merge → master, push, gh-pages-Worktree-Deploy (`.nojekyll` erhalten).

---

## Self-Review

**Spec coverage:** ref_schema (T1 S3) · cross_schema_fks-Methode (T1 S4) · Loader (T1 S5) · Route (T1 S6) · UI Count+Liste (T2 S3) · Tests Unit+Route (T1 S1) + Smoke (T2 S1) · Release minor + Übersichten + Deploy (T3). ✓
**Placeholder scan:** keine TBD; Code-Hunks vollständig. ✓
**Type/Name-Konsistenz:** `ref_schema`, `cross_schema_fks(current_schema)`, Keys `from_table/columns/to_schema/to_table/to_columns`, JSON-Feld `cross_schema_fks`, `SCHEMA.cross_schema_fks` — identisch in Model, Route, JS, Tests, Smoke. ✓
