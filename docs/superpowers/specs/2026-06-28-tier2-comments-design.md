# Design: Tier-2 — Tabellen-/Spaltenkommentare

**Datum:** 2026-06-28
**Status:** Genehmigt (Brainstorming abgeschlossen)
**Kontext:** Reflection-Ausbau, nächster Tier nach AP-50/51/52 (1-1-Erkennung, Multi-Schema).

## Ziel

Dieses Tool baut visuell Join-Pfade über eine reflektierte Fremd-Datenbank: man wählt
Start-/Ziel-**Spalten** und erhält daraus einen Join-Pfad plus read-only SQL. Spaltennamen
sind in echten DBs oft kryptisch (`kz`, `stat`, `dt_anl`, `fk_kdnr`). Datenbanken pflegen
dafür `COMMENT ON COLUMN` / `COMMENT ON TABLE` (Oracle/Postgres/MySQL/MSSQL).

**Tier-2 liest diese vorhandenen Kommentare bei der Reflection mit und zeigt sie im UI als
Hover-Tooltip**, damit die Spaltenauswahl ohne externes Nachschlagen gelingt und die
fachlich gemeinte Join-Spalte erkennbar wird.

**Ehrliche Einschränkung:** Der Nutzen hängt davon ab, dass die Ziel-DB Kommentare gepflegt
hat. Wo keine existieren, ist das Feature unsichtbar (kein Schaden, kein Gewinn). SQLite —
gegen das die Tests laufen — kennt keine Kommentare; das prägt die Teststrategie (siehe unten).

## Scope

**In Scope:**
- Tabellenkommentare
- Spaltenkommentare
- Anzeige als Hover-Tooltip (`title`-Attribut), keine Layout-Änderung, kein neues CSS

**Out of Scope (YAGNI):**
- Views (View-/View-Spaltenkommentare)
- Kommentare im generierten SQL (`-- …`) — `sqlgen.py` bleibt unverändert
- Sichtbarer Inline-Text oder Indikator-Icons im UI

## Reflection-Verhalten (verifiziert, SQLAlchemy 2.0.51)

Ein Probe-Lauf gegen SQLite ergab:
- `get_columns` enthält bei SQLite **keinen** `comment`-Key → Zugriff muss `col.get("comment")` sein.
- `get_table_comment` wirft bei SQLite **`NotImplementedError`** → muss abgefangen werden.

Beides bestimmt die Robustheit des Loaders.

## Architektur / Datenfluss

```
sqlalchemy_loader.py  (Reflection liest comment)
   └── core/model.py   (Column.comment, Table.comment — plain dataclass-Felder)
        └── web/routes.py  (/api/schema serialisiert comment in JSON)
             └── web/static/js/app.js  (title-Tooltip in Liste + UML)
```

`core/` bleibt Flask-frei (Layering-Regel). Kommentare sind reine Daten, die durch die
bestehenden Schichten fließen.

## Komponenten im Detail

### 1. Model — `core/model.py`
- `Column`: neues Feld `comment: str = ""`
- `Table`: neues Feld `comment: str = ""` (am Ende der Felderliste angehängt, damit
  bestehende positionsbasierte Konstruktoren nicht brechen)
- Konvention: leerer String bedeutet „kein Kommentar"; niemals `None`.

### 2. Loader — `core/loaders/sqlalchemy_loader.py`
- Spalte: `Column(col["name"], str(col["type"]), col.get("comment") or "")`
- Tabelle: Tabellenkommentar über `insp.get_table_comment(tname, schema=schema)`.
  Rückgabe ist ein Dict der Form `{"text": <str|None>}`. Daher:
  ```python
  try:
      tcomment = (insp.get_table_comment(tname, schema=schema).get("text") or "")
  except (NotImplementedError, SQLAlchemyError):
      tcomment = ""
  ```
  Das `try/except` folgt dem bestehenden Muster der unique-Reflection in derselben Datei.

### 3. Serialisierung — `web/routes.py` (`/api/schema`)
- Spalten-Dict: zusätzlich `"comment": c.comment`
- Tabellen-Dict: zusätzlich `"comment": t.comment`

### 4. UI — `web/static/js/app.js`
- Spaltenzeilen in der Tabellen-/Spaltenliste (~`:209`) und in der UML-Ansicht (~`:1073`):
  `title`-Attribut nur setzen, wenn ein Kommentar vorhanden ist (kein leeres `title=""`).
- Tabellen-Header / Tab-Titel: Tabellenkommentar als `title`.
- Werte über die bestehende `esc()`-Funktion absichern.

## Teststrategie

SQLite unterstützt keine Kommentare → Aufteilung nach Konfidenz:

**Pure Unit-Tests (laufen in CI, hohe Konfidenz):**
- *Model:* `Column`/`Table` tragen `comment` mit Default `""`; bestehende Konstruktoren
  brechen nicht.
- *Routes-Serialisierung:* Hand-gebautes `Schema` mit Kommentaren → `/api/schema`-JSON
  enthält `comment` bei Spalte und Tabelle (Flask-Testclient, Loader gemockt; Muster wie
  vorhandene Route-Tests).

**Loader-Positiv-Pfad (Fake-Inspector):**
- Monkeypatch von `inspect` → Fake-Inspector liefert `comment` in `get_columns` und
  `{"text": …}` aus `get_table_comment`. Assert: Werte landen im Model.
- Zweiter Fake: `get_table_comment` wirft `NotImplementedError` → Loader liefert `""`,
  kein Crash.

**Loader-Realität (SQLite, Negativ-Pfad):**
- Bestehende Fixture: reflektierte Spalten/Tabellen haben `comment == ""` (kein Crash trotz
  fehlendem Key / `NotImplementedError`).

**Live-Tests (optional, skip-guarded):**
- In `test_oracle_integration.py` / `test_mssql_integration.py` je eine Kommentar-Assertion
  ergänzen, falls die Test-DB Kommentare hat — „nice to have", nicht CI-tragend.

## Release-Hinweise (projektüblich)

- Version-Bump via `sync_version.py --minor` (Feature).
- Doku nachziehen: Changelog + Doc-Mirror, Roadmap/Board/Gantt, Architektur-Diagramme,
  „Bekannte Einschränkungen"-Block in CLAUDE.md (Tier-2 von „offen" nach „erledigt"),
  Site-Build, gh-pages-Deploy.
- Deutsch, NO-CDN, SDD-Final-Review nicht weglassen; Passwörter werden nie persistiert.
