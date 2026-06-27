# AP-50: Unique-Constraints → korrekte Fan-out-Klassifikation

**Datum:** 2026-06-27
**Status:** Design abgenommen
**Folge-AP:** AP-51 (Unique-Index als zusätzliche Uniqueness-Quelle) — schließt die bekannte Grenze unten.

## Ziel

Die Fan-out-Richtung eines Join-Schritts (`to_many`) so verfeinern, dass eine
**1-1-Beziehung** nicht länger fälschlich als **1-N** klassifiziert und gewarnt
wird. Heute leitet `core/pathfinder.py` `to_many` rein aus der FK-Besitzrichtung
ab und prüft nicht, ob die FK-haltende (Kind-)Seite selbst eindeutig ist.

## Motivation / Ist-Zustand

`core/pathfinder.py:67`:
```python
to_many = chosen.table_a == b   # b hält die FK → absteigend → 1-N (Annahme)
```
`web/routes.py:_path_warnings` wirft für **jeden** Schritt mit `to_many` eine
1-N-Warnung („Ast … ist 1-N — kann Zeilen vervielfachen.").

Hat die FK-Spalte der Kind-Seite jedoch einen `UNIQUE`-Constraint (oder ist sie
PK), ist die Beziehung tatsächlich **1-1** und vervielfacht keine Zeilen. Die
aktuelle Warnung ist dann falsch-positiv. AP-50 behebt genau das.

**Verifiziert:** SQLAlchemy `get_unique_constraints` reflektiert auf SQLite
(Test-Backend) sowohl inline-`UNIQUE` (Spalte) als auch table-level `UNIQUE(...)`
korrekt.

## Zuschnitt (bewusst minimal)

- **Nur Unique-Constraints**, keine Indizes (separate AP-51).
- **Darstellung minimal:** Ein als 1-1 erkannter Schritt setzt nur `to_many=False`
  → grüner Chip wie bei N-1, **keine** falsche 1-N-Warnung. KEIN neuer
  1-1-Chip, KEINE Legenden-/Frontend-/API-Schema-Änderung.
- Read-Only-Constraint und Layering (`core/` bleibt Flask-frei) unberührt.

## Architektur / Datenfluss

Uniqueness wird **einmal beim Graph-Bau** bestimmt und am Join-Option-Objekt
hinterlegt, damit `pathfinder` rein graph-basiert und deterministisch bleibt:

```
loader (reflect UNIQUE) → model.Table.unique_constraints
   → build_graph: pro JoinEdge fk_unique berechnen (hat das Schema)
   → pathfinder: to_many = absteigend  AND NOT fk_unique
   → _path_warnings: 1-N-Warnung entfällt automatisch bei 1-1
```

## Komponenten / Änderungen

### 1. `core/model.py`
`Table` bekommt ein neues Feld:
```python
unique_constraints: tuple[tuple[str, ...], ...] = ()
```
Je innere Tuple = Spaltennamen *einer* Unique-Constraint. Der Primärschlüssel
(`primary_key`) bleibt separat und zählt als implizit eindeutiges Set.

### 2. `core/loaders/sqlalchemy_loader.py`
Zusätzlich pro Tabelle `insp.get_unique_constraints(tname)` einlesen und die
`column_names`-Listen als `unique_constraints` in das `Table` übernehmen. Fehler
beim Reflektieren der Unique-Constraints dürfen die Reflektion nicht abbrechen
(best-effort → leeres Tuple bei Problemen, analog View-Definition).
Die übrigen Loader (`manual`, `ddl`, `schemaspy`) liefern den Default `()`.

### 3. `core/graph.py`
Helfer zur Eindeutigkeitsbestimmung — „sind diese Spalten auf dieser Tabelle
zusammen eindeutig?":
> Es existiert ein Eindeutigkeits-Set `U` (aus `table.unique_constraints` oder
> `== table.primary_key`) mit `set(U) ⊆ set(fk_local_columns)`. (Teilmenge
> genügt: ist eine Teilmenge eindeutig, ist die Obermenge erst recht eindeutig.)

`JoinEdge` bekommt ein Feld `fk_unique: bool`. In `build_graph` (hat Zugriff auf
das `Schema`) wird es pro deklarierter FK berechnet: die FK-haltende Seite ist
`table_a`, deren FK-Spalten sind die a-Seite der `column_pairs`. Implizite FKs
(`core/implied.py`) → `fk_unique=False` (Verhalten unverändert, keine
verlässliche Eindeutigkeitsinfo).

### 4. `core/pathfinder.py`
`_join_step`:
```python
to_many = (chosen.table_a == b) and not chosen.fk_unique
```
Ein absteigender Schritt in eine Tabelle mit eindeutiger FK-Spalte → `to_many=False`.

### 5. `web/routes.py`
Keine Änderung nötig: `_path_warnings` ist von `to_many` getrieben → die
falsche 1-N-Warnung verschwindet automatisch.

## Tests

Neue Fixture `tests/fixtures/onetoone_schema.sql`: ein Parent plus
- ein Kind mit **eindeutiger** FK-Spalte (1-1) und
- zum Kontrast ein Kind mit nicht-eindeutiger FK-Spalte (1-N).

Neue/erweiterte Tests:
- **Loader:** `unique_constraints` wird korrekt befüllt (inline + table-level).
- **Graph:** `JoinEdge.fk_unique` ist `True` für die eindeutige FK, `False` für
  die nicht-eindeutige; composite nur dann `True`, wenn das *ganze* FK-Spaltenset
  von einem Unique-Set abgedeckt ist.
- **Pathfinder:** unique-absteigender Schritt → `to_many is False`;
  nicht-unique-absteigend → `to_many is True`.
- **API/Warnung:** ein 1-1-Schritt erzeugt keine 1-N-Warnung.
- **Regression:** bestehende Inventory-Fixture (FKs nicht eindeutig) → `to_many`
  unverändert; Alt-Tests (`test_pathfinder.py`, `test_api.py`) bleiben grün.

## Doku / Release

- Version **minor** via `sync_version.py --minor` → v0.36.0.
- CHANGELOG (englisch) + Mirror (deutsch, kondensiert).
- Badges (`icon-rail.js`: APP_VERSION/TEST_COUNT/TEST_DATE) + `zensical.toml`
  site_description.
- `CLAUDE.md`: Fan-out-/Composite-FK-Notiz um die Unique-basierte
  1-1-Erkennung ergänzen.
- Architektur-Diagramme: kein neues Modul/Endpoint → i. d. R. unverändert,
  kurz gegenprüfen.
- Site-Build + SDD-Final-Review. Push/gh-pages nur auf Nutzer-Ansage.

## Bekannte Grenze (bewusst, → AP-51)

Eindeutigkeit, die *nur* als Unique-**Index** existiert (manche Postgres-/MSSQL-
Setups reflektieren inline-`UNIQUE` als Unique-Index statt als Constraint), wird
in AP-50 **nicht** erkannt. Das schließt die Folge-AP-51 (`get_indexes` mit
`unique=True` als weitere Uniqueness-Quelle). Auf SQLite (Test-Backend) ist die
Erkennung vollständig.

## Nicht-Ziele

- Kein Indizes-Feature, keine Perf-Hinweise (AP-51 bzw. spätere AP).
- Kein expliziter 1-1-Chip / keine Legenden-/Frontend-Änderung.
- Keine Änderung an der generierten SQL oder der Read-Only-Ausführung.
