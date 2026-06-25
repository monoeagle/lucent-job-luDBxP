# Insight 2026-06-25 — Lucent DB Explorer: Aufbau (Session 1)

Nicht-offensichtliche Erkenntnisse aus dem Aufbau von v1 + Erweiterungen
(Join-Pfad-Tool: „Wie komme ich von Tabelle A zu B?").

## 1. Filter-Einwebung ist ein Baum, kein linearer Pfad
Die ursprüngliche Plan-Logik webte Filter-Tabellen durch **Anhängen an die
lineare Knotenfolge** ein. Das erzeugt bei einem Anker, der nicht das Pfad-Ende
ist, **Duplikat-Tabellen** → ungültiges SQL (`JOIN X … JOIN X …`). Der
Task-Review fing es vor Task 7. Korrekte Lösung: Pfad als **Join-Baum** —
jeder Step joint eine *neue* Tabelle an eine *bereits enthaltene*. Test-Invariante:
`len(tables) == len(set(tables))` und „left already seen, right new". Lehre:
Eine geratene/gebaute Pfadfolge muss gegen die SQL-Semantik validiert werden,
nicht nur gegen „findet einen Pfad".

## 2. Flask cached Templates, nicht static
`render_template("index.html")` cached das kompilierte Template im Speicher →
**Template-Änderungen brauchen Server-Neustart**. `static/` (app.js, app.css)
wird dagegen pro Request frisch vom Dateisystem gelesen. In der Iteration hieß
das: JS/CSS-Edits sofort sichtbar (Browser-Reload reicht), HTML-Edits nicht.
Mehrfach Zeit gekostet, bis das Muster klar war.

## 3. `let` auf Skript-Ebene ≠ `window.X`
`let CY = …` auf Top-Level eines klassischen `<script>` erzeugt **keine**
`window.CY`-Property (anders als `var`). Playwright-Checks auf `window.CY`
liefen ins Timeout, obwohl die App funktionierte. Fix: bewusster Debug-Hook
`window.CY = CY;` — nützlich auch in der Browser-Konsole.

## 4. Verifikation der JS-UI: Playwright aus dem System-Python
pytest testet das Backend, aber **nicht das Frontend-JS**. Das echte Ende-zu-Ende-
Verhalten (Tabs, Filter-Einwebung, Graph-Highlight, Verbindungsformular) wurde
mit **Playwright (System-`python3`, nicht das venv)** gefahren — die Browser
lagen unter `~/.cache/ms-playwright`. Das fand reale Bugs (z. B. das gecachte
alte Template, den `window.CY`-Stolperstein) und lieferte aussagekräftige
Screenshots statt nur „Endpoint antwortet 200".

## 5. Implied Foreign Keys = der SchemaSpy-Hebel für CMDBs
Die größte Wirkung pro Aufwand: nicht-deklarierte FKs **raten** (Spaltenname
trifft einspaltige PK einer anderen Tabelle, Typ kompatibel). CMDB-/Inventar-DBs
deklarieren oft *keine* FKs — ohne implied bleibt der Graph leer (0 Kanten),
mit implied entstehen Join-Pfade. Konservative Heuristik (Name-auf-PK) hält die
Fehltreffer klein; im Graph **gestrichelt** dargestellt, damit „geraten" sichtbar bleibt.

## 6. Treiber-Realität: pip ≠ lauffähig (MSSQL)
`psycopg2-binary` (Postgres) und `PyMySQL` sind reine Wheels → sofort nutzbar.
`pyodbc` (MSSQL) **importiert**, braucht zur Laufzeit aber **System-ODBC**
(`unixODBC` + `msodbcsql17`) — nicht per pip lösbar. Konsequenz: MSSQL im UI
anbieten, aber mit klarer Fehlermeldung statt Absturz, und die System-
Voraussetzung dokumentieren.

## 7. PowerShell `&` löst relative Programmpfade nicht auf
In `run.ps1` scheiterte `& venv\Scripts\python.exe` mit „not recognized" —
PowershSells `&`-Operator sucht relative Programmpfade in `$PATH`, nicht im CWD.
Fix: Pfade über `Join-Path $PSScriptRoot` **absolut** verankern. Der Linux-`pwsh`
hat den Windows-Bug aufgedeckt (Parser + Ausführung).

## 8. Read-only-Prinzip bewusst nuanciert
v1-Constraint war „führt **nie** SQL aus". Der „Daten"-Tab (SQL-Developer-Stil)
bricht das **bewusst**: read-only `SELECT … LIMIT`, Objektname **gegen das
Schema validiert** (Allow-Liste) → kein Injection. Das generierte *Join*-SQL
wird weiterhin nie ausgeführt. Lehre: Ein hartes Prinzip darf nuanciert werden,
wenn der neue Pfad eng kontrolliert und getestet ist (Test mit `x'; DROP TABLE …`).
