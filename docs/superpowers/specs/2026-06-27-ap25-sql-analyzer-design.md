# AP-25 — SQL-Statement-Analyzer (read-only Analyse), erste Scheibe

**Datum:** 2026-06-27
**Status:** Design freigegeben (Brainstorming)

## Ziel

Ein neuer Tab „SQL-Analyzer", in den der Nutzer ein beliebiges SQL-Statement einfügt. Das Tool
**analysiert** es und zeigt seine **Auswirkungen**, **ohne es jemals auf der DB auszuführen**
(strikt read-only — passt zur Projekt-Grundausrichtung). Ziel: einschätzen, was ein Statement täte.

## Scope dieser Scheibe

**Drin:** Parsen + Klassifizieren + beteiligte Tabellen (gelesen vs. geschrieben) + Kern-Warnungen +
Graph-Highlight (wenn verbunden). Funktioniert **mit und ohne** aktive Verbindung.

**Bewusst draußen (YAGNI, spätere Scheiben):** „an Join-Builder übertragen", Join-**Pfad**-Highlight,
View-Abhängigkeiten, geschätzte Treffermenge (EXPLAIN).

## Befund (Ist-Stand, gegen echten Code geprüft)

- Weder `sqlglot` noch `sqlparse` ist installiert/gebündelt — Parser muss neu als Wheel ins Wheelhouse
  (NO-CDN), Eintrag in `requirements.txt`.
- Reuse-Punkte vorhanden: Graph-Node-Marker via Cytoscape (`_updateGraphNodeMarkers`, Klassen
  `sel-source`/`sel-target`), Dialekt-Ableitung `dialectFromUrl` (JS) / `dialect_for` + `_dialect_from_url`
  (Python, AP-29), Schema-Reflection `SqlAlchemyLoader(url).load()`, Tab-Mechanik `ensureTab`/`activateTab`.
- `core/` ist Flask-frei und bleibt es.

## Getroffene Entscheidungen

1. **Parser:** `sqlglot` — vollwertiger SQL-Parser mit echtem AST, dialekt-bewusst (passt zu AP-29),
   pure-Python ohne Transitiv-Deps, als Wheel bündelbar.
2. **Zwei Modi:**
   - **Mit Verbindung:** Analyse nutzt das reflektierte Schema (Tabellen-/Spalten-Abgleich) und den
     verbindungs-Dialekt; Graph-Highlight aktiv.
   - **Ohne Verbindung:** reine Text-Analyse; sqlglot parst dialekt-neutral; schema-abhängige
     Warnungen (unbekannte Tabelle/Spalte) und Highlight entfallen.
3. **Strikt keine Ausführung:** Es wird ausschließlich geparst; kein DB-Roundtrip, keine EXPLAIN.

## Architektur

```
web/ (neuer Tab, /api/analyze)
  └── ruft → core/sqlanalyze.analyze(sql, schema=None, dialect=None)
                └── nutzt → sqlglot (AST)
core/ bleibt Flask-frei
```

### 1. `core/sqlanalyze.py` (neu, Flask-frei)

```python
@dataclass(frozen=True)
class AnalysisWarning:
    level: str        # "info" | "warn" | "danger"
    code: str         # stable machine code, e.g. "WRITE_STATEMENT", "NO_WHERE"
    message: str      # German user-facing text

@dataclass(frozen=True)
class AnalysisResult:
    statement_type: str            # SELECT | INSERT | UPDATE | DELETE | DDL | OTHER
    tables_read: tuple[str, ...]
    tables_written: tuple[str, ...]
    warnings: tuple[AnalysisWarning, ...]
    parse_error: str | None        # set when sqlglot cannot parse; other fields empty

def analyze(sql: str, schema=None, dialect: str | None = None) -> AnalysisResult: ...
```

- Parst `sql` mit sqlglot (`read=dialect` wenn gesetzt, sonst dialekt-neutral). Bei Parse-Fehler:
  `parse_error` gesetzt, übrige Felder leer, keine Exception nach außen.
- `statement_type` aus dem Wurzel-AST-Knoten.
- `tables_read` / `tables_written`: aus dem AST. Schreibziel von INSERT/UPDATE/DELETE und das
  Objekt von CREATE/ALTER/DROP → `tables_written`; FROM/JOIN/Subquery-Quellen → `tables_read`.
  Deterministisch sortiert, dedupliziert.
- `dialect` ist der **Dialektname** (z. B. `"postgresql"`), gemappt auf sqlglots Dialekt; unbekannt →
  dialekt-neutral.

### 2. Warn-Set (Kern)

| code | level | Bedingung |
|---|---|---|
| `WRITE_STATEMENT` | danger | Statement ist INSERT/UPDATE/DELETE/DDL → „würde Daten/Schema verändern; das Tool führt nichts aus" |
| `NO_WHERE` | danger | UPDATE oder DELETE ohne WHERE → „betrifft alle Zeilen" |
| `CARTESIAN_JOIN` | warn | JOIN ohne ON-Bedingung bzw. Komma-Join ohne verknüpfende WHERE-Bedingung |
| `UNKNOWN_TABLE` | warn | nur **mit** Schema: referenzierte Tabelle nicht im reflektierten Schema |
| `UNKNOWN_COLUMN` | warn | nur **mit** Schema: qualifizierte Spalte nicht in ihrer Tabelle |

Schema-abhängige Warnungen (`UNKNOWN_TABLE`, `UNKNOWN_COLUMN`) werden nur erzeugt, wenn `schema`
übergeben wurde.

### 3. `web/routes.py` — `POST /api/analyze`

- Request: `{ sql, connection_url? }`.
- `connection_url` leer/fehlend → Text-Modus: `analyze(sql)` ohne Schema/Dialekt.
- `connection_url` gesetzt → `schema = SqlAlchemyLoader(url).load()`, `dialect = _dialect_from_url(url)`,
  `analyze(sql, schema, dialect)`. Verbindungsfehler → 400 mit klarer Meldung (Analyse braucht die
  Reflection; alternativ könnte der Client ohne URL erneut anfragen).
- Antwort: serialisiertes `AnalysisResult` (statement_type, tables_read, tables_written, warnings,
  parse_error). **Führt nie SQL aus.**

### 4. Frontend (`index.html`, `web/static/js/app.js`, `web/static/css/app.css`)

- Neuer Sidebar-Eintrag/Tab „SQL-Analyzer" (Reuse `ensureTab`/`activateTab`).
- Panel: `<textarea>` + Button „Analysieren" + Ergebnisbereich.
- Ergebnis: Statement-Typ-Badge, zwei Listen (gelesen / geschrieben), Warnungs-Liste (Farbe je
  `level`), bei `parse_error` eine Fehlermeldung.
- **Graph-Highlight (nur mit Verbindung):** beteiligte Tabellen im Schema-Graph markieren — zwei neue
  CSS-Klassen, z. B. `analyze-read` / `analyze-write` (analog zu `sel-source`/`sel-target`), gesetzt
  über die bestehende Cytoscape-Node-Markierung. Vor jeder neuen Analyse alte Marker entfernen.
- Alle in den DOM eingefügten Server-Strings über `esc()` (XSS), keine externen Assets (NO-CDN).

### 5. Dependency / Bundling

- `sqlglot` in `requirements.txt`; Wheel ins Wheelhouse (NO-CDN, offline-installierbar) entsprechend
  bestehendem Wheelhouse-Muster.

### 6. Tests

- **core/sqlanalyze (Schwerpunkt, schnell, ohne DB):**
  - SELECT mit JOIN → type=SELECT, tables_read korrekt, keine danger-Warnung.
  - UPDATE/DELETE ohne WHERE → `WRITE_STATEMENT` + `NO_WHERE`, tables_written korrekt.
  - INSERT → tables_written = Ziel, tables_read = Quelle (bei INSERT…SELECT).
  - DDL (CREATE/DROP) → type=DDL, `WRITE_STATEMENT`.
  - Kartesischer Join (JOIN ohne ON) → `CARTESIAN_JOIN`.
  - Mit Schema: `UNKNOWN_TABLE`/`UNKNOWN_COLUMN`; ohne Schema: diese Warnungen fehlen.
  - Unparsbarer Müll → `parse_error` gesetzt, keine Exception.
  - Determinismus: gleiche Eingabe → gleiche (sortierte) Tabellenlisten.
- **web/routes (API):** `/api/analyze` mit/ohne `connection_url`; Antwort-Form; nie Ausführung;
  Verbindungsfehler → 400.
- **Frontend:** Playwright-Verifikation (System-python3): Tab öffnen, Statement einfügen, Analyse mit
  und ohne Verbindung; Highlight nur mit Verbindung. (Kein JS-Unit-Harness im Projekt.)

### 7. Version & Doku

- **minor**-Bump via `sync_version.py` (Feature).
- Changelog + Mirror, Roadmap/Board/Gantt (AP-25 namentlich enumeriert), Badges, todo.md, Site-Build
  (Linux), gh-pages-Deploy.

## Bekannte Grenzen (dokumentiert)

- Tabellen-/Spalten-Extraktion ist so gut wie sqlglots AST; sehr exotische/dialektspezifische
  Konstrukte können unvollständig erkannt werden → im Zweifel als `parse_error` oder ohne Highlight.
- Spalten-Abgleich (`UNKNOWN_COLUMN`) nur für **qualifizierte** Spalten (`tabelle.spalte`) zuverlässig;
  unqualifizierte Spalten in Multi-Tabellen-Statements werden nicht hart als unbekannt gewarnt.
