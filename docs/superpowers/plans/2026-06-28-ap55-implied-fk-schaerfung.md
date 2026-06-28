# AP-55 — Implied-FK-Schärfung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Logische Links zwischen Tabellen (gemeinsame IDs ohne FK-Constraint) per Namensmuster-Heuristik mit Confidence-Score auffindbar machen und im Info-Panel anzeigen.

**Architecture:** `core/implied.py` bekommt neben dem heutigen Exakt-PK-Namen-Match eine Suffix→Tabellenname-Heuristik mit Normalisierung; jeder Treffer trägt eine diskrete Confidence-Stufe (hoch/mittel/niedrig) + DE-Begründung. `/api/schema` shippt die Treffer als JSON-Feld (analog AP-54 `cross_schema_fks`); das Info-Panel rendert Count + Liste mit Badge. Der Graph-Pfad bleibt unverändert.

**Tech Stack:** Python 3.10+ / SQLAlchemy-Reflection (nur Model-Konsum, kein neuer DB-Code), Vanilla JS (Render), pytest (Unit + Route) + Playwright-Smoke (System-python3).

**Spec:** `docs/superpowers/specs/2026-06-28-ap55-implied-fk-schaerfung-design.md`

## Global Constraints

- **Layering:** `core/` importiert **nie** Flask. `web/` ruft `core/` — nie umgekehrt.
- **Read-only:** Nur Schema-Metadaten lesen + Vorschläge erzeugen; nie FKs „anlegen", nie INSERT/UPDATE/DDL.
- **NO CDN:** Keine `<script src="https://…">`/`<link href="https://…">`. Badge nutzt die **bestehende** `.badge`-CSS-Klasse — kein neues CSS.
- **UI-Texte Deutsch.**
- **Version:** `config.APP_VERSION` **nie** von Hand editieren — nur via `./venv/bin/python sync_version.py --minor`.
- **Tests:** `./venv/bin/python -m pytest` (venv = Python 3.14). Baseline vor Start: 329 passed, 2 skipped.
- **Rückwärtskompatibilität:** `ImpliedFK` muss von `core/graph.py::build_graph` weiter über `.table/.column/.ref_table/.ref_column` nutzbar bleiben (neue Felder nur mit Defaults).
- **Branch:** `ap-55-implied-fk` (bereits angelegt, Spec committet).

---

### Task 1: Core — Suffix→Tabelle-Heuristik + Confidence in `core/implied.py`

**Files:**
- Modify: `core/implied.py` (komplett ersetzen, siehe Step 5)
- Test: `tests/test_implied.py` (neue In-Memory-Tests anhängen; bestehende Fixture-Tests **unverändert** lassen)

**Interfaces:**
- Consumes: `core.model.Schema/Table/Column/ForeignKey`.
- Produces:
  - `ImpliedFK(table, column, ref_table, ref_column, confidence="hoch", reason="exakter PK-Name")` — frozen dataclass, zwei neue defaultete Felder.
  - `find_implied_fks(schema: Schema) -> tuple[ImpliedFK, ...]` — deterministisch sortiert nach `(table, column, ref_table)`.

- [ ] **Step 1: Failing-Tests schreiben**

Am Ende von `tests/test_implied.py` anhängen:
```python
from core.model import Schema, Table, Column, ForeignKey


def _c(name, type_="INTEGER"):
    return Column(name, type_)


def test_exact_pk_name_is_high_confidence():
    schema = Schema((
        Table("Kunde", (_c("KundeID"), _c("Name", "TEXT")), (), primary_key=("KundeID",)),
        Table("Bestellung", (_c("BestellungID"), _c("KundeID")), (), primary_key=("BestellungID",)),
    ))
    hit = {(i.table, i.column, i.ref_table): i for i in find_implied_fks(schema)}[
        ("Bestellung", "KundeID", "Kunde")]
    assert hit.confidence == "hoch"
    assert hit.ref_column == "KundeID"
    assert hit.reason == "exakter PK-Name"


def test_suffix_to_table_generic_pk_is_medium():
    schema = Schema((
        Table("Kunde", (_c("id"), _c("name", "TEXT")), (), primary_key=("id",)),
        Table("Bestellung", (_c("nr"), _c("kunde_id")), (), primary_key=("nr",)),
    ))
    hit = {(i.column, i.ref_table): i for i in find_implied_fks(schema)}[("kunde_id", "Kunde")]
    assert hit.confidence == "mittel"
    assert hit.ref_column == "id"
    assert "Suffix" in hit.reason


def test_plural_table_is_low_confidence():
    schema = Schema((
        Table("Customers", (_c("id"), _c("name", "TEXT")), (), primary_key=("id",)),
        Table("Order", (_c("nr"), _c("customer_id")), (), primary_key=("nr",)),
    ))
    hit = {(i.column, i.ref_table): i for i in find_implied_fks(schema)}[("customer_id", "Customers")]
    assert hit.confidence == "niedrig"
    assert hit.ref_column == "id"


def test_no_hit_when_target_pk_is_not_a_generic_id():
    # Stem 'kunde' names table Kunde, but Kunde's PK is 'name' -> not a generic id form.
    schema = Schema((
        Table("Kunde", (_c("name", "TEXT"), _c("ort", "TEXT")), (), primary_key=("name",)),
        Table("Bestellung", (_c("nr"), _c("kunde_id")), (), primary_key=("nr",)),
    ))
    assert all(i.ref_table != "Kunde" for i in find_implied_fks(schema))


def test_no_hit_when_base_type_incompatible():
    schema = Schema((
        Table("Kunde", (_c("id"), _c("x", "TEXT")), (), primary_key=("id",)),
        Table("Bestellung", (_c("nr"), _c("kunde_id", "TEXT")), (), primary_key=("nr",)),
    ))
    assert find_implied_fks(schema) == ()


def test_short_stem_yields_no_suffix_match():
    # column 'id' -> stem '' (< 2 chars) -> no suffix match; the exact-name path
    # (Other.id == It.id) still fires as 'hoch'.
    schema = Schema((
        Table("It", (_c("id"),), (), primary_key=("id",)),
        Table("Other", (_c("nr"), _c("id")), (), primary_key=("nr",)),
    ))
    assert all(i.confidence == "hoch" for i in find_implied_fks(schema))


def test_declared_fk_is_excluded():
    schema = Schema((
        Table("Kunde", (_c("id"),), (), primary_key=("id",)),
        Table("Bestellung", (_c("nr"), _c("kunde_id")),
              (ForeignKey.single("kunde_id", "Kunde", "id"),), primary_key=("nr",)),
    ))
    assert all(i.ref_table != "Kunde" for i in find_implied_fks(schema))


def test_results_are_sorted_deterministically():
    schema = Schema((
        Table("A", (_c("id"),), (), primary_key=("id",)),
        Table("B", (_c("id"),), (), primary_key=("id",)),
        Table("C", (_c("nr"), _c("a_id"), _c("b_id")), (), primary_key=("nr",)),
    ))
    keys = [(i.table, i.column, i.ref_table) for i in find_implied_fks(schema)]
    assert keys == sorted(keys)
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `./venv/bin/python -m pytest tests/test_implied.py -q`
Expected: FAIL — die neuen `confidence`/`reason`-Asserts und die Suffix-Treffer scheitern (Felder/Strategie existieren noch nicht). Die bestehenden Fixture-Tests bleiben grün.

- [ ] **Step 3: `core/implied.py` ersetzen**

Gesamten Inhalt von `core/implied.py` ersetzen durch:
```python
"""Heuristic detection of implied (undeclared) foreign keys.

A column ``c`` in table A implies a relationship to table B when either
  * **exact:** ``c`` equals B's single-column primary-key name, or
  * **suffix:** ``c`` ends in an id-suffix and its stem names table B, whose
    single-column primary key is a conventional id form (``id``/``uuid``/``guid``
    or ``<stem>id``).
In all cases A != B, base types are compatible, and no declared FK ``A.c -> B``
already exists. Each hit carries a discrete confidence ("hoch"/"mittel"/"niedrig")
and a short German reason. Conservative variant of SchemaSpy's name heuristic.
"""
import re
from dataclasses import dataclass

from core.model import Schema

_ID_SUFFIXES = ("id", "uuid", "guid")       # recognised id endings (normalised)
_GENERIC_PK = {"id", "uuid", "guid"}        # conventional generic primary keys
_RANK = {"hoch": 3, "mittel": 2, "niedrig": 1}


@dataclass(frozen=True)
class ImpliedFK:
    table: str        # owning table (where the column lives)
    column: str
    ref_table: str
    ref_column: str   # the referenced (PK) column name in ref_table
    confidence: str = "hoch"          # "hoch" | "mittel" | "niedrig"
    reason: str = "exakter PK-Name"   # short German match reason


def _base_type(type_str: str) -> str:
    """Return the comparable base of a column type ('VARCHAR(50)' -> 'VARCHAR')."""
    return type_str.split("(")[0].strip().upper()


def _normalize(name: str) -> str:
    """Lowercase, strip non-alphanumerics ('Customer_ID' -> 'customerid')."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _strip_id_suffix(norm_col: str) -> str | None:
    """Entity stem of a normalised column ending in an id-suffix, else None.

    'customerid' -> 'customer', 'orderuuid' -> 'order'. Returns None when no
    known suffix is present or the remaining stem is shorter than 2 chars.
    """
    for suf in _ID_SUFFIXES:
        if norm_col.endswith(suf) and len(norm_col) - len(suf) >= 2:
            return norm_col[: -len(suf)]
    return None


def _singularize(norm_name: str) -> str:
    """Drop a trailing plural 'es'/'s' ('customers' -> 'customer')."""
    if norm_name.endswith("es") and len(norm_name) > 3:
        return norm_name[:-2]
    if norm_name.endswith("s") and len(norm_name) > 2:
        return norm_name[:-1]
    return norm_name


def find_implied_fks(schema: Schema) -> tuple[ImpliedFK, ...]:
    """Detect implied foreign keys via name heuristics with a confidence score.

    Args:
        schema: The reflected schema.

    Returns:
        One ImpliedFK per detected relationship, sorted by
        (table, column, ref_table). Each carries a confidence and reason.
    """
    col_type: dict[tuple[str, str], str] = {}
    pk_targets: dict[str, list[str]] = {}                 # exact pk-name -> tables
    # normalized / singularized table name -> [(table, pk_name, normalized_pk)]
    by_norm: dict[str, list[tuple[str, str, str]]] = {}
    by_singular: dict[str, list[tuple[str, str, str]]] = {}

    for t in schema.tables:
        for c in t.columns:
            col_type[(t.name, c.name)] = _base_type(c.type)
        if len(t.primary_key) == 1:
            pk = t.primary_key[0]
            pk_targets.setdefault(pk, []).append(t.name)
            norm = _normalize(t.name)
            entry = (t.name, pk, _normalize(pk))
            by_norm.setdefault(norm, []).append(entry)
            by_singular.setdefault(_singularize(norm), []).append(entry)

    # (table, column, ref_table) -> (rank, ImpliedFK); keep the highest rank.
    best: dict[tuple[str, str, str], tuple[int, ImpliedFK]] = {}

    def consider(a, col, b_name, ref_col, confidence, reason, declared):
        if b_name == a:
            return  # no self-implied relationship
        if (col, b_name) in declared:
            return  # already a declared FK on this column -> table
        if col_type.get((a, col)) != col_type.get((b_name, ref_col)):
            return  # incompatible base types
        key = (a, col, b_name)
        rank = _RANK[confidence]
        if key not in best or rank > best[key][0]:
            best[key] = (rank, ImpliedFK(a, col, b_name, ref_col, confidence, reason))

    for t in schema.tables:
        declared = {(local, fk.ref_table)
                    for fk in t.foreign_keys for local in fk.columns}
        for c in t.columns:
            # Strategy 1: exact column-name == single-column PK name -> hoch
            for b_name in pk_targets.get(c.name, []):
                consider(t.name, c.name, b_name, c.name,
                         "hoch", "exakter PK-Name", declared)
            # Strategy 2/3: suffix -> table name with a conventional generic PK
            stem = _strip_id_suffix(_normalize(c.name))
            if stem:
                allowed = _GENERIC_PK | {stem + "id"}
                for b_name, pk, norm_pk in by_norm.get(stem, []):
                    if norm_pk in allowed:
                        consider(t.name, c.name, b_name, pk, "mittel",
                                 f"Suffix→Tabelle ({c.name}→{b_name})", declared)
                for b_name, pk, norm_pk in by_singular.get(stem, []):
                    if norm_pk in allowed:
                        consider(t.name, c.name, b_name, pk, "niedrig",
                                 "Suffix→Tabelle (Plural)", declared)

    out = [v[1] for v in best.values()]
    out.sort(key=lambda i: (i.table, i.column, i.ref_table))
    return tuple(out)
```

- [ ] **Step 4: Tests laufen lassen, Erfolg bestätigen**

Run: `./venv/bin/python -m pytest tests/test_implied.py -q`
Expected: PASS — neue + bestehende Tests grün.

- [ ] **Step 5: Volle Suite (Regressionsschutz)**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -1`
Expected: `337 passed, 2 skipped` (329 vorher + 8 neue). Insbesondere `test_no_implied_when_relationships_are_declared` bleibt grün (alle Inventory-FKs deklariert → declared-Guard greift).

- [ ] **Step 6: Commit**

```bash
git add core/implied.py tests/test_implied.py
git commit -m "feat: AP-55 — implied-FK Suffix→Tabelle-Heuristik + Confidence-Score (core)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Route — `/api/schema` shippt `implied_fks`

**Files:**
- Modify: `web/routes.py` (`/api/schema`-Handler, nach `cross_schema_fks=…`, ~Zeile 150)
- Test: `tests/test_api.py` (neuen Test anhängen)

**Interfaces:**
- Consumes: `find_implied_fks` aus Task 1.
- Produces: `/api/schema`-JSON enthält `implied_fks: [{from_table, column, to_table, to_column, confidence, reason}, …]`.

- [ ] **Step 1: Failing-Route-Test schreiben**

Am Ende von `tests/test_api.py` anhängen:
```python
def test_schema_endpoint_returns_implied_fks(client, inventory_nofk_url):
    data = client.post("/api/schema", json={"connection_url": inventory_nofk_url}).get_json()
    assert "implied_fks" in data
    entry = next(e for e in data["implied_fks"]
                 if e["from_table"] == "VirtualMachines" and e["column"] == "OSID")
    assert entry["to_table"] == "OperatingSystems"
    assert entry["to_column"] == "OSID"
    assert entry["confidence"] == "hoch"
    assert entry["reason"]
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `./venv/bin/python -m pytest tests/test_api.py::test_schema_endpoint_returns_implied_fks -q`
Expected: FAIL — `KeyError`/`assert "implied_fks" in data` schlägt fehl (Feld fehlt).

- [ ] **Step 3: Import + Response-Feld ergänzen**

In `web/routes.py` den Import sicherstellen (oben bei den `core`-Imports):
```python
from core.implied import find_implied_fks
```
Im `/api/schema`-Handler im `jsonify(...)` direkt **nach** der Zeile
```python
        cross_schema_fks=list(schema.cross_schema_fks(schema_name)),
```
einfügen:
```python
        implied_fks=[
            {"from_table": i.table, "column": i.column,
             "to_table": i.ref_table, "to_column": i.ref_column,
             "confidence": i.confidence, "reason": i.reason}
            for i in find_implied_fks(schema)
        ],
```

- [ ] **Step 4: Test laufen lassen, Erfolg bestätigen**

Run: `./venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat: AP-55 — /api/schema liefert implied_fks (Route)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Frontend — Info-Panel zeigt implied-FK-Liste mit Confidence-Badge

**Files:**
- Modify: `web/static/js/app.js` (`openInfo`, ~Zeile 212–245)
- Smoke: `.superpowers/sdd/verify_implied.py` (neu)

**Interfaces:**
- Consumes: `SCHEMA.implied_fks` (aus Task 2), JS-Globals `openInfo`/`postJSON`/`doConnect`/`setCurrentUrl` (bestehend), CSS-Klassen `.objlist`/`.badge` (bestehend).
- Produces: Info-Panel-Count-Zeile „Implizite FKs (geraten)" + `<ul class="objlist">`-Block je Treffer mit `[stufe]`-Badge + Begründung.

- [ ] **Step 1: Failing Browser-Smoke schreiben**

Create `.superpowers/sdd/verify_implied.py`:
```python
"""Browser smoke for AP-55: the Info/Übersicht panel shows an 'Implizite FKs (geraten)'
count row and, when implied FKs exist, a list with a confidence badge. A JS-injected
fake edge verifies the list-render path independent of the demo data."""
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

    has_key = page.evaluate("Array.isArray(SCHEMA.implied_fks)")
    check("SCHEMA.implied_fks is an array", has_key)

    page.evaluate("openInfo()")
    page.wait_for_selector("#tabpanels .detail", timeout=5000)
    txt = page.eval_on_selector("#tabpanels", "el => el.textContent")
    check("Info panel shows 'Implizite FKs (geraten)' row", "Implizite FKs (geraten)" in txt)

    # populated case: inject a fake implied FK, re-render, expect edge + badge
    page.evaluate("""SCHEMA.implied_fks = [{from_table:'Bestellung', column:'kunde_id', to_table:'Kunde', to_column:'id', confidence:'mittel', reason:'Suffix→Tabelle (kunde_id→Kunde)'}]; openInfo();""")
    page.wait_for_timeout(300)
    txt2 = page.eval_on_selector("#tabpanels", "el => el.textContent")
    check("list renders injected implied edge", "Bestellung.kunde_id → Kunde.id" in txt2)
    badge = page.eval_on_selector("#tabpanels", "el => !!el.querySelector('.objlist .badge')")
    check("confidence badge rendered", badge)

    real = [e for e in errors if "favicon" not in e.lower()]
    check("no console errors (favicon ignored)", not real, "; ".join(real[:3]))
    b.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results)-len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
```

- [ ] **Step 2: App neu starten + Smoke laufen lassen, Fehlschlag bestätigen**

Voraussetzung: App nach Task 2 (Route-Änderung) **neu gestartet**, sonst liefert die laufende Route `implied_fks` noch nicht:
```bash
LUCENT_PORT=5057 bash run.sh --skip-setup   # (laufende Instanz vorher beenden)
```
Run: `python3 .superpowers/sdd/verify_implied.py`
Expected: FAIL — „Info panel shows 'Implizite FKs (geraten)' row" scheitert (Zeile fehlt noch).

- [ ] **Step 3: `openInfo` — Count-Zeile + Liste rendern**

In `web/static/js/app.js`, in `openInfo`, im `dbBlock`-Aufbau direkt **nach** der Zeile
```js
      `<tr><td>Cross-Schema-FKs</td><td>${(SCHEMA.cross_schema_fks || []).length}</td></tr>` +
```
einfügen:
```js
      `<tr><td>Implizite FKs (geraten)</td><td>${(SCHEMA.implied_fks || []).length}</td></tr>` +
```
Danach, direkt **nach** dem bestehenden `xfkBlock`-Aufbau (vor `panel.innerHTML = …`), einen Listenblock ergänzen:
```js
  const ifk = SCHEMA.implied_fks || [];
  const ifkBlock = ifk.length
    ? `<h3>Implizite (geratene) Foreign Keys</h3><ul class="objlist">` +
      ifk.map((e) =>
        `<li>${esc(e.from_table)}.${esc(e.column)} → ` +
        `${esc(e.to_table)}.${esc(e.to_column)} ` +
        `<span class="badge">${esc(e.confidence)}</span> · ${esc(e.reason)}</li>`).join("") +
      `</ul>`
    : "";
```
Im finalen `panel.innerHTML`-String den `ifkBlock` direkt **nach** `xfkBlock` einsetzen:
```js
    dbBlock +
    xfkBlock +
    ifkBlock +
    `<p class="hint">Implizite (geratene) Foreign Keys lassen sich über die ` +
```

- [ ] **Step 4: App neu starten ist nicht nötig (JS live) — Smoke laufen lassen, Erfolg bestätigen**

JS ist live; ein Reload reicht (der Smoke lädt die Seite frisch). Falls eine laufende Instanz fehlt, App wie in Step 2 starten.
Run: `python3 .superpowers/sdd/verify_implied.py`
Expected: `6/6 checks passed`.

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js .superpowers/sdd/verify_implied.py
git commit -m "feat: AP-55 — Info-Panel zeigt implizite FKs (Count + Liste + Confidence-Badge)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Release v0.47.0 + Doku/Übersichten + Deploy

**Files:** `config.py`, `lucent-hub.yml` (sync_version); `luDBxP-docs/docs/javascripts/icon-rail.js` (`APP_VERSION` + `TEST_COUNT`); `luDBxP-docs/zensical.toml`; `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`; `luDBxP-docs/docs/projekt/roadmap.md`; `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd`; `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd`; `luDBxP-docs/docs/referenz/oberflaeche.md`; `CLAUDE.md`; Site-Build.

- [ ] **Step 1: Version-Bump (MINOR)**

```bash
./venv/bin/python sync_version.py --minor      # 0.46.0 → 0.47.0
./venv/bin/python -m pytest -q 2>&1 | tail -1   # echte passed-Zahl für TEST_COUNT (erwartet 337)
```

- [ ] **Step 2: icon-rail + zensical**

`luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION` → `'0.47.0'`, `TEST_COUNT` → die neue passed-Zahl (337; `TEST_DATE` bleibt `2026-06-28`).
`luDBxP-docs/zensical.toml`: `· v0.46.0` → `· v0.47.0`.

- [ ] **Step 3: Changelog (Root EN)**

In `CHANGELOG.md` oben einfügen:
```markdown
## [0.47.0] — 2026-06-28

### Added
- Sharper implied-FK detection (AP-55): besides the exact-PK-name match, a column
  ending in an id-suffix whose stem names another table (case/separator/plural
  normalized) is now recognised as an implied FK when that table's single-column
  PK is a conventional id form (`id`/`uuid`/`guid`/`<stem>id`). Each hit carries a
  discrete confidence (hoch/mittel/niedrig) and is listed in the Info panel, clearly
  marked as a guess (no FK created, no SQL change). Cross-schema implied matching
  stays deferred (needs multi-schema reflection, same gate as AP-57).
```

- [ ] **Step 4: Changelog-Mirror (DE)**

In `luDBxP-docs/docs/entwicklung/changelog.md` oben einfügen:
```markdown
## [0.47.0] — 2026-06-28

### Hinzugefügt
- Geschärfte Implied-FK-Erkennung (AP-55): neben dem exakten PK-Namen-Match wird
  jetzt auch eine Spalte mit ID-Suffix erkannt, deren Stamm (Groß/Klein-, Trenner-
  und Plural-normalisiert) eine andere Tabelle benennt, sofern deren Single-Column-PK
  eine konventionelle ID-Form ist (`id`/`uuid`/`guid`/`<Stamm>id`). Jeder Treffer trägt
  eine Confidence-Stufe (hoch/mittel/niedrig) und erscheint im Info-Panel, klar als
  geraten markiert (kein FK wird angelegt, keine SQL-Änderung). Cross-Schema-Matching
  bleibt zurückgestellt (braucht Multi-Schema-Reflection, Gate wie AP-57).
```

- [ ] **Step 5: roadmap.md — AP-55 von Offen → Erledigt**

In `luDBxP-docs/docs/projekt/roadmap.md`:
(a) Den **AP-55-Bullet aus der „### Legacy-DB-Migration / Reverse-Engineering"-Offen-Liste entfernen** (aktuell Zeile 25, `- **AP-55** — Implied-FK-Schärfung: …`).
(b) Im Versionslog unter „## Erledigte Arbeitspakete" **vor** dem `**v0.46.0** (2026-06-28):`-Block den neuen Block einfügen:
```markdown
**v0.47.0** (2026-06-28):

- **AP-55** — Implied-FK-Schärfung: `core/implied.py` erkennt jetzt zusätzlich Suffix→Tabellenname-Matches (Groß/Klein-, Trenner-, Plural-normalisiert) mit konventionellem Ziel-PK; jeder Treffer trägt eine Confidence-Stufe (hoch/mittel/niedrig) + Begründung, `/api/schema` liefert sie, das Info-Panel zeigt Count + Liste mit Badge. Cross-Schema bleibt zurückgestellt. **Aufwand M** — v0.47.0
```

- [ ] **Step 6: Gantt + Board**

Gantt `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd`:
- In der erledigt-Sektion **nach** `AP-54 — Cross-Schema-FK-Diagnose :done, f20, 2026-06-28, 1d` einfügen: `    AP-55 — Implied-FK-Schärfung                :done, f21, 2026-06-28, 1d`
- Die **AP-55-Zeile aus „section Legacy-DB-Migration (geplant)"** entfernen (aktuell `AP-55 — Implied-FK-Schärfung :p21, 2026-07-02, 1d`).
- Falls die erledigt-Sektionsüberschrift eine Versionsspanne trägt (`… –v0.46.0 (erledigt)`), Obergrenze auf `v0.47.0` ziehen.

Board `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd`:
- `class M2,M3,M4 plan` → `class M3,M4 plan`
- Neue Zeile `class M2 done` ergänzen (M2 = AP-55).

- [ ] **Step 7: oberflaeche.md**

In `luDBxP-docs/docs/referenz/oberflaeche.md` im Info/Übersicht-nahen Abschnitt einen Satz ergänzen: das Info-Panel listet jetzt zusätzlich die **impliziten (geratenen) Foreign Keys** mit Confidence-Stufe (hoch/mittel/niedrig) — read-only, kein FK wird angelegt.

- [ ] **Step 8: Site bauen + gegenprüfen**

```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
cd luDBxP-docs/site && grep -o "v0.47.0" index.html | head -1 && grep -o "AP&#45;55\|AP-55" images/mermaid/projekt-roadmap-1.svg | head -1
```
Expected: `v0.47.0` und ein AP-55-Treffer in der gerenderten Roadmap-SVG (beachte die Entity-Kodierung `&#45;` für `-`).

- [ ] **Step 9: SDD-Final-Review** (opus, über den gesamten Branch-Diff `git diff master...ap-55-implied-fk`): Layering (core ohne Flask), NO-CDN, Read-only, Doku-Vollständigkeit, keine Test-Regression.

- [ ] **Step 10: Commit Doku/Version**

```bash
git add -A
git commit -m "docs: Release v0.47.0 — Implied-FK-Schärfung (AP-55)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 11: CLAUDE.md — Einschränkungen aktualisieren**

In `CLAUDE.md` unter „## Bekannte Einschränkungen" einen Blockquote ergänzen:
```markdown
> **Implied-FK-Schärfung (AP-55, v0.47.0):** Implied-FKs werden neben dem exakten
> PK-Namen-Match auch über Suffix→Tabellenname (Groß/Klein-, Trenner-, Plural-
> normalisiert, Ziel-PK = generische ID-Form) erkannt; jeder Treffer trägt eine
> Confidence-Stufe (hoch/mittel/niedrig) und erscheint read-only im Info-Panel.
> Es werden keine FKs angelegt; Cross-Schema-Implied-Matching bleibt zurückgestellt
> (braucht Multi-Schema-Reflection, Gate wie AP-57).
```
Danach: `git add CLAUDE.md && git commit -m "docs: CLAUDE.md — AP-55 Implied-FK-Schärfung in Einschränkungen"` (mit Co-Authored-By-Footer).

- [ ] **Step 12: Merge + Deploy** (nach Freigabe): ff-merge → master, push origin/master, gh-pages-Worktree-Deploy (`.nojekyll` erhalten). Anschließend KPI-Zeile #13 in `docs/session-kennzahlen.md` + Handoff erst beim Sessionende (separater Handoff-Flow).

---

## Self-Review

**Spec coverage:**
- §1 Datenmodell (`confidence`/`reason`, `_ID_SUFFIXES`, `_normalize`, Plural) → Task 1 Step 3 ✓
- §2 Matching (3 Strategien + FP-Bremsen + Determinismus + Ambiguität via Rank-Dedup) → Task 1 Step 3 + Tests Step 1 ✓
- §3 Route (`implied_fks` immer geliefert, Graph unverändert) → Task 2 ✓
- §3 UI (Count + objlist + Badge, „geraten") → Task 3 ✓
- §4 Tests (Unit: 3 Strategien + Nicht-Treffer + Determinismus + Rückwärtskompat über Bestands-Fixture-Tests; Route; Browser-Smoke) → Task 1/2/3 ✓
- §5 Scope-Cuts (Cross-Schema Carryover, Konstanten statt Config, kein Graph-Styling, kein Auto-FK) → in Code-Konstanten + Changelog/CLAUDE.md dokumentiert ✓
- §6 Release/Doku → Task 4 ✓

**Placeholder scan:** Keine TBD/TODO; alle Code-Hunks vollständig, alle Commands mit Expected.

**Type/Name-Konsistenz:** `ImpliedFK(table, column, ref_table, ref_column, confidence, reason)` identisch in Core, Tests; Route-Keys `from_table/column/to_table/to_column/confidence/reason` identisch in `web/routes.py`, `tests/test_api.py`, `app.js`-Render und Smoke (`SCHEMA.implied_fks` mit denselben Keys). JSON-Feldname `implied_fks` durchgängig. `find_implied_fks(schema)` Signatur unverändert (nur Rückgabe-Felder erweitert) → `build_graph` bleibt kompatibel.
