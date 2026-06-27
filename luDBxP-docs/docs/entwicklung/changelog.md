# Changelog

## [0.33.0] — 2026-06-27
### Hinzugefügt
- **AP-31 (Kern) — Multi-User-Basis:** Mehrere Nutzer können die App kollisionsfrei auf einer
  Maschine betreiben.
  - **Dynamische Port-Wahl pro Session:** ohne `LUCENT_PORT` erst 5057 (Hub-reserviert), sonst
    automatisch ein freier Port; `LUCENT_PORT=<n>` erzwingt fest, `=0` immer dynamisch. Die
    tatsächliche URL wird beim Start ausgegeben. Bind weiterhin nur `127.0.0.1`.
  - **Pro-Nutzer-Datenpfade:** `config.json` + Logs liegen im OS-Nutzerverzeichnis (Slug `luDBxP`;
    Linux `~/.config` bzw. `~/.local/state`, Windows `%LOCALAPPDATA%`). Overrides `LUCENT_CONFIG_DIR`/
    `LUCENT_LOG_DIR`. Eine vorhandene App-Verzeichnis-`config.json` wird einmalig übernommen.
  - Neues pures Stdlib-Modul `core/userpaths.py` (Pfade + `pick_port`/`resolve_port` + Migration).
  - `run.sh`/`run.ps1` brechen bei belegtem Port **nicht mehr ab** — `app.py` wählt selbst einen
    freien Port. 220 Tests grün (1 skipped).
  - *Offen (Rest von AP-31):* lokaler WSGI-Server (waitress), Idle-Shutdown/Stop, Deployment-Packaging.

## [0.32.1] — 2026-06-27
### Geändert
- **AP-45 Feinschliff — Filter sofort wirksam:** Wird ein Filterwert gesetzt (getippt oder aus dem
  DISTINCT-Dropdown gewählt), ein wertloser Operator (`IS NULL`/`IS NOT NULL`) gewählt oder eine
  Filterzeile entfernt, baut der Join-Builder **sofort neu** — die `WHERE`-Bedingung erscheint
  umgehend im SQL und im Ergebnis (vorher erst nach „Aktualisieren").
### Behoben
- **DISTINCT-Dropdown zeigte gelegentlich die falsche Spalte:** Beim Vorbelegen einer Filterzeile
  (z. B. via „Als Filter") wurde kurzzeitig auch die Default-Spalte geladen; bei ungünstigem
  Timing füllte deren Antwort die Vorschlagsliste. `_loadFilterDistinct` verwirft jetzt veraltete
  Antworten (Race-Guard) — es gewinnt immer die aktuell gewählte Spalte.
### Doku
- Referenz **Oberfläche/Architektur**: die **zwei „DISTINCT"** klar abgegrenzt — die `DISTINCT`-Checkbox
  fließt als `SELECT DISTINCT` ins generierte SQL, das **Filter-Wertdropdown** (`/api/distinct`) ist
  dagegen ein **separater Lookup** auf eine Spalte und erscheint **nicht** im Join-SQL.

## [0.32.0] — 2026-06-27
### Hinzugefügt
- **AP-45 — Ergebnis-Hilfen Teil 2: Spaltenkopf-Aktionen + DISTINCT-Filterwerte:**
  - **Klickbare Spaltenköpfe** in der Ergebnistabelle: ein Klick auf eine Spalte öffnet ein
    Menü mit **Sortieren ASC/DESC**, **Als Filter…** und **Spalte entfernen**. Sortieren legt
    eine ORDER-BY-Zeile an und baut neu; „Als Filter" füllt eine Filterzeile vor und fokussiert
    das Wertfeld; „Spalte entfernen" wirkt auf Zusatzspalten — **Start-/Ziel-Spalten** definieren
    den Join-Pfad und sind geschützt (Menüeintrag deaktiviert).
  - **Filter-Wertfeld mit echten Werten:** jedes Wertfeld ist mit einer `<datalist>` der echten
    **DISTINCT-Werte** der Spalte hinterlegt (Auswahl per Dropdown, Freitext bleibt möglich).
    Neues read-only Endpoint **`/api/distinct`** (`SELECT DISTINCT … ORDER BY …`, auf
    `config.DISTINCT_LIMIT` begrenzt, spalten-validiert, best-effort wie `/api/orphan_check`).
  - **`/api/joinpath/run`** liefert zusätzlich **`columns_meta`** (Tabelle/Spalte je Ausgabespalte
    in Selektionsreihenfolge) → jeder Spaltenkopf lässt sich eindeutig seiner Quellspalte zuordnen,
    auch wenn zwei verbundene Tabellen denselben Spaltennamen haben. 205 Tests grün, 1 skipped.

## [0.31.0] — 2026-06-27
### Behoben
- **Parsefehler zeigte ANSI-Müll:** sqlglot unterstreicht das Fehler-Token mit ANSI-Farbcodes,
  die im Browser als `□[4m…□[0m` erschienen. Werden jetzt **entfernt** — die Meldung ist sauberer
  Text. Layout neu: Label „Konnte nicht geparst werden:", darunter die Meldung (beginnend mit
  „Invalid expression …") samt mehrzeiligem SQL-Ausschnitt in einem roten Block (das „abgesetzte"
  Stück war dieser Kontext-Ausschnitt).
### Geändert
- **AP-49 — Analyzer-Feinschliff:** Eingabe-Textbox per Default **größer** (~17 rem); der
  **read-only**-Hinweis sitzt jetzt als grünes **Badge** abgesetzt neben „Analysieren". 200 Tests grün, 1 skipped.

## [0.30.0] — 2026-06-27
### Geändert
- **AP-48 — SQL-Analyzer: größere Eingabe + Tippfehler-Lint:**
  - Die Eingabe-Textbox ist **größer** (volle Breite, ~14 Zeilen) und nur **vertikal**
    in der Höhe verstellbar (nicht in der Breite, `resize: vertical`).
  - Neuer Lint **`SUSPICIOUS_ALIAS`**: Ein vertippter Join-Typ wie `LEFTI` ist für sqlglot
    syntaktisch gültig (Tabellen-**Alias**) und damit kein Parser-Fehler. Die Heuristik
    erkennt jetzt Aliasse, die einem Join-Schlüsselwort (LEFT/RIGHT/INNER/OUTER/FULL/CROSS)
    stark ähneln, und warnt vor dem möglichen Tippfehler. *Hinweis:* sqlglot bleibt ein
    toleranter Parser — echte Syntaxfehler (z. B. ein fehlendes `"`) werden erkannt, aber
    nicht jeder Tippfehler ist ein Syntaxfehler. 199 Tests grün, 1 skipped.

## [0.29.1] — 2026-06-27
### Behoben
- **Waisen-Chip war falsch-positiv:** Die Probe testete jeden Join **isoliert** und meldete
  Waisen, die im Pfad-Kontext gar nicht erscheinen (unerreichbar von der FROM-Tabelle, oder
  von nachfolgenden INNER-Joins wieder herausgefiltert) — der Chip versprach eine Änderung,
  die das Umschalten auf LEFT dann nicht brachte. `/api/orphan_check` **zählt jetzt das echte
  Ergebnis** (COUNT je Join-Typ vs. INNER, übrige Schritte auf aktuellem Stand) und meldet nur
  Typen, die die Zeilenzahl **tatsächlich** ändern. Chip und Tabelle sind damit konsistent.

## [0.29.0] — 2026-06-27
### Hinzugefügt
- **AP-47 — Pfad-Auswahl sichtbar + Waisen-Hinweis am Join-Typ:**
  - Die Pfad-Liste nutzt **`[*]` (aktiv) / `[ ]`** statt Bullets — der gewählte Alternativpfad
    ist eindeutig markiert (aktiver Pfad zusätzlich hervorgehoben).
  - Pro Join-Schritt zeigt ein **datengetriebener Waisen-Chip** (z. B. `⚠ LEFT/FULL`), welche
    Join-Typen hier **tatsächlich** unverknüpfte (Waisen-)Zeilen aufdecken. Neuer read-only
    Endpoint `/api/orphan_check` prüft per `NOT EXISTS`-Probe je Schritt links/rechts; die
    betroffenen Dropdown-Optionen werden zusätzlich amber getönt (so weit der Browser native
    `<option>`-Farben rendert). 197 Tests grün, 1 skipped.

## [0.28.1] — 2026-06-27
### Behoben
- **Graph bleibt beim Aufklappen der Detailkarten zentriert:** Erscheint unten der
  Detailbereich (Start/Ziel-Karten), rückt der Graph nach oben und wird in seinem
  kleineren Bereich **zentriert** — bei **gleichem Zoom** (`CY.center()` statt zu fitten),
  ohne Überlauf in den Kartenbereich. Beim Ausblenden zentriert er sich wieder im vollen Panel.

## [0.28.0] — 2026-06-27
### Geändert
- **AP-46 — Detailkarten folgen der Join-Builder-Auswahl:** Solange **nichts ausgewählt**
  ist, bleibt der Schema-Graph **zentriert** (der Detailbereich darunter ist ausgeblendet).
  Sobald Start/Ziel gesetzt sind — **auch wenn über die Dropdowns statt per Graph-Klick** —
  rückt der Graph nach oben und darunter erscheinen die **Tabellen-Detailkarten** für Start
  und Ziel (mit markierten Spalten), wie sonst beim Doppelklick auf einen Knoten. „Auswahl
  zurücksetzen" blendet den Bereich wieder aus. 195 Tests grün, 1 skipped.

## [0.27.0] — 2026-06-27
### Geändert
- **AP-44 — Join-Builder kompakter + Ergebnis-Hilfen:** Der obere Bereich ist gestrafft —
  die beiden Button-Zeilen (`Filter+/Sortierung+/Spalten+` und `DISTINCT/LIMIT/Dialekt/Bauen`)
  sind **eine** Zeile, die 1-N-Info sitzt als **kleine Kachel oben rechts** (keine eigene Zeile),
  engere Abstände + kompakteres SQL-Feld → **mehr Platz für die Ergebnistabelle**.
- **Ergebnis-Hilfen:** **NULL-Zellen** (Outer-Join-/Waisen-Zeilen) werden hervorgehoben;
  die Statuszeile zeigt jetzt **Zeilen · Join-Typ · Fan-out** (z. B. „8 Zeilen · LEFT · ⚠ 1-N").
  195 Tests grün, 1 skipped.

## [0.26.0] — 2026-06-27
### Geändert
- **AP-43 — Lesbares SQL-Layout:** Das generierte SQL ist jetzt **mehrzeilig formatiert** —
  eine Spalte pro Zeile, jeder `JOIN` auf eigener Zeile mit `ON`/`AND` darunter und
  **ausgerichteten `=`** bei zusammengesetzten Schlüsseln. Dadurch bleiben die Zeilen kurz
  (kein Horizontal-Scroll/keine Umbruch-Sorgen) und ein eingefügtes Statement ist sauber.
  Die **Copy/Anzeige**-Variante endet mit `;` (paste-and-run); das intern ausgeführte
  parametrisierte SQL ohne. 195 Tests grün, 1 skipped.

## [0.25.0] — 2026-06-27
### Geändert
- **AP-42 — Join-Builder-Politur:** Der verbose Fan-out-Warntext pro Ast („Ast „X" ist
  1-N (absteigend) — kann Zeilen vervielfachen") ist **raus** — die Richtung steht ohnehin
  als **N-1/1-N-Chip** an jedem Join. Stattdessen **eine** kompakte Kachel unter der
  Pfadliste: „**1-N** kann Zeilen vervielfachen (Fan-out)", nur wenn ein Pfad einen
  1-N-Schritt hat. Spart deutlich Platz.
- **SQL-Fenster bricht jetzt um** statt waagerecht zu scrollen (`white-space: pre-wrap`).
  Der Umbruch ist rein **visuell** — Copy/Paste liefert das Statement mit den echten
  Zeilenumbrüchen, bleibt also lauffähig.

## [0.24.2] — 2026-06-27
### Geändert
- **Ziel-Knoten jetzt Amber/Gold** statt Rot: Das Rot war auf der orangenen Pfad-Füllung
  noch zu ähnlich. Ziel = **Amber (#f3b305) mit dunkler Schrift**, hebt sich klar von Start
  (grün) und Pfad (orange) ab. Legende angepasst (so unterscheidet sich „Ziel" nun auch klar
  von „Analyzer: geschrieben"/rot).

## [0.24.1] — 2026-06-27
### Behoben
- **Ziel im Graph schlecht lesbar:** Der rote Ziel-**Ring** verschwamm mit der orangenen
  Pfad-Füllung. Endpunkte werden jetzt **voll eingefärbt** — Start grün, Ziel rot,
  Zwischenstationen orange — und heben sich klar ab. Legende auf gefüllte Quadrate angepasst.

## [0.24.0] — 2026-06-27
### Hinzugefügt
- **AP-41 — Join-Typ pro Schritt:** Im Join-Builder lässt sich jetzt **je Join-Station**
  der Typ wählen — **INNER** (Standard), **LEFT**, **RIGHT**, **FULL**. Pro Schritt ein
  Dropdown über der SQL-Ausgabe; eine Änderung baut SQL **und** Ergebnis neu. Damit gehen
  z. B. Start-Zeilen ohne Match nicht mehr verloren (LEFT statt INNER). `sqlgen`/`/api/joinpath`
  + `/api/joinpath/run` nehmen `join_types` (positionsweise; read-only-Ausführung bleibt
  parametrisiert). Der **SQL-Analyzer** erkannte Outer Joins bereits korrekt (LEFT/RIGHT/FULL/CROSS).
### Behoben
- **Graph-Marker passten nicht zur Legende:** Beim Bauen über die Dropdowns wurden Start/Ziel
  nicht eingefärbt (alle Knoten gleich). Jetzt markiert der Graph **Start grün / Ziel rot**
  (Ringe) auch ohne Klick-Auswahl — passend zur Legende. 194 Tests grün, 1 skipped.

## [0.23.0] — 2026-06-27
### Hinzugefügt
- **AP-40 — Graph-Legende** (klein, oben links im Schema-Graph): erklärt die
  Hervorhebungen — blau = Analyzer (gelesen/Joins), rot = Analyzer (geschrieben),
  orange = Join-Pfad, N-1/1-N = Join-Richtung, grüner/roter Rahmen = Start/Ziel.
### Behoben
- **Überlagernde Graph-Marker:** Join-Builder-Pfad und Analyzer-Markierungen sind jetzt
  **wechselseitig exklusiv** — die blaue Analyzer-Spur verschwindet, sobald ein Join-Pfad
  gebaut wird (und umgekehrt). Vorher blieben blaue Knoten/Kanten neben dem orangen Pfad
  stehen. Verifiziert via Playwright. 190 Tests grün, 1 skipped.

## [0.22.0] — 2026-06-27
### Hinzugefügt
- **AP-39 — SQL-Analyzer: Struktur-/Klauselanalyse, Graph-Zeichnung, Lints, Komplexität:**
  Der Analyzer wertet den sqlglot-AST jetzt deutlich tiefer aus (statt nur Typ + gelesene/
  geschriebene Tabellen). Neu im Panel: **Spalten**, **Joins** (Typ + ON-Bedingung),
  **Filter (WHERE)**, **GROUP BY/HAVING**, **Sortierung (ORDER BY)**, **DISTINCT/LIMIT**,
  ein **Struktur-Zähler** (Tabellen/Joins/Subqueries/CTEs/UNION/Window/Aggregate/CASE) und
  ein **Komplexitäts-Score** (gewichtet, Note A–E). Der **Schema-Graph zeichnet die JOIN-Kanten**
  des Statements (nicht mehr nur die Knoten einfärben). Zusätzliche statische Lints ohne DB:
  `SELECT_STAR`, `LEADING_WILDCARD` (LIKE '%…'), `FUNC_ON_COLUMN`. Weiterhin **read-only —
  nie ausgeführt**. `/api/analyze` liefert die neuen Felder. 190 Tests grün, 1 skipped.

## [0.21.0] — 2026-06-27
### Hinzugefügt
- **AP-38 — Kopierbares, lauffähiges SQL (Werte eingesetzt):** Die SQL-Anzeige und das
  Copy-Icon liefern jetzt **direkt ausführbares** SQL — Filterwerte werden als Literale
  eingesetzt (Zahlen roh, Strings in `'…'` mit `''`-Escaping, führende Nullen & LIKE bleiben
  String). Damit ist ein in einen externen SQL-Editor eingefügter SELECT sofort lauffähig,
  ohne `:p0`-Bind-Variablen ausfüllen zu müssen. Die **parametrisierte** Form (`:p0` + `params`)
  bleibt intern die read-only-**Ausführungs**­schiene (injection-sicher); `/api/joinpath`
  liefert beide als `sql` und `sql_inline`. 180 Tests grün, 1 skipped.

## [0.20.0] — 2026-06-27
### Hinzugefügt
- **AP-37 — Start ⇄ Ziel tauschen:** Neuer **⇄-Knopf** neben den Ziel-Dropdowns
  vertauscht Start- und Ziel-(Tabelle+Spalte), spiegelt die Graph-Marker und baut
  bei bereits gezeigtem Pfad sofort neu. Praktisch, weil die **warnungsfreie
  Richtung oft die umgekehrte** ist (aufsteigend zum Elternteil erzeugt kein Fan-out).
- **Doku:** Fan-out-Seite um **Beispiel 3** erweitert (langen Pfad lesen → Kette
  verkürzen *oder* Filter auf die „Viele"-Tabelle setzen; Faustregel + ⇄-Hinweis).

## [0.19.0] — 2026-06-27
### Hinzugefügt
- **AP-36 — Fan-out-Richtung pro Join sichtbar:** Jeder Join-Schritt eines Pfads
  trägt jetzt einen **Richtungs-Chip** — grün `N-1` (aufsteigend, sicher) oder
  gelb `1-N` (absteigend, kann Zeilen vervielfachen) — sowohl in der **Pfad-Liste**
  als auch als **Label an der hervorgehobenen Kante** im Schema-Graph. Macht
  sichtbar, dass ein Pfad eine *Mischung* aus N-1- und 1-N-Schritten ist, statt
  „alles 1-N". `/api/joinpath` liefert dafür pro Pfad ein neues `steps`-Feld
  (`left`/`right`/`to_many`); die bestehende `.path-warn`-Box bleibt. 172 Tests grün, 1 skipped.
- **Doku:** Neue Referenzseite **Fan-out-Warnung (1-N)** mit durchgerechneten
  Beispielen, inkl. Abschnitt „Warum beide Richtungen warnen — und eines trotzdem N-1 ist".

## [0.18.0] — 2026-06-27
### Hinzugefügt
- **AP-25 — Read-only SQL-Statement-Analyzer:** Neuer **SQL-Analyzer**-Tab; Statement
  wird via **sqlglot** (lokal gebündelt, kein CDN) geparst — **nie ausgeführt**.
  Zeigt Statement-Typ, gelesene/geschriebene Tabellen sowie Warnungen:
  `WRITE_STATEMENT`, `NO_WHERE` (UPDATE/DELETE ohne WHERE), `CARTESIAN_JOIN`;
  mit Verbindung zusätzlich `UNKNOWN_TABLE`/`UNKNOWN_COLUMN` (case-insensitiv).
  Beteiligte Tabellen werden im Graphen markiert (`analyze-read`/`analyze-write`).
  Funktioniert mit und ohne Verbindung. 165 Tests grün, 1 skipped.

## [0.17.0] — 2026-06-27
### Hinzugefügt
- **AP-30 — N-1-Stern (Auto-Weaving, Fan-out-Warnung):** Select-/ORDER-BY-/Filter-
  Tabellen werden automatisch in den Join-Baum gewebt — stilles Verwerfen entfällt.
  Unerreichbare Tabellen lösen einen `NoPathError` aus. Absteigende (1-N) Äste
  erzeugen eine **nicht-blockierende Fan-out-Warnung** pro Pfad (`warnings`-Feld
  in `/api/joinpath`); das Frontend zeigt diese als `.path-warn`-Box am betroffenen
  Pfad an. 144 Tests grün, 1 skipped.

## [0.16.0] — 2026-06-27
### Hinzugefügt
- **AP-12 (Abschluss) — MSSQL-Verschlüsselungsfelder in der UI:** Verbindungs-Tab
  hat für MS SQL Server zwei Tri-State-Dropdowns **Verschlüsselung** (`Encrypt`)
  und **Server-Zertifikat vertrauen** (`TrustServerCertificate`) — Standard/ja/nein;
  „Standard" lässt den Parameter weg. Persistiert mit gespeicherten Verbindungen.
- **AP-12 real verifiziert:** skip-guardeter Integrationstest gegen SQL Server 2022
  (`tests/test_mssql_integration.py`, `LUCENT_MSSQL_TEST_URL`) — provisioniert ein
  Schema mit FK und prüft die Reflection (ODBC Driver 18 / `msodbcsql18`).

## [0.15.0] — 2026-06-26
### Hinzugefügt
- **AP-29 — SQL-Dialekt umschalten:** Dialekt-Dropdown im Join-Builder
  (SQLite · PostgreSQL · MySQL · MSSQL · Oracle). Das read-only SELECT wird
  dialekt-treu gerendert — **Identifier-Quoting** (`"x"` / `` `x` `` / `[x]`)
  und **Zeilenlimit** (`LIMIT n` / `SELECT TOP n` / `FETCH FIRST n ROWS ONLY`).
  Default aus der Verbindung; **Anzeige** nutzt den gewählten Dialekt, die
  **Ausführung** den der echten Verbindung. Hand-gerollte `Dialect`-Schicht in
  `core/sqlgen.py` (keine neue Abhängigkeit), test-first, 137 Tests grün.
### Geändert
- **Identifier werden jetzt immer quotiert** (auch im SQLite-Default):
  `SELECT "VirtualMachine"."VMID"` statt `SELECT VirtualMachine.VMID`.

## [0.14.0] — 2026-06-26
### Geändert
- **AP-14 (Teil 2, Linux) — Python-3.14-AppImage:** venv und AppImage laufen jetzt
  gegen **Python 3.14.6** (user-lokal via `uv`, kein Root; alle 5 C-Extensions als
  **cp314-manylinux**-Wheels → venv rein aus Wheels, 125 Tests grün). AppImage
  gegen 3.14 gebaut & verifiziert (HTTP 200, bundelt 3.14.6).
- **AppImage-Fixes (`run.sh` AppRun):** **versions-bewusstes App-Update** (Code wird
  bei Versionswechsel erneuert, Nutzerdaten `config.json`/`Logs/` bleiben — vorher
  lief stiller Alt-Code weiter, real 0.1.0 statt der gebauten Version); **Browser**
  öffnet bevorzugt Chrome/Chromium statt `xdg-open`-Default.
### Behoben
- **`run.sh` unter Python 3.14:** `re.split(..., 1)` (positionsbasiertes `maxsplit`)
  löste einen DeprecationWarning aus → `maxsplit=1`.

## [0.13.0] — 2026-06-26
### Geändert
- **AP-33 — Logging sauber gemacht:** `core/log.py` rotiert jetzt (`RotatingFileHandler`,
  ~1 MB × 5) statt unbegrenzter `app.log`; Level via `LUCENT_LOG_LEVEL`
  (`LUCENT_DEBUG` ⇒ DEBUG), Logpfad via `LUCENT_LOG_DIR` (Pro-Nutzer-Hook;
  volle Terminal-Server-Verdrahtung bleibt AP-31). `init_logging` ist idempotent
  + reconfigurierbar (Handler-Ersatz) mit Startup-Zeile. Neu: **Request-Logging**
  (Methode · Pfad · Status · Dauer) in der `web/`-App-Factory — Layering gewahrt
  (`core/log.py` bleibt Flask-frei). 125 Tests grün (7 neue, test-first).

## [0.12.0] — 2026-06-26

### Geändert

- **AP-15 (Teil 2, Linux) — `run.sh` abbruchsicher + idempotent (Parität zu
  `run.ps1`):** Der Linux-Launcher heilt sich nach abgebrochenen Läufen selbst.
  Jeder Schritt prüft seine Vorbedingungen und meldet seinen Status
  (`_ok`/`_warn`/`_info`/`_hdr`/`_fail`):
  - **venv-Integrität statt nur Existenz** (`venv_healthy`: `python -c import sys`);
    ein halbes/kaputtes venv wird automatisch neu gebaut.
  - **Echter Paket-Vollständigkeits-Check:** `pip check` **plus** Vorhandensein
    jeder in `requirements.txt` gelisteten Distribution (`importlib.metadata`) —
    fängt sowohl abgebrochene Installs als auch ein frisch gebautes, leeres venv.
  - **Atomarer Stamp:** `.req_stamp` wird erst **nach** erfolgreichem Install
    geschrieben; ein abgebrochener Install wiederholt sich beim nächsten Lauf.
  - **Port-/Instanz-Check** vor App-Start (5057 belegt via `ss`/`lsof` → klare
    Abbruch-Meldung statt Crash).
  - **Robustes Menü:** ein fehlgeschlagener Schritt beendet das Menü nicht mehr
    (Subshell-Isolierung, bash-Pendant zum try/catch).
  - **Exit-Codes nicht mehr verschluckt:** das `|| true` in `do_start`/
    `do_skip_setup` entfernt; der App-Exit-Code wird sauber durchgereicht.
  - **`--debug`-Flag** (Pendant zu `run.ps1 -DebugMode`, setzt `LUCENT_DEBUG=1`).
- **AP-15 / NO-CDN auf Linux (adaptiv):** Installation versucht zuerst **strikt
  offline** aus `wheels/` (`--no-index`-Dry-Run-Probe, kein Netz). Deckt das
  Wheelhouse die Plattform ab → Offline-Install; sonst — z. B. die gebundelten
  `win_amd64`/cp314-Wheels auf Linux — **lauter** Fallback auf Online-pip (kein
  stilles Nachladen). Schaltet automatisch auf offline, sobald ein passendes
  Linux-Wheelhouse vorliegt.

### Behoben

- **Leeres venv galt fälschlich als „vollständig":** `pip check` allein ist auf
  einem frisch gebauten, paketleeren venv vacuously grün — in Kombination mit
  einem noch passenden `.req_stamp` wäre der Install übersprungen worden (App
  hätte beim Import gecrasht). Der Vollständigkeits-Check prüft jetzt zusätzlich
  das tatsächliche Vorhandensein der Requirements. **Hinweis:** dieselbe latente
  Schwäche steckt in `run.ps1` (Windows) — dort zur Behebung vorgemerkt (Skript
  ist signiert, separate Session).

## [0.10.0] — 2026-06-26

### Hinzugefügt

- **AP-20 — Copy-Icon am SELECT:** In der oberen rechten Ecke des generierten
  SELECT sitzt ein Copy-Icon; ein Klick kopiert das SQL in die Zwischenablage
  (`navigator.clipboard`) mit kurzem „kopiert"-Feedback.

### Behoben

- **AP-21 — Kosmetik:** Der „Schema-Graph"-Balken (`.panelhead`) und die Tab-Linie
  (`.tabbar`) haben jetzt exakt dieselbe Höhe (gemeinsame `min-height` +
  `box-sizing`), vorher war der Graph-Balken minimal höher.

## [0.9.0] — 2026-06-26

### Geändert

- **AP-12 (Backend) — MS SQL Server: ODBC-Treiber & Verschlüsselung
  konfigurierbar, klare Treiber-Fehlermeldung:** `build_url` nutzt jetzt
  standardmäßig den aktuellen **ODBC Driver 18 for SQL Server** (überschreibbar
  per `driver`) und unterstützt optionale `Encrypt`/`TrustServerCertificate`-
  Parameter — nichts Unsicheres wird per Default angenommen. Fehlt der ODBC-
  Treiber, meldet die App das klar (AP-2-Stil) statt einer rohen pyodbc-Exception
  (`_odbc_driver_hint`: IM002 / „no default driver" / „Can't open lib"). Installations-
  Doku ergänzt. 118 Tests grün. (Realer Integrationstest gegen eine MSSQL-Instanz
  und UI-Felder für Encrypt/Trust folgen separat.)

## [0.8.0] — 2026-06-26

### Geändert

- **AP-15 (Teil 1, Windows) — `run.ps1` abbruchsicher + idempotent:** Der
  Windows-Launcher heilt sich nach abgebrochenen Läufen selbst. Jeder Schritt
  prüft seine Vorbedingungen (Python, venv-Integrität per Funktionstest,
  Paket-Vollständigkeit per `pip check`, freier Port) und zieht nur Fehlendes
  nach; der Requirements-Stamp wird erst nach erfolgreichem Install geschrieben
  (atomar). **NO-CDN / nur lokale Sourcen:** Installation strikt `--no-index`
  aus `wheels\` mit `--dry-run`-Vorabprüfung — fehlt ein Wheel, steigt das Setup
  mit Protokoll (welche Pakete fehlen) aus, **ohne etwas zu installieren oder
  online nachzuladen**. Neu außerdem: durchgängige Status-Ausgaben, Port-Check
  vor App-Start (5057 belegt → klare Meldung) und ein gegen Einzelfehler robustes
  Menü. Verifiziert: idempotenter Lauf, fehlender Stamp, fehlendes Wheel, belegter
  Port. (`run.sh`/Linux-Parität folgt separat.)

## [0.7.0] — 2026-06-26

### Hinzugefügt

- **AP-13 — UI-Politur:** Drei Verbesserungen in Objekt-Browser und Graph-Panel:
  (1) **Suchfeld** über dem Objekt-Browser filtert die Tabellen-/View-Listen live
  nach Namen; (2) **linker Splitter** macht die Sidebar-Breite per Drag verschiebbar
  (analog zum Graph-Splitter, via `--sidebar-width`); (3) **„Neu anordnen"-Button**
  im Graph-Panel würfelt das cose-Layout neu, dessen Abstände jetzt für dichte
  Schemas (> 12 Knoten) hochskalieren, damit Knoten weniger überlappen. Reines
  Frontend (`index.html`/`app.js`/`app.css`). Im Browser verifiziert (Playwright);
  115 Tests grün.

## [0.6.0] — 2026-06-26

### Hinzugefügt

- **AP-10 — Gespeicherte Verbindungen in der Topbar:** Neues Dropdown in der
  Topbar (neben „Verbinden") listet die in `config.json` gespeicherten
  Verbindungen; eine Auswahl verbindet sofort — passwortlose Verbindungen
  (SQLite oder Server ohne Auth) direkt, sonst öffnet sich der Verbindungs-Tab
  vorbefüllt zum Ergänzen des Passworts. Beide Verbindungs-Picker (Topbar +
  Verbindungs-Tab) teilen dieselbe Liste und spiegeln die Auswahl. Ein
  Verbindungswechsel setzt den UI-Zustand zurück (Detail-Tabs schließen,
  Graph-Highlight/UML-Karten leeren, Schema neu laden). Reines Frontend
  (`index.html`/`app.js`/`app.css`); die `/api/connections`-API blieb unverändert.
  Im Browser verifiziert (Playwright/Chromium); 114 Tests grün.

## [0.5.0] — 2026-06-26

### Geändert

- **AP-11 — Composite Foreign Keys voll unterstützt:** Mehrspaltige FKs werden
  nicht mehr nur auf dem ersten Spaltenpaar gejoint. Ein FK trägt jetzt alle
  `(lokal, referenziert)`-Spaltenpaare (`ForeignKey.column_pairs`, mit Properties
  `columns`/`ref_columns`/`is_composite`); der Join-Pfad-Generator emittiert
  `JOIN … ON a.x = b.x AND a.y = b.y`. Zwei **separate** einspaltige FKs zwischen
  denselben Tabellen bleiben weiterhin alternative Join-Wege (nicht mit AND
  verschmolzen). Betroffen: Loader, FK-Graph (`JoinEdge`), Pathfinder
  (`JoinStep.column_pairs`), SQL-Generator, DDL-Ansicht und `/api/schema`
  (FKs jetzt als `columns`/`ref_columns`-Listen, Frontend angepasst). 112 Tests grün.

## [0.4.0] — 2026-06-26

### Geändert

- **AP-14 — Python-3.14-Readiness (Windows):** Das Offline-Wheelhouse (`wheels/`)
  wurde von der CPython-3.12- auf die **3.14-ABI** umgestellt. Die fünf
  kompilierten Wheels (SQLAlchemy, psycopg2-binary, pyodbc, greenlet, MarkupSafe)
  liegen jetzt als `cp314-win_amd64` vor — identische Paketversionen, nur neuer
  ABI-Tag; die `py3-none-any`-Wheels bleiben versionsunabhängig. Die Launcher
  `run.ps1` (Offline-Gate) und `run.sh` (Präferenzreihenfolge) verlangen bzw.
  bevorzugen jetzt Python 3.14; `wheels/README.md` entsprechend aktualisiert.
  Verifiziert: venv mit Python 3.14.6, Offline-Setup aus `wheels/`, `pip check`
  sauber, alle **111 Tests grün**, App startet (HTTP 200).

## [0.3.1] — 2026-06-26

### Geändert

- **AP-9 — Ergebnisliste maximiert**: Die Ergebnistabelle unter dem Join-Builder
  nutzt jetzt den vollen vertikalen Restplatz nach unten (fixe `max-height: 320px`
  entfernt). Das Join-Builder-Panel ist eine Flex-Spalte; `#join_result` wächst
  mit (`flex: 1`, eigener Scroll). Auf das Join-Builder-Panel beschränkt, sodass
  Detail-Tabs ihren normalen Fluss behalten.

## [0.3.0] — 2026-06-26

### Hinzugefügt

- **AP-6 — Ausgabe-Steuerung im Join-Builder**: Auswahl der Ausgabezeilen
  (200 / 400 / Alle) plus „Aktualisieren"-Button im Ergebnisbereich.
  `/api/joinpath/run` akzeptiert nun `max_rows`; der Wert wird serverseitig auf
  `config.MAX_RESULT_ROWS` (5000) geklemmt — „Alle" heißt „alle bis zur
  Obergrenze" zum Schutz der Oberfläche. Die Antwort liefert `row_cap`; die
  Info-Zeile zeigt „N Zeilen (begrenzt auf …)". „Aktualisieren" liest das
  Formular neu (geänderte Sortierungen/Spalten) und behält den gewählten Pfad;
  ein Zeilenwechsel führt nur das aktuelle SELECT neu aus. Der hervorgehobene
  Join-Pfad im Graphen bleibt stabil, da Sortierungen/Zusatzspalten auf die
  Pfad-Tabellen beschränkt sind.
- **AP-7 — Feiner Graph-Zoom + Slider**: Mausrad-Zoom feinstufig
  (`wheelSensitivity` 0.2 statt 1, Zoom-Grenzen 10 %–400 %) plus vertikaler
  Zoom-Slider mit Prozent-Anzeige am rechten Graph-Rand, beidseitig
  synchronisiert (Scrollen ↔ Slider).

### Behoben

- **AP-8 — „Auswahl zurücksetzen"**: Der Button bereinigt jetzt zusätzlich den
  hervorgehobenen Join-Pfad im Graphen (`hl`) und schließt die UML-Karten
  darunter (`#uml_cards`) — vorher blieb beides stehen. Der interne
  Auswahl-Reset (neue Selektion starten) lässt die Karten bewusst bestehen.

## [0.2.0] — 2026-06-26

### Hinzugefügt

- **AP-5 — Tabellarischer Ausgabebereich im Join-Builder**: Beim Wählen eines
  Join-Pfads wird das generierte SELECT angezeigt **und** ausgeführt; die
  zurückgelieferten Zeilen erscheinen als Tabelle unter dem SQL. Neuer
  read-only Endpoint `POST /api/joinpath/run`: das SELECT wird **serverseitig**
  aus den validierten Join-Parametern erzeugt (kein client-geliefertes SQL),
  parametrisiert ausgeführt und auf max. 200 Zeilen begrenzt
  (`core.datapreview.execute_select`). Gemeinsame Pfad-/SQL-Bau-Logik in
  `_parse_joinpath_params` + `_make_path_gen` (von beiden Endpoints geteilt).

## [0.1.0] — 2026-06-25

### Hinzugefügt

- **FK-Graph** aus Live-DB-Reflection (SQLAlchemy, SQLite + PostgreSQL).
- **Join-Pfad-Builder** (k-kürzeste Pfade, deterministischer Tie-Break).
- **Filterobjekte** (WHERE über erreichbare Tabellen).
- **Read-only SQL-Generierung** mit parametrisierten Platzhaltern.
- **Flask-Web-UI** mit lokal gebundelten Assets.
- **Portable Demo-CMDB** (`sample_data/`): SQLite-DB + reproduzierbarer Generator,
  deckt mehrdeutige Pfade (Diamant), zusammengesetzte FKs, Graph-Sonderfälle
  (Selbstreferenz, Mehrfach-FK, isolierte Tabelle) und realistische Daten ab;
  inkl. Integrationstests pro Fall.
- **Interaktives Menü** in `run.sh` (ohne Argument) plus `run.ps1` für Windows mit
  identischem Menü; Flags (`--skip-setup` etc.) bleiben Hub-kompatibel.
- **Filter-UI**: „Filter +" fügt Filterzeilen hinzu (Tabelle · Spalte · Operator ·
  Wert · Entfernen); mehrere Filter werden mit UND verknüpft und an die
  bestehende, getestete Backend-Filterlogik (parametrisiertes WHERE) gesendet.
- **Graph-Visualisierung**: neuer `/api/graph`-Endpoint (Knoten/Kanten) und eine
  interaktive Schema-Graph-Ansicht mit Cytoscape.js (lokal gebundelt, kein CDN).
  Der gewählte Join-Pfad wird im Graph farblich hervorgehoben; die
  joinpath-Antwort liefert die konkreten Pfad-Kanten.
- **Implizite (geratene) Foreign Keys**: optionale Heuristik (Spaltenname trifft
  einspaltigen Primärschlüssel einer anderen Tabelle, kompatibler Typ).
  Per Checkbox einschaltbar; gefundene Beziehungen erscheinen im Graph
  gestrichelt und ermöglichen Join-Pfade auch ohne deklarierte FKs. Neue
  FK-lose Demo-DB (`demo_cmdb_nofk.db`) zum Ausprobieren.
- **Verbindungs-Manager** (Tools → Verbindungen): strukturiertes Formular mit
  Datenbank-Typ-Auswahl (SQLite, PostgreSQL, MySQL/MariaDB, MS SQL Server) und
  passenden Feldern. Das Backend baut die SQLAlchemy-URL (`core.connection.build_url`)
  und testet die Verbindung (`/api/connect`). Benannte Verbindungen speicherbar
  in `config.json` (ohne Passwort).

### Geändert

- **Info-Bereich** in der Sidebar ans untere Ende gesetzt; zeigt App-Metadaten und
  Technologie-Stack via `GET /api/info`.
- **3-Panel-Layout** (wie ein minimalistischer SQL Developer): Objekt-Browser links,
  Tab-Bereich Mitte, Schema-Graph rechts mit eigenem Scrolling.
- **Views** werden reflektiert; `/api/schema` liefert Spalten + SQL-Definition.
- **Detail-Tabs**: „Definition", „Daten" (Vorschau erste 100 Zeilen via `/api/data`),
  „SQL" (rekonstruiertes DDL).
- **UX**: Connection-URL aus `default_connection` vorbelegt — Demo-DB direkt startbereit.

### Bekannte Einschränkungen

- **Composite Foreign Keys**: Schemas mit Mehrspaltigen FKs werden in v1 nur auf der
  ersten Spalte gejoint; einspaltigen FKs sind vollständig unterstützt.
- **Datenbank-Backends**: PostgreSQL-Support ist implementiert, aber in der
  automatisierten Testsuite nur gegen SQLite abgedeckt.
