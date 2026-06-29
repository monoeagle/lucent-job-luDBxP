# Insight — Skip-guarded „nur-live"-Tests echt fahren: ein gecachtes Container-Image findet, was Naht-Tests strukturell nicht sehen

**Datum:** 2026-06-30 (Session 16)
**Kontext:** AP-63·S3 / Trigger-FF / AP-67 — DB-Objekt-Reflektion, die nur gegen echte Server-DBs (PG/Oracle/MSSQL) läuft; in CI nur skip-guarded.

## Beobachtung

Die ganze Reflektions-Serie (Procedures/Functions/Packages/Synonyms/Sequences/Trigger) war
durch **Naht-Tests** (Monkeypatch-Loader + konstruiertes Schema) und **SQLite-Unit-Tests** CI-grün —
alle Tests passierten. Die eigentlichen Pro-Dialekt-Katalog-SQL-Pfade liefen dabei **nie**.

Als der Nutzer fragte „können wir nicht gegen unsere MSSQL-Instanz testen?", habe ich den
**podman-MSSQL-Container neu aufgesetzt** (Image war gecacht → in ~30 s oben) und die
skip-guarded Tests mit gesetzter `LUCENT_MSSQL_TEST_URL` echt gefahren. Das fand **sofort**:

1. **Einen realen Loader-Crash** (→ v0.55.1): `insp.get_unique_constraints()`/`get_indexes()`
   werfen auf MSSQL ein **bare `NotImplementedError`** (kein `SQLAlchemyError`) → der ganze
   `load()` crashte, **MSSQL war gar nicht reflektierbar** — entgegen der „verifiziert"-Doku. Kein
   einziger der grünen Naht-/SQLite-Tests konnte das sehen (sie berühren die echte SQLAlchemy-
   Inspector-API nicht). Fix: `except (SQLAlchemyError, NotImplementedError)` + CI-Regressionstest.
2. **Einen Doku-Bug**: die Projekt-Doku behauptete „MSSQL-Sequences = leer". Live: `get_sequence_names()`
   liefert sie sehr wohl. „Verifiziert"-Aussagen ohne Live-Lauf altern zu Fehlinformation.
3. **Bestätigung** des S3-/Trigger-FF-/AP-67-Katalog-SQL gegen die echte Engine (inkl. AP-66·S1
   View→Routine an einem echten View).

## Lehre

**Naht-Tests sichern die Verdrahtung, nicht die Katalog-Query-Korrektheit.** Wenn ein Backend
**billig hochziehbar** ist (Image gecacht, ~30 s), ist „skip-guarded, läuft nur live" **keine
Ausrede, es nicht zu fahren** — genau dieser Lauf findet, was die grünen Tests strukturell nicht
sehen können (echte Dialekt-API-Eigenheiten, echte Katalog-Spalten, Doku-vs-Realität).

Das ist die **Ergänzung** zum Naht-Test-Insight (`2026-06-29-scheiben-nach-testbarkeit-und-naht-tests.md`):
- Backend **nicht** verfügbar → synthetische Daten an der Naht injizieren (Naht-Test).
- Backend **billig verfügbar** (gecachtes Image) → **echt hochziehen und fahren**, bevor man „verifiziert" sagt.

## How to apply

- Skip-guarded Integrationstest geschrieben? Prüfen, ob das Backend per gecachtem Container
  bring-up-bar ist (`podman images | grep`). Wenn ja: **vor dem Release einmal echt fahren**
  (`LUCENT_*_TEST_URL=… pytest …`), nicht auf „skippt grün" verlassen.
- Bei Reflektion gegen die SQLAlchemy-Inspector-API: Methoden, die nicht jeder Dialekt
  implementiert (`get_unique_constraints`/`get_indexes`/`get_check_constraints`/…), **immer**
  `except (SQLAlchemyError, NotImplementedError)` fangen — bare `NotImplementedError` ist kein
  `SQLAlchemyError`.
- „Verifiziert gegen X" in der Doku ist nur wahr, solange es **gefahren** wird; bei Treiber-/
  SQLAlchemy-Upgrades neu prüfen.

## Begleit-Reibung (auch notiert in der Reflektions-Memory)

**Veraltete laufende App-Instanz.** Mehrfach lief beim „App starten / Screenshot prüfen" noch eine
**alte Instanz** (Python/Route/Analyzer-Änderungen wirken erst nach Neustart) — der Nutzer sah
veralteten Stand und schloss auf einen Bug, der real schon gefixt war. **Vor jeder Live-Demo
`/api/info`-Version prüfen + neu starten** (alte killen: `ss -ltnp | grep 5057`). Screenshots können
veralteten Code zeigen.

Etabliert 2026-06-30, nachdem ein 30-Sekunden-Container-Lauf einen kompletten MSSQL-Reflektions-
Crash + einen Doku-Bug aufdeckte, die über mehrere grüne Releases unbemerkt waren.
