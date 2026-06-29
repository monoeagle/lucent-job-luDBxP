# AP-63·S3 — Stored Procedures / Functions / Packages / Synonyms

**Datum:** 2026-06-29 · **Zielversion:** v0.55.0 · **Typ:** read-only Reflektions-Anreicherung (neue Sidebar-Kategorien)

## Zweck

Die DB-Objekt-Kategorie-Serie (AP-63) um **ausführbare Routinen** erweitern: Stored
Procedures, Functions, Oracle Packages und Oracle Synonyms werden **read-only** reflektiert
und je als eigene Sidebar-Kategorie mit Detail (Quelltext) angezeigt. Folgt exakt dem in
S2 (Trigger) / S2b (Sequences/Matviews) etablierten Kategorie-Muster.

**Constraint (unverändert):** Routinen werden **nie ausgeführt**, nehmen an keinem Join-Pfad
teil, erzeugen kein DDL. Reine Anzeige.

## Scope (bewusst gewählt)

Volle S3-Scheibe inkl. **Oracle Packages + Synonyms** (Nutzerentscheidung 2026-06-29,
entgegen der kleineren „nur Proc/Func"-Empfehlung). Bewusst festgehalten: Oracle
Packages/Synonyms sind **nur gegen Live-Oracle** real verifizierbar — die Naht-Tests decken
die Verdrahtung CI-grün ab, der echte Reflektions-Schritt bleibt skip-guarded.

**Out of scope:** MySQL-Routinen (Projekt testet nur PG/Oracle/MSSQL live), MSSQL-Synonyms
(Synonyme hier Oracle-only zugeschnitten), Routinen-Parameter/Signaturen, Aufruf/Ausführung,
Join-Teilnahme, Cross-Schema (AP-57, bedingt).

## 1. Model (`core/model.py`)

Zwei neue frozen Dataclasses + zwei **Trailing-Felder** am `Schema` (`()`-Default → andere
positionale Konstruktoren unberührt):

```python
@dataclass(frozen=True)
class Routine:
    name: str
    kind: str        # "procedure" | "function" | "package"
    sql: str = ""    # Quelltext (CREATE … / Package-Source); "" falls nicht lesbar

@dataclass(frozen=True)
class Synonym:
    name: str
    target: str      # (owner.)object — Zielobjekt; kein Quelltext

# Schema — neue Trailing-Felder:
routines: tuple[Routine, ...] = ()
synonyms: tuple[Synonym, ...] = ()
```

Ein **flaches** `routines`-Tupel mit `kind`-Diskriminator (proc/func/package); die Aufteilung
in die drei UI-Kategorien geschieht in Route/JS per `kind`-Filter. Hält die Schema-Erweiterung
minimal (2 Felder statt 3 Tupeln). Synonyme haben eine andere Form (Ziel statt Quelltext) →
eigene Dataclass.

## 2. Loader (`core/loaders/sqlalchemy_loader.py`)

Zwei Helfer analog `_reflect_triggers`: dialekt-gegated, resilient (`except SQLAlchemyError → ()`),
keine native SQLAlchemy-API → Pro-Dialekt-Katalog-SQL mit gebundenen Parametern.

### `_reflect_routines(engine, schema) -> tuple[Routine, ...]`

- **PostgreSQL** (`dialect == "postgresql"`): `pg_proc` ⋈ `pg_namespace`,
  `prokind IN ('p','f')` → kind p=procedure / f=function; Quelltext via
  `pg_get_functiondef(p.oid)`. Schema-Filter `n.nspname = :schema` (Fallback `public`,
  wenn kein Schema übergeben). PG hat keine Packages/Synonyms.
- **Oracle** (`dialect == "oracle"`): `all_objects` mit
  `object_type IN ('PROCEDURE','FUNCTION','PACKAGE')`, `owner = :schema`
  (Fallback: aktueller User via `sys_context`/übergebenes Schema). Quelltext je Objekt via
  `all_source` (`owner`/`name`/`type`, `ORDER BY line`, zeilenweise zusammengefügt).
- **MSSQL** (`dialect in ("mssql",)`): `sys.objects` (`type IN ('P','FN','IF','TF')`,
  P=procedure, FN/IF/TF=function) `LEFT JOIN sys.sql_modules` für `definition`,
  `SCHEMA_NAME(schema_id) = :schema`. Keine Packages.
- **SQLite / sonstige:** `()` (wie Trigger).

### `_reflect_synonyms(engine, schema) -> tuple[Synonym, ...]`

- **Oracle-only:** `all_synonyms` (`owner = :schema`), target =
  `table_owner || '.' || table_name` (owner weggelassen, wenn = Schema). Sonst `()`.

Beide werden in `load()` aufgerufen und in den `Schema(...)`-Konstruktor als neue Trailing-Args
gefädelt (nach `materialized_views`).

## 3. Route (`web/routes.py`)

In `/api/schema` vier neue Arrays — `schema.routines` nach `kind` gefiltert + `synonyms`:

```python
procedures=[{"name": r.name, "sql": r.sql} for r in schema.routines if r.kind == "procedure"],
functions =[{"name": r.name, "sql": r.sql} for r in schema.routines if r.kind == "function"],
packages  =[{"name": r.name, "sql": r.sql} for r in schema.routines if r.kind == "package"],
synonyms  =[{"name": s.name, "target": s.target} for s in schema.synonyms],
```

## 4. Frontend (`web/static/js/app.js`)

Vier neue Sidebar-Kategorien — je **nur bei N>0**, exakt das `objList`-Muster (wie
Trigger/Sequences/Matviews):

- **Prozeduren** (`SCHEMA.procedures`, kind `"procedure"`)
- **Funktionen** (`SCHEMA.functions`, kind `"function"`)
- **Packages** (`SCHEMA.packages`, kind `"package"`)
- **Synonyme** (`SCHEMA.synonyms`, kind `"synonym"`)

Vier neue `openDetail`-Zweige:

- **Proc/Func/Package:** `<h2>` mit Typ-Label + Quelltext im **SQL-Subtab**, **kein Daten-Tab**
  (wie Trigger). `hasData` bleibt `false`.
- **Synonym:** `<h2>` + `<p class="hint">Ziel: …</p>`; SQL-Subtab **bleibt** (zeigt
  „(keine Definition)") → konsistent mit dem Sequenz-Muster, kein Detail-Layout-Sonderfall.

### Cleanup mitnehmen (Backlog-Items, betreffen genau diesen Code)

- `objList`: `data-name` von `esc` auf **`escAttr`** umstellen (gleiche Klasse wie der schon
  gefixte `data-table`).
- **`findByName(kind, name)`-Helfer** einführen, den die neuen + bestehenden Detail-Zweige
  (table/view/trigger/sequence/matview/procedure/function/package/synonym) teilen — statt
  wiederholter `(SCHEMA.x || []).find(...)`-Aufrufe mit Undefined-Risiko.

## 5. Tests

**Naht-Tests (CI-grün, ohne Live-DB — etabliertes Muster aus S2b):**

- **Endpoint** (`tests/test_routes*.py` o. ä.): Loader monkeypatchen → konstruiertes `Schema`
  mit Routines (alle drei kinds) + Synonyms; `/api/schema`-JSON prüfen (procedures/functions/
  packages/synonyms korrekt nach kind gesplittet, leere Kategorien = `[]`).
- **UI** (Playwright, System-`python3`): `page.route`-Injektion der vier Kategorien →
  Sidebar zeigt vier Kategorien, Detail öffnet mit Quelltext / Ziel.
- **Model/Loader-Unit** (`tests/test_model.py`, `tests/test_sqlalchemy_loader.py`):
  Routine/Synonym-Konstruktoren; `_reflect_routines`/`_reflect_synonyms` gegen SQLite →
  `()` (Dialekt-Gating).

**Live (skip-guarded, nur mit URL):**

- `tests/test_pg_integration.py`: um Routine-Reflektion erweitern (PG-Function anlegen →
  in `routines` mit kind `"function"` + Quelltext).
- `tests/test_oracle_integration.py`, `tests/test_mssql_integration.py`: Routinen-Reflektion
  aufnehmen, wenn `LUCENT_*_TEST_URL` gesetzt; Oracle zusätzlich Package + Synonym.

## 6. Release (voller SDD-Zyklus)

`sync_version.py --minor` → **v0.55.0**, dann Doku **vollständig am Code geprüft**:
Changelog EN + DE-Mirror, Roadmap-Prosa + `.mmd`-Diagramme (Gantt/Board/Architektur),
Referenz-Prosa (Architektur/Datenmodell/Projektstruktur/Oberfläche — neue Model-Klassen/
Endpoint-Felder/Kategorien), Kennzahlen-Dashboard inkl. Nicht-Versionsfelder (Commits/Sessions/
Coverage frisch erhoben), icon-rail/zensical, AP-63-Konzept-Status, Site-Build, master + gh-pages.

## Verifikation

- `./venv/bin/python -m pytest` → grün (neue Naht-/Unit-Tests; Live-Tests skipped ohne URL).
- Browser-Smoke: vier Kategorien + Detail via `page.route`-Injektion.
- Falls Live-PG/Oracle/MSSQL erreichbar: echte Reflektion gegenprüfen.

## Risiken / offene Punkte

- **Pro-Dialekt-Katalog-SQL ohne Live-DB blind geschrieben** (Oracle/MSSQL): Syntax/Spalten
  best-effort nach Doku; real erst gegen Live-Instanz bestätigt. Naht-Tests sichern nur die
  Verdrahtung, nicht die Katalog-Query-Korrektheit.
- `pg_get_functiondef` kann für Nicht-`p`/`f`-Routinen scheitern → strikt auf `prokind IN ('p','f')`
  begrenzen.
- Große Package-Sources / viele Routinen: keine Paginierung — wie bei View-Definitionen
  unbeschränkt angezeigt (read-only, akzeptiert).
