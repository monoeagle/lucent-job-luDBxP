# AP-56a — Subset-Footprint + Export-Skelett — Design

**Datum:** 2026-06-28
**Status:** Spec (genehmigt im Brainstorming)
**Aufwand:** M (die schema-basierte erste Scheibe von AP-56; der Live-Walk ist AP-56b)
**Vorgänger-Konzept:** `docs/concepts/2026-06-28-legacy-db-migration-tooling.md` (Abschnitt AP-56)

## Ziel

„Gib mir Entität X **und alle referenziell abhängigen Tabellen** (Kinder via Reverse-FK nach unten, Eltern/Lookups via FK nach oben)" → ein **referenziell konsistenter Export-Bauplan**. Klassisches Database-Subsetting (vgl. Jailer), der größte echte Mehrwert für „sauberer Export" im HCMX-Migrations-Use-Case.

**Gestaffelt (wie AP-54→57):**
- **AP-56a (diese Spec):** rein **schema-basierter** Footprint + Export-**Skelett**. Berechnet welche Tabellen einbezogen sind, in welcher Reihenfolge, und generiert je Tabelle ein parametrisiertes SELECT, das zur Wurzel zurück-joint. **Führt nichts aus.**
- **AP-56b (später):** Live-datengetriebener Walk gegen die echte DB — echte Zeilenzahlen, konkrete IN-Listen/Daten-Dump.

## Code-Befunde (Ist-Stand verifiziert)

- **Graph ist ungerichtet** (`core/graph.py`, `nx.Graph`). Für die gerichtete Closure baut `subset.py` die Adjazenz **direkt aus dem Model** (nicht aus `build_graph`).
- **FK-Richtung:** `Table.foreign_keys` = Kind→Eltern. „Kinder" einer Tabelle = Rückwärts-Scan aller FKs. Implizite FKs (`core.implied.find_implied_fks`, AP-55) liefern dieselbe Kind→Eltern-Richtung (`ImpliedFK.table` = Kind, `.ref_table` = Eltern).
- **Read-only Ausführung** existiert (`core/datapreview.py::execute_select`), wird in AP-56a aber **nicht** gebraucht (schema-only).
- **SQL-Rendering wiederverwendbar:** `core.sqlgen.Dialect` (frozen) mit `quote()`, `table_ref(table, schema)`, `qualify(table, column, schema)` — dieselbe Dialekt-Auswahl wie `generate_sql`.

## 1. Core-Modul + Closure-Algorithmus (`core/subset.py`, pur, kein Flask)

**Gerichtete FK-Adjazenz aus dem `Schema`:**
- `parents[t]` = Tabellen, die `t` per FK referenziert (aus `Table.foreign_keys`).
- `children[t]` = Tabellen, deren FK auf `t` zeigt (Rückwärts-Scan).
- Bei `include_implied=True` ergänzen die `find_implied_fks(schema)`-Kanten dieselbe Kind→Eltern-Adjazenz.

**Closure (down-then-up), als BFS mit Ableitungsbaum:**
1. **Abwärts** von `root`: rekursiv `children`-Kanten folgen → Menge `D`. Jede Tabelle merkt sich ihre **Ableitungskante** (Vorgänger + FK-Paare + Richtung).
2. **Aufwärts** von `{root} ∪ D`: rekursiv `parents`-Kanten folgen → Menge `U` (Lookups). **Kein erneutes Absteigen** von U-Tabellen — das verhindert die Explosion („up-then-down" wird unterbunden).
3. `closure = {root} ∪ D ∪ U`. **Erst-erreicht** gewinnt die Ableitungskante, mit **D-Priorität** (eine sowohl ab- als auch aufwärts erreichbare Tabelle behält die Abwärts-Ableitung).

**Schutz:** Visited-Set je Phase (Zyklen, Self-FKs), konfigurierbares **Tiefenlimit** (Default `max_depth=5`). Greift es, wird `truncated=True` gesetzt.

**Datenmodell (Rückgabe):**
```python
@dataclass(frozen=True)
class SubsetEdge:
    via_table: str                       # Vorgänger im Ableitungsbaum
    pairs: tuple[tuple[str, str], ...]   # (local_col, ref_col) der FK
    kind: str                            # "child" | "parent" | "root"

@dataclass(frozen=True)
class SubsetTable:
    name: str
    edge: SubsetEdge | None              # None nur für root
    depth: int

@dataclass(frozen=True)
class SubsetResult:
    start: str
    tables: tuple[SubsetTable, ...]      # topologisch sortiert (Eltern vor Kindern)
    truncated: bool

def compute_subset(schema, start_table, *, include_implied=False, max_depth=5) -> SubsetResult: ...
```

**Topologische Ordnung:** Closure-Tabellen so sortiert, dass referenzierte (Eltern/Lookups) vor referenzierenden (Kindern) stehen (Kahn über den FK-DAG der Closure; Zyklen-Reste in stabiler Namensreihenfolge). Relevant für AP-56b (Insert-Order) und als nachvollziehbare Präsentation.

## 2. SELECT-Skelett + Wurzel-Filter

Getrennt von der reinen Closure (testbar ohne Filter):
```python
def generate_subset_sql(schema, result: SubsetResult, root_filter, *, dialect="") -> tuple[SubsetScript, ...]
# SubsetScript(table: str, sql: str, params: dict)
```

**Wurzel-Filter:** ein einzelnes parametrisiertes Prädikat auf der Start-Tabelle — `(column, op, value)` mit `op ∈ {=, !=, <, >, <=, >=, IN}` → `WHERE <root>.<col> <op> :root`. (Multi-Filter/komplexes WHERE bewusst später.)

**SELECT je Closure-Tabelle `T`:** Der Ableitungsbaum liefert den Pfad `T → via → … → root`. Daraus:
```sql
SELECT [DISTINCT] t0.*
FROM   <schema.>T   t0
JOIN   <schema.>via t1 ON t0.<localcol> = t1.<refcol> [AND …]
JOIN   …
JOIN   <schema.>root tN ON …
WHERE  tN.<col> <op> :root;
```
- **Aliasse** positional (`t0…tN`) → robust gegen Self-FKs / wiederholte Namen.
- **ON-Orientierung:** Der FK liegt immer auf der **Kind-Seite**. Die `pairs` einer Ableitungskante sind `(child_local_col, parent_ref_col)`. Beim Rendern joint man `child.local = parent.ref` — unabhängig davon, ob die Kante beim Walk abwärts (`kind="child"`, `T` ist Kind von `via`) oder aufwärts (`kind="parent"`, `T` ist Eltern von `via`) erreicht wurde. Die Kante muss also festhalten, welche der beiden Tabellen die Kind-Seite ist.
- **`DISTINCT`** genau dann, wenn der Ableitungspfad eine **Aufwärts-Kante** (`kind="parent"`) enthält (ein Lookup kann mehrfach getroffen werden); reine Abwärts-Pfade liefern eine Zeile je `T`.
- **Quoting/Schema-Qualifizierung** via `core.sqlgen.Dialect` (`quote`/`table_ref`/`qualify`), dieselbe Dialekt-Auswahl wie `generate_sql`.
- **`root` selbst:** `SELECT * FROM <schema.>root WHERE <col> <op> :root`.
- Parametrisiert (`:root`); eine Inline-Literal-Variante (analog `sqlgen.sql_inline`) ist optional dabei.

**Read-only:** AP-56a führt **nichts** aus — reine String-Erzeugung. Der Nutzer führt die SELECTs extern aus.

## 3. Route + UI

**Route `/api/subset`** (POST, read-only, keine Ausführung):
- Input: `{connection_url, schema, start_table, root_filter:{column,op,value}, include_implied, max_depth?}`
- Lädt Schema (bestehender Loader), ruft `compute_subset` + `generate_subset_sql`.
- Output: `{start, tables:[{name, kind, via_table, depth}], scripts:[{table, sql, params}], truncated}`.
- Validierung: unbekannte Start-Tabelle/Spalte → 400 (wie `/api/joinpath`).

**UI — neuer Modus „Entität exportieren"** (analog SQL-Analyzer):
- Sidebar-Eintrag `data-action="subset"` → `openSubset()` öffnet Tab via `ensureTab` (wie `openAnalyzer`).
- Formular: **Start-Tabelle** (Dropdown aus `SCHEMA.tables`), **Wurzel-Filter** (Spalten-Dropdown der Start-Tabelle + Op + Wert), **Checkbox „implizite FKs einbeziehen"**, optional Tiefenlimit (Default 5).
- Ergebnis: (a) **Vorschau** — Closure-Tabellen als Liste mit Badge `root`/`child`/`parent` + `via`-Tabelle + Tiefe, topologisch sortiert, plus `truncated`-Hinweis falls gegriffen; (b) **SQL-Block** mit den SELECTs je Tabelle (kopierbar, wie die Join-Builder-Ausgabe).

## 4. Tests

**`tests/test_subset.py`** (pytest, konstruierte `Schema`-Objekte):
- Abwärts: Kinder rekursiv gesammelt.
- Aufwärts: Eltern/Lookups von root + von Kindern gesammelt.
- **down-then-up-Regel:** die *anderen* Kinder eines Lookups werden NICHT gezogen (kein Re-Descent).
- Zyklus-Schutz (A→B→A) terminiert; Self-FK (A→A) terminiert.
- Tiefenlimit → `truncated=True` und Tiefe begrenzt.
- declared-vs-implied: ohne Toggle keine impliziten Kanten, mit Toggle schon.
- Topologische Ordnung: Eltern vor Kindern.
- **SQL-Gen:** Kind-SELECT joint zurück zur Wurzel; `DISTINCT` bei Aufwärts-Pfad, keins bei reinem Abwärts-Pfad; Wurzel-Filter parametrisiert (`:root` in `params`); Schema-Qualifizierung; Alias-Korrektheit; `IN`-Operator.

**Route-Test** (`tests/test_api.py`): `/api/subset` gegen `inventory_url` liefert `tables` + `scripts`; unbekannte Start-Tabelle → 400.

**Browser-Smoke** (Playwright, System-python3): Demo verbinden → „Entität exportieren"-Tab → Start-Tabelle + Filter → Vorschau-Liste + SQL-Block rendern. App-Neustart vor Smoke (Route/Template-Änderung).

## 5. Scope-Cuts (bewusst, → AP-56b)

- **Keine Live-Ausführung**, keine echten Zeilenzahlen, keine konkreten IN-Listen, kein Daten-Dump (CSV/JSON).
- Einzel-Wurzel-Prädikat (kein Multi-Filter).
- Keine per-Assoziation-Steuerung (Jailer-Stil) — voll-automatisch down-then-up mit Tiefenlimit.
- Kein Insert-/DDL-Skript für eine Ziel-DB, keine Anonymisierung (ETL-Schicht).

## 6. Release / Doku (nach Implementierung)

- `sync_version.py --minor` (Feature) + icon-rail `APP_VERSION`/`TEST_COUNT`.
- Roadmap/Board/Gantt: AP-56 → AP-56a (erledigt) + AP-56b (offen) aufsplitten, jedes Item namentlich.
- CLAUDE.md „Bekannte Einschränkungen": Subset-Footprint-Block + Projekt-Kennzahlen-Seite mitziehen.
- Changelog EN+DE-Mirror, zensical, Site-Build, gh-pages.
- Deutsch / NO-CDN / SDD-Final-Review nicht weglassen.
