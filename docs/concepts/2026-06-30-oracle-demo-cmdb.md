# Konzept & Arbeitspaket — Oracle-Demo-CMDB (AP-67)

**Datum:** 2026-06-30
**Status:** MSSQL-Grundlage erledigt (v0.60.0); Oracle-Adaption erledigt (v0.64.0, live gegen Oracle 21c XE verifiziert). Slice 2a (reiches Oracle-Schema, ~37 Tab) erledigt (v0.65.0). Slice 2b („Offline-Fixture-Vorschau ohne DB") **verworfen** (2026-07-01, off-mission — Tool verbindet sich mit echten DBs).
**Auslöser:** Nutzerwunsch — *„oracle_demo cmdb, damit wir auch im Tree alle Oracle-spezifischen Sachen zu sehen sind."* Die mitgelieferte SQLite-Demo kann die Oracle-spezifischen Objektkategorien (Sequences, Materialized Views, Packages, Procedures, Functions, Synonyms) **prinzipiell nicht** enthalten — sie erscheinen im Sidebar-Tree daher nie.

## 1. Problem

Das Werkzeug ist ein Reverse-Engineering-/Migrationstool für die **HCMX-Ablösung**, die auf **Oracle** läuft. Über mehrere APs wurde die Oracle-Reflektion ausgebaut:

- **AP-63·S1** Indizes + Check-Constraints, **S2** Trigger, **S2b** Sequences + Materialized Views, **S3** Procedures/Functions/Packages/Synonyms,
- **AP-63·Trigger-FF** PG/Oracle/MSSQL-Trigger,
- **AP-66·S1** Views → referenzierte Routinen.

All das ist **read-only reflektierbar**, aber die mitgelieferte Demo ist **SQLite** — und SQLite kennt keine Sequences, Materialized Views, Stored Procedures/Functions, Packages oder Synonyms. Wer das Tool ohne eigene Oracle-DB ausprobiert, sieht diese Kategorien **nie**. Es fehlt ein realistischer Datensatz, der die volle Oracle-Reflektion demonstriert — sowohl als **Showcase** als auch zur **manuellen Verifikation** der nur-live testbaren Pfade (die heute nur skip-guarded automatisiert getestet sind).

## 2. Code-Befund (Ist-Stand verifiziert)

- `sample_data/build_demo_db.py` baut die portable **SQLite**-Demo (`sample_data/demo_cmdb.db`): eine VMware-artige Datacenter-CMDB. Aktuell reflektiert: **13 Tabellen, 2 Views, 1 Trigger, 0 Sequences / 0 Matviews / 0 Routines / 0 Synonyms** (empirisch geprüft). Nur stdlib (`sqlite3`).
- Die gebündelte Verbindung **„Demo"** ist eine gespeicherte Connection, die auf die SQLite-Datei zeigt (Frontend setzt sie als Default, `web/static/js/app.js`).
- **Oracle ist verbindbar seit AP-53**: `oracle+oracledb://user:pw@host:1521/?service_name=XEPDB1` (python-oracledb Thin-Mode); skip-guardeter Live-Test `tests/test_oracle_integration.py` (`LUCENT_ORACLE_TEST_URL`).
- **Oracle hat kein portables Einzeldatei-Format** (anders als SQLite) → eine Oracle-Demo lässt sich **nicht als Datei bündeln**; sie braucht eine laufende Instanz (Container) + ein Seed-Skript.

## 3. Was ich tun würde (gestuft)

**Stufe 1 — Oracle-Seed-Skript (Kern, größter Nutzen):**
- Ein idempotentes Seed (analog `build_demo_db.py`, aber SQL/PL-SQL für Oracle), das die **gleiche CMDB-Tabellenstruktur** wie die SQLite-Demo anlegt (damit Join-Pfade, der „Diamond", Composite-FK, Self-FK, No-Path-Tabelle weiter greifen) **plus** Oracle-spezifische Objekte:
  - ≥1 `SEQUENCE`, ≥1 `MATERIALIZED VIEW`,
  - ein `PACKAGE` (Spec + Body) mit je einer Function + Procedure,
  - eine standalone `FUNCTION` + `PROCEDURE`,
  - ≥1 `SYNONYM` (auf eine Tabelle),
  - ≥1 PL/SQL-`TRIGGER`,
  - eine `VIEW`, die eine der Functions aufruft → macht **AP-66·S1** (View→Routine) im Tree sichtbar.
- Drop-if-exists am Anfang (Oracle hat kein `IF EXISTS` → per-Objekt `BEGIN … EXCEPTION …`-Muster wie in den Oracle-Integrationstests).
- Ablage z. B. `sample_data/oracle/seed_oracle_cmdb.sql` (+ optional ein Python-Runner).

**Stufe 2 — Bring-up dokumentieren:**
- podman/docker **Oracle XE** (analog zum MSSQL-Container, der in Session 16 bereits einen realen Reflektions-Bug aufdeckte). `sample_data/oracle/README.md`: Container-Start, Seed-Ausführung, Connection-String, plus Hinweis auf `LUCENT_ORACLE_TEST_URL` für den Live-Test.
- Optional eine gespeicherte **„Oracle-Demo"**-Verbindung (zeigt auf den lokalen Container), damit sie wie „Demo" im Dropdown auswählbar ist.

**Stufe 3 (optional) — One-command-Bring-up:**
- Ein Skript/`run.sh`-Helfer, der den Container startet, das Seed einspielt und die Verbindung registriert — für „in 30 s die volle Oracle-Reflektion sehen" (vgl. die in Session 16 etablierte podman-MSSQL-Routine).

## 4. Nicht-Scope

- **Kein gebündeltes portables Oracle-File** — gibt es nicht; die Demo bleibt container-/instanzgebunden.
- **Kein Auto-Provisioning ohne Nutzer-Opt-in** — der Oracle-XE-Image-Download ist groß; Bring-up ist ein bewusster Schritt.
- **Read-only-Invariante unberührt** — das Seed ist ein einmaliges *Setup*-Skript **außerhalb** des Tools (manuell ausgeführt), nicht vom Werkzeug selbst. Das Tool liest die Demo weiterhin nur.

## 5. Aufwand, Abhängigkeit, Sequenzierung

- **Stufe 1:** **M** — Seed-Skript schreiben + **manuell gegen einen Oracle-XE-Container verifizieren** (alle Kategorien erscheinen im Tree). Die CMDB-Tabellen können aus `build_demo_db.py` übernommen/übersetzt werden.
- **Stufe 2:** **S** — Doku + optional gespeicherte Verbindung.
- **Stufe 3:** **S–M** — Bring-up-Automatisierung.
- **Abhängigkeit:** Oracle-Verbindung existiert (AP-53); die Reflektion aller Objektkategorien existiert (AP-63·S1–S3 + Trigger-FF, AP-66·S1). AP-67 liefert **nur die Daten**, kein neuer Reflektions-Code.

**Empfehlung:** **Stufe 1 zuerst** — das Seed-Skript ist der eigentliche Wert (zeigt die komplette Oracle-Reflektion an einem realistischen CMDB) und verifiziert nebenbei manuell die nur-live-Pfade, die bisher nur skip-guarded getestet sind. Bring-up-Doku (Stufe 2) direkt danach, damit es reproduzierbar ist.
