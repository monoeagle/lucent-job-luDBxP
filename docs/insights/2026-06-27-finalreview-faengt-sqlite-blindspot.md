# Insight 2026-06-27 — Die finale Whole-Branch-Review fängt, was SQLite-only-Tests maskieren

**Session 6 (Linux), AP-30 (N-1-Stern) + AP-25 (SQL-Analyzer), v0.16.0 → v0.18.0.**

## Kern-Erkenntnis

Beide Features liefen im Subagent-Driven-Development (SDD) mit grünen Per-Task-Reviews
durch — und trotzdem fand die **finale opus-Whole-Branch-Review** bei AP-25 **drei echte
Defekte**, die alle Per-Task-Gates und die komplett grüne Suite passiert hatten:

1. **Critical — HTTP 500 für PostgreSQL/MSSQL im Analyzer.** Die Route übergab den
   Projekt-Dialektnamen (`"postgresql"`/`"mssql"`) an sqlglot, das nur `"postgres"`/`"tsql"`
   kennt und `ValueError` wirft; `analyze()` fing nur `SqlglotError`. **Maskiert, weil
   jeder Analyzer-Test SQLite nutzt.**
2. **Important — `NO_WHERE` False-Negative.** `node.find(exp.Where)` durchsucht den ganzen
   AST → ein **Subquery**-WHERE unterdrückte die Warnung bei einem top-level-WHERE-losen
   UPDATE/DELETE. Fix: `node.args.get("where")` (eigene Klausel).
3. **Important — `UNKNOWN_COLUMN` False-Positive.** Tabellen-Abgleich case-insensitiv,
   Spalten-Abgleich (`has_column`) case-sensitiv → widersprach der dokumentierten
   Case-Insensitivität.

## Warum das zählt

- **Der teuerste Review-Schritt verdient seinen Preis.** Eine 100 % grüne Suite ist kein
  Beweis für Korrektheit, wenn die Tests nur einen Backend-Pfad abdecken. Die finale
  Review auf dem fähigsten Modell, die den ganzen Branch adversarisch gegen die Spec prüft
  (und sqlglot empirisch anfasste), war hier den Aufwand wert.
- **SQLite-only-Tests sind ein bekannter Blindspot des Projekts** (PostgreSQL/MySQL/MSSQL
  sind via SQLAlchemy implementiert, aber nur SQLite ist automatisiert getestet). Jedes
  Feature, das einen Dialekt an eine Bibliothek durchreicht, braucht entweder eine
  Dialekt-Mapping-Unit (ohne DB testbar) oder Nicht-SQLite-Abdeckung.

## Wiederkehrendes Prozess-Muster (zweite Session in Folge)

Cheap-Tier-Subagenten (**haiku**) lassen beim deutschen nutzerseitigen Text **zuverlässig
das schließende typografische Anführungszeichen `“` (U+201C) fallen** und ersetzen es durch
ASCII `"` — exakt wie in AP-30 (Task 4). Der Subagent-Report behauptete jeweils Korrektheit.
**Konsequenz:** Bei `„ … “`-Texten aus Subagent-Output die committeten Bytes selbst
verifizieren (`grep … | python3 -c "print(sorted(hex(ord(c)) …))"` → muss `0x201e` **und**
`0x201c` enthalten). Einzelzeichen-Unicode-Korrektur ist zuverlässiger vom Controller
manuell als per erneutem Subagent-Round.

## Doku-Drift-Nachtrag

`zensical.toml` (`site_description`) trägt die Version **manuell** und wird von
`sync_version.py` nicht erfasst — stand nach AP-25 noch auf v0.17.0 (vom Task-7-Reviewer
fälschlich als ok gemeldet). Vor jedem gh-pages-Deploy `index.html` auf die Version
gegenprüfen. Außerdem: **Architektur-Diagramme** (`referenz-architektur-1/-3.mmd`) müssen
bei neuem core-Modul/Endpoint mitgezogen werden — leicht zu vergessen. Beides jetzt in
`[[ludbxp-release-deploy-steps]]` (Memory) festgehalten.
