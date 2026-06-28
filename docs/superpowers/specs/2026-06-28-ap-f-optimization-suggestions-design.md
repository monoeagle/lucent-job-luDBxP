# AP-F — Optimierungs-Vorschläge im SQL-Analyzer

**Datum:** 2026-06-28
**Status:** genehmigt (Design)
**Scope:** `core/sqlanalyze.py` (Logik), `web/routes.py` (JSON-Serialisierung), `web/static/js/app.js` + `web/static/css/app.css` (Render). Read-only, rein sqlglot-AST-basiert. Layering bleibt: `core/` kennt kein Flask.

## Ziel

Der SQL-Analyzer (Paste-SQL-Panel, `/api/analyze`) liefert bereits Warnungen (Korrektheit/Gefahr) + Lints + Komplexitäts-Score. AP-F ergänzt eine **eigene, semantisch getrennte Kategorie „Optimierungs-Vorschläge"** — neutrale, hilfreiche Hinweise zur Query-Verbesserung, getrennt von „Warnungen" (= Probleme). Vier kuratierte, rein AST-basierte Heuristiken mit niedriger False-Positive-Rate.

## Warum getrennte Kategorie (nicht mehr Lints)

„Warnungen" konnotieren Probleme/Gefahr (`WRITE_STATEMENT`, `NO_WHERE`, `CARTESIAN_JOIN`). Optimierungs-**Vorschläge** sind neutral. Eine eigene Liste + eigener UI-Abschnitt hält die Semantik sauber und erlaubt eigenes Styling.

## Datenmodell (`core/sqlanalyze.py`)

Neue frozen dataclass, bewusst **ohne `level`** (Vorschläge sind uniform „Rat"):

```python
@dataclass(frozen=True)
class AnalysisSuggestion:
    code: str      # stabile Maschinen-Code, z. B. "DISTINCT_WITH_GROUP_BY"
    message: str   # deutscher Anzeigetext
```

Neues Feld an `AnalysisResult`, am Ende mit Default-leer (damit die bestehenden 5-positional Parse-Error-/Empty-Returns `AnalysisResult("OTHER", (), (), (), err)` gültig bleiben):

```python
    suggestions: tuple[AnalysisSuggestion, ...] = ()
```

## Logik — `_optimization_suggestions(node) -> list[AnalysisSuggestion]`

Greift **nur am Top-Level-SELECT** (kein Rauschen aus verschachtelten Subqueries). Je Heuristik max. ein Vorschlag, feste Reihenfolge. Aufgerufen aus `analyze()` nur wenn `isinstance(node, exp.Select)`.

Alle Bedingungen sind gegen die echte sqlglot-API verifiziert.

| Code | Bedingung (sqlglot) | Text (DE) |
|---|---|---|
| `DISTINCT_WITH_GROUP_BY` | `node.args.get("distinct") is not None and node.args.get("group") is not None` | „DISTINCT ist überflüssig — GROUP BY macht die Zeilen bereits eindeutig." |
| `ORDER_BY_NO_LIMIT` | `node.args.get("order") is not None and node.args.get("limit") is None` | „ORDER BY ohne LIMIT sortiert das gesamte Ergebnis — LIMIT ergänzen, wenn nur ein Ausschnitt gebraucht wird." |
| `OR_IN_WHERE` | `where is not None and where.find(exp.Or) is not None` | „OR in WHERE kann die Nutzung von Indizes verhindern — IN(…) (gleiche Spalte) oder UNION erwägen." |
| `SUBQUERY_IN_WHERE` | `where` enthält ein `exp.Select`, das **nicht** unter einem `exp.Exists` steht | „Unterabfrage in WHERE — oft als JOIN oder EXISTS effizienter formulierbar." |

`where = node.args.get("where")`.

**`SUBQUERY_IN_WHERE`-Detail (EXISTS-Ausschluss):**
```python
if where is not None:
    for sub in where.find_all(exp.Select):
        if sub.find_ancestor(exp.Exists) is None:
            out.append(AnalysisSuggestion("SUBQUERY_IN_WHERE", "…"))
            break
```
`EXISTS (SELECT …)` ist bereits die empfohlene Form und wird daher nicht vorgeschlagen (verifiziert: bei `WHERE EXISTS (SELECT …)` ist `find_ancestor(exp.Exists)` truthy → kein Vorschlag; bei `WHERE a IN (SELECT …)` ist er `None` → Vorschlag).

`analyze()` ruft am Ende (parallel zu `warnings.extend(_static_lints(node))`):
```python
suggestions = (_optimization_suggestions(node)
               if isinstance(node, exp.Select) else [])
```
und übergibt `suggestions=tuple(suggestions)` an die `AnalysisResult`-Konstruktion.

## Route (`web/routes.py`, `api_analyze`)

Im `jsonify(...)` ergänzen:
```python
        suggestions=[{"code": s.code, "message": s.message}
                     for s in result.suggestions],
```

## Frontend (`web/static/js/app.js`, `renderAnalyzeResult`)

Neuer Abschnitt **„Optimierungs-Vorschläge"**, gerendert **nur wenn nicht leer** (analog zur bestehenden `section()`-Logik — hält das Panel fokussiert; im Gegensatz zum Warnungs-Block, der immer „keine Warnungen" zeigt). Platzierung direkt **vor** dem Warnungen-Block.

```js
const suggs = (res.suggestions && res.suggestions.length)
  ? `<h4>Optimierungs-Vorschläge</h4>` +
    res.suggestions.map((s) =>
      `<div class="an-sugg">💡 ${esc(s.message)}</div>`).join("")
  : "";
```
…in den `out.innerHTML`-Aufbau vor `` `<h4>Warnungen</h4>${warns}` `` eingefügt.

CSS `app.css`: neue Klasse `.an-sugg` — abgesetzt von `.an-warn`/`.an-l-*`, neutral/hilfreich (z. B. linker Akzentstreifen in Blau, dezenter Hintergrund). Eigenständig, keine Wiederverwendung der Warn-Level-Farben.

## Tests

Reines Python → echtes TDD (pytest).

1. **`tests/test_sqlanalyze.py`** — je Heuristik ein Positiv- + ein Negativ-Fall:
   - `DISTINCT_WITH_GROUP_BY`: `SELECT DISTINCT a FROM t GROUP BY a` → vorhanden; `SELECT DISTINCT a FROM t` → fehlt; `SELECT a FROM t GROUP BY a` → fehlt.
   - `ORDER_BY_NO_LIMIT`: `SELECT a FROM t ORDER BY a` → vorhanden; `SELECT a FROM t ORDER BY a LIMIT 10` → fehlt.
   - `OR_IN_WHERE`: `SELECT a FROM t WHERE a=1 OR b=2` → vorhanden; `SELECT a FROM t WHERE a=1 AND b=2` → fehlt.
   - `SUBQUERY_IN_WHERE`: `SELECT a FROM t WHERE a IN (SELECT x FROM u)` → vorhanden; `SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.t_id=t.id)` → fehlt; `SELECT a FROM t WHERE a=1` → fehlt.
   - Negativ-Gesamt: ein No-Op-SELECT (`SELECT a FROM t`) liefert leere `suggestions`; ein Nicht-SELECT (Parse-Fehler / Nicht-Select) liefert leere `suggestions`.
   - Codes werden über `{s.code for s in result.suggestions}` geprüft (stabil, sprachunabhängig).

2. **Route-Test** in `tests/test_api.py` (nutzt das bestehende `client`-Fixture = `app.test_client()`; text-only, **ohne** `connection_url`): `POST /api/analyze` mit `{"sql": "SELECT DISTINCT a FROM t GROUP BY a"}` liefert im JSON eine `suggestions`-Liste, die ein Objekt mit `code == "DISTINCT_WITH_GROUP_BY"` enthält.

3. **Browser-Smoke** `verify_suggestions.py` (System-`python3`, Vorlage `.superpowers/sdd/verify_*.py`): Analyzer-Panel öffnen, auslösendes SQL eingeben, „Analysieren" — der Abschnitt „Optimierungs-Vorschläge" erscheint mit ≥1 `.an-sugg`-Eintrag; ein nicht-auslösendes SQL zeigt den Abschnitt nicht.

## Release-Schritte

- `sync_version.py --minor` (0.44.0 → **0.45.0**) + icon-rail `APP_VERSION` **manuell**.
- icon-rail `TEST_COUNT` auf die neue pytest-Zahl aktualisieren (TEST_DATE bleibt 2026-06-28).
- Changelog (Root EN + Mirror DE), `roadmap.md`-Versionslog (v0.45.0 / AP-F), Gantt + Board (AP-F **namentlich**), `oberflaeche.md` (Analyzer-Funktionen + Stand).
- Site bauen + gerenderte Übersichten gegenprüfen; gh-pages-Deploy (manuelles Worktree).
- Deutsch / NO-CDN. SDD-Final-Review nicht weglassen.

## Nicht im Scope (YAGNI)

- Analyse verschachtelter Subqueries (nur Top-Level-SELECT).
- Schema-abhängige Vorschläge (z. B. Index-Empfehlungen — der Analyzer hat keine vollständige Index-Metadaten).
- Weitere Heuristiken (NOT IN / `!=` non-sargable, LIMIT ohne ORDER BY, COUNT(DISTINCT)-Kosten) — bewusst zurückgestellt; können später ergänzt werden.
- Automatisches Umschreiben der Query (nur Hinweise, keine Rewrites).
- `level`-Feld an `AnalysisSuggestion` (Vorschläge sind uniform).
