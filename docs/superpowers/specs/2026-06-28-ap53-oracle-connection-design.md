# AP-53: Verbindung gegen Oracle-DB

**Datum:** 2026-06-28
**Status:** Design abgenommen

## Ziel

Oracle als **Verbindungs-Backend** ergänzen: live verbinden und das Schema
reflektieren. Bisher existiert Oracle nur als **SQL-Generierungs-Dialekt**
(`core/sqlgen.py` `ORACLE`, `FETCH FIRST`); ein Verbindungsaufbau ist nicht
implementiert (kein Treiber, kein `oracle`-Eintrag in `core/connection.py`,
Oracle fehlt im Verbindungsformular). Diese AP schließt die Verbindungs-Lücke.

## Entscheidungen (Brainstorming)

- **Treiber:** `python-oracledb` im **Thin-Mode** (reines Python, kein Oracle
  Instant Client; SQLAlchemy-Prefix `oracle+oracledb`). Offline-bündelbar.
- **Adressierung:** nur **Service-Name** (modern, 12c+/PDBs) — kein SID, kein TNS.
- **Scope:** Connect + Reflektion. SQL-Generierung ist bereits vorhanden und
  **nicht** Teil dieser AP.
- **Oracle-System-Schema-Filter** in `list_schemas` ist **Teil dieser AP**.

## Architektur / betroffene Schichten

```
Verbindungsformular (db_type=oracle, host, port, service_name, user, pw)
  → /api/connect → core/connection.build_url → oracle+oracledb://…/?service_name=…
  → SqlAlchemyLoader(url).load([schema]) reflektiert (python-oracledb thin)
list_schemas(): Oracle-System-Schemas herausgefiltert
```

Read-Only-Constraint und Layering (`core/` Flask-frei) bleiben unberührt.

## Komponenten / Änderungen

### 1. Dependency
- `requirements.txt`: `oracledb>=2.0` (Kommentar: Oracle-Treiber, Thin-Mode,
  kein Client nötig).
- Offline-Wheelhouse: das plattformspezifische Wheel (cp314/win_amd64) für das
  Windows-Offline-Ziel in `wheels/` aufnehmen — konsistent mit
  `psycopg2_binary`/`pyodbc`. Auf Linux greift der adaptive Online-Fallback
  (`run.sh::install_requirements`). Die exakte Wheel-Plattform-Natur wird im
  Plan verifiziert (oracledb liefert Plattform-Wheels, kein `py3-none-any`).

### 2. `core/connection.py`
- `_DRIVERS["oracle"] = "oracle+oracledb"`.
- `_DEFAULT_PORTS["oracle"] = 1521`.
- Oracle-Sonderzweig in `build_url` (analog der MSSQL-Behandlung): Oracle nutzt
  **Service-Name** statt Datenbank-Pfad. Erforderlich: `host`, `service_name`.
  Ergebnis:
  `oracle+oracledb://<user>:<pw>@<host>:<port>/?service_name=<service>`
  (User/Passwort URL-enkodiert wie bisher; `service` URL-enkodiert). Fehlt
  `service_name`, klare `ValueError` („Service-Name fehlt.").

### 3. `core/loaders/sqlalchemy_loader.py`
- `_SYSTEM_SCHEMAS` um die gängigen **Oracle-System-Schemas** erweitern
  (Großschreibung, wie Oracle sie liefert), u. a.: `SYS`, `SYSTEM`, `XDB`,
  `OUTLN`, `DBSNMP`, `APPQOSSYS`, `CTXSYS`, `MDSYS`, `ORDSYS`, `ORDDATA`,
  `OLAPSYS`, `WMSYS`, `LBACSYS`, `DVSYS`, `AUDSYS`, `GSMADMIN_INTERNAL`,
  `DBSFWUSER`, `REMOTE_SCHEDULER_AGENT`, `SYS$UMF`, `GGSYS`, `ANONYMOUS`,
  `XS$NULL`. Best-effort/kuratierte Liste; dokumentiert als nicht vollständig.

### 4. Persistenz / Routes (`web/routes.py`)
- `_CONN_FIELDS` um `service_name` erweitern (wird gespeichert). Passwort wird
  weiterhin **nie** persistiert.

### 5. Frontend (`web/static/js/app.js`)
- `DB_TYPES` += `{ v: "oracle", label: "Oracle" }`.
- `PORT_DEFAULTS.oracle = 1521`.
- `connFieldsHtml` Oracle-Zweig: Host · Port (1521) · **Service-Name** ·
  Benutzer · Passwort (kein „Datenbank"-Feld; stattdessen `cf_service_name`).
- `formParams` (Oracle): `{db_type:"oracle", host, port, service_name, user, password}`.
- Prefill (`connFieldsHtml(c)`) und Speichern übernehmen `service_name`.

## Tests

- **Unit (immer grün):** in den Connection-Unit-Tests ein Oracle-Fall für
  `build_url`:
  `build_url({db_type:"oracle", host:"h", service_name:"XEPDB1", user:"u", password:"p"})`
  → `oracle+oracledb://u:p@h:1521/?service_name=XEPDB1`; sowie Fehlerfall ohne
  `service_name` (`ValueError`).
- **Loader:** Unit-Test, dass `list_schemas` Oracle-System-Schemas filtert
  (z. B. eine Kandidatenliste mit `SYS`/`SYSTEM`/`XDB` + ein Nutzer-Schema →
  nur das Nutzer-Schema bleibt; via direktem Test des Filters bzw. einer
  Hilfsfunktion, da SQLite keine Oracle-Schemas liefert).
- **Integration, skip-guarded** (analog `tests/test_mssql_integration.py`):
  `tests/test_oracle_integration.py` läuft nur, wenn `LUCENT_ORACLE_TEST_URL`
  gesetzt ist; sonst `pytest.skip`. Verbindet, reflektiert, prüft mind. eine
  Tabelle.
- Bestehende Suite bleibt grün.

## Doku / Release

- `CLAUDE.md` „Bekannte Einschränkungen": Oracle jetzt verbindbar (skip-guarded
  Integrationstest via `LUCENT_ORACLE_TEST_URL`), analog zur MSSQL-Formulierung;
  Thin-Mode/Service-Name nennen.
- Architektur-`referenz-architektur-3.mmd`: DB-Knoten um „Oracle" ergänzen.
- CHANGELOG (englisch) + Mirror (deutsch), Badges (`icon-rail.js`),
  `zensical.toml`, Site-Build.
- Version **minor** via `sync_version.py --minor` → v0.39.0.
- SDD-Final-Review; Push/gh-pages nur auf Nutzer-Ansage.

## Nicht-Ziele / bewusste Grenzen

- Kein SID, kein TNS-Alias, kein Easy-Connect-Freitextfeld (nur Service-Name).
- Kein Thick-Mode / Instant Client.
- Keine Änderung an der bestehenden Oracle-SQL-Generierung.
- Der Oracle-System-Schema-Filter ist eine kuratierte Liste (nicht garantiert
  vollständig über alle Oracle-Editionen/Versionen).
