# Arbeitspakete — Lucent DB Explorer

Offene APs (erledigte wandern nach `todo-erledigt.md`).

## AP-3 — SQL-Optionen-Paket (Join-Builder)
Kleine, read-only + parametrisierte Erweiterungen der SQL-Generierung; jede als
optionales Bedienelement im Join-Builder.

- **DISTINCT** — Checkbox; `SELECT DISTINCT …` (entfernt Duplikate, die über
  n:m-Join-Pfade entstehen).
- **ORDER BY** — Spalte (aus den Pfad-Tabellen) + Richtung ASC/DESC.
- **LIMIT** — Zahl; begrenzt das generierte Join-SQL (analog zur Datenvorschau).
- **WHERE-Erweiterungen** zusätzlich zur bestehenden Operator-Allowlist:
  - `IS NULL` / `IS NOT NULL` (z. B. „VMs ohne zugewiesenes Netz")
  - `IN (…)` (Mehrfachwerte, z. B. `OS_Family IN ('Windows','Ubuntu')`)
  - `BETWEEN x AND y` (Bereiche, z. B. `VLAN BETWEEN 100 AND 200`)

**Betroffen:** `core/sqlgen.py` (Klauseln + parametrisierte Werte, Operator-/
Options-Validierung), `web/routes.py` (`/api/joinpath` nimmt die Optionen),
`web/static/js/app.js` (Bedienelemente im Join-Builder), Tests in
`tests/test_sqlgen.py` + `tests/test_api.py`. **Constraint:** weiterhin read-only,
Werte als Named-Placeholder, kein roher User-SQL.

## AP-4 — Mehrere SELECT-Spalten
Aktuell selektiert das generierte SQL nur Start- und Ziel-Spalte. Erweiterung:
beliebig viele Spalten aus den Tabellen entlang des Join-Pfads auswählbar.

- UI: Spalten-Mehrfachauswahl im Join-Builder (und idealerweise aus den
  AP-1-UML-Karten / dem Graph heraus — Klick fügt eine Spalte zur Auswahl hinzu).
- `SELECT t.col, …` über alle gewählten Spalten; Start/Ziel bleiben die
  Pfad-Endpunkte.

**Betroffen:** `core/sqlgen.py` (`selects` ist bereits eine Liste — UI/API
müssen mehrere liefern), `web/routes.py`, `web/static/js/app.js`, Tests.
