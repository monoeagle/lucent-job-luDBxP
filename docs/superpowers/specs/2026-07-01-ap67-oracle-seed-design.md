# Design — AP-67·Oracle-Adaption · Slice 1: Oracle-Seed (Server-Demo-CMDB)

**Datum:** 2026-07-01
**Kontext:** LucentTools DB Explorer. AP-67 (Server-Demo-CMDB), Konzept
`docs/concepts/2026-06-30-oracle-demo-cmdb.md`. Die MSSQL-Grundlage ist seit v0.60.0 fertig
(`sample_data/seed_server_demo.py`, dialekt-dispatch mit MSSQL-Zweig; der `oracle`-Zweig ist ein
`NotImplementedError`-Stub). Diese Scheibe füllt den Oracle-Zweig und verifiziert ihn **live**
gegen einen echten Oracle-XE-Container.

> **Teil einer erweiterten AP-67-Initiative (zwei Scheiben, diese Session):** Slice 1 (hier) =
> Oracle-Seed. Slice 2 (eigene Spec danach) = Offline-Fixture-Vorschau (`Schema.to_dict/from_dict`,
> Schema-Snapshot aus der Reflektion, Fixture-Loader + Load-Dispatcher, „Oracle-Vorschau"-Verbindung,
> Graceful-No-Exec). Slice 1 liefert die reale Datenquelle, aus der Slice 2 den Snapshot generiert.

## Problem

Die mitgelieferte Demo ist **SQLite** und kann Oracle-spezifische Objektkategorien (Sequences,
Materialized Views, Packages, Procedures, Functions, Synonyms, PL/SQL-Trigger) prinzipiell nicht
enthalten — sie erscheinen im Sidebar-Tree nie. Es fehlt ein realistischer Oracle-Datensatz, der
die volle Oracle-Reflektion (AP-63·S1–S3 + Trigger-FF + AP-66·S1) demonstriert und die nur-live
testbaren Pfade manuell verifiziert.

## Scope

Nur `sample_data/seed_server_demo.py` (Oracle-Zweig) + Doku + ein skip-guardeter Live-Test.
**Kein Tool-/Reflektions-Code** — alle Reflektionspfade existieren; AP-67 liefert nur Daten. Das
Seed ist ein **externes Setup-Skript**, das das read-only-Werkzeug nie ausführt (Read-only-Invariante
unberührt).

## Objekt-Set (Oracle) — spiegelt den MSSQL-Seeder + Oracle-Spezifika

**5 Tabellen** (gleiche Struktur/Namen wie der MSSQL-Zweig, damit Join-Pfade/Diamond/Composite-FK/
Self-Referenz weiter greifen): `OperatingSystem`, `Datacenter`, `Cluster`, `Host`, `VirtualMachine`
mit den FKs (`Cluster→Datacenter`, `Host→Cluster`, `VirtualMachine→Host`, `VirtualMachine→OperatingSystem`).

**Oracle-spezifische Objekte** (jede eine eigene Sidebar-Kategorie):
- ≥1 `SEQUENCE` (`demo_vm_seq`),
- ≥1 `MATERIALIZED VIEW` (z. B. `mv_vm_per_host` — Aggregat je Host),
- ein `PACKAGE` (Spec + Body) mit je einer Function + Procedure (`pkg_vm`),
- eine standalone `FUNCTION` (`fn_vm_label`) + standalone `PROCEDURE` (`usp_vm_count`),
- ≥1 `SYNONYM` (`syn_vm` → `VirtualMachine`),
- ≥1 PL/SQL-`TRIGGER` (`trg_vm_audit` auf `VirtualMachine`),
- eine `VIEW` (`vw_vm_labeled`), die `fn_vm_label` aufruft → macht **AP-66·S1** (View→Routine) im Tree sichtbar.

Damit sind alle Oracle-Sidebar-Kategorien abgedeckt: Tabellen, Views, Sequences, Materialized Views,
Trigger, Procedures, Functions, Packages, Synonyms.

## Oracle-Besonderheiten (vs. MSSQL-Zweig)

- Datentypen `NUMBER` / `VARCHAR2(n)` statt `INT` / `NVARCHAR`.
- **Kein `IF EXISTS`** → Drop je Objekt als eigener anonymer Block:
  `BEGIN EXECUTE IMMEDIATE 'DROP <kind> <name>'; EXCEPTION WHEN OTHERS THEN NULL; END;`
  Reihenfolge: abhängige zuerst (View, Materialized View, Synonym, Trigger, Package, Function,
  Procedure, Sequence), dann Tabellen in FK-sicherer Reihenfolge.
- `CREATE OR REPLACE` für PL/SQL-Objekte (Function/Procedure/Package/Trigger/View) — Idempotenz auch
  ohne Drop; Sequence/Matview/Tabellen brauchen den Drop-first-Weg.
- **Einzeilige INSERTs** — Oracle kennt kein Multi-Row-`VALUES (),()`. Je Zeile ein `INSERT`.
- **Kein `dbo.`-Präfix** — Objekte landen im Schema des Connect-Users (`demo`).
- **PL/SQL-Blöcke als je ein `execute()`** ohne abschließendes `/` (das `/` ist ein SQL*Plus-Terminator,
  kein Teil des Statements; `oracledb`/SQLAlchemy führt einen Block direkt aus).
- `AUTOCOMMIT` wie im MSSQL-Zweig (`create_engine(url, isolation_level="AUTOCOMMIT")`).

## Struktur im Seeder

Analog zu den `_MSSQL_*`-Listen: `_ORACLE_DROPS`, `_ORACLE_TABLES`, `_ORACLE_DATA`, `_ORACLE_OBJECTS`
(jedes Statement ein eigener String). Der `oracle`-Zweig in `seed()` ersetzt den `NotImplementedError`
durch die Ausführung dieser Listen in Reihenfolge (Drops → Tables → Data → Objects), Statement für
Statement über `conn.execute(text(stmt))`.

## Bring-up-Doku

`sample_data/server-demo-README.md` um einen **Oracle**-Abschnitt ergänzen:
- podman-Befehl: `podman run -d --name oracle-luDBxP -p 1521:1521 -e ORACLE_PASSWORD=<pw>
  -e APP_USER=demo -e APP_USER_PASSWORD=demo docker.io/gvenzl/oracle-xe:21-slim-faststart`
- Seed-Aufruf: `./venv/bin/python sample_data/seed_server_demo.py 'oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1'`
- Connection-String für die App + `LUCENT_ORACLE_TEST_URL`-Hinweis für den Live-Test.

## Test

Ein skip-guardeter Integrationstest analog `tests/test_mssql_integration.py`, gesteuert über
`LUCENT_ORACLE_TEST_URL`: seedet die Demo und reflektiert sie über den `SqlAlchemyLoader`, dann
Assertions, dass **jede** Oracle-Objektkategorie erscheint (Tabellen inkl. FKs, View, Sequence,
Materialized View, Trigger, Procedure, Function, Package, Synonym) inkl. der AP-66·S1-View→Routine-
Verknüpfung (`vw_vm_labeled` referenziert `fn_vm_label`). Ohne gesetzte URL → `skip`. Die volle
Suite bleibt ohne Oracle grün.

## Verifikation

**Live** gegen den laufenden Container `oracle-luDBxP` (`gvenzl/oracle-xe:21-slim-faststart`,
Oracle 21c XE, `demo/demo @ localhost:1521/XEPDB1`): Seed ausführen, App gegen die Oracle-URL
verbinden, im Sidebar-Tree prüfen, dass **alle** Kategorien erscheinen; der skip-guardete Test läuft
mit gesetzter `LUCENT_ORACLE_TEST_URL` grün (`PASSED`, nicht `skipped`).

## Randbedingungen

- Read-only-Invariante: das Seed ist externes Setup, nicht vom Tool ausgeführt.
- Deutsch für neue Doku/Kommentare (Code-Kommentare wie bestehend englisch möglich).
- Kein Auto-Provisioning ohne Nutzer-Opt-in (Container-Bring-up bleibt ein bewusster, dokumentierter Schritt).

## Betroffene Dateien

- `sample_data/seed_server_demo.py` — `_ORACLE_*`-Listen + `oracle`-Zweig in `seed()`.
- `sample_data/server-demo-README.md` — Oracle-Bring-up-Abschnitt.
- `tests/test_oracle_seed_integration.py` (neu) — skip-guardeter Kategorien-Test, eigene Datei analog
  `tests/test_mssql_integration.py` (die bestehende `test_oracle_integration.py` prüft nur Basis-Reflektion
  und bleibt unangetastet).
