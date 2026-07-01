# Reflektion grün heißt nicht, dass das generierte SQL round-trippt

**Datum:** 2026-07-01 (Session 17)
**Kontext:** AP-67 (Oracle-Server-Demo) + Slice 2a (reiches ~37-Tabellen-Schema). Ein einziger,
real hochgezogener Oracle-21c-XE-Container (podman) legte über die Session **fünf** echte Bugs
offen, die grüne Unit-Tests und skip-guarded „nur-live"-Tests strukturell nie sahen.

## Beobachtung

Session 16 lehrte bereits: *einen echten Container hochziehen findet, was Naht-Tests nicht sehen*
(MSSQL-Reflektions-Crash). Session 17 schärft das an einer zweiten Achse:

**Dass die Reflektion (Schema-Lesen) grün ist, sagt nichts darüber, ob das vom Tool *erzeugte*
SQL gegen dieselbe DB läuft.** Die Bugs saßen alle *hinter* der Reflektion — im ausgeführten SQL:

1. **Reserviertes Wort** `CLUSTER` → `CREATE TABLE Cluster` scheitert (ORA-00903). Fand der
   Container beim ersten Seed-Versuch.
2. **Connect-Flow:** gespeicherte Passwort-DBs ließen sich über das Header-Dropdown gar nicht
   verbinden (passwortloser Versuch → ORA-01017, kein „Verbinden"-Knopf im Tab). Fand der Nutzer.
3. **Daten-Vorschau:** `SELECT … LIMIT n` — Oracle kennt kein `LIMIT` (ORA-00933) **und** der
   quoted-lowercase-Reflektions-Name traf das uppercase-Objekt nicht (ORA-00942). Fand der Nutzer.
4. **Stale Test-Namen:** der Integrationstest prüfte alte Slice-1-Objektnamen, die die reiche
   Demo umbenannt/gedroppt hatte. Fand der Live-Test-Lauf (nicht die grüne Suite — der Test war
   skip-guarded).
5. **Generiertes SQL, Casing:** `Dialect.quote()` quotete Bezeichner immer → auf Oracle über
   **drei** Pfade (Join-Ausführung, `/api/distinct`, Subset-Export) ORA-00942. Fand der Nutzer.

## Zwei Lehren

**(a) Beim Anbinden eines neuen Backends jeden generierten-SQL-Ausführungspfad gegen die echte
DB fahren — nicht nur die Reflektion.** Vorschau, Join-Ausführung, Filter-Distinct, Subset-Export
sind eigene SQL-Erzeugungspfade; jeder kann eigene Dialekt-Fallen (LIMIT-Syntax, Identifier-Casing,
reservierte Wörter) haben. „Alle Kategorien reflektieren" ist ein **Teil**-Beweis.

**(b) Dialekt-/Casing-Bugs clustern an einer geteilten Quelle — dort fixen, nicht pro Symptom.**
Bug 5 wirkte wie drei Bugs (Join, Distinct, Subset), war aber **eine** Stelle (`Dialect.quote()`);
eine Korrektur (SQLAlchemy-Preparer „quote-if-needed" für Oracle) reparierte alle drei. Vorher
prüfen: *teilen sich die Symptome eine Rendering-Funktion?* Dann ist der Fix eine Zeile, nicht drei.

**(c) Eine reiche Demo ist selbst ein Bug-Detektor.** Erst das große ~37-Tabellen-Schema mit
vielen Join-Pfaden brachte den Nutzer dazu, jeden Ausführungspfad anzufassen — jeder Klick fand
den nächsten latenten Casing-Bug. Ein 5-Tabellen-Demo hätte die drei generierten-SQL-Pfade nie so
gründlich belaufen.

## Konsequenz

- Bei Backend-Arbeit eine **Ausführungspfad-Checkliste** gegen den echten Container: Preview ·
  Join-Run · Distinct · Subset (count/dump/inlist) — je einmal live, nicht nur Reflektion.
- Vor einem Per-Symptom-Fix: **greppen, ob die Symptome eine gemeinsame Quelle teilen** (hier
  `Dialect.quote`/`.qualify`/`.table_ref`), und dort einmal fixen + Offline-Regressions-Test.
- Round-Trip von reflektierten Bezeichnern ist eine eigene Invariante: reflektierter Name →
  generiertes SQL → dieselbe DB muss ihn wieder auflösen (Oracle: lowercase-reflektiert →
  **unquoted** rendern, nicht quoted).
