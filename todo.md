# Arbeitspakete — LucentTools DB Explorer

Offene APs (erledigte wandern nach `todo-erledigt.md`).
Zuletzt erledigt: **AP-43** (lesbares mehrzeiliges SQL-Layout, v0.26.0), **AP-44** (Join-Builder kompakter + NULL-Hervorhebung + Status-Kopfzeile, v0.27.0). Offen: **AP-45** (Spaltenkopf-Aktionen + Filter-Dropdown mit echten DISTINCT-Werten).

**Definition of Done (jedes AP):** Code + Tests grün · betroffene Doku aktualisiert
(CLAUDE.md + Zensical-Doku) · `sync_version.py`-Versionsbump + CHANGELOG · AP nach
`todo-erledigt.md` umhängen · AP-Diagramm + Site **auf Linux** neu bauen.

---

## AP-35 — `run.ps1`: leeres venv gilt fälschlich als „vollständig" (Folgefund aus AP-15)
**Bezug:** beim Linux-Spiegeln in AP-15 entdeckt — dieselbe latente Schwäche steckt in `run.ps1`.
- [ ] `Test-RequirementsInstalled` prüft nur `pip check`; das ist auf einem frisch gebauten,
      paketleeren venv **vacuously grün**. Mit noch passendem `.req_stamp` würde der Install
      übersprungen (App crasht beim Import). Fix wie in `run.sh`: zusätzlich das tatsächliche
      Vorhandensein der `requirements.txt`-Distributionen prüfen (`importlib.metadata`).
- [ ] **Constraint:** `run.ps1` ist signiert → ASCII + UTF-8-BOM-Pattern beachten (PS 5.1),
      nicht blind mit dem Edit-Tool bearbeiten. Eigene Windows-Session.

## AP-19 — `.pattern_transfer` (projektlokale Pattern sammeln)
- [ ] Verzeichnis `.pattern_transfer` im Projekt: Sammelstelle für Pattern, die im aktiven Projekt entstehen
- [ ] In einer globalen Claude-Session werden alle projektlokalen Pattern eingesammelt und — wo sinnvoll — ins globale `.pattern` zusammengeführt

## AP-25 — Tool: SQL-Statement-Analyzer (read-only Analyse) ✓ v0.18.0 (Scheibe 1)
**Idee:** Neuer Tab, in dem der Nutzer ein beliebiges SQL-Statement in ein Freitextfeld
einfügt; das Tool **analysiert** es (egal ob lesend, schreibend oder Update) und zeigt
die **Auswirkungen**, **ohne irgendeine Aktion auf der DB auszuführen** (strikt read-only,
passt zur Projekt-Grundausrichtung). Ziel: einschätzen, was ein Statement täte.
Design-Spec: `docs/superpowers/specs/2026-06-27-ap25-sql-analyzer-design.md` · Plan: `docs/superpowers/plans/2026-06-27-ap25-sql-analyzer.md`
- [x] Neuer Tab „SQL-Analyzer" mit Freitextfeld zum Einfügen eines Statements
- [x] Statement parsen/analysieren (SELECT/INSERT/UPDATE/DELETE/DDL, Views) — **keine** Ausführung auf der DB
- [x] Im Graphenbereich die **beteiligten Tabellen markieren** (geändert / beteiligt unterscheiden)
- [ ] Bei Joins den **Pfad markieren** (wie im Join-Builder) — **spätere Scheibe**
- [ ] Button **„an Join-Builder übertragen"** → wechselt zum Join-Builder, füllt die Felder und zeigt die Alternativen — **spätere Scheibe**
- [ ] Views sowie eigene/fremde Statements analysieren können (View-Abhängigkeiten) — **spätere Scheibe**
- [x] **Brainstorm (Scheibe 1):** Warnungen (WRITE_STATEMENT, NO_WHERE, CARTESIAN_JOIN; mit Verbindung UNKNOWN_TABLE/UNKNOWN_COLUMN) umgesetzt.
      Deferred: geschätzte Treffermenge (EXPLAIN read-only) — **spätere Scheibe**; Abhängigkeiten einer View — **spätere Scheibe**
- [x] Technik: `sqlglot` lokal gebündelt (NO-CDN); Tabellen-/Join-Extraktion → Graph-Highlight wiederverwenden
- [x] Betroffen: neue `core/sqlanalyze.py` (Parser), `web/routes.py` (read-only `/api/analyze`-Endpoint), `web/static/js/app.js`, `index.html`

## AP-30 — N-1-Stern-Abfrage (ein Start, mehrere Lookup-Ziele) ✓ v0.17.0
**Entschieden 2026-06-26 (war Frage):** Umsetzen — aber zugeschnitten auf den **N-1-Stern-Fall**; eigenes Feature-AP, Umsetzung separat (nicht jetzt).
Design-Spec: `docs/superpowers/specs/2026-06-27-ap30-n1-stern-design.md` · Plan: `docs/superpowers/plans/2026-06-27-ap30-n1-stern.md`
- [x] **Scope = N-1-Stern:** Start zieht Attribute aus mehreren **Eltern-/Lookup-Tabellen** (z. B. VM + Host-Name + OS-Name + VLAN) — **kein** Zeilen-Fan-out, ein erweiterter Report in einem SELECT
- [x] Modell: **Join-Baum** mit mehreren Ziel-Ästen (analog zum Filter-Tabellen-Weaving in `find_paths`)
- [x] **1-N-Kind-Äste** (mehrere absteigende Ziele): nicht anbieten bzw. **vor quasi-kartesischem Fan-out warnen**
- [x] Betroffen: `core/pathfinder.py`, `core/sqlgen.py`, `web/static/js/app.js`/`index.html` (mehrere Ziel-Zeilen)

## AP-31 — Terminal-Server-Tauglichkeit (Multi-User)
**Frage:** Läuft die App korrekt für **mehrere gleichzeitige** Nutzer auf einem (RDS-)Terminal-Server?
**Befund — Single-User pro Maschine: ja; gleichzeitige Mehrbenutzung: aktuell NEIN.**
- [ ] **Fester Port 5057 auf gemeinsamem Loopback:** Windows-RDS teilt `127.0.0.1` über alle Sessions → zweite Instanz kann 5057 nicht binden (run.ps1 bricht mit „Port belegt" ab); fremder Browser auf `127.0.0.1:5057` erreicht die fremde Instanz (keine Session-Isolation)
- [ ] **Gemeinsame `config.json`** (Default- + gespeicherte Verbindungen) im App-Verzeichnis → Nutzer überschreiben sich gegenseitig
- [ ] **Gemeinsames `Logs/`** → konkurrierende Schreibzugriffe — *Hook vorhanden seit AP-33: `LUCENT_LOG_DIR` setzt den Logpfad pro Nutzer; hier nur noch verdrahten (z. B. `%LOCALAPPDATA%`)*
- [ ] **Flask-Dev-Server** (`app.run`) ist kein Mehrbenutzer-Produktionsserver
- [ ] **Port-Lebensdauer:** Port 5057 bleibt für die **gesamte Laufzeit** des Server-Prozesses gebunden und wird erst vom OS freigegeben, wenn der Prozess endet (Strg+C / Fenster schließen / Prozess beenden / Session-Ende) — **kein** Idle-Timeout. Browser schließen ≠ Port frei. Auf RDS blockiert ein „vergessener" laufender Prozess die anderen Nutzer
**Nötig für Multi-User:**
- [ ] **Pro-Session dynamischer Port** (freien Port wählen + URL dem Nutzer anzeigen) statt fix 5057
- [ ] **Pro-Nutzer `config.json` + `Logs/`** (z. B. `%LOCALAPPDATA%\<AppName>\`) statt App-Verzeichnis
- [ ] Session-Isolation prüfen (RDS-Loopback geteilt) — pro Nutzer getrennte Ports; ggf. Bind-Strategie dokumentieren
- [ ] Optional: lokaler WSGI-Server (z. B. `waitress`, NO-CDN-konform) statt Flask-Dev-Server
- [ ] Betroffen: `config.py` (Port/Pfade), `app.py` (Port-Wahl), `core/settings.py` (config.json-Pfad), Logging-Pfad
**Hinweis:** read-only begrenzt den Schaden (keine DB-Mutation); Verbindungen werden ohne Passwort gespeichert.

### Brainstorm — vollständiger Maßnahmenkatalog (Terminalserver-Tauglichkeit)
**1. Server-Binding / Port (Kernproblem)**
- [ ] **Pro-Session dynamischer Port:** Port `0` binden → OS vergibt freien Port; gewählten Port ermitteln und dem Nutzer anzeigen/Browser automatisch öffnen
- [ ] Alternativ Port-Range/Offset pro Session; Kollision von 5057 auf geteiltem RDS-Loopback vermeiden
- [ ] Weiter nur an `127.0.0.1` binden (kein `0.0.0.0`) — kein Zugriff von außen
- [ ] Optional **Session-Token** in der URL, damit ein anderer Nutzer den fremden Port nicht „errät" (read-only mindert das Risiko, aber sauberer)

**2. Pro-Nutzer-Daten statt App-Verzeichnis**
- [ ] `config.json` (Default- + gespeicherte Verbindungen) nach `%LOCALAPPDATA%\LucentTools DB Explorer\` pro Nutzer
- [ ] `Logs/` pro Nutzer am selben Ort (Bezug AP-33)
- [ ] `.req_stamp`/State pro Nutzer; App-Verzeichnis als **read-only** behandeln (Program Files → keine Schreibrechte)

**3. Produktions-Server statt Flask-Dev**
- [ ] `waitress` (rein lokal, NO-CDN, als Wheel ins Wheelhouse) statt `app.run()` → multithread-stabil, keine Dev-Warnung, kein Reloader

**4. Prozess-Lebenszyklus / Port-Freigabe**
- [ ] Sauberes Beenden (Port wird erst bei Prozess-Ende frei — siehe oben); „Stop"-Aktion / Tray
- [ ] **Idle-Shutdown:** Server beendet sich nach X Minuten ohne Requests → gibt Port + RAM frei (RDS-freundlich)

**5. Mehrere Instanzen nebeneinander / Deployment**
- [ ] **Shared venv read-only** (Admin richtet einmal ein); Nutzer nur `skip-setup`/`start`, kein Schreibzugriff ins venv
- [ ] Installation nach Program Files (read-only) + signierte `run.ps1` (AllSigned); Startmenü-Verknüpfung pro Nutzer

**6. Ressourcen & Betrieb**
- [ ] Lastabschätzung: N Nutzer × je 1 Python-Prozess (RAM/CPU); Idle-Shutdown begrenzt das
- [ ] Doku „Betrieb auf Terminalserver" (Admin-Setup, Pro-Nutzer-Pfade, Ports)

**Risiko/Aufwand:** Punkte 1+2 sind die Pflicht-Basis (sonst Kollisionen); 3+4 erhöhen Robustheit; 5+6 sind Deployment/Betrieb. Schätzung: mittel-groß, am besten als eigener Meilenstein.

## AP-34 — Tray-Icon-Launcher (versteckte Konsole, sauberes Beenden, Auto-Browser)
**Ziel:** Der Programmstart zeigt **keine** sichtbare `run.ps1`-Konsole mehr, sondern ein
**Tray-Icon**. Darüber wird die Instanz gesteuert; der Browser (Chrome) öffnet sich beim
ersten Start automatisch, sobald der Webserver steht.
- [ ] **Tray-Icon** beim Start (statt sichtbarer Konsole); Kontextmenü mit:
  - [ ] **Beenden** — Instanz sauber stoppen (Server-Prozess beenden → **Port wird frei**, Bezug AP-31)
  - [ ] **Info** — App-Info öffnen (Version, URL/Port, aktive Verbindung)
  - [ ] **Debug/Log/Ausgabe-Fenster** — Fenster mit Live-Ausgabe/Logtail (Bezug AP-33; da die Konsole versteckt ist, braucht es diese Sicht)
  - [ ] (optional) **Im Browser öffnen** — URL erneut öffnen
- [ ] **Konsole verstecken:** Start ohne sichtbares Fenster (z. B. via `pythonw.exe`/verstecktem Launcher bzw. `-WindowStyle Hidden`); die signierte `run.ps1` soll im Normalbetrieb nicht als Konsole erscheinen
- [ ] **Auto-Browser:** beim **ersten** Start nach kurzem Delay **pollen**, bis der Webserver antwortet (`HTTP 200` auf `127.0.0.1:<Port>`), dann **Chrome** öffnen (Fallback: Standardbrowser, falls Chrome fehlt)
- [ ] **Ansatz prüfen (NO-CDN!):**
  - Variante A (Python): Launcher via `pythonw.exe` (keine Konsole) startet Flask + Tray via `pystray`+`Pillow`; Log-Fenster via Tkinter (stdlib). → `pystray`/`Pillow` als Wheels ins Wheelhouse aufnehmen.
  - Variante B (PowerShell/.NET): `System.Windows.Forms.NotifyIcon` (keine Extra-Abhängigkeit) startet `app.py` versteckt; Tray + Log-Fenster in PowerShell. → berührt das **signierte** Skript (Re-Signatur) — ggf. eigener signierter Launcher.
- [ ] **Bezug:** AP-31 (sauberes Beenden gibt den Port frei; pro Session) · AP-33 (Log-Fenster braucht ordentliches Logging) · Port-Lebensdauer-Notiz
- [ ] Betroffen: neuer Launcher (`tray`/`launcher`), `run.ps1` (versteckter Start), ggf. `wheels/` (pystray/Pillow), `app.py`/`config.py` (Port/URL bereitstellen)
