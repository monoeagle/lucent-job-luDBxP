# AP-70 — Oracle-Verbindung: SID *oder* Service-Name (+ Thin-Mode wahren)

**Datum:** 2026-07-02 · **Status:** Design (Review offen) · **Version-Ziel:** v0.68.0 (minor, neues Feature)

## Problem / Auslöser

Eine reale Ziel-DB (`Configdb`) ist **SID-adressiert** (`jdbc:oracle:thin:@host:port:SID`). Die
Verbindungsmaske kann bisher **nur Service-Name** → Reflection scheitert mit
`DPY-6001: Service "configdb" is not registered with the listener`. Nutzer sollen SID **oder**
Service-Name wählen können.

### Verifizierte Fakten (gegen echten Code/Verhalten, nicht geraten)

1. `core/connection.py::build_url` ist im Repo noch **Service-Name-only**; der vom Nutzer gezeigte
   „angepasste" Code ist ein Draft, **nicht gemergt**.
2. `app.py` enthält **kein** `oracledb.init_oracle_client(...)`. Der im Draft aufgetretene
   `DPY-4027 no configuration directory` stammt **allein aus dem Draft** (dieser Aufruf schaltet
   auf **Thick-Mode** und braucht ein Config-Verzeichnis). AP-70 fügt ihn **nicht** ein — Thin-Mode
   ist der Default (seit AP-53) und bleibt.
3. **SID-Kodierung empirisch geprüft** (`create_engine(url).dialect.create_connect_args`):
   - `…:1521/?sid=Configdb` (Draft) → **KAPUTT**: `dsn='host'`, `sid` als loses Kwarg.
   - `…:1521/Configdb` (SID im **Pfad**) → **KORREKT**: `(CONNECT_DATA=(SID=Configdb))`.
   - `…:1521/?service_name=XEPDB1` → korrekt: `(CONNECT_DATA=(SERVICE_NAME=XEPDB1))`.
   → **SID gehört in den URL-Pfad, nicht in die Query.**

## Scope (YAGNI)

**In Scope:** Oracle **Easy-Connect** SID- vs. Service-Name-Wahl in Maske, `build_url`, Persistenz,
Tests. **Out of Scope (→ AP-71):** TNS-Alias/`TNS_ADMIN`, Wallet/mTLS, MSSQL-Named-Instance, freie
Zusatz-Parameter. Kein `init_oracle_client` / kein Thick-Mode.

## Design

### Datenfluss
UI-Formular → `formParams()` `{db_type:"oracle", host, port, user, password, oracle_connect_type,
service_name, sid}` → `/api/connect` bzw. `/api/connections` → `build_url` → SQLAlchemy-Engine
(Thin) → Reflection.

### Komponente 1 — `core/connection.py::build_url` (Oracle-Zweig)
- Neuer Parameter `oracle_connect_type` ∈ {`"service"`, `"sid"`}; **Default = `"service"`**, wenn
  fehlend → **rückwärtskompatibel** zu gespeicherten Verbindungen (die tragen nur `service_name`).
- `service` → `oracle+oracledb://{auth}{host}:{port}/?service_name={quote_plus(svc)}` (unverändert).
- `sid` → `oracle+oracledb://{auth}{host}:{port}/{quote_plus(sid)}` (**Pfad-Form**, verifiziert).
- Validierung: leeres aktives Feld → klare deutsche `ValueError` („Service-Name fehlt." / „SID fehlt.").
- Ein unbekannter `oracle_connect_type` (≠ service/sid) → `ValueError`.

### Komponente 2 — `web/static/js/app.js` (`connFieldsHtml` / `formParams`)
- Oracle-Zweig rendert: **Verbindungsart**-Dropdown (Service-Name / SID) + **beide** Feld-Zeilen
  (`cf_service_name`, `cf_sid`), von denen die inaktive per `display:none` ausgeblendet ist (beide
  bleiben im DOM → Werte überleben das Umschalten, keine Re-Render-Logik nötig).
- Change-Handler am Dropdown togglet die Sichtbarkeit der beiden Zeilen.
- `formParams()` sendet immer `oracle_connect_type` + beide Werte (`service_name`, `sid`); `build_url`
  wählt anhand `oracle_connect_type`. Default-Auswahl im Dropdown = Service-Name.

### Komponente 3 — `web/routes.py::_CONN_FIELDS`
- Whitelist um `"sid"` + `"oracle_connect_type"` ergänzen, damit sie in gespeicherten Verbindungen
  persistieren (sonst gehen sie beim Speichern verloren).

### Fehlerbehandlung
Unverändert zu AP-64: `build_url`-`ValueError` und Treiberfehler kommen als **HTTP 400** mit echter
Meldung zurück; die Maske zeigt sie im Infofeld.

### Tests
- **`tests/test_connection.py`** (Unit, kein DB-Zugang — voll CI-grün):
  - `sid` → erwartete Pfad-URL (String-Assertion).
  - `service` explizit **und** ohne `oracle_connect_type` (Default) → Query-URL.
  - Fehlende SID / fehlender Service → `ValueError` mit deutschem Text.
  - Unbekannter `oracle_connect_type` → `ValueError`.
  - **DSN-Absicherung:** `create_engine(build_url(sid-params)).dialect.create_connect_args(...)`
    ergibt einen DSN, der `SID=` enthält (verhindert Regression zur kaputten `?sid=`-Form).
- **Live (skip-guarded):** `tests/test_oracle_integration.py` bleibt Service-Name-basiert (Oracle-XE
  spricht Service-Namen; SID-Connect gegen eine PDB ist umgebungsabhängig → keine erzwungene
  Live-SID-Prüfung; die DSN-Unit-Assertion ist die Garantie).
- **JS:** Playwright-Smoke — Dropdown umschalten zeigt das jeweils korrekte Feld (Projekt-Konvention:
  konkrete Interaktion rendern + Screenshot).

### Rückwärtskompatibilität
Gespeicherte Oracle-Verbindungen ohne `oracle_connect_type` funktionieren unverändert (Default
`service`). Keine Migration nötig.

## Release
`sync_version.py --minor` → **v0.68.0**; Changelog EN + DE-Mirror; icon-rail `APP_VERSION`/`TEST_COUNT`;
Roadmap-Status AP-70 → done (`roadmap_data.py` + `roadmap.md`-Prosa + `.mmd`-Klasse `done`); kennzahlen;
Site + gh-pages; Whole-Branch-Review (opus).

## Offene Punkte für den Review
- **Masken-Layout:** Design nimmt **Dropdown-togglet-ein-Feld** an (Alternativen: beide Felder immer
  sichtbar; Radio-Buttons). Änderbar.
