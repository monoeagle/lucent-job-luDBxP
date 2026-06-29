# Konzept & gestufte Scheibe — AP-63: Weitere DB-Objekt-Kategorien

**Datum:** 2026-06-28
**Status:** Stufe 1 (v0.52.0), Stufe 2 = Trigger (v0.53.0) + Stufe 2b = Sequences/Materialized Views (v0.54.0) + Stufe 3 = Procedures/Functions/Packages/Synonyms (v0.55.0) **erledigt**; offen: PG/Oracle-Trigger-Fast-Follow. (S2 wurde nach Testbarkeit zugeschnitten: Trigger zuerst, weil SQLite-CI-testbar; Sequences/Matviews als S2b, PG-only; S3 nur live testbar.)
**Auslöser:** Die Sidebar zeigt heute nur **Tabellen** und **Views** (`core.model.Schema` trägt nur diese zwei Sammlungen; `sqlalchemy_loader.py` reflektiert nur `get_table_names`/`get_view_names`). Eine SQL-Datenbank enthält mehr anzeigbare Objekte.

## Landkarte der anzeigbaren Objekte

**Eigenständige Schema-Objekte** (Geschwister von Tabellen/Views → Sidebar-Kategorien): Stored Procedures, Functions, Triggers, Sequences, Materialized Views, Synonyms (MSSQL/Oracle), Packages (Oracle), Custom Types/Domains/Enums.

**Tabellen-gebundene Objekte** (besser im Tabellen-Detail genestet, keine eigene Säule): Indizes, Constraints (PK/FK/Unique/**Check**/Default), Partitionen.

Zwei Realitäten prägen die Stufung:
1. **Engine-Abdeckung:** SQLite hat nur **Indizes + Trigger** — Sequences/Mat-Views/Procedures/Functions/Synonyms/Packages existieren dort nicht. Diese zählen für die echten Ziele **Oracle / PostgreSQL / MSSQL**.
2. **Reflektions-Aufwand:** SQLAlchemy liefert **Indizes, Check-Constraints, Sequences, Materialized Views** nativ (`get_indexes`/`get_check_constraints`/`get_sequence_names`/`get_materialized_view_names`). **Procedures, Functions, Triggers, Synonyms, Packages** brauchen **pro Dialekt eigene Katalog-Abfragen** (`information_schema.routines` für PG/MySQL/MSSQL; `ALL_PROCEDURES`/`ALL_TRIGGERS`/`ALL_SYNONYMS`/`ALL_OBJECTS` für Oracle).

Daraus folgt die Reihenfolge: erst die CI-testbaren, nativ reflektierbaren Objekte, zuletzt die dialekt-spezifischen, nur-live-testbaren Code-Objekte.

## Gemeinsame Architektur (alle Stufen)

Read-only, kein SQL-Generator-Bezug (diese Objekte nehmen **nicht** an Join-Pfaden teil — rein informativ/zum Browsen). Pro Stufe:
- `core/model.py::Schema` bekommt neue Sammlung(en) + ggf. neue Dataclass(es).
- `core/loaders/sqlalchemy_loader.py` reflektiert die Objekte (mit `try/except` + graceful Fallback, wenn der Dialekt sie nicht unterstützt — wie bei `uniques`/`uidx` heute).
- Sidebar (`web/static/js/app.js` ~Z.155-217) zeigt neue Kategorien bzw. das Tabellen-Detail wird angereichert; Info-Panel-Counts mitziehen.

## Stufe 1 — Tabellen-Detail anreichern: Indizes + Check-Constraints (genestet)

**Was:** Im Tabellen-Detail (Definition-Sub-Tab) **alle** Indizes (Name, Spalten, unique) und **Check-Constraints** auflisten. Heute werden nur *unique* Indizes gelesen (zur 1-1-Erkennung) und gar nicht angezeigt; Check-Constraints werden nie gelesen.
**Reflection:** SQLAlchemy nativ — `get_indexes()` (vorhanden) + `get_check_constraints()`. Alle Engines **inkl. SQLite**.
**Surface:** **keine** neue Sidebar-Kategorie — Anreicherung der bestehenden Detail-Ansicht.
**Testbar:** ✓ **SQLite** (Demo-CMDB um einen Index + Check-Constraint erweitern) → volle pytest-Abdeckung, CI-freundlich.
**Aufwand:** **S.** Risikoarm, etabliert das „mehr Objekte lesen + anzeigen" ohne Dialekt-SQL und ohne neues Sidebar-Konzept.

## Stufe 2 — Neue Sidebar-Kategorien: Sequences, Materialized Views, Triggers

**Was:** Drei neue Sidebar-Säulen (mit Count, analog Tabellen/Views) + einfache Detailansicht (Mat-View wie View: Spalten + Definition; Sequence: Name/Start/Increment soweit verfügbar; Trigger: Name + Tabelle + Definition).
**Reflection:** Sequences + Mat-Views via SQLAlchemy nativ; **Triggers** via leichte Pro-Dialekt-Abfrage (`sqlite_master` für SQLite, `information_schema.triggers` für PG/MySQL/MSSQL, `ALL_TRIGGERS` für Oracle).
**Surface:** etabliert das **„neue Sidebar-Kategorie"-Muster** (Model→Loader→Sidebar→Detail).
**Testbar:** Triggers ✓ in SQLite (Demo-CMDB-Trigger) → CI; Sequences/Mat-Views nur gegen **PostgreSQL** (Podman, skip-guarded) — SQLite hat sie nicht.
**Aufwand:** **M.**

## Stufe 3 — Programmierbarer Code: Stored Procedures + Functions (+ Oracle Packages, Synonyms)

**Was:** Sidebar-Kategorien für Procedures/Functions (Oracle zusätzlich Packages; MSSQL/Oracle Synonyms) + Detail mit **Quelltext/Definition**.
**Reflection:** **pro Dialekt** Katalog-SQL, read-only (`information_schema.routines` für PG/MySQL/MSSQL; `ALL_PROCEDURES`/`ALL_SOURCE`/`ALL_OBJECTS`/`ALL_SYNONYMS` für Oracle). Kapseln in eine kleine, pure Dialekt-Abfrage-Schicht.
**Testbar:** **nur live** gegen PostgreSQL/Oracle/MSSQL (Podman, skip-guarded). **Nicht** SQLite.
**Aufwand:** **L.** Größter Brocken; engine-spezifisch.

## Reihenfolge & Sequenzierung

```
Stufe 1 (Indizes/Check, SQLite-CI)  →  Stufe 2 (Sequences/Mat-Views/Triggers)  →  Stufe 3 (Procedures/Functions/Packages/Synonyms)
   risikoarm, voll testbar              Sidebar-Kategorie-Muster                  dialekt-SQL, nur live testbar
```

**Empfehlung:** Stufe 1 zuerst (kleinster, voll CI-testbarer Gewinn, kein Dialekt-SQL); Stufe 2 etabliert das Kategorie-Muster; Stufe 3 nur, wenn der Bedarf an Code-Objekt-Browsing real ist (engine-spezifisch + nur live verifizierbar). Die konkrete Anzeige/Darstellung je Objekttyp wird vor der jeweiligen Stufe ausgearbeitet (eigenes Brainstorm/Spec).

## Nicht im Scope

- Kein Ausführen von Procedures/Functions; nur Anzeige der Definition (read-only).
- Keine Teilnahme dieser Objekte an Join-Pfaden/SQL-Generierung.
- Partitionen, Scheduled Jobs/Events, Custom Types/Domains: bewusst zurückgestellt (Nische).
