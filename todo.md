# Arbeitspakete — LucentTools DB Explorer

Offene APs (erledigte wandern nach `todo-erledigt.md`).
Zuletzt erledigt: AP-9, AP-11, AP-10, AP-13. Offen hier: **AP-12** und **AP-15**
sowie der **Linux/AppImage-Rest von AP-14**.

**Definition of Done (jedes AP):** Code + Tests grün · betroffene Doku aktualisiert
(CLAUDE.md + Zensical-Doku) · `sync_version.py`-Versionsbump + CHANGELOG · AP nach
`todo-erledigt.md` umhängen · AP-Diagramm + Site **auf Linux** neu bauen.

---

## AP-12 — MSSQL real testbar machen
**Backend UMGESETZT (v0.9.0):**
- [x] **ODBC Driver 18 als Default** + `Encrypt`/`TrustServerCertificate`-Parameter in der Connection-URL; Treibername überschreibbar (`core/connection.py::_mssql_query`)
- [x] **Klare Fehlermeldung bei fehlendem Treiber** (AP-2-Stil, statt roher pyodbc-Exception) — `_odbc_driver_hint` im Loader (IM002 / „no default driver" / „Can't open lib")
- [x] Setup-Doku in `grundlagen/installation.md` (Driver 18, TrustServerCertificate, überschreibbar)
- [x] Tests: Default-Driver 18, Custom-Driver + Encrypt/Trust, Treiber-Hinweis-Erkennung (118 grün, gegen SQLite)

**Noch offen (braucht echte MSSQL-Instanz / heute Abend Linux):**
- [ ] System-ODBC real einrichten (`unixODBC` + `msodbcsql18` Linux; ODBC Driver 18 Windows)
- [ ] Optionaler Integrationstest gegen lokale MSSQL-Instanz (markiert, überspringbar wenn Treiber fehlt)
- [ ] UI: MSSQL-Felder für `Encrypt`/`TrustServerCertificate` im Verbindungs-Tab (aktuell nur via API/`config.json` setzbar)

## AP-14 — Python-3.14-Readiness (Wheel-ABI cp312 → cp314)
**Analyse:** Von 20 Wheels sind 15 plattformunabhängig (`py3-none-any`) und 3.14-tauglich.
Blockierend waren **5 kompilierte cp312-Wheels** (CPython-3.12-ABI):
`sqlalchemy 2.0.51` (Core), `greenlet 3.5.2` (transitiv via SQLAlchemy),
`markupsafe 3.0.3` (transitiv via Jinja2/Werkzeug), `psycopg2-binary 2.9.12` (PostgreSQL),
`pyodbc 5.3.0` (MSSQL). Auf 3.14 lädt der Interpreter `cp312`-Wheels nicht → `cp314`-Builds nötig.

**Stand 2026-06-26 — Windows-Pfad UMGESETZT & verifiziert:**
- [x] cp314-win_amd64-Wheels für alle 5 Pakete existieren auf PyPI in **identischer Version** (kein Upgrade nötig) — gezogen & ins Wheelhouse eingespielt; alte cp312 entfernt
- [x] `run.ps1`-Gate auf 3.14 (Kommentar Z27, Find-Python Z31-33 `@('3.14')`, Fehlermeldung Z42); `run.sh` pick_python um `python3.14` vorangestellt
- [x] `wheels/README.md` von 3.12 → 3.14 (inkl. `pip download`-Beispiel mit `--abi cp314`)
- [x] Python 3.14.6 via winget installiert; venv neu gebaut, offline-Install aus wheels/ ✓, `pip check` sauber, alle 5 C-Extensions importieren, **111 Tests grün**, App startet (HTTP 200)
- [x] **psycopg2-Risiko entschärft:** cp314-Wheel existiert bereits (kein psycopg3-Fallback nötig)

**Wheel-Strategie-Optimierungen — geprüft 2026-06-26:**
- [x] ~~greenlet weglassen~~ **verworfen:** SQLAlchemy 2.0.51 deklariert greenlet als **harte** Dependency auf AMD64/win (`Requires-Dist: greenlet>=1; platform_machine=="AMD64"…` — nicht nur `asyncio`-Extra), `pip show` listet es als `Requires`. `pip install -r requirements.txt` (run.ps1/run.sh) zieht es daher immer mit; Weglassen ginge nur über `--no-deps` + manuelle Dep-Liste (bricht das Offline-Setup). 240 KB Ersparnis rechtfertigt das nicht.
- [x] ~~SQLAlchemy als `py3-none-any`~~ **verworfen:** macht nur SQLAlchemy versionsunabhängig; markupsafe/psycopg2/pyodbc/greenlet bleiben cp-spezifisch und binden das Wheelhouse weiter an genau eine Python-Version (die `run.ps1` ohnehin erzwingt) → kein praktischer Gewinn, aber Verlust der C-Speedups. Echte „ein Wheelhouse für alle 3.x"-Unabhängigkeit gäbe es erst mit komplettem Treiberwechsel (pg8000 / python-tds / markupsafe-sdist) = eigenes größeres AP.

**Noch offen:**
- [ ] Optional: explizite Lock-/Constraints-Datei mit exakten Versionen (Reproduzierbarkeit; requirements.txt hat aktuell nur `>=`-Untergrenzen)
- [ ] **Linux/AppImage-Pfad auf 3.14:** `run.sh _bundle_python_standalone` bundelt System-Python → auf der Linux-Build-Maschine 3.14 bereitstellen und AppImage gegen 3.14 bauen (Windows-Wheelhouse gilt dort nicht)
- [ ] Abschluss: `sync_version.py` (Versionsbump) + CHANGELOG + AP nach `todo-erledigt.md` + AP-Diagramm (auf Linux neu bauen)
- [ ] Betroffen (erledigt): `wheels/`, `wheels/README.md`, `run.ps1`, `run.sh` · (offen): `requirements.txt`, ggf. `core/connection.py`

## AP-15 — `run.sh` & `run.ps1` abbruchsicher + idempotent machen
**Ziel:** Egal an welcher Stelle ein vorheriger Lauf abgebrochen wurde (Strg-C, Fehler,
halbes venv, halber pip-Install) — der nächste Lauf erkennt den Zustand, zieht fehlende
Prereqs nach und führt **idempotent** zum sauberen Ergebnis. Jeder Schritt meldet seinen Status.

**Stand 2026-06-26 — `run.ps1` (Windows) UMGESETZT & verifiziert:**
- [x] **Prereq-Check pro Schritt** (Python, venv-Integrität, Paket-Vollständigkeit, Port) vor jeder Aktion
- [x] **venv-Integrität statt nur Existenz** (`Test-VenvHealthy`: `python -c import sys`); kaputtes/halbes venv wird automatisch neu gebaut
- [x] **Idempotenter, selbstheilender Install:** `pip check` erkennt unvollständige Installation und repariert; Stamp erst nach Erfolg (atomar)
- [x] **NO-CDN / nur lokale Sourcen:** Install strikt `--no-index` aus `wheels\`; **--dry-run-Vorabprüfung** listet fehlende Wheels und steigt mit **Protokoll** aus — KEINE (Teil-)Installation, kein Online-Nachladen
- [x] **Statusausgabebereich:** durchgängige Helfer `_ok`/`_warn`/`_info`/`_hdr`/`_fail`
- [x] **Port-/Instanz-Check** vor App-Start (5057 belegt → klare Abbruch-Meldung)
- [x] **Robustes Menü** (`_fail` beendet das Menü nicht mehr; try/catch)
- [x] Verifiziert: idempotenter Lauf · fehlender Stamp (Selbstheilung) · fehlendes Wheel (Protokoll + Abbruch) · Port belegt

**Noch offen — `run.sh` (Linux, heute Abend):**
- [ ] `run.sh` mit identischer Logik spiegeln (venv-Integrität, idempotent + `pip check`, Status-Helfer, Port-Check via `ss`/`lsof`); **Parität** halten
- [ ] **`run.sh`-Fehler nicht mehr verschlucken:** `do_start`/`do_skip_setup` enden auf `|| true` → Exit-Code sauber durchreichen
- [ ] **NO-CDN auf Linux:** braucht ein **Linux-Wheelhouse** (manylinux-cp314); die aktuellen `wheels/` sind `win_amd64`. Quelle/Strategie auf Linux entscheiden
- [ ] Funktionale Verifikation beider Skripte auf Linux (simulierte Abbrüche)
- [ ] Betroffen: `run.sh` (· `run.ps1` erledigt)

## AP-17 — Delivery-Verzeichnis bereinigen
- [ ] Ein Auslieferungs-Verzeichnis, das **nur** enthält, was zum Betrieb explizit benötigt wird
- [ ] **Keine Rückschlüsse auf Claude-/AI-Einsatz** (keine CLAUDE.md, Handoffs, `.pattern`, Insights, AI-Spuren im Delivery)
- [ ] Abgrenzen: was gehört ins Delivery vs. nur ins Entwickler-Repo

## AP-19 — `.pattern_transfer` (projektlokale Pattern sammeln)
- [ ] Verzeichnis `.pattern_transfer` im Projekt: Sammelstelle für Pattern, die im aktiven Projekt entstehen
- [ ] In einer globalen Claude-Session werden alle projektlokalen Pattern eingesammelt und — wo sinnvoll — ins globale `.pattern` zusammengeführt

## AP-22 (Frage) — Implizite FKs immer aktivieren?
- [ ] Klären: macht es Sinn, implizite FKs **standardmäßig** zu aktivieren? Was spricht dagegen?
- [ ] Abwägung: mehr Join-Pfade out-of-the-box vs. falsch-positive (geratene) Beziehungen, die zu fragwürdigen Joins führen können

## AP-24 (Frage) — Session-KPIs erheben & dokumentieren?
- [ ] Erheben wir beim Sessionwechsel bereits KPIs für dieses Projekt? (vgl. `docs/session-kennzahlen.md`)
- [ ] Sind diese KPIs Teil der (Projekt-)Dokumentation?
- [ ] Falls lückenhaft: KPI-Erhebung beim Handoff festlegen + in die Doku aufnehmen

## AP-25 — Tool: SQL-Statement-Analyzer (read-only Analyse)
**Idee:** Neuer Tab, in dem der Nutzer ein beliebiges SQL-Statement in ein Freitextfeld
einfügt; das Tool **analysiert** es (egal ob lesend, schreibend oder Update) und zeigt
die **Auswirkungen**, **ohne irgendeine Aktion auf der DB auszuführen** (strikt read-only,
passt zur Projekt-Grundausrichtung). Ziel: einschätzen, was ein Statement täte.
- [ ] Neuer Tab „SQL-Analyzer" mit Freitextfeld zum Einfügen eines Statements
- [ ] Statement parsen/analysieren (SELECT/INSERT/UPDATE/DELETE/DDL, Views) — **keine** Ausführung auf der DB
- [ ] Im Graphenbereich die **beteiligten Tabellen markieren** (geändert / beteiligt unterscheiden)
- [ ] Bei Joins den **Pfad markieren** (wie im Join-Builder)
- [ ] Button **„an Join-Builder übertragen"** → wechselt zum Join-Builder, füllt die Felder und zeigt die Alternativen
- [ ] Views sowie eigene/fremde Statements analysieren können, nur zur Wirkungsabschätzung
- [ ] **Brainstorm:** wie lässt sich das AP weiter sinnvoll gestalten (für den Einsatzzweck)?
      Ideen: betroffene Spalten/PK-FK hervorheben · geschätzte Treffermenge (EXPLAIN read-only, falls vertretbar) ·
      Warnungen (fehlendes WHERE bei UPDATE/DELETE, kartesische Joins) · Lesbarkeits-/Formatierungs-Ansicht ·
      Abhängigkeiten einer View aufzeigen
- [ ] Technik prüfen: SQL-Parser (z. B. `sqlglot`/`sqlparse`) lokal gebündelt (NO-CDN); Tabellen-/Join-Extraktion → Graph-Highlight wiederverwenden
- [ ] Betroffen: neue `core/`-Analyse (Parser), `web/routes.py` (read-only Analyse-Endpoint), `web/static/js/app.js`, `index.html`

## AP-29 — SQL-Dialekt umschalten (Oracle, MSSQL, PostgreSQL, MySQL, SQLite)
**Frage/Recherche:** Gibt es syntaktische und elementare Unterschiede im generierten
read-only SELECT je Datenbank-Typ — und lohnt sich ein Dialekt-Umschalter?
- [ ] Unterschiede sichten: Zeilenbegrenzung `LIMIT n` (Postgres/MySQL/SQLite) vs. `TOP n` (MSSQL) vs. `FETCH FIRST n ROWS ONLY` / `ROWNUM` (Oracle); Identifier-Quoting `"…"` (Standard/Oracle/Postgres) vs. `[…]` (MSSQL) vs. `` `…` `` (MySQL); Schema-/Owner-Präfix; Case-Sensitivity der Bezeichner
- [ ] Ziel: Dropdown zur Dialektwahl → `core/sqlgen` rendert dialektabhängig (mind. LIMIT/TOP/FETCH + Identifier-Quoting); Default-Dialekt evtl. aus der aktiven Verbindung ableiten
- [ ] Technik prüfen: `sqlglot` lokal gebündelt (NO-CDN) zum Transpilieren — **Überschneidung mit AP-25** (SQL-Analyzer), evtl. gemeinsam lösen
- [ ] Betroffen: `core/sqlgen.py`, `web/static/js/app.js`/`index.html` (Dialekt-Dropdown), ggf. `core/connection.py`

## AP-30 (Frage) — 1-N: ein Start, mehrere Zieltabellen in einem SELECT?
- [ ] Frage: Gibt es den sinnvollen Fall, in **einem** SELECT von **einer** Start-Tabelle zu **mehreren** Ziel-Tabellen zu joinen (Stern-/1-N-Abfrage)?
- [ ] Heute: genau **eine** Start- und **eine** Ziel-Tabelle (linearer Pfad); Zusatzspalten + Filter-Tabellen werden eingewebt, aber **kein** zweites unabhängiges Ziel (vgl. AP-18-Abgrenzung)
- [ ] Abwägung: Mehrwert (breitere Abfrage in einem Schritt) vs. Komplexität (mehrere Pfade vereinen, Mehrdeutigkeit, kartesische Risiken bei 1-N-Fan-out)
- [ ] Falls sinnvoll: als **Join-Baum** mit mehreren Ziel-Ästen modellieren (analog zum bestehenden Filter-Tabellen-Weaving in `find_paths`)
- [ ] **Erkenntnis (Anwendungsfälle):** wertvoll v. a. für **N-1-Äste** (Stern-/Report-Abfrage: Start zieht Attribute aus mehreren Eltern-/Lookup-Tabellen, z. B. VM + Host-Name + OS-Name + VLAN) — kein Zeilen-Fan-out. Mehrere **1-N-Kind**-Äste gleichzeitig blähen quasi-kartesisch auf → eher **warnen** statt anbieten

## AP-31 — Terminal-Server-Tauglichkeit (Multi-User)
**Frage:** Läuft die App korrekt für **mehrere gleichzeitige** Nutzer auf einem (RDS-)Terminal-Server?
**Befund — Single-User pro Maschine: ja; gleichzeitige Mehrbenutzung: aktuell NEIN.**
- [ ] **Fester Port 5057 auf gemeinsamem Loopback:** Windows-RDS teilt `127.0.0.1` über alle Sessions → zweite Instanz kann 5057 nicht binden (run.ps1 bricht mit „Port belegt" ab); fremder Browser auf `127.0.0.1:5057` erreicht die fremde Instanz (keine Session-Isolation)
- [ ] **Gemeinsame `config.json`** (Default- + gespeicherte Verbindungen) im App-Verzeichnis → Nutzer überschreiben sich gegenseitig
- [ ] **Gemeinsames `Logs/`** → konkurrierende Schreibzugriffe
- [ ] **Flask-Dev-Server** (`app.run`) ist kein Mehrbenutzer-Produktionsserver
**Nötig für Multi-User:**
- [ ] **Pro-Session dynamischer Port** (freien Port wählen + URL dem Nutzer anzeigen) statt fix 5057
- [ ] **Pro-Nutzer `config.json` + `Logs/`** (z. B. `%LOCALAPPDATA%\<AppName>\`) statt App-Verzeichnis
- [ ] Session-Isolation prüfen (RDS-Loopback geteilt) — pro Nutzer getrennte Ports; ggf. Bind-Strategie dokumentieren
- [ ] Optional: lokaler WSGI-Server (z. B. `waitress`, NO-CDN-konform) statt Flask-Dev-Server
- [ ] Betroffen: `config.py` (Port/Pfade), `app.py` (Port-Wahl), `core/settings.py` (config.json-Pfad), Logging-Pfad
**Hinweis:** read-only begrenzt den Schaden (keine DB-Mutation); Verbindungen werden ohne Passwort gespeichert.
