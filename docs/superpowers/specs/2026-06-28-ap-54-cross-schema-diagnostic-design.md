# AP-54 — Cross-Schema-FK-Diagnose (read-only)

**Datum:** 2026-06-28
**Status:** genehmigt (Design)
**Scope:** `core/model.py`, `core/loaders/sqlalchemy_loader.py`, `web/routes.py`, `web/static/js/app.js`. Read-only; keine Join-/SQL-Änderung. Konzept-Kontext: [Legacy-DB-Migration-Tooling](../../concepts/2026-06-28-legacy-db-migration-tooling.md) (AP-54 ist das Entscheidungs-Gate für AP-57).

## Ziel

Empirisch sichtbar machen, ob die **verbundene Datenbank FKs über Schema-Grenzen** hat. Heute verwirft der Loader `referred_schema`; AP-54 trägt es ins Model, leitet daraus die Cross-Schema-Kanten ab und zeigt sie im Info/Übersicht-Panel. Damit ist beantwortbar, ob die volle Cross-Schema-Join-Stufe (AP-57) überhaupt nötig ist.

## Komponenten

### 1. Model (`core/model.py`)
`ForeignKey` (frozen dataclass) bekommt ein neues Feld **nach** `column_pairs`, mit Default:
```python
    ref_schema: str = ""   # Schema, auf das der FK zeigt, falls abweichend; "" = gleiches/unbekanntes Schema
```
Default am Ende → bestehende positionale Konstruktion (`ForeignKey(ref_table, pairs)`) und `ForeignKey.single(...)` bleiben gültig.

Neue Methode an `Schema`:
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
`current_schema` ist der reflektierte Schema-Name (kann `""` sein → dann gilt jedes nicht-leere `ref_schema` als cross-schema).

### 2. Loader (`core/loaders/sqlalchemy_loader.py:70`)
`referred_schema` mitnehmen statt verwerfen:
```python
fks.append(ForeignKey(fk["referred_table"], pairs, fk.get("referred_schema") or ""))
```

### 3. Route (`web/routes.py`, `api_schema`)
Im `jsonify(...)` ergänzen (nutzt das bereits vorhandene `schema_name`):
```python
        cross_schema_fks=list(schema.cross_schema_fks(schema_name)),
```

### 4. UI (`web/static/js/app.js`)
- Die `/api/schema`-Antwort trägt `cross_schema_fks`; dieses Array wird beim Laden auf dem `SCHEMA`-Global mitgespeichert (dort, wo `SCHEMA` aus der Antwort gesetzt wird).
- `openInfo()` rendert im Übersicht-Block eine Zeile **„Cross-Schema-FKs: N"**. Bei `N > 0` darunter eine Liste der Kanten im Format `from_table.col → to_schema.to_table.col` (mehrspaltige FKs: Spalten kommagetrennt); bei `N = 0` „keine".

## Datenfluss

```
Reflection (1 Schema) → ForeignKey.ref_schema gefüllt (Loader)
   → Schema.cross_schema_fks(schema_name) (core, pur)
   → /api/schema JSON: cross_schema_fks[]
   → SCHEMA.cross_schema_fks (JS) → Info/Übersicht-Panel (Count + Kantenliste)
```

## Tests

Reine Logik ist CI-testbar (konstruierte Model-Objekte); die Live-Reflexion echter Cross-Schema-FKs braucht Postgres/Oracle (manuell, da SQLite keine Schemas hat).

1. **`tests/test_model.py`** — `Schema.cross_schema_fks()`:
   - Positiv: Tabelle mit `ForeignKey(..., ref_schema="Production")`, `current_schema="Sales"` → Kante enthalten (richtige from/to-Felder).
   - Negativ: `ref_schema=""` (gleiches Schema) → nicht enthalten; `ref_schema="Sales"` mit `current_schema="Sales"` → nicht enthalten.
   - `current_schema=""`: jedes nicht-leere `ref_schema` zählt als cross-schema.
   - Default: `ForeignKey("T", ((a,b),))` hat `ref_schema == ""`.
2. **`tests/test_api.py`** — `/api/schema` enthält den Schlüssel `cross_schema_fks` (leere Liste für die SQLite-Demo, die keine Cross-Schema-FKs hat).

## Release

- `sync_version.py --minor` (0.45.3 → **0.46.0**) + icon-rail `APP_VERSION` + `TEST_COUNT` (neue pytest-Zahl) + `zensical.toml`.
- Changelog (Root EN + Mirror DE), `roadmap.md` (AP-54 von Offen → v0.46.0 erledigt), Gantt + Board (AP-54/M1 plan → done), `oberflaeche.md` (Info-Panel-Diagnose), Site, gh-pages.
- Deutsch / NO-CDN. SDD-Final-Review nicht weglassen.

## Nicht im Scope

- Keine Cross-Schema-**Joins** (das ist AP-57, gegated durch diese Diagnose).
- Kein Multi-Schema-Reflection-Merge; weiterhin ein Schema je Reflexion (AP-52).
- Keine `Table.schema`-Zuordnung (erst AP-57).
