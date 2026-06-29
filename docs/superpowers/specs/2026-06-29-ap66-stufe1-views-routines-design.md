# AP-66·Stufe 1 — Views → referenzierte Routinen (Diagnose)

**Datum:** 2026-06-29 · **Zielversion:** v0.57.0 (Minor) · **Typ:** read-only Reflektions-Anreicherung (View→Routine-Beziehung sichtbar machen)

## Zweck

Sichtbar machen, **welche Views auf Routinen-Logik beruhen** — also in ihrer Definition
Stored Procedures/Functions (inkl. Oracle Packages) aufrufen. Für das Migrations-Ziel
(HCMX/Oracle) sind das genau die Views, die **nicht** über reine Join/FK-Lineage migrierbar
sind: ein Teil der Datenlogik steckt in der Routine, nicht in Tabellen/FKs. Read-only, keine
Auflösung/Ausführung der Routine selbst.

Baut auf AP-63·S3 auf: die reflektierte `schema.routines`-Liste liefert die **Grundwahrheit**,
gegen die View-Funktionsaufrufe abgeglichen werden — präziser als eine reine Built-in-Heuristik.

## Scope

- **In:** Aus dem View-Definitionstext referenzierte Routinennamen via sqlglot-AST extrahieren,
  **gegen `schema.routines` abgleichen** (case-insensitiv), die bestätigten Routinen am View-Detail
  anzeigen + betroffene Views in der Sidebar markieren. Gilt auch für Materialized Views (reusen `View`).
- **Out (Stufe 2/3, zurückgestellt):** Reflektion/Verlinkung des Routinen-Quelltexts aus dem View
  heraus (Stufe 2 — überlappt mit S3, das die Routinen schon reflektiert); echte Daten-Lineage durch
  den PL/SQL-Body (Stufe 3, XL). Keine Confidence-Stufen / „möglich, nicht reflektiert"-Treffer
  (nur bestätigte Matches). Kein Ausführen, keine PL/SQL-Übersetzung.

## 1. Core-Extraktion — neues Modul `core/viewdeps.py`

Eine fokussierte, pure Funktion (sqlglot, kein Flask/DB):

```python
def referenced_routines(definition: str, known_routine_names, dialect=None) -> tuple[str, ...]:
    ...
```

- **Parsen:** `sqlglot.parse_one(definition, read=<mapped>)`; Dialekt-Mapping wie in
  `core/sqlanalyze.py::_SQLGLOT_DIALECT` (`postgresql→postgres`, `mssql→tsql`, `oracle→oracle`,
  `sqlite→sqlite`, sonst neutral `None`). Bei `SqlglotError`/leerer Definition → `()`.
- **Kandidaten sammeln:** alle `exp.Anonymous`-Knoten (benutzerdefinierte Funktionsaufrufe; SQL-
  Built-ins sind getypte sqlglot-Knoten und fallen automatisch raus) → deren `.name`; **zusätzlich
  der führende Qualifier dotted Aufrufe** (`PKG.FN(...)`), damit Oracle-Package-Aufrufe gegen die
  reflektierte Package-Routine (`Routine(kind="package")`, Name = Package) matchen. Qualifier wird
  aus der `exp.Dot`/`db`-Struktur des Aufrufs gezogen.
- **Abgleich:** Kandidatennamen **case-insensitiv** gegen `known_routine_names` matchen (Oracle
  liefert Bezeichner groß). Rückgabe = die **kanonischen** Namen aus `known_routine_names` (Original-
  Schreibweise der reflektierten Routine), **dedupliziert + sortiert**.
- `known_routine_names` ist ein `set`/`frozenset` von Strings; die Funktion baut intern eine
  case-insensitive Lookup-Map (`upper() → kanonisch`).

Vollständig CI-testbar mit synthetischen Definitionen + Namensmenge.

## 2. Model — `core/model.py::View`

Neues Trailing-Feld:

```python
@dataclass(frozen=True)
class View:
    name: str
    columns: tuple[Column, ...]
    definition: str = ""
    routines: tuple[str, ...] = ()   # referenzierte (reflektierte) Routinennamen
```

Default `()` → bestehende positionale `View(...)`-Konstruktionen bleiben gültig. Matviews reusen
`View` und bekommen das Feld automatisch.

## 3. Loader-Verdrahtung — `core/loaders/sqlalchemy_loader.py::load()`

- Routinen **vor** der View-/Matview-Schleife reflektieren (heute am Ende): `routines = _reflect_routines(engine, schema)`
  hochziehen, Namensmenge `routine_names = frozenset(r.name for r in routines)` bilden.
- Dialektname `dname = getattr(getattr(engine, "dialect", None), "name", "")`.
- Je View/Matview: `referenced_routines(definition, routine_names, dname)` berechnen und als neues
  Trailing-Arg in `View(name, cols, definition, routines)` durchreichen.
- SQLite → `routines` leer → keine Matches (korrekt; SQLite hat keine Stored Routines).
- `_reflect_routines` wird weiterhin genau einmal aufgerufen (das Ergebnis im finalen `Schema(...)`
  wiederverwenden, nicht doppelt reflektieren).

## 4. Route — `/api/schema`

In den `views`- und `materialized_views`-Arrays je View ein Feld `"routines": list(v.routines)`.

## 5. Frontend — `web/static/js/app.js`

- **View-/Matview-Detail** (`openDetail`, View- und Matview-Zweig): wenn `v.routines?.length`, einen
  Abschnitt rendern: `<h3>Verwendet Routinen</h3>` + Liste der Namen (`esc`). Klartext (Verlinkung
  zum Routinen-Detail = Stufe 2). Wenn leer: kein Abschnitt.
- **Sidebar-Markierung** in `objList`: für Items mit `o.routines && o.routines.length` ein kleines
  Kennzeichen rendern — Badge „ƒ" mit `title="${escAttr('nutzt Routinen: ' + o.routines.join(', '))}"`.
  Generisch: andere Objekt-Typen tragen kein `routines` → kein Badge. `data-name` bleibt `escAttr`.

## 6. Tests

- **Unit `tests/test_viewdeps.py` (CI, kein DB):**
  - Direkter Funktionsaufruf in der Definition + Name in der Routinenmenge → wird zurückgegeben.
  - SQL-Built-in (z. B. `COUNT(...)`, `UPPER(...)`) ohne passende Routine → nicht zurückgegeben.
  - Package-qualifizierter Aufruf `PKG.FN(x)` mit `PKG` in der Routinenmenge → `PKG` zurückgegeben.
  - Case-Insensitivität (Definition `myfn()`, Routine `MYFN`) → kanonischer Name `MYFN`.
  - Parse-Fehler / leere Definition → `()`. Kein Match → `()`. Dedup + Sortierung.
- **Loader-Naht `tests/test_sqlalchemy_loader.py`:** Monkeypatch-Inspector mit einer View-Definition,
  die eine reflektierte Routine aufruft → `schema.views[..].routines` korrekt befüllt; SQLite
  (`inventory_url`, keine Routinen) → `routines == ()` an allen Views.
- **Route `tests/test_api.py`:** Monkeypatch-Schema mit View(routines=("FOO",)) → `/api/schema`
  liefert `routines: ["FOO"]`; ohne Routinen → `[]`.
- **JS-Smoke (`page.route`):** View-Detail zeigt „Verwendet Routinen", Sidebar-Item trägt das Badge.
- **Live (optional):** Oracle/MSSQL nur falls Instanz; der Kern ist CI-grün.

## 7. Release (voller SDD-Zyklus)

`sync_version.py --minor` → **v0.57.0**. Doku am Code geprüft: Changelog EN + DE-Mirror, Roadmap-
Prosa + Diagramme (AP-66·S1 done, enumeriert), **neues `core/viewdeps.py`** in `architektur.md`-Prosa
+ `referenz-architektur-1.mmd` (core-Modulkarte), `datenmodell.md` (`View.routines`), `oberflaeche.md`
(View-Detail-Abschnitt + Sidebar-Badge), Kennzahlen frisch erhoben, Site, gh-pages. Der bereits auf
master liegende **Per-Modul-Coverage-Balken-Fix** (core 92 % / GUI ~72 %) deployt hier mit.

## Verifikation

- `./venv/bin/python -m pytest` grün (viewdeps-Unit + Loader-Naht + Route; JS-Smoke separat).
- Browser-Smoke: View mit Routinen-Aufruf zeigt Abschnitt + Badge; View ohne → keiner.
- Falls Live-Oracle/MSSQL: echte View-Definition mit Routinenaufruf gegenprüfen.

## Risiken / offene Punkte

- **sqlglot-Parsbarkeit von View-Definitionen:** `get_view_definition` liefert je Dialekt teils nur
  den SELECT-Body, teils mit Eigenheiten (Oracle PL/SQL-nahe Konstrukte). Bei Parse-Fehler → `()`
  (View erscheint ohne Routinen-Markierung, kein Crash) — bewusst konservativ.
- **Package-interne / nicht reflektierte Routinen:** nur gegen `schema.routines` gematcht; eine im
  View genutzte, aber nicht reflektierte Routine (z. B. Cross-Schema, oder Package-**interne** Funktion
  ohne eigenen Katalogeintrag) erscheint nicht. Bewusst (Stufe 1 = bestätigte Treffer; „möglich"-
  Treffer waren die verworfene Heuristik-Variante).
- **False Negatives bei dynamischem SQL** in der View sind möglich — nicht Scope.
