# Arbeitspakete — Lucent DB Explorer

Offene APs (erledigte wandern nach `todo-erledigt.md`).
Letzte erledigte Nummer: **AP-9** (v0.3.1). Neue offene APs ab **AP-10**.

**Definition of Done (jedes AP):** Code + Tests grün · betroffene Doku aktualisiert
(CLAUDE.md + Zensical-Doku) · `sync_version.py`-Versionsbump + CHANGELOG · AP nach
`todo-erledigt.md` umhängen · AP-Diagramm + Site **auf Linux** neu bauen.

---

## AP-10 — Gespeicherte Verbindungen in der Topbar auswählbar
- [ ] Dropdown oben (neben „Verbinden") listet die in `config.json` gespeicherten Verbindungen — wie ein SQL Developer
- [ ] Auswahl füllt das Verbindungsformular vor / verbindet direkt; Passwort bleibt versteckt (wird wie bisher nicht gespeichert)
- [ ] Zweiweg-Sync mit dem Verbindungs-Tab (Auswahl dort ↔ Topbar)
- [ ] **Verbindungswechsel setzt UI-Zustand zurück:** offene Detail-Tabs, Graph-Highlight/UML-Karten und Reflection-Cache leeren — sonst bleibt das Schema der alten DB stehen
- [ ] Betroffen: `web/templates/index.html`, `web/static/js/app.js`, ggf. `core/settings.py` (Liste der Verbindungen)
- [ ] Tests: API liefert gespeicherte Verbindungen; UI-Verifikation (Playwright)

## AP-12 — MSSQL real testbar machen
- [ ] System-ODBC einrichten/dokumentieren (`unixODBC` + `msodbcsql17` Linux; ODBC Driver 17/18 Windows)
- [ ] **ODBC Driver 18 verschlüsselt per Default** → `Encrypt`/`TrustServerCertificate=yes`-Parameter in der Connection-URL unterstützen; Driver-Name konfigurierbar
- [ ] **Klare Fehlermeldung bei fehlendem Treiber** (im Stil von AP-2, statt roher pyodbc-Exception)
- [ ] Setup-Doku in `wheels/README.md` / Installations-Doku ergänzen
- [ ] Optionaler Integrationstest gegen lokale MSSQL-Instanz (markiert, überspringbar wenn Treiber fehlt)
- [ ] Betroffen: `core/connection.py` (URL/Driver-Param), Doku, ggf. `run.ps1`/`run.sh`

## AP-13 — UI-Politur
- [ ] Suchfeld im Objekt-Browser (Tabellen/Views filtern)
- [ ] Linker Splitter: Sidebar-/Objekt-Browser-Breite verschiebbar (analog Graph-Splitter)
- [ ] Graph-Auto-Layout bei dichten Schemas entzerren (Layout-Parameter/Alternativ-Layout)
- [ ] Betroffen: `web/static/js/app.js`, `web/static/css/app.css`, `web/templates/index.html`

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

- [ ] **Prereq-Check pro Schritt** statt nur am Anfang: vor jeder Aktion prüfen, was sie braucht (Python gefunden? venv funktionsfähig? pip vorhanden? wheels vollständig? requirements installiert? Port frei?), und Fehlendes nachziehen
- [ ] **venv-Integrität prüfen, nicht nur Existenz:** aktuell `[ -d venv ]` / `Test-Path $VenvPy` — bei einem mittendrin abgebrochenen `venv`-Bau liegt ein kaputtes Verzeichnis. Bei kaputtem/halbem venv automatisch neu aufbauen (Funktionstest: `python -c "import sys"` im venv)
- [ ] **Idempotenter pip-Install:** Stamp wird erst nach Erfolg geschrieben (gut) — zusätzlich nach Abbruch verifizieren, dass alle Pakete wirklich da sind (`pip check` / Import-Smoke-Test), sonst neu installieren
- [ ] **Statusausgabebereich:** in `run.ps1` durchgängige Status-Helfer einführen (analog `_ok`/`_warn`/`_info`/`_fail` aus `run.sh`); jeder Schritt gibt klar „prüfe … / ziehe nach … / ✓ fertig" aus, am Ende eine Zusammenfassung
- [ ] **`run.sh`-Fehler nicht mehr verschlucken:** `do_start`/`do_skip_setup` enden auf `|| true` (schluckt App-Exit-Code) — bewusst sauberen Exit-Code durchreichen, sonst sieht der Hub Fehlstarts nicht
- [ ] **Atomare Schritte:** Teilarbeiten (venv-Bau, wheel-Install) so kapseln, dass ein Abbruch keinen inkonsistenten Halbzustand hinterlässt, der beim nächsten Lauf unentdeckt bleibt (z. B. Stamp/Marker erst nach vollständigem Schritt)
- [ ] **Port-/Instanz-Check vor App-Start:** prüfen, ob Port 5057 schon belegt ist (läuft bereits eine Instanz?) → klare Meldung statt stillem Fehlstart; passt zu Prereq-Check + Idempotenz
- [ ] **Parität halten:** `run.sh` und `run.ps1` müssen sich gleich verhalten (gleiche Checks, gleiche Status-Sprache, gleiche Idempotenz-Garantien)
- [ ] Betroffen: `run.sh`, `run.ps1`
- [ ] Verifikation: Lauf nach simuliertem Abbruch in jeder Phase (venv halb, pip halb, Stamp fehlt) → sauberer Selbstheilungslauf; beide Skripte
