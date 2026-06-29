# AP-63·Stufe 2 (erste Scheibe) — Trigger als Sidebar-Kategorie — Design

**Datum:** 2026-06-29
**Status:** Spec (genehmigt im Brainstorming)
**Aufwand:** S–M (etabliert das Sidebar-Kategorie-Muster end-to-end + führt dialekt-Katalog-SQL testbar ein; nur Trigger/SQLite in dieser Scheibe)
**Vorgänger-Konzept:** `docs/concepts/2026-06-28-sidebar-object-categories.md` (Abschnitt „Stufe 2"). AP-63·S1 (Indizes/Checks, v0.52.0) lieferte die Detail-Anreicherung; diese Scheibe etabliert eine **neue Objekt-Kategorie**.

## Ziel

Trigger als **eigene read-only Sidebar-Kategorie** (über Tabellen/Views hinaus) reflektieren und anzeigen — Name, besitzende Tabelle, Quelltext. Etabliert das „neue Objekt-Kategorie"-Muster (Model → Loader → Endpoint → Sidebar-Kategorie → Detail) und führt **dialekt-spezifisches Katalog-SQL** erstmals ein, voll SQLite-CI-testbar.

**Gestaffelt (bewusst):**
- **Diese Scheibe:** nur **Trigger**, nur **SQLite**-Reflektion (voll testbar). Andere Dialekte liefern vorerst `()`.
- **AP-63·S2b (Folge):** Sequences + Materialized Views (SQLAlchemy-nativ `get_sequence_names`/`get_materialized_view_names`, nur PG/Oracle, skip-guarded) auf demselben Kategorie-Muster.
- **Fast-Follow:** PG/Oracle-Trigger-Reflektion (eigene Katalog-Query).

## Code-Befunde (Ist-Stand verifiziert)

- **SQLAlchemy hat KEIN Trigger-API** (`hasattr(insp, "get_triggers")` = False) → Katalog-SQL nötig. `get_sequence_names`/`get_materialized_view_names` existieren (für S2b), liefern auf SQLite `[]`.
- **SQLite-Katalog:** `SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger'` liefert Name, besitzende Tabelle, vollständiges `CREATE TRIGGER …`-SQL.
- **`core/model.py`**: reine frozen Dataclasses; `Schema` hat `tables`, `views` (View ist schema-level mit `name`/`columns`/`definition`). Trigger passt als weiteres schema-level Objekt daneben.
- **Loader (`core/loaders/sqlalchemy_loader.py`)**: hält `engine` + `insp`; führt heute nur Inspector-Reflection aus. Katalog-SQL läuft read-only über `engine.connect()` (wie `core/datapreview.py`). `core/` darf SQLAlchemy importieren (kein Flask).
- **`/api/schema` (`web/routes.py:134–162`)**: serialisiert `tables`/`views`/`cross_schema_fks`/`implied_fks`. Ergänzungspunkt für `triggers`.
- **Sidebar (`web/static/js/app.js::renderSidebar`, ~Z. 159–172)**: rendert `<h3>Tabellen (N)</h3>` + Liste, `<h3>Views (N)</h3>` + Liste; Klick → `openDetail(kind, name)`. `objList(items, kind)` baut `<li data-kind data-name>`.
- **`openDetail` (~Z. 290–342)**: feste Subtab-Bar Definition/Daten/SQL; Table-Zweig (Spalten+FKs+Indizes+Checks), View-Zweig (Spalten + Definition im SQL-Subtab). Daten-Subtab lädt `loadData(name, …)`.

## 1. Reflection — Trigger-Katalog (Loader)

In `core/loaders/sqlalchemy_loader.py` eine Helper-Funktion (pur bzgl. Flask, nutzt `engine`):
```python
def _reflect_triggers(engine) -> tuple[Trigger, ...]:
    """Read-only trigger reflection. SQLite via sqlite_master; other dialects
    return () for now (SQLAlchemy has no native trigger API)."""
    if engine.dialect.name != "sqlite":
        return ()
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT name, tbl_name, sql FROM sqlite_master "
                "WHERE type='trigger' AND sql IS NOT NULL ORDER BY name"
            )).fetchall()
        return tuple(Trigger(r[0], r[1] or "", r[2] or "") for r in rows)
    except SQLAlchemyError:
        return ()
```
- Aufruf in `load()` nach dem Views-Block; Ergebnis an `Schema(tables, views, triggers)` durchreichen.
- `text`, `SQLAlchemyError` sind oben bereits importiert; `Trigger` aus `core.model` ergänzen.
- **Read-only** — reine SELECTs gegen den Katalog. Kein Schreiben.

## 2. Model (`core/model.py`, pur)

```python
@dataclass(frozen=True)
class Trigger:
    name: str
    table: str       # besitzende Tabelle (tbl_name); "" falls unbekannt
    sql: str         # CREATE TRIGGER …-Quelltext
```
`Schema` um ein Feld erweitern (am Ende, Default `()`):
```python
triggers: tuple[Trigger, ...] = ()
```

## 3. Endpoint (`/api/schema`, `web/routes.py`)

Je Response ergänzen:
```python
triggers=[
    {"name": tr.name, "table": tr.table, "sql": tr.sql}
    for tr in schema.triggers
],
```

## 4. Sidebar (`web/static/js/app.js::renderSidebar`)

Nach dem Views-Block eine Trigger-Kategorie ergänzen — **nur wenn vorhanden** (kein leerer Abschnitt auf den vielen DBs ohne Trigger):
```javascript
((SCHEMA.triggers && SCHEMA.triggers.length)
  ? `<h3>Trigger (${SCHEMA.triggers.length})</h3>` +
    `<ul class="objlist">${objList(SCHEMA.triggers, "trigger")}</ul>`
  : "") +
```
- `SCHEMA.triggers` wird beim Schema-Laden gesetzt (wie `SCHEMA.tables`/`views`).
- Klick-Handler ist bereits generisch (`openDetail(li.dataset.kind, li.dataset.name)`); `kind="trigger"` wird durchgereicht.

## 5. Detail (`openDetail`, neuer `trigger`-Zweig)

Trigger haben keine Spalten/Joins/Daten → schlankeres Detail:
- Subtab-Bar für `kind==="trigger"` auf **Definition + SQL** reduziert (kein „Daten").
- **Definition:** `<h2>Trigger: <name></h2>` + `<p>auf Tabelle: <table></p>`.
- **SQL-Subtab:** `sqlText = trigger.sql` (der CREATE-TRIGGER-Quelltext).
- Lookup: `const tr = (SCHEMA.triggers||[]).find(x => x.name === name)`.
- Alle dynamischen Werte via `esc`. Read-only; keine Ausführung, keine Join-Teilnahme.

**Umsetzungshinweis:** Die feste Subtab-Bar in `openDetail` wird so angepasst, dass der „Daten"-Button nur für `kind` mit Daten (table/view) erscheint — für `trigger` entfällt er und der zugehörige `dataPanel`/`loadData`-Pfad wird nicht verdrahtet.

## 6. Demo-DB + Tests

**`sample_data/build_demo_db.py`** minimal erweitern: im `_SCHEMA` nach den Tabellen einen harmlosen Trigger ergänzen (keine Datenänderung, keine bestehenden Tests betroffen):
```sql
CREATE TRIGGER trg_vm_audit AFTER INSERT ON VirtualMachine
BEGIN SELECT 1; END;
```

**Tests:**
- **Loader** (`tests/test_sqlalchemy_loader.py` + neue Fixture `triggers_url` in `conftest.py`, file-SQLite mit einem benannten Trigger): `schema.triggers` enthält den Trigger mit korrektem `name`/`table`; `sql` enthält `CREATE TRIGGER`.
- **Loader ohne Trigger:** gegen `inventory_url` (keine Trigger) → `schema.triggers == ()`.
- **Demo-Loader** (`tests/test_demo_db_cases.py`): `schema.triggers` enthält `trg_vm_audit` mit `table == "VirtualMachine"`.
- **Endpoint** (`tests/test_api.py`): `/api/schema` gegen `demo_url` → `triggers` nicht leer, enthält `trg_vm_audit`.
- **Browser-Smoke** (Playwright, System-python3): Demo verbinden → Sidebar zeigt „Trigger"-Kategorie mit `trg_vm_audit` → Trigger öffnen → Detail zeigt „auf Tabelle: VirtualMachine" + SQL-Subtab mit `CREATE TRIGGER`; **kein** „Daten"-Subtab. **App-Neustart** vor Smoke.

## 7. Scope-Cuts (bewusst)

- **Nur Trigger, nur SQLite-Reflektion.** Andere Dialekte → `()` (dokumentiert). PG/Oracle-Trigger = Fast-Follow.
- **Sequences + Materialized Views = AP-63·S2b** (separate Scheibe, PG-only, skip-guarded).
- Keine Join-Pfad-Teilnahme, keine Ausführung von Triggern; reine read-only Anzeige des Quelltexts.
- Trigger-Kategorie nur sichtbar bei N>0.

## 8. Release / Doku (nach Implementierung)

- `sync_version.py --minor` (Feature) + icon-rail `APP_VERSION`/`TEST_COUNT`.
- Roadmap: AP-63·S2 → „Trigger erledigt; Sequences/Mat-Views = S2b offen"; AP-63·S3 bleibt offen.
- CLAUDE.md „Bekannte Einschränkungen": Trigger-Kategorie (read-only, SQLite-Reflektion) als Tier notieren; Kennzahlen-Seite (hartkodiert) mitziehen.
- Changelog EN + DE-Mirror, zensical, Site-Build, gh-pages.
- Deutsch / NO-CDN / SDD-Final-Review nicht weglassen.
