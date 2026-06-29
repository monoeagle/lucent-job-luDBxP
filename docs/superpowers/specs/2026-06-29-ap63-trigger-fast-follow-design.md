# AP-63·Trigger-Fast-Follow — PG/Oracle/MSSQL-Trigger-Reflektion

**Datum:** 2026-06-29 · **Zielversion:** v0.56.0 (Minor) · **Typ:** read-only Reflektions-Anreicherung (bestehende Trigger-Kategorie auf weitere Dialekte ausweiten)

## Zweck

Die Trigger-Sidebar-Kategorie (AP-63·S2, v0.53.0) reflektiert heute **nur SQLite**
(`sqlite_master`). Dieser Fast-Follow zieht **PostgreSQL, Oracle und MS SQL Server** nach,
via Pro-Dialekt-Katalog-SQL — strukturell identisch zum AP-63·S3-Routinen-Muster. Trigger
werden **nie ausgeführt**, nehmen an keinem Join-Pfad teil, erzeugen kein DDL. Reine Anzeige.

## Scope

- **In:** PG/Oracle/MSSQL-**Tabellen-/DML-Trigger** (an eine Tabelle gebunden).
- **Out:** DB-/Schema-weite DDL-Trigger (MSSQL `parent_id=0`, Oracle Schema-/Database-Trigger) —
  selten, nicht „in" einem Schema verortet. Cross-Schema (AP-57). Trigger-Ausführung/Join-Teilnahme.

## 1. Model & Signatur

`Trigger(name, table, sql)` **bleibt unverändert** (Name, besitzende Tabelle, DDL/Quelltext —
passt für alle Dialekte). Einzige Strukturänderung:

`_reflect_triggers(engine)` → **`_reflect_triggers(engine, schema)`** (schema-Param fürs Filtern,
analog `_reflect_routines`). Call-Site in `load()` (`Schema(...)`-Konstruktion) entsprechend auf
`_reflect_triggers(engine, schema)` anpassen.

## 2. Loader — `core/loaders/sqlalchemy_loader.py`

`_reflect_triggers` bekommt PG/Oracle/MSSQL-Zweige neben dem bestehenden SQLite-Zweig.
Dialekt-gegated (`engine.dialect.name`), resilient (`except SQLAlchemyError → ()`),
Early-Return-Guard für nicht-passende Dialekte (wie `_reflect_routines`/`_reflect_synonyms`).

- **SQLite (unverändert):** `sqlite_master` `WHERE type='trigger' AND sql IS NOT NULL`.
- **PostgreSQL:**
  ```sql
  SELECT t.tgname, c.relname, pg_get_triggerdef(t.oid)
  FROM pg_trigger t
  JOIN pg_class c     ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE NOT t.tgisinternal AND n.nspname = :s
  ORDER BY t.tgname
  ```
  `tgisinternal` schließt FK-/Constraint-interne Trigger aus. `:s` = `schema or "public"`.
  → `Trigger(tgname, relname, triggerdef or "")`.
- **Oracle:** zweistufig (Liste + per-Trigger volle DDL, mirror des Routinen-`all_source`-Musters):
  ```sql
  SELECT trigger_name, table_name FROM all_triggers
  WHERE owner = :o AND base_object_type = 'TABLE'
  ORDER BY trigger_name
  ```
  je Trigger: `dbms_metadata.get_ddl('TRIGGER', :name, :owner)` (CLOB, volle `CREATE TRIGGER`-DDL —
  sauberer als das `LONG`-`trigger_body`). `:o` = `(schema or "").upper()` bzw.
  `SYS_CONTEXT('USERENV','CURRENT_SCHEMA')`-Fallback (wie `_reflect_routines`).
  → `Trigger(trigger_name, table_name, ddl or "")`; DDL-Lesefehler je Trigger best-effort → leerer sql.
- **MS SQL Server:**
  ```sql
  SELECT tr.name, OBJECT_NAME(tr.parent_id), m.definition
  FROM sys.triggers tr
  LEFT JOIN sys.sql_modules m ON m.object_id = tr.object_id
  WHERE tr.is_ms_shipped = 0 AND OBJECT_SCHEMA_NAME(tr.parent_id) = :s
  ORDER BY tr.name
  ```
  `:s` = `schema or "dbo"`. `parent_id=0` (DDL-Trigger) fällt durch `OBJECT_SCHEMA_NAME=NULL` raus.
  → `Trigger(name, OBJECT_NAME(parent_id) or "", definition or "")`.

## 3. Route & Frontend — **keine Änderung**

`/api/schema` serialisiert `triggers` bereits (`{name, table, sql}`, AP-63·S2). Die JS-Trigger-
Sidebar-Kategorie (N>0) + das Trigger-Detail (Quelltext im SQL-Tab, kein Daten-Tab) existieren
schon. Sobald der Loader für PG/Oracle/MSSQL Trigger liefert, erscheinen sie automatisch — das
ist der Kern des Fast-Follows.

## 4. Tests

- **Naht/Unit (`tests/test_sqlalchemy_loader.py`):** SQLite-Trigger-Pfad bleibt grün
  (`test_loader_reflects_triggers`); nicht-passende Dialekte → `()` (bestehend
  `test_loader_no_triggers_is_empty`, ggf. um die neue Signatur erweitert).
- **Live (skip-guarded):**
  - **MSSQL** (`tests/test_mssql_integration.py`) — Container verfügbar → **echt verifizierbar**:
    Trigger anlegen, reflektieren, in `schema.triggers` mit table + Definition prüfen, droppen.
  - **PostgreSQL** (`tests/test_pg_integration.py`) — Trigger + Trigger-Funktion provisionieren
    (PG-Trigger brauchen eine Trigger-Funktion), reflektieren, prüfen (`pg_get_triggerdef`-Text),
    droppen. PG schnell per podman verifizierbar.
  - **Oracle** (`tests/test_oracle_integration.py`) — Trigger-Assertion ergänzen, wenn
    `LUCENT_ORACLE_TEST_URL` gesetzt; sonst naht-/lesen-verifiziert (kein Live-Oracle).

## 5. Release (voller SDD-Zyklus)

`sync_version.py --minor` → **v0.56.0**. Doku am Code geprüft: Changelog EN + DE-Mirror,
Roadmap-Prosa + Diagramme (Trigger-Eintrag von „SQLite" auf „PG/Oracle/MSSQL" erweitern),
**CLAUDE.md** „Bekannte Einschränkungen" — die AP-63·S2-Trigger-Notiz aktualisieren (heute steht
dort „nur SQLite … andere Dialekte = Fast-Follow"; jetzt PG/Oracle/MSSQL erledigt), Referenz-Prosa
(architektur.md: `_reflect_triggers` jetzt multi-dialekt), Kennzahlen frisch erhoben, Site, gh-pages.

## Verifikation

- `./venv/bin/python -m pytest` grün (SQLite + Naht; Live-Tests skipped ohne URL).
- **Live-MSSQL** (laufender Container) + **Live-PG** (podman): Trigger real reflektiert.
- Browser-Smoke: Trigger-Kategorie erscheint mit echten PG/MSSQL-Triggern (via Live-Reflektion
  oder `page.route`-Injektion).

## Risiken / offene Punkte

- **Oracle `dbms_metadata.get_ddl`** braucht Leserecht auf das eigene Schema (Default vorhanden);
  bei fehlendem Recht/Fehler je Trigger best-effort → leerer sql (Trigger erscheint trotzdem mit
  Name+Tabelle). Nur gegen Live-Oracle real bestätigbar.
- **PG `pg_get_triggerdef`** liefert die volle `CREATE TRIGGER`-Definition inkl. Funktion-Referenz
  (nicht den Funktionskörper) — gewollt (der Funktionskörper steht in der Functions-Kategorie, S3).
- Naht-Tests sichern Verdrahtung + SQLite; Katalog-Query-Korrektheit für PG/MSSQL über die
  Live-Tests, für Oracle nur gelesen.
