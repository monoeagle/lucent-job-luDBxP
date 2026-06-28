# Design: COUNT(*) + COUNT(DISTINCT)

**Datum:** 2026-06-28
**Status:** Genehmigt (Brainstorming abgeschlossen)
**Kontext:** Dritte Aggregat-Ausbaustufe nach Tier-3 (GROUP BY/Aggregate, v0.41.0) und
Aggregat-Operationen (HAVING + ORDER BY auf Aggregaten, v0.42.0). Schließt die beiden in Tier-3
ausgeklammerten COUNT-Varianten.

## Ziel

Der Generator kennt seit Tier-3 die Aggregate `COUNT/SUM/AVG/MIN/MAX` als `func(Spalte)`, seit
v0.42.0 auch in HAVING und ORDER BY. Zwei sehr gebräuchliche COUNT-Formen fehlen noch:

1. **`COUNT(*)`** — Zeilen je Gruppe. Die häufigste Gruppierungsfrage überhaupt
   (`SELECT k, COUNT(*) … GROUP BY k`), inklusive `HAVING COUNT(*) > 5` und `ORDER BY COUNT(*) DESC`.
   Nicht spaltengebunden.
2. **`COUNT(DISTINCT col)`** — Anzahl verschiedener Werte einer Spalte. Spaltengebunden.

Beide werden als zusätzliche Aggregat-Tokens in das bestehende Aggregat-Modell eingefügt, sodass
sie **automatisch** in SELECT, HAVING und ORDER BY funktionieren.

## Scope

**In Scope:**
- Aggregat-Token **`COUNT*`** → rendert `COUNT(*)` (Spalte ignoriert).
- Aggregat-Token **`COUNT DISTINCT`** → rendert `COUNT(DISTINCT <Spalte>)`.
- Beide in SELECT-Spalten, HAVING-Bedingungen und ORDER-BY-Einträgen (alle drei nutzen denselben
  Aggregat-Begriff).
- UI: beide als Einträge in den Aggregat-Dropdowns (mit Labels `COUNT(*)` / `COUNT(DISTINCT)`).
- UI: bei Auswahl von `COUNT(*)` wird das zugehörige Spalten-Dropdown deaktiviert (sichtbar
  irrelevant); der (deaktivierte) Spaltenwert wird weiterhin gesendet.

**Out of Scope (YAGNI):**
- DISTINCT-Varianten anderer Aggregate (`SUM(DISTINCT)`, `AVG(DISTINCT)`, …) — nur **COUNT** bekommt
  die DISTINCT-Form.
- Mehrspaltiges `COUNT(DISTINCT a, b)`.
- Harte Typprüfung.

## Entscheidungen

- **Unified Aggregat-Wert (kein neues Strukturfeld):** `COUNT*` und `COUNT DISTINCT` sind nur neue
  Werte der bestehenden `_ALLOWED_AGGS`-Allowlist. Ein zentraler Render-Helfer ersetzt die drei
  identischen `f"{agg}({expr})"`-Stellen. Dadurch fädeln beide Aggregate ohne weiteren
  Generator-Eingriff durch SELECT/HAVING/ORDER BY, und `Selection`/`Having`/`order_by` brauchen
  **keine** neuen Felder.
- **COUNT(*) ist tabellen-, nicht spaltengebunden:** Die Spalte wird beim Rendern ignoriert, die
  **Tabelle** des Eintrags bleibt aber im AP-30-`required_tables`-Weaving. Das ist gewollt: „COUNT(*)
  an Tabelle T + GROUP BY K" erzeugt `… JOIN T … GROUP BY K` und zählt die (gejointen) T-Zeilen je
  Gruppe. Man wählt die Tabelle, deren Zeilen man zählt.
- **Route bleibt unverändert:** `agg` fließt verbatim durch; `schema.has_column(table, column)`
  validiert die (für COUNT(*) ignorierte, aber weiter gewählte) Spalte; der Generator validiert das
  Aggregat gegen die Allowlist. Es ist kein Route-Eingriff nötig.

## Komponenten & Änderungen

### 1. Generator — `core/sqlgen.py`
- `_ALLOWED_AGGS` erhält die zwei neuen Tokens:
  `frozenset({"COUNT", "SUM", "AVG", "MIN", "MAX", "COUNT*", "COUNT DISTINCT"})`.
- Neuer Helfer:
  ```python
  def _render_agg(agg: str, expr: str) -> str:
      """Render an aggregate over a qualified column expression.
      COUNT* ignores the column (COUNT(*)); COUNT DISTINCT dedups it."""
      if agg == "COUNT*":
          return "COUNT(*)"
      if agg == "COUNT DISTINCT":
          return f"COUNT(DISTINCT {expr})"
      return f"{agg}({expr})"
  ```
- Die drei bestehenden Render-Stellen rufen den Helfer auf:
  - SELECT-Liste (`expr = _render_agg(s.agg, expr)`),
  - ORDER BY (`expr = _render_agg(agg, expr)`),
  - HAVING (`expr = _render_agg(h.agg, dialect.qualify(h.table, h.column, schema))`).
- Validierung unverändert (`agg in _ALLOWED_AGGS` an allen drei Stellen) — die neuen Tokens passieren.
- GROUP-BY-Ableitung unverändert: ein Eintrag mit nicht-leerem `agg` (auch `COUNT*`/`COUNT DISTINCT`)
  gilt als aggregiert und ist kein Gruppenschlüssel.

### 2. Route — `web/routes.py`
Keine Änderung. (Begründung siehe „Entscheidungen".)

### 3. Frontend — `web/static/js/app.js`
- `AGG_FUNCS` und der HAVING-Aggregat-Bau erhalten die zwei neuen Optionen mit eigenen Labels:
  `<option value="COUNT*">COUNT(*)</option>` und
  `<option value="COUNT DISTINCT">COUNT(DISTINCT)</option>`.
  (Da Token ≠ Label, kann `aggOptions()` nicht mehr aus reinem `AGG_FUNCS.map(f => <option>${f})`
  bauen — es braucht eine `{value,label}`-Liste, z. B. `AGG_OPTIONS = [{v:"COUNT",l:"COUNT"}, …,
  {v:"COUNT*",l:"COUNT(*)"}, {v:"COUNT DISTINCT",l:"COUNT(DISTINCT)"}]`, und der HAVING-Bau nutzt
  dieselbe Liste. Bestehende Tokens behalten Wert==Label.)
- **Spalten-Disable bei COUNT(*):** gemeinsamer Helfer
  ```javascript
  function wireAggColDisable(aggSel, colSel) {
    const sync = () => { colSel.disabled = (aggSel.value === "COUNT*"); };
    aggSel.addEventListener("change", sync); sync();
  }
  ```
  gewirkt an den fünf agg/col-Paaren: Start (`start_agg`/`start_col`), Ziel (`target_agg`/
  `target_col`), Extra-Zeile (`.c-agg`/`.c-col`), ORDER-BY-Zeile (`.ob-agg`/`.ob-col`), HAVING-Zeile
  (`.h-agg`/`.h-col`). Der deaktivierte Spaltenwert bleibt erhalten und wird weiter gesendet — kein
  Eingriff in `collectExtraSelects`/`collectOrderBy`/`collectHaving`/`collectJoinBody`.

## Rückwärtskompatibilität

`_ALLOWED_AGGS` wird nur erweitert; der Render-Helfer fällt für die fünf bestehenden Tokens auf
`f"{agg}({expr})"` zurück. Ohne die neuen Tokens ist das erzeugte SQL **zeichengleich** zu v0.42.0;
bestehende 296 Tests bleiben grün.

## Edge Cases

- **COUNT(*) als einzige SELECT-Spalte ohne Gruppenschlüssel:** `SELECT COUNT(*) FROM …` — gültige
  Ein-Zeilen-Zählung (kein GROUP BY), durch die bestehende Logik abgedeckt.
- **COUNT(*) an Start/Ziel:** zulässig; die Spalte wird ignoriert, die Tabelle ist ohnehin FROM-/
  Join-Tabelle.
- **HAVING COUNT(*) op n:** häufigster HAVING-Fall; Aggregat verpflichtend ist erfüllt (`COUNT*` ist
  ein gültiges Aggregat), Wert weiterhin parametrisiert (`:h{i}`).
- **COUNT(DISTINCT)** ist normal spaltengebunden — Spalten-Dropdown bleibt aktiv.

## Teststrategie

- **`tests/test_sqlgen.py`** — `COUNT*` rendert `COUNT(*)` (Spalte ignoriert) in SELECT; `COUNT DISTINCT`
  rendert `COUNT(DISTINCT col)`; beide auch in HAVING (`HAVING COUNT(*) > :h0`) und ORDER BY
  (`ORDER BY COUNT(*) DESC`); GROUP-BY-Ableitung mit einer `COUNT*`-Spalte (gruppiert nach der
  nicht-aggregierten Spalte); unverändertes SQL ohne die neuen Tokens; unbekanntes Aggregat weiterhin
  `ValueError`.
- **`tests/test_sqlgen_dialect.py`** — `COUNT(DISTINCT [dbo].[t].[c])` mit Quoting/Schema (MSSQL);
  `COUNT(*)` ist dialektunabhängig.
- **`tests/test_api.py`** — Route akzeptiert `COUNT*` und `COUNT DISTINCT` als `agg` auf
  start/target/extra, order_by und having; read-only Run-Pfad führt eine `COUNT(*)`-Gruppierung aus
  und liefert je-Gruppe-Zeilen.

## Architektur-Diagramme

Kein neues Modul und kein neuer Endpoint → Architektur-/Komponenten-Diagramme bleiben unverändert.
Release: Version-**Minor**-Bump (0.42.0 → 0.43.0), Changelog + Doc-Mirror, Roadmap/Board/Gantt (neues
AP namentlich enumeriert), „Bekannte Einschränkungen" in CLAUDE.md (COUNT(*)/COUNT(DISTINCT) erledigt;
offen: Cross-Schema-Joins), Test-Badge, Site-Build + gh-pages-Deploy.
