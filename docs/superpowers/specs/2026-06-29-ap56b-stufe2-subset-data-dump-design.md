# AP-56b·Stufe 2 — Subset-Daten-Dump (JSON) — Design

**Datum:** 2026-06-29
**Status:** Spec (genehmigt im Brainstorming)
**Aufwand:** S–M (Daten-Ebene von AP-56b; baut auf Stufe 1 auf — IN-Listen bleiben separates Folge-AP)
**Vorgänger:** `docs/superpowers/specs/2026-06-29-ap56b-subset-live-count-design.md` (Stufe 1) · `docs/superpowers/specs/2026-06-28-ap56a-subset-footprint-design.md` (AP-56a) · Konzept `docs/concepts/2026-06-28-legacy-db-migration-tooling.md` (Abschnitt AP-56)

## Ziel

Stufe 1 zählt die Zeilen der referenziellen FK-Hülle live. Stufe 2 holt die **Zeilen selbst**: die AP-56a-Hüll-SELECTs werden read-only ausgeführt und je Closure-Tabelle die echten Datenzeilen als **herunterladbares JSON-Bundle** geliefert — das, was die ETL-Schicht zum Transformieren/Laden in das neue Modell braucht.

**Gestaffelt (wie AP-54→56a→56b·Stufe 1):**
- **Stufe 2 (diese Spec):** Roh-**Daten-Dump** (Zeilen je Tabelle) als ein JSON-Bundle, per-Tabelle-Cap + lautes Truncation-Flag.
- **Später:** explizite **IN-Listen** (kompakte PK-Mengen je Tabelle als Export-Identität) — aus dem Dump ableitbar, separates Folge-AP. CSV/ZIP, SQL-INSERT, Anonymisierung bleiben bewusst draußen (ETL-Schicht).

## Code-Befunde (Ist-Stand verifiziert)

- **`core/subset.py`** liefert `SubsetResult` + `generate_subset_sql(...) -> tuple[SubsetScript, ...]` mit `SubsetScript(table, sql, params)`. Jedes `sql` ist `SELECT [DISTINCT] t0.* FROM … WHERE tN.<col> <op> :root;` — **roh ausgeführt (nicht COUNT-gewrappt) liefert es genau die Subset-Zeilen** der Tabelle. Kein neues pures Core-Modul nötig.
- **`core/datapreview.py::execute_select(url, sql, params, max_rows)`** führt read-only aus, kappt via `fetchmany(max_rows)`, gibt `{"columns":[...], "rows":[[...]]}`, `engine.dispose()` im finally. Kein Flask. Stufe-1-Aggregator `count_subset_rows` liegt schon hier.
- **`/api/subset/run`** (Stufe 1, `web/routes.py`) ist die Vorlage: gleiche Validierung, Run-Dialekt aus URL (`_dialect_from_url`), `incomplete`-Semantik. `/api/subset/dump` spiegelt sie.
- **UI-Panel „Entität exportieren"** (`web/static/js/app.js`): `runSubset`/`runSubsetCount` + `SUB_LAST_PAYLOAD` (Build-Zeit-Payload-Cache, in Stufe 1 eingeführt) + Hüll-Tabelle. Wird erweitert, nicht ersetzt.
- **Keine** vorhandene CSV/Download/Blob-Maschinerie → der Download wird client-seitig via Blob gebaut (Browser-nativ, kein CDN, kein Server-Filehandling).
- **`config.MAX_RESULT_ROWS = 5000`** ist der bestehende harte Result-Cap (auch von `/api/joinpath/run` genutzt) → als Per-Tabelle-Cap wiederverwendet.

## 1. Execution-Aggregator (`core/datapreview.py`)

```python
def dump_subset_rows(connection_url, scripts, *, max_rows_per_table) -> list:
    """Execute each subset SELECT read-only and capture its rows. Resilient per table.

    Fetches up to ``max_rows_per_table + 1`` rows to detect truncation: if more
    than the cap come back, the table is flagged ``truncated`` and the rows are
    cut to the cap. A per-table ``ConnectionError`` is caught and recorded as
    ``error`` (empty rows) so the remaining tables still dump.

    Returns a list of dicts in input order:
      {"table", "columns": [...], "rows": [[...]], "row_count": int,
       "truncated": bool, "error": str|None}
    """
    out = []
    for s in scripts:
        try:
            res = execute_select(connection_url, s.sql, s.params,
                                 max_rows=max_rows_per_table + 1)
            rows = res["rows"]
            truncated = len(rows) > max_rows_per_table
            if truncated:
                rows = rows[:max_rows_per_table]
            out.append({"table": s.table, "columns": res["columns"], "rows": rows,
                        "row_count": len(rows), "truncated": truncated, "error": None})
        except ConnectionError as exc:
            out.append({"table": s.table, "columns": [], "rows": [], "row_count": 0,
                        "truncated": False, "error": str(exc)})
    return out
```

- **Read-only** — nur `execute_select` (SELECT). Kein Schreiben.
- **Resilient pro Tabelle** (wie `count_subset_rows`): ein Fehler kippt nicht den ganzen Dump.
- **Truncation-Erkennung** über `cap+1`-Fetch — kein zusätzlicher COUNT nötig.
- Reihenfolge = Eingabereihenfolge (= topologische Closure-Ordnung).

## 2. Route `/api/subset/dump` (POST, read-only)

- **Gleicher Payload** wie `/api/subset/run`: `{connection_url, schema, start_table, root_filter:{column,op,value}, include_implied, max_depth?, dialect?}`.
- Server: Schema laden → `compute_subset(...)` → `generate_subset_sql(..., dialect=_dialect_from_url(url), schema_name=schema)` → `dump_subset_rows(url, scripts, max_rows_per_table=config.MAX_RESULT_ROWS)`.
- Validierung identisch zu `/api/subset/run`: leere URL → 400 (`_NO_URL_MSG`); `ConnectionError` beim Schema-Laden → 400; unbekannte Start-Tabelle/Spalte → 400; `ValueError` → 400.
- **Antwort (JSON-Bundle):**
  ```json
  {
    "start": "...",
    "truncated": false,              // Footprint-Tiefenlimit (aus SubsetResult)
    "incomplete": false,             // truncated OR any table.truncated OR any table.error
    "row_cap": 5000,
    "tables": [
      {"name":"...", "kind":"root|child|parent", "via_table":"...|null", "depth":0,
       "columns":["..."], "rows":[["..."]], "row_count":123,
       "truncated":false, "error":null}
    ]
  }
  ```
  - Tabellen-Metadaten (`kind`/`via_table`/`depth`) aus `result.tables` gejoint mit dem `dump_subset_rows`-Ergebnis per Tabellenname (Fallback `{"error":"not dumped", …}` falls eine Closure-Tabelle fehlt → erzwingt `incomplete`).
- **Serialisierung:** `rows`-Werte werden via Flask `jsonify` ausgegeben — identisches Verhalten wie der bestehende Result-Preview-Pfad (`/api/joinpath/run`). Nicht-native Typen (Datum/Decimal/bytes bei echtem Oracle/MSSQL) erben dessen Grenzen; keine Sonderbehandlung in dieser Scheibe.

## 3. UI — Panel „Entität exportieren" erweitern (`web/static/js/app.js`)

- Neuer Button **„Daten-Dump (JSON)"** im Ergebnisbereich neben „Zeilen zählen (live)", aktiv sobald ein Footprint vorliegt.
- Klick → `POST /api/subset/dump` mit `SUB_LAST_PAYLOAD` (dem Build-Zeit-Payload der angezeigten Hülle; Null-Guard „Erst Footprint bauen." wie bei `runSubsetCount`).
- Erfolg → Bundle als **Blob** (`new Blob([JSON.stringify(res, null, 2)], {type:"application/json"})`) → temporärer `<a download>` mit Klick → Datei `subset_<start>_<col><op><val>.json` (Wert sanitisiert: nur `[A-Za-z0-9._-]`, Rest `_`). `URL.revokeObjectURL` danach.
- **Laute Unvollständigkeits-Warnung** im Panel (`#sub_total` oder eigene Zeile), wenn `res.incomplete`: z. B. „Export unvollständig — abgeschnitten/Fehler bei: <Tabellen>" (Tabellen mit `truncated` oder `error` namentlich). Bei vollständigem Export kurze Bestätigung „Dump: <n> Tabellen, <Summe row_count> Zeilen".
- Read-only-Charakter: kein Schreiben; der Hinweistext des Panels nennt jetzt drei Aktionen (Footprint / Zählen / Dump).

## 4. Tests

**`tests/test_subset.py` / Integration gegen Demo-CMDB (SQLite):**
- `dump_subset_rows` für einen befüllten Start (z. B. `VirtualMachine`, `VMID=1`): je Tabelle `rows` == die Zeilen, die das jeweilige Hüll-SELECT direkt via `execute_select` liefert (Cross-Check, datenunabhängig); `columns` nicht leer; `error is None`; `truncated False`.
- **Deterministischer Anker:** `Datacenter`, `DatacenterID=3` (DC-Empty) → Root-Tabelle 1 Zeile, Kind-Tabellen 0 Zeilen, `incomplete`-Aggregat False.
- **Truncation:** `max_rows_per_table=2` auf einen Start, dessen Hülle eine Tabelle mit >2 Zeilen enthält → diese Tabelle `truncated=True`, `len(rows)==2`, `row_count==2`.
- **Resilienz:** ein `SubsetScript` mit ungültiger Referenz → `error` gesetzt, `rows==[]`, übrige Tabellen intakt.

**Route-Test** (`tests/test_api.py`): `POST /api/subset/dump` gegen `demo_url` liefert `tables` mit `columns`/`rows`/`row_count` + `incomplete`/`row_cap`; unbekannte Start-Tabelle → 400; leere URL → 400.

**Browser-Smoke** (Playwright, System-python3): Demo verbinden → „Entität exportieren" → Start `Datacenter`, Filter `DatacenterID = 3` → „Footprint bauen" → „Daten-Dump (JSON)" → Download-Event abfangen, geladenes JSON parsen, `start=="Datacenter"` und die Root-Tabelle mit `row_count==1` vorhanden. **App-Neustart** vor Smoke (Route/Python-Änderung).

## 5. Scope-Cuts (bewusst)

- **Nur JSON-Bundle** — kein CSV/ZIP, kein SQL-INSERT-/DDL-Skript, keine Anonymisierung (ETL-Schicht).
- **Keine expliziten IN-Listen** — aus dem Dump ableitbar; separates Folge-AP.
- **Kein Streaming/Pagination** — ein gekapptes Bundle je Tabelle (`config.MAX_RESULT_ROWS`).
- Kein eigener Dump-Cap-Config-Wert — `MAX_RESULT_ROWS` wiederverwendet (eigener Wert bei Bedarf als Folge-AP).
- Einzel-Wurzel-Prädikat (wie AP-56a/Stufe 1).

## 6. Release / Doku (nach Implementierung)

- `sync_version.py --minor` (Feature) + icon-rail `APP_VERSION`/`TEST_COUNT`.
- Roadmap/Board/Gantt: AP-56b·Stufe 2 → erledigt; verbleibendes IN-Listen-Folge-AP namentlich führen. Übersicht nach Build gegenprüfen.
- CLAUDE.md „Bekannte Einschränkungen": Subset-Block um den Daten-Dump ergänzen; Kennzahlen-Seite (hartkodiert) mitziehen.
- Changelog EN + DE-Mirror, zensical, Site-Build, gh-pages.
- Deutsch / NO-CDN / SDD-Final-Review nicht weglassen.
