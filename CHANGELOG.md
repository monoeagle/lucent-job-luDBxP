# Changelog

## [0.62.0] — 2026-07-01

### Added
- **Analyzer line-number gutter + error-line highlight (AP-65·B):** the SQL-Analyzer's input
  textarea now has a scroll-synced line-number gutter, and on a parse error the offending line
  (`parse_error_line`) is highlighted in the input. Implemented as a pure-frontend 3-layer editor
  (`web/static/js/app.js::attachLineGutter`): a line-number gutter, a scroll-synced backdrop that
  holds one row per logical line (the error row gets `.an-line-error`), and the textarea
  (transparent, `wrap="off"` → one logical line = one visual row) on top, which stays the single
  value source. `openAnalyzer` wires it (`panel._gutter`); `renderAnalyzeResult` calls
  `setErrorLine(res.parse_error_line)` (cleared on a successful parse or on any edit). NO-CDN
  (no editor library), read-only, no backend change. The input stays vertically resizable.

## [0.61.0] — 2026-07-01

### Changed
- **Analyzer points unclosed quotes at the true error line (AP-65·A-Härtung 2):** when a
  statement has a non-terminated quote, sqlglot raises a positionless `TokenError`. Previously
  the analyzer marked the quote left open at end-of-input; with a *shifted* quote (the real
  missing quote sits higher up, followed by again-balanced quotes) that pointed at the wrong
  line. A new pure helper `core/sqlanalyze.py::_odd_quote_line(sql, quote_char)` finds the sole
  line whose count of that quote character is odd — the real error line. When that line differs
  from the end-of-input line, `_parse_error_location` now redirects the reported parse error to
  it, without a column or char-mark (a *missing* quote has no exact position) and with a German
  hint naming the line. When the odd line coincides with the end-of-input line, or the count is
  ambiguous (zero or ≥2 odd lines, e.g. a legitimate multi-line string), the previous
  end-of-input behavior is unchanged. The Analyzer UI omits ", Spalte N" from the error header
  when no column is available. Read-only, no new core module, fully CI-testable.

## [0.60.0] — 2026-06-30

### Added
- **MSSQL synonyms now reflect (AP-67·MSSQL-Grundlage):** `_reflect_synonyms` in
  `core/loaders/sqlalchemy_loader.py` gained an MSSQL branch (`sys.synonyms`); synonyms were
  previously Oracle-only (`all_synonyms`). A new idempotent SQLAlchemy seeder
  `sample_data/seed_server_demo.py` builds a compact 5-table CMDB plus all MSSQL-specific
  object categories (sequence, function, procedure, trigger, a view that calls the function,
  synonym) — MSSQL-first, structured to adapt to Oracle later; external setup script not run by
  the read-only tool. `sample_data/server-demo-README.md` documents bring-up. A new
  skip-guarded MSSQL integration test verifies all 7 reflectable object categories including
  the AP-66·S1 view→routine link, live against an MSSQL container.

### Fixed
- **Doc: MSSQL sequences incorrectly claimed empty:** Project docs stated `get_sequence_names`
  returns empty for MSSQL (`"SQLite/MSSQL → leer"`); MSSQL sequences **do** reflect via
  `get_sequence_names`. Corrected in CLAUDE.md, architektur.md, and datenmodell.md.

## [0.59.0] — 2026-06-30

### Fixed
- **Unclosed/shifted quote (TokenError) now shows a position and an honest hint (AP-65·A-Härtung):**
  Before, a missing `"` in a multi-line statement caused sqlglot to consume to EOF; the analyzer showed
  no position for the error. A new pure-scanner helper `_unclosed_quote_offset(sql)` in
  `core/sqlanalyze.py` locates the quote left open at end of input. The analyzer now shows the
  line/column of the unclosed quote, marks it in the context excerpt, and adds an honest hint:
  at shifted-quote situations the real cause may sit earlier in the statement (sqlglot cannot
  pinpoint it exactly). `AnalysisResult` gains two new trailing fields: `parse_error_highlight_pos: int`
  (context-relative index of the marked token, replaces the old `indexOf` first-occurrence logic) and
  `parse_error_hint: str` (optional hint text shown below the excerpt when sqlglot's position is
  approximate). `/api/analyze` serializes both fields. The analyzer UI marks via the index and shows
  the hint when present. Read-only — no auto-correction. Fully CI-testable (no DB required).
  No new core module — `sqlanalyze.py` already existed.

## [0.58.0] — 2026-06-29

### Added
- **SQL Analyzer now shows parse-error position — line, column, and marked token (AP-65·A):**
  A new helper `_parse_error_location(exc, sql)` in `core/sqlanalyze.py` extracts structured
  position information from sqlglot errors. `ParseError` is resolved via sqlglot's
  `.errors[0]` (line/col/context); `TokenError` (e.g. unterminated string literal) derives the
  position best-effort from the consumed prefix in its message. `AnalysisResult` gains four
  trailing fields: `parse_error_line: int | None`, `parse_error_col: int | None`,
  `parse_error_context: str` (excerpt around the offending token), and
  `parse_error_highlight: str` (the offending token for marking). `/api/analyze` serializes
  all four fields. In the UI the analyzer shows **„Parse-Fehler in Zeile N, Spalte M:"** plus
  the context excerpt with the offending token in a red `.an-err-mark` span; when no position
  is available it falls back to the plain error string. Read-only — no auto-correction.
  Stufe B (line gutter) and C (lints with line refs) remain backlog.

## [0.57.0] — 2026-06-29

### Added
- **Views now surface which stored routines they reference (AP-66·Stufe 1):**
  A new pure module `core/viewdeps.py::referenced_routines(definition, known_routine_names, dialect)`
  parses the view SQL definition via sqlglot, matches function-call names (including Oracle
  package qualifiers) against the already-reflected `schema.routines` set, and returns only
  confirmed matches — built-in SQL functions are excluded. The `View` model gains a trailing
  `routines: tuple[str, ...] = ()` field; materialized views reuse the same shape. The loader
  fills it for views and materialized views (reflecting routines once before the view loop).
  `/api/schema` carries `"routines": [...]` on every view and materialized-view entry. In the UI,
  a view or matview detail shows a **„Verwendet Routinen"** section when routine references are
  present, and a **`ƒ`** badge appears in the sidebar on any view that uses routines. Migration-
  relevant signal: views that call stored routines are not migratable via pure join/FK lineage.
  Fully CI-testable (sqlglot, no DB required). Read-only — no routine execution.

## [0.56.0] — 2026-06-29

### Added
- **Trigger reflection extended to PostgreSQL, Oracle, and MS SQL Server (AP-63·Trigger-Fast-Follow):**
  `_reflect_triggers` in `core/loaders/sqlalchemy_loader.py` now takes `(engine, schema)` and uses
  per-dialect catalog SQL — **PostgreSQL** via `pg_trigger` + `pg_get_triggerdef`
  (`NOT tgisinternal`); **Oracle** via `all_triggers` (`base_object_type='TABLE'`) +
  `dbms_metadata.get_ddl`; **MSSQL** via `sys.triggers` + `sys.sql_modules`
  (`is_ms_shipped=0`). Only table/DML triggers are reflected. The `Trigger` model,
  `/api/schema` serialisation, and the JS trigger sidebar category are unchanged (AP-63·S2,
  v0.53.0) — triggers now simply appear for the new dialects too. MSSQL verified live against
  SQL Server 2022; PG and Oracle are skip-guarded integration tests. SQLite reflection
  (via `sqlite_master`) is unchanged.

## [0.55.1] — 2026-06-29

### Fixed
- **MS SQL Server reflection no longer crashes.** The MSSQL dialect exposes
  `get_unique_constraints`/`get_indexes` partly as a bare `NotImplementedError`
  (not a `SQLAlchemyError`), which escaped the loader's `except SQLAlchemyError`
  and aborted the whole `load()` — no MSSQL database was reflectable. These calls
  now catch `(SQLAlchemyError, NotImplementedError)`, consistent with the existing
  `get_check_constraints` handling, and fall back to empty. Verified against a live
  SQL Server 2022 (both MSSQL integration tests green, including the AP-63·S3 routine
  reflection); guarded in CI by a regression test using a `NotImplementedError`-raising
  fake inspector.

## [0.55.0] — 2026-06-29

### Added
- **Stored Procedures, Functions, Oracle Packages, and Oracle Synonyms as four new read-only
  sidebar categories (AP-63·S3):** reflected via per-dialect catalog SQL (`pg_proc` for
  PostgreSQL; `all_objects`/`all_source` for Oracle; `sys.objects`/`sys.sql_modules` for MSSQL;
  synonyms via `all_synonyms`, Oracle-only). Each category is shown only when N>0; the detail
  includes the source text/definition. Model gains `Routine(name, kind, sql)` (kind ∈
  procedure/function/package) + `Synonym(name, target)` and two trailing `Schema` fields
  `routines`/`synonyms`; `/api/schema` serialises `procedures`, `functions`, `packages`,
  `synonyms` (each `{"name","sql"}`, synonyms `{"name","target"}`). Display-only — no Data tab,
  no join participation. Skip-guarded live integration tests for PostgreSQL, Oracle, and MSSQL;
  SQLite/others return none.

## [0.54.0] — 2026-06-29

### Added
- **Sequences and materialized views as two new read-only sidebar categories (AP-63·S2b):**
  reflected via SQLAlchemy (`get_sequence_names` / `get_materialized_view_names`). Sequences
  show their name; materialized views show columns + definition (display-only, no Data tab).
  Model gains `Sequence` + `Schema.sequences`/`materialized_views` (materialized views reuse the
  `View` shape); `/api/schema` serializes both; the sidebar shows each category only when
  present. Real reflection works on **PostgreSQL/Oracle** (skip-guarded live test
  `tests/test_pg_integration.py`, set `LUCENT_PG_TEST_URL`); SQLite/MSSQL return none.

## [0.53.0] — 2026-06-29

### Added
- **Triggers as a new read-only sidebar category (AP-63·S2):** triggers are now reflected
  (name, owning table, source) and shown as their own "Trigger" sidebar category (only when
  present). Reflection uses dialect catalog SQL — **SQLite** via `sqlite_master`; other
  dialects return none for now (PG/Oracle trigger reflection is a fast-follow). The trigger
  detail is slim: definition (owning table) + the `CREATE TRIGGER` source in the SQL tab, no
  Data tab. Model gains `Trigger` + `Schema.triggers`; `/api/schema` serializes them; the
  demo CMDB gained a trigger. Sequences and materialized views remain AP-63·S2b. Display only
  — triggers are never executed and don't take part in join paths.

## [0.52.0] — 2026-06-29

### Added
- **Indexes + check constraints in the table detail (AP-63·S1):** the table detail's
  "Definition" tab now lists **all indexes** (name, columns, a `unique` badge) and
  **check constraints** (name, expression), read-only via SQLAlchemy reflection
  (`get_indexes()` / `get_check_constraints()`, all engines incl. SQLite). The model
  gains `Index`/`CheckConstraint` and `Table.indexes`/`check_constraints`; `/api/schema`
  serializes them. The demo CMDB gained an index (`ix_host_cluster`) and a check
  (`VMDisk.SizeGB > 0`). Display only — the reconstructed DDL and join paths are unchanged;
  expression/functional indexes are skipped.

## [0.51.0] — 2026-06-29

### Added
- **Subset IN-lists (AP-56c):** the "Entität exportieren" panel can now export the
  referential **export identity** — per closure table the primary-key set rendered as a
  self-contained read-only `SELECT * FROM tab WHERE pk IN (…);`. Composite primary keys use
  the portable `(a = … AND b = …) OR …` form (no row-value IN); literals are type-rendered
  (strings single-quoted with `'` doubled). The keys are derived from the AP-56b·Stage-2
  dump (`core/subset.py::subset_keys`/`subset_in_list_sql`) via the new endpoint
  `POST /api/subset/inlists`; the UI adds an "IN-Listen (SQL)" button that downloads one
  `.sql` (one annotated block per table). Tables without a primary key are loudly flagged
  (`incomplete`). Note: PK literals assume int/str/Decimal/bool; datetime/bytes PKs render
  best-effort.

## [0.50.0] — 2026-06-29

### Added
- **Subset data dump (AP-56b·Stage 2):** the "Entität exportieren" panel can now export
  the actual rows of the referential closure. A new `core.datapreview.dump_subset_rows`
  executes the AP-56a footprint SELECTs read-only and captures the rows per closure table;
  a per-table cap (`config.MAX_RESULT_ROWS`) is enforced with a loud truncation flag
  (detected by fetching `cap + 1`), and a per-table failure is reported as an error while
  the others still dump. New endpoint `POST /api/subset/dump` returns a JSON bundle
  `{start, truncated, incomplete, row_cap, tables[{columns, rows, row_count, truncated,
  error}]}`; the UI adds a "Daten-Dump (JSON)" button that downloads the bundle client-side
  (browser-native Blob, no server file). Read-only — no writes. Explicit IN-lists remain a
  follow-up.

## [0.49.0] — 2026-06-29

### Added
- **Subset live row counts (AP-56b·Stage 1):** the "Entität exportieren" panel can now
  execute the AP-56a footprint SELECTs read-only and show the real row count per closure
  table plus a total. A new `count_sql` wrapper (`SELECT COUNT(*) FROM (<subset SELECT>)`,
  Oracle-portable alias) feeds `core.datapreview.count_subset_rows`, which counts each
  table resiliently (a per-table failure is reported as an error and the others still
  count). New endpoint `POST /api/subset/run` returns `{tables[], total, incomplete}`;
  the UI adds a "Zeilen zählen (live)" button, a "Zeilen" column and a "Summe" footer.
  Counts only — no data dump, no writes. The IN-list / data dump is AP-56b·Stage 2.

## [0.48.3] — 2026-06-29

### Fixed
- The generated-SQL box in the SQL-Builder now keeps a full height before the first
  "Generieren" (it previously collapsed to a thin strip that clipped the copy icon)
  and shows a placeholder hint while empty.

## [0.48.2] — 2026-06-28

### Fixed
- HAVING comparison values are now bound type-correctly: a numeric-looking value
  (e.g. `HAVING COUNT(...) > 1`) is bound as a number instead of a string. Before,
  the read-only result preview silently returned zero rows in SQLite (an aggregate
  expression has no column affinity, so a TEXT-bound `'1'` never equals the integer
  COUNT). The generated SQL was already correct; now the preview matches.

### Docs
- All seven surface screenshots refreshed to the current UI (1920×1080) and shown at
  full content width; two new screenshots demonstrate the SQL-Builder clause sections
  (filter / sort / extra columns, and aggregate with GROUP BY + HAVING).

## [0.48.1] — 2026-06-28

### Changed
- Connection form reworked (AP-64): the save-name field now aligns with the
  fields above it; the old "Verbinden" button is gone; a new "Testen" button
  (left of "Speichern", below the fields) tests the connection read-only and
  reports the result in an info box below the buttons. Loading a schema stays a
  topbar action on a saved connection. Reuses `/api/connect`.

### Fixed
- Connection failures (e.g. unreachable Oracle host) now return HTTP 400 with
  the real driver message instead of 500, so the new "Testen" button surfaces
  the actual cause.

## [0.48.0] — 2026-06-28

### Added
- Database subsetting — schema footprint + export skeleton (AP-56a): from a start
  table and a root filter, the tool computes the referential closure (dependent
  children downward, lookup parents upward, Jailer-style "down-then-up" without
  re-descent; cycle-safe, depth-limited) and generates one read-only SELECT per
  included table that joins back to the root. New mode "Entität exportieren" and
  read-only endpoint `/api/subset`. Executes nothing; the live data-driven walk
  with real row counts is the deferred AP-56b.

## [0.47.0] — 2026-06-28

### Added
- Sharper implied-FK detection (AP-55): besides the exact-PK-name match, a column
  ending in an id-suffix whose stem names another table (case/separator/plural
  normalized) is now recognised as an implied FK when that table's single-column
  PK is a conventional id form (`id`/`uuid`/`guid`/`<stem>id`). Each hit carries a
  discrete confidence (hoch/mittel/niedrig) and is listed in the Info panel, clearly
  marked as a guess (no FK created, no SQL change). Cross-schema implied matching
  stays deferred (needs multi-schema reflection, same gate as AP-57).

## [0.46.0] — 2026-06-28

### Added
- Cross-schema FK diagnostic (read-only): foreign keys that point to a different
  schema are now reflected (`referred_schema`) and surfaced in the Info/Übersicht
  panel as a „Cross-Schema-FKs" count plus the list of crossing edges
  (`table.col → schema.table.col`). Answers empirically whether a connected
  database uses cross-schema FKs — the decision gate for full cross-schema joins.
  No join/SQL change. (AP-54)
  Known limitation: counts edges by reflected `referred_schema`; when no schema
  is explicitly selected, dialects that qualify same-schema FKs with the default
  schema name may over-report.

## [0.45.3] — 2026-06-28

### Fixed
- Connection form: the field rows are now cleanly aligned. The label column has
  a fixed width (long labels like „Server-Zertifikat vertrauen" wrap within the
  column instead of pushing their field rightward) and all inputs/selects share
  one width, so every field lines up across SQLite/PostgreSQL/MySQL/MSSQL/Oracle.
  CSS only. (AP-60)

## [0.45.2] — 2026-06-28

### Changed
- SQL-Builder layout: each clause section (Filter, Sortierung, Spalten, HAVING)
  is now a single „+ Label" button in the left column with its first row on the
  same line, instead of a separate „Label [+]" header row. The whole builder is
  one 2-column grid — every field column aligns with Start/Ziel. Saves a row per
  populated section. Markup/CSS only — IDs and generated SQL unchanged. (AP-59)

## [0.45.1] — 2026-06-28

### Fixed
- SQL-Builder: the HAVING clause rows now render like the other clause sections
  (Filter/Sortierung/Spalten) — same flex layout, same left indent, and a small
  square delete button instead of a ballooned 140px one. HAVING (v0.42.0)
  predated the AP-B section layout and had no matching CSS. CSS only — no
  behavior change. (AP-58)

## [0.45.0] — 2026-06-28

### Added
- SQL-Analyzer: a new „Optimierungs-Vorschläge" (optimization suggestions)
  section, separate from warnings, with four schema-free AST heuristics:
  redundant DISTINCT alongside GROUP BY, ORDER BY without LIMIT, OR in the
  top-level WHERE (can defeat index use), and a non-EXISTS subquery in WHERE
  (often better as a JOIN/EXISTS). Read-only, suggestions only — no query
  rewriting. (AP-F)

## [0.44.0] — 2026-06-28

### Added
- SQL-Builder: each ORDER BY row and each extra SELECT/column row now carries
  small ↑/↓ move buttons (no drag & drop) to reorder rows within their section.
  Because the form is read in DOM order, reordering changes the generated SQL:
  ORDER BY rows set the sort priority, column rows set the SELECT/GROUP BY
  order. The first row's ↑ and the last row's ↓ are disabled. Moving stays
  staged (no auto-rebuild) — click „Generieren" to apply. WHERE/HAVING rows are
  deliberately left without move buttons (their order is cosmetic). Markup/CSS
  + JS only — no route, no `core/` change. (AP-E)

### Fixed
- Schema-graph legend: the `1-N` chip is now left-aligned with the `N-1` chip
  (removed a stray `margin-left` that pushed it slightly right). CSS only.

## [0.43.4] — 2026-06-28

### Changed
- SQL-Builder: the per-step join-type dropdowns now sit inline in the active
  candidate-path row (next to the 1-N/N-1 direction chips), so the separate
  join-type row is gone. The fan-out explanation moved from the builder hint
  tile into the schema-graph legend (1-N vervielfacht Zeilen / N-1 sicher).
  Markup/CSS only — no behavior change.

## [0.43.3] — 2026-06-28

### Changed
- SQL-Builder layout: the clause builders are now four labeled sections
  (Filter, Sortierung, Spalten, HAVING), each with its own compact „+"
  add-button, and the output options (DISTINCT, LIMIT, Dialekt) plus the
  „Generieren" button moved into a separate bottom action bar. Markup/CSS
  only — no behavior change, all element IDs and the generated SQL are
  unchanged.

## [0.43.2] — 2026-06-28

### Changed
- Renamed the builder from „Join-Builder" to „SQL-Builder" across the UI
  (menu, tab, build button now „Generieren") and the current documentation.
  Internal identifiers were renamed in lockstep (`jb-`→`sb-`, `jb_`→`sb_`,
  `JB_`→`SB_`, `joinbuilder`→`sqlbuilder`). No behavior change; the
  `/api/joinpath` endpoint is unchanged.

## [0.43.1] — 2026-06-28

### Fixed
- GROUP BY is now derived from aggregates in HAVING and ORDER BY too, not only
  the SELECT list. Previously a non-aggregated SELECT column combined with an
  aggregate that lived solely in HAVING or ORDER BY produced GROUP-BY-less SQL
  that strict engines (e.g. PostgreSQL) reject. Backward-compatible: no
  aggregate anywhere still emits no GROUP BY; all-aggregated selects still emit
  none. Change in `core/sqlgen.py`.

## [0.43.0] — 2026-06-28

### Added
- COUNT(*) + COUNT(DISTINCT): two new aggregate options. COUNT(*) counts rows
  per group (column-ignored; the entry's table is still joined, so
  'COUNT(*) on table T + GROUP BY K' counts the joined T-rows per group).
  COUNT(DISTINCT col) counts distinct values. Both work across SELECT, HAVING,
  and ORDER BY. No route or core-module change (changes in `core/sqlgen.py`
  and `web/static/js/app.js`). Still open: Cross-Schema joins.

## [0.42.0] — 2026-06-28

### Added
- Aggregat-Operationen — HAVING + ORDER BY auf Aggregaten: ORDER BY may now
  sort by an aggregate (e.g. `ORDER BY COUNT(...) DESC`) and a new HAVING
  clause filters groups by an aggregate (scalar comparison `= != < > <= >=`,
  parametrised value). Clause order: WHERE → GROUP BY → HAVING → ORDER BY →
  LIMIT. The read-only run path executes HAVING. Aggregate is mandatory on a
  HAVING row. No new core module or endpoint (changes in `core/sqlgen.py`,
  `web/routes.py`, `web/static/js/app.js`). Still open: COUNT(*)/COUNT(DISTINCT),
  Cross-Schema joins.

## [0.41.0] — 2026-06-28

### Added
- Tier-3 GROUP BY / aggregate functions: each SELECT column may now carry an
  aggregate (COUNT/SUM/AVG/MIN/MAX); GROUP BY is auto-derived from the
  non-aggregated columns. The generated SQL gains a GROUP BY clause and the
  read-only run path executes grouped queries. Changes confined to
  `core/sqlgen.py`, `web/routes.py`, and `web/static/js/app.js`; no new
  core module or endpoint. Still open: HAVING, COUNT(*)/COUNT(DISTINCT),
  Cross-Schema joins.

## [0.40.0] — 2026-06-28

### Added
- Table and column comments (Tier-2): comments are now read during schema
  reflection and surfaced in the UI as hover tooltips (`title`) — in the
  detail-tab column list and on UML cards. The generated SQL is unchanged.
  No new core module and no new API endpoint; changes confined to
  `core/model.py`, `core/loaders/sqlalchemy_loader.py`, `web/routes.py`
  (`/api/schema`), and `web/static/js/app.js`.

## [0.39.0] — 2026-06-28

### Added
- Oracle database connections: connect to and reflect an Oracle database via
  python-oracledb (thin mode, no Instant Client), addressed by service name.
  System schemas are filtered from the schema picker. Optional skip-guarded
  live integration test (`LUCENT_ORACLE_TEST_URL`).

## [0.38.0] — 2026-06-28

### Added
- Multi-schema support: a schema picker lets you reflect and query any one
  database schema. The chosen schema is threaded through reflection and SQL
  generation, so the generated SQL is schema-qualified (`schema.table`) and
  runs regardless of the search path. New `/api/schemas` endpoint.

## [0.37.0] — 2026-06-27

### Added
- One-to-one detection now also recognizes uniqueness backed by a UNIQUE
  index (full-column, non-partial), not just UNIQUE constraints and primary
  keys — so a descending FK that is unique only through an index no longer
  raises a false fan-out warning. Partial and expression unique indexes are
  deliberately ignored.

## [0.36.0] — 2026-06-27

### Added
- One-to-one fan-out detection: a descending foreign key whose child columns
  carry a UNIQUE constraint (or are the primary key) is now classified as 1-1
  instead of 1-N, so the join-builder no longer raises a false fan-out warning
  for it.

## [0.35.0] — 2026-06-27
### Added
- Production WSGI server: the app now serves via **waitress** in normal
  operation; `--debug` keeps the Werkzeug dev server with auto-reload.

## [0.34.1] — 2026-06-27
### Added
- **AP-34 — Info-Dialog:** Das Tray-„Info" öffnet jetzt einen echten Dialog (eigener Prozess,
  `launcher/about.py`) mit **Ersteller, Art (read-only), Repo, URL/Port und vollem Stack**
  (Python/Flask/SQLAlchemy/NetworkX/sqlglot/Cytoscape/pystray/Pillow) sowie den Pro-Nutzer-Pfaden.
  Inhaltsbasierte Fenstergröße (keine Zeilenumbrüche), **Zentrierung auf dem primären Monitor**
  (Multi-Monitor-fest via xrandr auf Linux).
- **AP-34 — Linux-Tray-Menü:** mit dem AppIndicator/GTK-Backend (PyGObject) funktioniert das
  Kontextmenü (Öffnen/Info/Beenden) auch auf Linux. Optionale Deps in `requirements-tray-linux.txt`
  (Setup-Schritte auf der Betriebsseite); ohne sie Xorg-Fallback (Icon ohne Menü). Windows: nativ.
### Fixed
- **AP-34 — sauberes Beenden:** der Launcher räumt den `app.py`-Kindprozess bei **jedem** Ende
  (Menü „Beenden", Schließen, SIGTERM/SIGINT, normales Exit) ab → **keine verwaisten Prozesse**,
  Port wird frei. 232 Tests grün.

## [0.34.0] — 2026-06-27
### Added
- **AP-34 (Kern) — Tray-Icon-Launcher:** Ein-Klick-Start, ohne dass der Nutzer ein venv
  einrichtet. Eine Verknüpfung auf `run.ps1 -Action tray` (Linux: `run.sh --tray`) baut beim
  ersten Start das venv automatisch (bestehende adaptive Logik) und startet einen **fensterlosen**
  Python-Tray-Launcher (`launcher/`): Tray-Menü **Im Browser öffnen · Info · Beenden**,
  Auto-Browser beim Start (pollt bis der Server antwortet), „Beenden" stoppt den App-Prozess →
  Port frei. Neue Pakete `pystray`/`Pillow` (als Wheels gebündelt, NO-CDN). `launcher/core.py`
  ist stdlib-only und vollständig getestet; Tray-GUI auf Windows/Desktop zu verifizieren.
  *Offen:* Live-Log-Fenster, automatisches Ausrollen der Verknüpfung.

## [0.33.0] — 2026-06-27
### Added
- **AP-31 (Kern) — Multi-User-Basis:** Mehrere Nutzer können die App kollisionsfrei auf einer
  Maschine betreiben.
  - **Dynamische Port-Wahl pro Session:** ohne `LUCENT_PORT` erst 5057 (Hub-reserviert), sonst
    automatisch ein freier Port; `LUCENT_PORT=<n>` erzwingt fest, `=0` immer dynamisch. Die
    tatsächliche URL wird beim Start ausgegeben. Bind weiterhin nur `127.0.0.1`.
  - **Pro-Nutzer-Datenpfade:** `config.json` + Logs liegen im OS-Nutzerverzeichnis (Slug `luDBxP`;
    Linux `~/.config` bzw. `~/.local/state`, Windows `%LOCALAPPDATA%`). Overrides `LUCENT_CONFIG_DIR`/
    `LUCENT_LOG_DIR`. Eine vorhandene App-Verzeichnis-`config.json` wird einmalig übernommen.
  - Neues pures Stdlib-Modul `core/userpaths.py` (Pfade + `pick_port`/`resolve_port` + Migration).
  - `run.sh`/`run.ps1` brechen bei belegtem Port **nicht mehr ab** — `app.py` wählt selbst einen
    freien Port. 220 Tests grün (1 skipped).
  - *Offen (Rest von AP-31):* lokaler WSGI-Server (waitress), Idle-Shutdown/Stop, Deployment-Packaging.

## [0.32.1] — 2026-06-27
### Changed
- **AP-45 Feinschliff — Filter sofort wirksam:** Wird ein Filterwert gesetzt (getippt oder aus dem
  DISTINCT-Dropdown gewählt), ein wertloser Operator (`IS NULL`/`IS NOT NULL`) gewählt oder eine
  Filterzeile entfernt, baut der Join-Builder **sofort neu** — die `WHERE`-Bedingung erscheint
  umgehend im SQL und im Ergebnis (vorher erst nach „Aktualisieren").
### Fixed
- **DISTINCT-Dropdown zeigte gelegentlich die falsche Spalte:** Beim Vorbelegen einer Filterzeile
  (z. B. via „Als Filter") wurde kurzzeitig auch die Default-Spalte geladen; bei ungünstigem
  Timing füllte deren Antwort die Vorschlagsliste. `_loadFilterDistinct` verwirft jetzt veraltete
  Antworten (Race-Guard) — es gewinnt immer die aktuell gewählte Spalte.
### Docs
- Referenz **Oberfläche/Architektur**: die **zwei „DISTINCT"** klar abgegrenzt — die `DISTINCT`-Checkbox
  fließt als `SELECT DISTINCT` ins generierte SQL, das **Filter-Wertdropdown** (`/api/distinct`) ist
  dagegen ein **separater Lookup** auf eine Spalte und erscheint **nicht** im Join-SQL.

## [0.32.0] — 2026-06-27
### Added
- **AP-45 — Ergebnis-Hilfen Teil 2: Spaltenkopf-Aktionen + DISTINCT-Filterwerte:**
  - **Klickbare Spaltenköpfe** in der Ergebnistabelle: ein Klick auf eine Spalte öffnet ein
    Menü mit **Sortieren ASC/DESC**, **Als Filter…** und **Spalte entfernen**. Sortieren legt
    eine ORDER-BY-Zeile an und baut neu; „Als Filter" füllt eine Filterzeile vor und fokussiert
    das Wertfeld; „Spalte entfernen" wirkt auf Zusatzspalten — **Start-/Ziel-Spalten** definieren
    den Join-Pfad und sind geschützt (Menüeintrag deaktiviert).
  - **Filter-Wertfeld mit echten Werten:** jedes Wertfeld ist mit einer `<datalist>` der echten
    **DISTINCT-Werte** der Spalte hinterlegt (Auswahl per Dropdown, Freitext bleibt möglich).
    Neues read-only Endpoint **`/api/distinct`** (`SELECT DISTINCT … ORDER BY …`, auf
    `config.DISTINCT_LIMIT` begrenzt, spalten-validiert, best-effort wie `/api/orphan_check`).
  - **`/api/joinpath/run`** liefert zusätzlich **`columns_meta`** (Tabelle/Spalte je Ausgabespalte
    in Selektionsreihenfolge) → jeder Spaltenkopf lässt sich eindeutig seiner Quellspalte zuordnen,
    auch wenn zwei verbundene Tabellen denselben Spaltennamen haben. 205 Tests grün, 1 skipped.

## [0.31.0] — 2026-06-27
### Fixed
- **Parse error showed ANSI garbage:** sqlglot underlines the bad token with ANSI colour codes,
  which rendered as `□[4m…□[0m` in the browser. These are now **stripped** — the message is clean
  text. New layout: a "could not parse" label, then the message (starting "Invalid expression …")
  with its multi-line SQL excerpt in a red box (that excerpt was the "offset" piece).
### Changed
- **AP-49 — Analyzer polish:** the input textbox is **larger** by default (~17 rem); the
  **read-only** note now sits as a green **badge** set off from "Analysieren". 200 tests green, 1 skipped.

## [0.30.0] — 2026-06-27
### Changed
- **AP-48 — SQL Analyzer: larger input + typo lint:**
  - the input textbox is **larger** (full width, ~14 rows) and only **vertically** resizable
    (not in width, `resize: vertical`).
  - new lint **`SUSPICIOUS_ALIAS`**: a mistyped join type like `LEFTI` is valid SQL to sqlglot
    (a table **alias**), so it is not a parse error. The heuristic now flags aliases that closely
    resemble a join keyword (LEFT/RIGHT/INNER/OUTER/FULL/CROSS) as a likely typo. *Note:* sqlglot
    remains a lenient parser — real syntax errors (e.g. a missing `"`) are caught, but not every
    typo is a syntax error. 199 tests green, 1 skipped.

## [0.29.1] — 2026-06-27
### Fixed
- **Orphan chip was a false positive:** the probe tested each join **in isolation** and flagged
  orphans that never appear in the path context (unreachable from the FROM table, or filtered out
  by downstream INNER joins) — so the chip promised a change that switching to LEFT didn't deliver.
  `/api/orphan_check` now **counts the real result** (COUNT per join type vs INNER, other steps at
  their current types) and only flags types that actually change the row count. Chip and table now agree.

## [0.29.0] — 2026-06-27
### Added
- **AP-47 — Visible path selection + orphan hint on join type:**
  - the path list uses **`[*]` (active) / `[ ]`** instead of bullets — the chosen alternative
    path is unambiguous (active path also emphasised).
  - each join step shows a **data-driven orphan chip** (e.g. `⚠ LEFT/FULL`) indicating which
    join types would **actually** reveal unmatched (orphan) rows here. New read-only endpoint
    `/api/orphan_check` probes each step left/right via `NOT EXISTS`; the affected dropdown
    options are also tinted amber (where the browser renders native `<option>` colours).
    197 tests green, 1 skipped.

## [0.28.1] — 2026-06-27
### Fixed
- **Graph stays centered when the detail cards expand:** when the detail area (start/target
  cards) appears below, the graph slides up and is **centered** in its smaller area at the
  **same zoom** (`CY.center()` instead of refitting), without overflowing into the cards.
  When the area hides, it re-centers in the full panel.

## [0.28.0] — 2026-06-27
### Changed
- **AP-46 — Detail cards follow the join-builder selection:** while **nothing is selected**,
  the schema graph stays **centered** (the detail area below is hidden). Once start/target are
  set — **even via the dropdowns instead of clicking the graph** — the graph moves up and the
  **table detail cards** for start and target appear below it (with the chosen columns marked),
  just like double-clicking a node. "Reset selection" hides the area again. 195 tests green, 1 skipped.

## [0.27.0] — 2026-06-27
### Changed
- **AP-44 — Join-builder more compact + result helpers:** the top area is tightened — the two
  button rows are now **one** row, the 1-N hint sits as a **small tile top-right** (no longer a
  full row), tighter spacing + a more compact SQL box → **more room for the result table**.
- **Result helpers:** **NULL cells** (outer-join / orphan rows) are highlighted; the status line
  now shows **rows · join type · fan-out** (e.g. "8 Zeilen · LEFT · ⚠ 1-N"). 195 tests green, 1 skipped.

## [0.26.0] — 2026-06-27
### Changed
- **AP-43 — Readable SQL layout:** generated SQL is now **multi-line formatted** — one column
  per line, each `JOIN` on its own line with `ON`/`AND` beneath it and **aligned `=`** for
  composite keys. Lines stay short (no horizontal scroll / wrap worries) and a pasted statement
  is clean. The **copy/display** variant ends with `;` (paste-and-run); the internally executed
  parameterised SQL does not. 195 tests green, 1 skipped.

## [0.25.0] — 2026-06-27
### Changed
- **AP-42 — Join-builder polish:** the verbose per-branch fan-out warning text ("branch X is
  1-N (descending) — may multiply rows") is **gone** — direction already shows as an **N-1/1-N
  chip** on each join. Instead, one compact tile under the path list: "**1-N** may multiply rows
  (fan-out)", only when a path has a 1-N step. Saves noticeable space.
- **SQL box now wraps** instead of scrolling horizontally (`white-space: pre-wrap`). The wrap is
  purely **visual** — copy/paste yields the statement with its real line breaks, so it stays runnable.

## [0.24.2] — 2026-06-27
### Changed
- **Target node now amber/gold** instead of red: red was still too close to the orange path
  fill. Target = **amber (#f3b305) with dark text**, clearly distinct from start (green) and
  path (orange). Legend adjusted (so "target" is now also clearly different from "Analyzer:
  written"/red).

## [0.24.1] — 2026-06-27
### Fixed
- **Target hard to read in the graph:** the red target **ring** blended into the orange path
  fill. Endpoints are now **fully coloured** — start green, target red, intermediate orange —
  so they stand out clearly. Legend adjusted to filled squares.

## [0.24.0] — 2026-06-27
### Added
- **AP-41 — Per-step join type:** the join-builder now lets you pick the type **per join
  station** — **INNER** (default), **LEFT**, **RIGHT**, **FULL**. One dropdown per step above
  the SQL output; changing one rebuilds SQL **and** result. So e.g. start rows without a match
  are no longer dropped (LEFT instead of INNER). `sqlgen`/`/api/joinpath` + `/api/joinpath/run`
  accept `join_types` (positional; read-only execution stays parameterised). The **SQL Analyzer**
  already detected outer joins correctly (LEFT/RIGHT/FULL/CROSS).
### Fixed
- **Graph markers didn't match the legend:** building via the dropdowns left start/target
  uncoloured (all nodes the same). The graph now marks **start green / target red** (rings)
  even without click-selection — matching the legend. 194 tests green, 1 skipped.

## [0.23.0] — 2026-06-27
### Added
- **AP-40 — Graph legend** (small, top-left of the schema graph): explains the highlights —
  blue = Analyzer (read/joins), red = Analyzer (written), orange = join path, N-1/1-N = join
  direction, green/red ring = start/target.
### Fixed
- **Overlapping graph markers:** the join-builder path and the analyzer markers are now
  **mutually exclusive** — the blue analyzer trace disappears as soon as a join path is built
  (and vice versa). Previously blue nodes/edges lingered next to the orange path. Verified via
  Playwright. 190 tests green, 1 skipped.

## [0.22.0] — 2026-06-27
### Added
- **AP-39 — SQL Analyzer: structure/clause analysis, graph drawing, lints, complexity:**
  the analyzer now reads the sqlglot AST far more deeply (beyond type + read/written tables).
  New in the panel: **columns**, **joins** (type + ON), **filters (WHERE)**, **GROUP BY/HAVING**,
  **ORDER BY**, **DISTINCT/LIMIT**, a **structure counter** (tables/joins/subqueries/CTEs/UNION/
  window/aggregate/CASE) and a weighted **complexity score** (grade A–E). The **schema graph now
  draws the statement's JOIN edges** (not only colours the nodes). Extra schema-free static lints:
  `SELECT_STAR`, `LEADING_WILDCARD` (LIKE '%…'), `FUNC_ON_COLUMN`. Still **read-only — never executed**.
  `/api/analyze` returns the new fields. 190 tests green, 1 skipped.

## [0.21.0] — 2026-06-27
### Added
- **AP-38 — Copyable, runnable SQL (values inlined):** the SQL display and copy icon now
  produce **directly runnable** SQL — filter values are inlined as literals (numbers bare,
  strings single-quoted with `''` escaping; leading zeros and LIKE operands stay strings).
  A SELECT pasted into an external SQL editor runs as-is, without filling in `:p0` bind
  variables. The **parameterised** form (`:p0` + `params`) stays the internal read-only
  **execution** path (injection-safe); `/api/joinpath` returns both as `sql` and `sql_inline`.
  180 tests green, 1 skipped.

## [0.20.0] — 2026-06-27
### Added
- **AP-37 — Swap start ⇄ target:** new **⇄ button** next to the target dropdowns swaps
  start and target (table + column), mirrors the graph markers, and rebuilds immediately
  if a path was already shown. Handy because the **warning-free direction is often the
  reverse** (ascending toward a parent never fans out).
- **Docs:** fan-out page extended with **Example 3** (reading a long path → shorten the
  chain *or* filter the "many"-side table; rule of thumb + ⇄ hint).

## [0.19.0] — 2026-06-27
### Added
- **AP-36 — Per-join fan-out direction made visible:** every join step of a path now
  carries a **direction chip** — green `N-1` (ascending, safe) or amber `1-N`
  (descending, can multiply rows) — both in the **path list** and as a **label on the
  highlighted edge** in the schema graph. Makes it obvious that a path is a *mix* of
  N-1 and 1-N steps rather than "all descending". `/api/joinpath` now returns a per-path
  `steps` field (`left`/`right`/`to_many`) for this; the existing `.path-warn` box stays.
  172 tests green, 1 skipped.
- **Docs:** new reference page **Fan-out warning (1-N)** with worked examples, including a
  section explaining why both join directions warn while one step is still N-1.

## [0.18.0] — 2026-06-27
### Added
- **AP-25 — Read-only SQL-Statement-Analyzer:** New **SQL Analyzer** tab lets users
  paste any SQL statement; it is parsed by **sqlglot** (bundled locally, no CDN) and
  **never executed** against any database. Shows statement type (SELECT/INSERT/UPDATE/
  DELETE/DDL), read and written tables, and structural/schema warnings:
  `WRITE_STATEMENT`, `NO_WHERE` (UPDATE/DELETE without WHERE), `CARTESIAN_JOIN`
  (multi-table FROM without JOIN condition); with an active connection also
  `UNKNOWN_TABLE` and `UNKNOWN_COLUMN` (case-insensitive, schema-aware).
  Involved tables are highlighted in the schema graph (`analyze-read` / `analyze-write`
  CSS classes). Works with and without a database connection. 165 Tests grün, 1 skipped.

## [0.17.0] — 2026-06-27
### Added
- **AP-30 — N-1-Stern (Auto-Weaving, Fan-out-Warnung):** Select-/ORDER-BY-/Filter-
  Tabellen werden automatisch in den Join-Baum gewebt — stilles Verwerfen entfällt.
  Fehlende Tabellen (unerreichbar im FK-Graphen) lösen einen `NoPathError` aus.
  Absteigende (1-N) Join-Äste erzeugen eine **nicht-blockierende Fan-out-Warnung**
  pro Pfad (`warnings`-Feld in `/api/joinpath`); das Frontend zeigt diese als
  `.path-warn`-Box direkt am betroffenen Pfad an. 144 Tests grün, 1 skipped.

## [0.16.0] — 2026-06-27
### Added
- **AP-12 (Abschluss) — MSSQL-Verschlüsselungsfelder in der UI:** Im Verbindungs-Tab
  gibt es für **MS SQL Server** jetzt zwei Tri-State-Dropdowns **Verschlüsselung**
  (`Encrypt`) und **Server-Zertifikat vertrauen** (`TrustServerCertificate`), je
  **Standard / ja / nein**. „Standard" lässt den Parameter weg (nichts Unsicheres
  wird angenommen). Die Werte werden mit gespeicherten Verbindungen persistiert
  (`_CONN_FIELDS`, kein Secret) und beim Laden wiederhergestellt.
- **AP-12 real verifiziert:** Optionaler, skip-guardeter Integrationstest
  (`tests/test_mssql_integration.py`) gegen **SQL Server 2022** — provisioniert
  ein Schema mit FK und prüft die Reflection. Treiber `msodbcsql18` (ODBC Driver 18)
  + Instanz lokal eingerichtet; End-to-End im Browser bestätigt (ohne „vertrauen"
  scheitert die Verbindung am selbst-signierten Zertifikat, mit „ja" verbindet sie).

## [0.15.0] — 2026-06-26
### Added
- **AP-29 — SQL-Dialekt umschalten:** Der Join-Builder hat ein **Dialekt-Dropdown**
  (SQLite · PostgreSQL · MySQL · MSSQL · Oracle); das generierte read-only SELECT
  wird dialekt-treu gerendert:
  - **Identifier-Quoting** je Dialekt: `"x"` (SQLite/PG/Oracle), `` `x` `` (MySQL),
    `[x]` (MSSQL) — mit korrektem Escaping (schließendes Zeichen verdoppelt).
  - **Zeilenlimit** je Dialekt: `LIMIT n` (SQLite/PG/MySQL), `SELECT TOP n …`
    (MSSQL), `FETCH FIRST n ROWS ONLY` (Oracle).
  - Default-Dialekt aus der aktiven Verbindung abgeleitet; bei Änderung wird das
    SQL neu gerendert.
  - **Anzeige vs. Ausführung getrennt:** Das angezeigte SQL nutzt den gewählten
    Dialekt (zum Kopieren), die **Ausführung** (`/api/joinpath/run`) nutzt den
    Dialekt der *echten* Verbindung — generiertes SQL läuft also immer.
  - Umgesetzt als kleine `Dialect`-Schicht in `core/sqlgen.py` (keine neue
    Abhängigkeit); test-first, 12 neue Tests; **137 Tests grün**.
### Changed
- **Identifier werden jetzt immer quotiert** (auch im SQLite-Default): aus
  `SELECT VirtualMachine.VMID` wird `SELECT "VirtualMachine"."VMID"`. Korrekt und
  reserved-word-/case-sicher; Ausführung gegen SQLite unverändert gültig.

## [0.14.0] — 2026-06-26
### Changed
- **AP-14 (Teil 2, Linux) — Python-3.14-AppImage:** Der Linux-Pfad von AP-14 ist
  abgeschlossen — venv und AppImage laufen jetzt gegen **Python 3.14.6**:
  - **3.14 user-lokal** via `uv` beschafft (kein Root); alle 5 C-Extensions
    (sqlalchemy, greenlet, markupsafe, psycopg2-binary, pyodbc) liegen als
    **cp314-manylinux**-Wheels auf PyPI vor → venv-Neubau rein aus Wheels,
    **125 Tests grün** auf 3.14.
  - **AppImage gegen 3.14 gebaut & verifiziert** (HTTP 200; bundelt 3.14.6
    standalone, direkt geprüft).
- **AppImage-Fixes (`run.sh` AppRun):**
  - **Versions-bewusstes App-Update:** Der AppRun kopierte den App-Code bisher
    nur beim Erststart und aktualisierte nie → eine neuere AppImage führte stillen
    Alt-Code aus (real beobachtet: 0.1.0 statt der gebauten Version). Jetzt wird
    der Code bei Versionswechsel erneuert, **Nutzerdaten** (`config.json`, `Logs/`)
    bleiben erhalten (`.app_version`-Stamp).
  - **Browser:** AppRun öffnet bevorzugt **Chrome/Chromium** statt des
    Default-Browsers (vorher `xdg-open` → ggf. Firefox).
### Fixed
- **`run.sh` unter Python 3.14:** `re.split(..., 1)` löste einen
  `DeprecationWarning` aus (positionsbasiertes `maxsplit`) → auf `maxsplit=1`
  umgestellt.

## [0.13.0] — 2026-06-26
### Changed
- **AP-33 — Logging sauber gemacht:** `core/log.py` heilt das bisher minimale
  Logging (fix INFO, unbegrenzte Datei) zu einem konfigurierbaren, rotierenden
  Setup:
  - **Rotation:** `RotatingFileHandler` (`config.LOG_MAX_BYTES` ≈ 1 MB,
    `config.LOG_BACKUP_COUNT` = 5) statt unbegrenzt wachsender `app.log`.
  - **Level konfigurierbar:** `LUCENT_LOG_LEVEL` (DEBUG/INFO/…); `LUCENT_DEBUG`
    impliziert DEBUG; sonst `config.LOG_LEVEL` (INFO).
  - **Logpfad konfigurierbar:** `LUCENT_LOG_DIR` überschreibt `config.LOG_DIR` —
    der Hook für einen **Pro-Nutzer-Logpfad** (volle Terminal-Server-Verdrahtung
    bleibt AP-31).
  - **Idempotent + reconfigurierbar:** Handler werden bei jedem `init_logging`
    sauber ersetzt (keine Duplikate); Startup-Zeile mit App/Version/Level/Pfad.
  - **Request-Logging:** `web/`-App-Factory loggt jede Anfrage (Methode · Pfad ·
    Status · Dauer) via `after_request` — deutlich höhere Abdeckung. Layering
    gewahrt: `core/log.py` bleibt Flask-frei, der Hook liegt in `web/`.
  - 125 Tests grün (7 neue in `tests/test_log.py`, test-first).

## [0.12.0] — 2026-06-26
### Changed
- **AP-15 (Teil 2, Linux) — `run.sh` abbruchsicher + idempotent (Parität zu
  `run.ps1`):** Der Linux-Launcher heilt sich nach abgebrochenen Läufen selbst.
  Jeder Schritt prüft seine Vorbedingungen und meldet seinen Status
  (`_ok`/`_warn`/`_info`/`_hdr`/`_fail`):
  - **venv-Integrität statt nur Existenz** (`venv_healthy`: `python -c import sys`);
    ein halbes/kaputtes venv wird automatisch neu gebaut.
  - **Echter Paket-Vollständigkeits-Check:** `pip check` **plus** Vorhandensein
    jeder in `requirements.txt` gelisteten Distribution (`importlib.metadata`) —
    fängt sowohl abgebrochene Installs als auch ein frisch gebautes, leeres venv.
  - **Atomarer Stamp:** `.req_stamp` wird erst **nach** erfolgreichem Install
    geschrieben; ein abgebrochener Install wiederholt sich beim nächsten Lauf.
  - **Port-/Instanz-Check** vor App-Start (5057 belegt via `ss`/`lsof` → klare
    Abbruch-Meldung statt Crash).
  - **Robustes Menü:** ein fehlgeschlagener Schritt beendet das Menü nicht mehr
    (Subshell-Isolierung, bash-Pendant zum try/catch).
  - **Exit-Codes nicht mehr verschluckt:** das `|| true` in `do_start`/
    `do_skip_setup` entfernt; der App-Exit-Code wird sauber durchgereicht.
  - **`--debug`-Flag** (Pendant zu `run.ps1 -DebugMode`, setzt `LUCENT_DEBUG=1`).
- **AP-15 / NO-CDN auf Linux (adaptiv):** Installation versucht zuerst **strikt
  offline** aus `wheels/` (`--no-index`-Dry-Run-Probe, kein Netz). Deckt das
  Wheelhouse die Plattform ab → Offline-Install; sonst — z. B. die gebundelten
  `win_amd64`/cp314-Wheels auf Linux — **lauter** Fallback auf Online-pip (kein
  stilles Nachladen). Schaltet automatisch auf offline, sobald ein passendes
  Linux-Wheelhouse vorliegt.

### Fixed
- **Leeres venv galt fälschlich als „vollständig":** `pip check` allein ist auf
  einem frisch gebauten, paketleeren venv vacuously grün — in Kombination mit
  einem noch passenden `.req_stamp` wäre der Install übersprungen worden (App
  hätte beim Import gecrasht). Der Vollständigkeits-Check prüft jetzt zusätzlich
  das tatsächliche Vorhandensein der Requirements. **Hinweis:** dieselbe latente
  Schwäche steckt in `run.ps1` (Windows) — dort zur Behebung vorgemerkt (Skript
  ist signiert, separate Session).

## [0.10.0] — 2026-06-26
### Added
- **AP-20 — Copy-Icon am SELECT:** In der oberen rechten Ecke des generierten
  SELECT sitzt ein Copy-Icon; ein Klick kopiert das SQL in die Zwischenablage
  (`navigator.clipboard`) mit kurzem „kopiert"-Feedback.

### Fixed
- **AP-21 — Kosmetik:** Der „Schema-Graph"-Balken (`.panelhead`) und die Tab-Linie
  (`.tabbar`) haben jetzt exakt dieselbe Höhe (gemeinsame `min-height` +
  `box-sizing`), vorher war der Graph-Balken minimal höher.

## [0.9.0] — 2026-06-26
### Changed
- **AP-12 (Backend) — MS SQL Server: ODBC-Treiber & Verschlüsselung
  konfigurierbar, klare Treiber-Fehlermeldung:** `build_url` nutzt jetzt
  standardmäßig den aktuellen **ODBC Driver 18 for SQL Server** (überschreibbar
  per `driver`) und unterstützt optionale `Encrypt`/`TrustServerCertificate`-
  Parameter — nichts Unsicheres wird per Default angenommen. Fehlt der ODBC-
  Treiber, meldet die App das klar (AP-2-Stil) statt einer rohen pyodbc-Exception
  (`_odbc_driver_hint`: IM002 / „no default driver" / „Can't open lib"). Installations-
  Doku ergänzt. 118 Tests grün. (Realer Integrationstest gegen eine MSSQL-Instanz
  und UI-Felder für Encrypt/Trust folgen separat.)

## [0.8.0] — 2026-06-26
### Changed
- **AP-15 (Teil 1, Windows) — `run.ps1` abbruchsicher + idempotent:** Der
  Windows-Launcher heilt sich nach abgebrochenen Läufen selbst. Jeder Schritt
  prüft seine Vorbedingungen (Python, venv-Integrität per Funktionstest,
  Paket-Vollständigkeit per `pip check`, freier Port) und zieht nur Fehlendes
  nach; der Requirements-Stamp wird erst nach erfolgreichem Install geschrieben
  (atomar). **NO-CDN / nur lokale Sourcen:** Installation strikt `--no-index`
  aus `wheels\` mit `--dry-run`-Vorabprüfung — fehlt ein Wheel, steigt das Setup
  mit Protokoll (welche Pakete fehlen) aus, **ohne etwas zu installieren oder
  online nachzuladen**. Neu außerdem: durchgängige Status-Ausgaben, Port-Check
  vor App-Start (5057 belegt → klare Meldung) und ein gegen Einzelfehler robustes
  Menü. Verifiziert: idempotenter Lauf, fehlender Stamp, fehlendes Wheel, belegter
  Port. (`run.sh`/Linux-Parität folgt separat.)

## [0.7.0] — 2026-06-26
### Added
- **AP-13 — UI-Politur:** Drei Verbesserungen in Objekt-Browser und Graph-Panel:
  (1) **Suchfeld** über dem Objekt-Browser filtert die Tabellen-/View-Listen live
  nach Namen; (2) **linker Splitter** macht die Sidebar-Breite per Drag verschiebbar
  (analog zum Graph-Splitter, via `--sidebar-width`); (3) **„Neu anordnen"-Button**
  im Graph-Panel würfelt das cose-Layout neu, dessen Abstände jetzt für dichte
  Schemas (> 12 Knoten) hochskalieren, damit Knoten weniger überlappen. Reines
  Frontend (`index.html`/`app.js`/`app.css`). Im Browser verifiziert (Playwright);
  115 Tests grün.

## [0.6.0] — 2026-06-26
### Added
- **AP-10 — Gespeicherte Verbindungen in der Topbar:** Neues Dropdown in der
  Topbar (neben „Verbinden") listet die in `config.json` gespeicherten
  Verbindungen; eine Auswahl verbindet sofort — passwortlose Verbindungen
  (SQLite oder Server ohne Auth) direkt, sonst öffnet sich der Verbindungs-Tab
  vorbefüllt zum Ergänzen des Passworts. Beide Verbindungs-Picker (Topbar +
  Verbindungs-Tab) teilen dieselbe Liste und spiegeln die Auswahl. Ein
  Verbindungswechsel setzt den UI-Zustand zurück (Detail-Tabs schließen,
  Graph-Highlight/UML-Karten leeren, Schema neu laden). Reines Frontend
  (`index.html`/`app.js`/`app.css`); die `/api/connections`-API blieb unverändert.
  Im Browser verifiziert (Playwright/Chromium); 114 Tests grün.

## [0.5.0] — 2026-06-26
### Changed
- **AP-11 — Composite Foreign Keys voll unterstützt:** Mehrspaltige FKs werden
  nicht mehr nur auf dem ersten Spaltenpaar gejoint. Ein FK trägt jetzt alle
  `(lokal, referenziert)`-Spaltenpaare (`ForeignKey.column_pairs`, mit Properties
  `columns`/`ref_columns`/`is_composite`); der Join-Pfad-Generator emittiert
  `JOIN … ON a.x = b.x AND a.y = b.y`. Zwei **separate** einspaltige FKs zwischen
  denselben Tabellen bleiben weiterhin alternative Join-Wege (nicht mit AND
  verschmolzen). Betroffen: Loader, FK-Graph (`JoinEdge`), Pathfinder
  (`JoinStep.column_pairs`), SQL-Generator, DDL-Ansicht und `/api/schema`
  (FKs jetzt als `columns`/`ref_columns`-Listen, Frontend angepasst). 112 Tests grün.

## [0.4.0] — 2026-06-26
### Changed
- **AP-14 — Python-3.14-Readiness (Windows):** Das Offline-Wheelhouse (`wheels/`)
  wurde von der CPython-3.12- auf die **3.14-ABI** umgestellt. Die fünf
  kompilierten Wheels (SQLAlchemy, psycopg2-binary, pyodbc, greenlet, MarkupSafe)
  liegen jetzt als `cp314-win_amd64` vor — identische Paketversionen, nur neuer
  ABI-Tag; die `py3-none-any`-Wheels bleiben versionsunabhängig. Die Launcher
  `run.ps1` (Offline-Gate) und `run.sh` (Präferenzreihenfolge) verlangen bzw.
  bevorzugen jetzt Python 3.14; `wheels/README.md` entsprechend aktualisiert.
  Verifiziert: venv mit Python 3.14.6, Offline-Setup aus `wheels/`, `pip check`
  sauber, alle **111 Tests grün**, App startet (HTTP 200).

## [0.3.1] — 2026-06-26
### Changed
- **AP-9 — Ergebnisliste maximiert:** Die Ergebnistabelle unter dem Join-Builder
  nutzt jetzt den vollen vertikalen Restplatz nach unten (fixe `max-height: 320px`
  entfernt). Das Join-Builder-Panel ist eine Flex-Spalte; `#join_result` wächst
  mit (`flex: 1`, eigener Scroll). Auf das Join-Builder-Panel beschränkt, sodass
  Detail-Tabs ihren normalen Fluss behalten.

## [0.3.0] — 2026-06-26
### Added
- **AP-6 — Ausgabe-Steuerung im Join-Builder:** Auswahl der Ausgabezeilen
  (200 / 400 / Alle) plus „Aktualisieren"-Button im Ergebnisbereich.
  `/api/joinpath/run` akzeptiert nun `max_rows`; der Wert wird serverseitig
  auf `config.MAX_RESULT_ROWS` (5000) geklemmt — „Alle" heißt „alle bis zur
  Obergrenze" zum Schutz der Oberfläche. Die Antwort liefert `row_cap`; die
  Info-Zeile zeigt „N Zeilen (begrenzt auf …)". „Aktualisieren" liest das
  Formular neu (geänderte Sortierungen/Spalten) und behält den gewählten Pfad;
  ein Zeilenwechsel führt nur das aktuelle SELECT neu aus. Der hervorgehobene
  Join-Pfad im Graphen bleibt dabei stabil — Sortierungen/Zusatzspalten sind
  auf die Pfad-Tabellen beschränkt und ändern den Pfad nicht.
- **AP-7 — Feiner Graph-Zoom + Slider:** Mausrad-Zoom feinstufig
  (`wheelSensitivity` 0.2 statt 1, Zoom-Grenzen 10 %–400 %). Neuer vertikaler
  Zoom-Slider mit Prozent-Anzeige am rechten Graph-Rand, beidseitig
  synchronisiert (Scrollen ↔ Slider).

### Fixed
- **AP-8 — „Auswahl zurücksetzen":** Der Button bereinigt jetzt zusätzlich den
  hervorgehobenen Join-Pfad im Graphen (`hl`-Klassen) und schließt die
  UML-Karten darunter (`#uml_cards`) — vorher blieb beides stehen. Die interne
  Auswahl-Zurücksetzung (neue Selektion starten) lässt die Karten bewusst
  bestehen.

## [0.2.0] — 2026-06-26
### Added
- Join-Builder: tabellarischer **Ausgabebereich** unter dem generierten SELECT.
  Beim Wählen eines Join-Pfads wird das SQL angezeigt **und** ausgeführt; die
  zurückgelieferten Zeilen erscheinen als Tabelle (`#join_result`). Neuer
  read-only Endpoint `POST /api/joinpath/run`: das SELECT wird **serverseitig**
  aus den (validierten) Join-Parametern erzeugt (kein client-geliefertes SQL),
  parametrisiert ausgeführt und auf max. 200 Zeilen begrenzt
  (`core.datapreview.execute_select`). DRY-Refaktorierung der gemeinsamen
  Pfad-/SQL-Bau-Logik (`_parse_joinpath_params`, `_make_path_gen`).

## [0.1.0] — 2026-06-25
### Added
- FK-Graph aus Live-DB-Reflection (SQLAlchemy, SQLite + Postgres).
- Join-Pfad-Builder (k-kürzeste Pfade, deterministischer Tie-Break).
- Filterobjekte (WHERE über erreichbare Tabellen).
- Read-only SQL-Generierung mit parametrisierten Platzhaltern.
- Flask-Web-UI mit lokal gebundelten Assets.
- Portable Demo-CMDB (`sample_data/`): SQLite-DB + reproduzierbarer Generator,
  deckt mehrdeutige Pfade (Diamant), zusammengesetzte FKs, Graph-Sonderfälle
  (Selbstreferenz, Mehrfach-FK, isolierte Tabelle) und realistische Daten ab;
  inkl. Integrationstests pro Fall.
- Interaktives Menü in `run.sh` (ohne Argument) plus `run.ps1` für Windows mit
  identischem Menü; Flags (`--skip-setup` etc.) bleiben Hub-kompatibel.
- Filter-UI: „Filter +" fügt Filterzeilen hinzu (Tabelle · Spalte · Operator ·
  Wert · Entfernen); mehrere Filter werden mit UND verknüpft und an die
  bestehende, getestete Backend-Filterlogik (parametrisiertes WHERE) gesendet.
- Graph-Visualisierung: neuer `/api/graph`-Endpoint (Knoten/Kanten) und eine
  interaktive Schema-Graph-Ansicht mit Cytoscape.js (lokal gebundelt, keine
  CDN). Der gewählte Join-Pfad wird im Graph farblich hervorgehoben; die
  joinpath-Antwort liefert dazu die konkreten Pfad-Kanten.
- Implizite (geratene) Foreign Keys: optionale Heuristik (Spaltenname trifft
  einspaltige Primärschlüssel-Spalte einer anderen Tabelle, kompatibler Typ).
  Per Checkbox einschaltbar; gefundene Beziehungen erscheinen im Graph
  gestrichelt und ermöglichen Join-Pfade auch ohne deklarierte FKs. Loader/
  Modell führen jetzt Primärschlüssel-Infos. Neue FK-lose Demo-DB
  (`demo_cmdb_nofk.db`) zum Ausprobieren.

### Added
- Verbindungs-Manager (Tools → Verbindungen): strukturiertes Formular mit
  Datenbank-Typ-Auswahl (SQLite, PostgreSQL, MySQL/MariaDB, MS SQL Server) und
  passenden Feldern (Host/Port/DB/Benutzer/Passwort bzw. Dateipfad). Das
  Backend baut die SQLAlchemy-URL (`core.connection.build_url`) und testet die
  Verbindung (`/api/connect`). Passwort-Feld versteckt; die echte URL liegt in
  einem versteckten Feld, die Topbar zeigt sie maskiert. Benannte Verbindungen
  sind in `config.json` speicherbar (`/api/connections`, ohne Passwort).
  Treiber: psycopg2-binary, PyMySQL, pyodbc (MSSQL braucht zusätzlich System-
  ODBC: unixODBC + msodbcsql).

### Changed
- Info-Bereich in der Sidebar ans untere Ende gesetzt; die Info-Seite zeigt
  jetzt App-Metadaten (Name, Version, Ersteller) und den Technologie-Stack
  mit Versionen (Python/Flask/SQLAlchemy/NetworkX/Cytoscape.js) über den neuen
  `GET /api/info`-Endpoint, plus die Verbindungs-Übersicht.
- Layout-Feinschliff: senkrechte Trennlinie zwischen Hauptbereich und Graph
  ist per Drag verschiebbar; der Graph-Bereich ist standardmäßig 1/3 der
  Breite (Cytoscape skaliert beim Ziehen mit). Sidebar bekommt Kategorien
  „Tools" (Join-Builder) und „Info" (Übersicht: URL, Anzahl Tabellen/Views/FKs).
- Detail-Tabs haben jetzt Unter-Tabs „Definition" (Struktur), „Daten"
  (read-only Vorschau der ersten 100 Zeilen über den neuen `/api/data`-
  Endpoint) und „SQL" (rekonstruiertes CREATE-DDL bzw. View-Definition).
  Hinweis: Die Datenvorschau führt erstmals eine Abfrage aus — strikt
  read-only (`SELECT … LIMIT`), Objektname gegen das Schema validiert.
- UI-Redesign zum 3-Panel-Layout (wie ein minimalistischer SQL Developer):
  Objekt-Browser links (Tabellen + Views), Tab-Bereich in der Mitte mit festem
  „Join-Builder"-Tab plus dynamisch öffenbaren, schließbaren Detail-Tabs für
  Tabellen/Views, und der Schema-Graph als festes Panel rechts mit eigenem
  Scrolling (scrollt nicht mehr mit der Seite). Tabellen-Detail zeigt Spalten
  (Typ, PK) und Foreign Keys; View-Detail zeigt Spalten und die SQL-Definition.
- Views werden jetzt reflektiert; `/api/schema` liefert ein vollständiges
  Struktur-Format (Spalten mit Typ/PK, Foreign Keys, Views mit Definition).
  Demo-DBs enthalten zwei Beispiel-Views.
- UX: Connection-URL wird aus `default_connection` (config.json) vorbefüllt —
  standardmäßig die mitgelieferte Demo-DB, sodass „Schema laden" sofort
  funktioniert. Verdrahtet `core/settings.py` in die Index-Route.
- UX: Leere Connection-URL liefert eine klare Meldung statt der internen
  SQLAlchemy-„Could not parse URL"-Fehlermeldung.
