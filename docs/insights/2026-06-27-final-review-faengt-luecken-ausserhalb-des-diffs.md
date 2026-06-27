# Insight — Der Final-Whole-Branch-Review fängt Integrationslücken *außerhalb* des Task-Diffs

**Datum:** 2026-06-27 (Session 8) · Kontext: AP-31- und AP-34-Kern via Subagent-Driven Development (SDD)

## Erkenntnis

Per-Task-Reviews sind **diff-skopiert** — der Reviewer sieht nur den Diff *seiner* Aufgabe und
prüft Spec-Konformität + Qualität dieses Ausschnitts. Der **Final-Whole-Branch-Review (opus)**
liest dagegen den **breiteren Code rund um den Branch** und fängt genau die Klasse von Fehlern,
die kein Task-Review sehen kann: **die Feature-Scheibe wird durch *bestehenden* Code außerhalb
ihres Diffs entwertet.**

Zwei Belege diese Session:

- **AP-31 (Multi-User):** Alle 6 Task-Reviews waren grün. Der Final-Review las `run.sh`/`run.ps1`
  (die der Plan §6 ausdrücklich „nicht ändern" wollte) und fand: beide Launcher **brechen bei
  belegtem Port ab** — der gerade gebaute dynamische Port-Fallback in `app.py` wird auf dem
  *dokumentierten* Startweg also **nie erreicht**. Die Spec-Annahme „keine Launcher-Änderung
  nötig" war falsch (ein „Spec gegen echten Code prüfen"-Miss). Meine eigene E2E-Verifikation
  hatte das maskiert, weil sie `app.py` **direkt** startete und den Guard umging.
- **AP-25 (frühere Session):** dieselbe Mechanik — der Final-Review fing 3 echte Bugs
  (PG/MSSQL-500, NO_WHERE-Subquery, UNKNOWN_COLUMN-Case), die die **SQLite-only-Tests**
  maskierten.

## Warum (How to apply)

1. **Den Final-Review niemals weglassen** — auch wenn alle Task-Reviews grün sind. Sein Wert
   liegt nicht in der Wiederholung der Task-Prüfung, sondern im **Lesen außerhalb des Diffs**:
   Aufrufer, Launcher, Start-/Deploy-Pfade, plattformübergreifende Annahmen.
2. **Eigene E2E-Smokes prüfen den echten Auslieferungspfad**, nicht eine Abkürzung. Wer das
   Feature über einen Direktaufruf testet (`app.py` statt `run.sh`), umgeht genau die Stelle,
   die der Nutzer trifft. → E2E so nah wie möglich am realen Start.
3. **Plan-Annahmen „X muss nicht geändert werden" sind Hypothesen**, keine Fakten — der
   Final-Review (oder ein gezielter Blick in den Aufrufer) muss sie verifizieren.

## Übergeordnet

Das ist die Review-Phasen-Variante von „immer prüfen, nie raten" bzw. „Spec gegen den echten
Code prüfen": **Task-Reviews sichern die Bausteine, der Final-Review sichert die Integration in
den bestehenden Code.** Beide Stufen sind nötig; die teurere opus-Stufe verdient sich ihren
Preis genau an den Stellen, die der enge Diff-Blick strukturell nicht sehen kann.
