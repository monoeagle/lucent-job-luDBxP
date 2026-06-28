# Session-Kennzahlen — Lucent DB Explorer

Eine Zeile je Session (Schema: `.pattern/session-handoff-kpi.pattern`).
Macht den Projektverlauf auswertbar (Tokens/Commit, Tokens/Feature, Tests-Δ je 100k Tokens, Modell-Mix).

| # | Datum | Modell | Tokens ges. (Hauptschleife) | Commits (Merges) | Tests (von→bis) | Version | Subagent-Dispatches | feat/fix | LOC (insert/Dateien) | Geräte-verifiziert | Notiz |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-06-25 | Opus 4.8 (1M) Hauptschleife; Subagenten haiku/sonnet/opus | 664.8k (`/context` Endstand; Messages 644.9k / Tools 13.2k) | 30 (1 FF-Merge) | 0 → 81 | (neu) → 0.1.0 | ~28 (v1-SDD: ~10 Implementer + ~10 Reviewer + ~6 Fixer + 1 Final-Review/opus) | 16 / 5 | 5065 / 64 | Browser (Chrome) + Playwright e2e ✓ | Session 1: neues Projekt von Null; Flask-Web statt PyQt6-Pattern |
| 2 | 2026-06-26 | Opus 4.8 (1M) Hauptschleife; Subagenten sonnet (Verify/Screenshots) + general-purpose/opus (Deploy) | ~800k (Schätzung; Session lief in Auto-Compaction, `/context`-Endstand nicht abgerufen) | 26 (31→56; 1 fremd: 9d55a9c) | 81 → 111 | 0.1.0 → 0.3.1 | ~25 (Pre-Compaction: AP-1/2-SDD + Wheelhouse + Docs; Post-Compaction ~7: Verify + Screenshots + 4× Deploy) | 7 / 1 (Commit-Ebene; AP-8/AP-2-Fixes gebündelt) | 11267 / 98 (inkl. gener. SVG/JSON/Screenshots/Wheels) | Playwright e2e (21/21 + 7 Screenshots) + Chrome ✓ | Session 2: AP-1…AP-9; read-only-Ausführung eingeführt; Doku-Versions-Drift (icon-rail.js/zensical/poster) behoben; Startseite 2-spaltig + AP-Band 3-spaltig |
| 3 | 2026-06-26 | Opus 4.8 (1M) Hauptschleife; **keine Subagenten** (alles inline); Playwright/Chromium zur UI-Verifikation | ~640k (Schätzung; letzter `/context` 584.7k bei 58 %) | 10 eigene (56→69; +7 Session-2-Commits beim Rebase integriert) | 111 → 118 | 0.3.1 → 0.10.0 | 0 | 6 / 1 (+ 8 docs, 1 build) | ~1419 ins. / 101 Dateien (inkl. der integrierten Session-2-Commits) | Playwright/Chromium (AP-10/13/20/21: Clipboard-, Höhen-, Filter-, Splitter-Checks) ✓ | Session 3: Remote-Divergenz → Rebase + AP-Umnummerierung; Python-3.14-Wheelhouse (cp314); AP-10/11/13/20/21 komplett + AP-12-Backend/AP-15-Windows; Backlog AP-16…25 dokumentiert; **Windows-only** (Linux abends) |
| 4 | 2026-06-26 | Opus 4.8 (1M) Hauptschleife; **keine Subagenten** (alles inline, wie Session 3) | n/a (nicht erfasst — Windows-Session ohne `/context`-Endstand) | 18 eigene (0 Merges) | 118 → 118 (±0; reine UI-/Build-/Doku-Arbeit) | 0.10.0 → 0.11.3 | 0 | 1 / 4 (Commit-Ebene) | 4507 ins. / 32 Dateien (Code-only ~698 ins.; 3809 davon = gebündelte `dagre.min.js`) | Windows (PowerShell 5.1, Chrome) ✓ | Session 4 (Windows): AP-23/AP-16 (dagre-Layout lokal gebündelt) + App-Rename „LucentTools DB Explorer" + AP-26 Audit-Prozess + AP-28/AP-32 UI-Fixes + AP-17 Release-ZIP (GitHub-Releases v0.11.2/v0.11.3). Schwerpunkt **PS-5.1-Deployment** (run.ps1 ASCII+UTF-8-BOM, Start-Abbruch-Fix, `-DebugMode`). Insight `2026-06-26-ps51-deployment-und-dagre.md`. |
| 5 | 2026-06-27 | Opus 4.8 (1M) Hauptschleife; Subagenten general-purpose/opus (Doku-Reconcile + UI-Screenshots) | ~799k (`/context` Endstand 799.2k bei 80 %) | 17 eigene (0 Merges; ab Pull 05de9a5) | 118 → 138 | 0.11.3 → 0.16.0 | 2 | feature-lastig (5 APs) | 3468 ins. / 68 Dateien (inkl. gener. SVG/Screenshots/Site) | Chrome + Playwright + **echtes MSSQL 2022** (podman) ✓ | Session 5 (Linux): AP-15/33/14/29/12 → v0.16.0; Python 3.14 via uv; MSSQL real getestet; Backlog konsolidiert (AP-17 gestrichen, AP-22/24 entschieden, AP-30 rescoped); Doku/Pages durchgehend deployed. **Session 4 (Windows, v0.10→0.11.3) noch nachzutragen.** |
| 6 | 2026-06-27 | Opus 4.8 (1M) Hauptschleife; Subagenten **haiku** (Transkription) / **sonnet** (Task-Reviews+Integration) / **opus** (Final-Whole-Branch-Reviews) | ~473k (`/context` Endstand 473.3k bei 47 %) | 26 eigene (2 FF-Merges, 0 Merge-Commits) | 138 → 171 | 0.16.0 → 0.18.0 | ~32 (AP-30 ~16 + AP-25 ~16: Implementer+Task-Reviewer je Task, Fixer, 2× Final/opus) | 2 feat (AP-30, AP-25; beide minor) | 2788 ins. / 52 Dateien (Code-only 626 ins. / 9 Dateien; Rest gener. SVG/Site) | Chrome + Playwright (AP-30 Fan-out-Warnung, AP-25 Analyzer-Tab + Graph-Highlight) ✓ | Session 6 (Linux): AP-30 (N-1-Stern) + AP-25 (read-only SQL-Analyzer, sqlglot) → v0.18.0 via SDD; **finale opus-Reviews fingen 3 echte Bugs** (PG/MSSQL-500, NO_WHERE-Subquery, UNKNOWN_COLUMN-Case) die SQLite-only-Tests maskierten; Architekturbild + zensical-Drift nachgezogen; gh-pages deployed. **Session 4 (Windows) weiter offen.** |
| 7 | 2026-06-27 | Opus 4.8 (1M) Hauptschleife; **keine Subagenten** (alles inline); Playwright (System-python3) zur UI-Verifikation, jede AP per Screenshot/Messung | ~796k (`/context` Endstand 795.6k bei 80 %) | 23 eigene (0 Merges) | 171 → 200 | 0.18.0 → 0.31.0 | 0 | 13 feat / 4 fix (+ 4 docs, 2 data) | 7180 ins. / 51 Dateien (Code-only 1119 ins. / 15 Dateien; Rest gener. SVG/Site/Demo-DBs) | Chrome + Playwright (jede UI-Änderung getrieben: Chips, Graph-Refit, NULL-Highlight, Analyzer) ✓ | Session 7 (Linux): **iterativer UI-/UX-Ausbau** Join-Builder + SQL-Analyzer, **AP-36…49** → v0.31.0. Join-Typ pro Schritt (LEFT/RIGHT/FULL), **count-basierter Waisen-Chip** (Fix der isolierten Probe), mehrzeiliges SQL-Layout, kompaktere UI + Detailkarten/Graph-Refit, Analyzer vertieft + ANSI-Fix + Tippfehler-Lint. Demo-CMDB um Waisen ergänzt; 2 neue Referenzseiten; Gantt/Board bis AP-49 nachgezogen. Sehr viele kleine Nutzer-getriebene Iterationen → hoher Token-/Commit-Verbrauch bei kleiner Code-LOC. |
| 8 | 2026-06-27 | Opus 4.8 (1M) Hauptschleife; Subagenten **haiku** (Transkription) / **sonnet** (Task-Reviews + Wiring) / **opus** (Final-Whole-Branch-Reviews) | ~800k (Schätzung; `/context` zuletzt 404k bei 40 % während AP-45; SDD hält die Hauptschleife schlank — Subagent-Arbeit zählt separat) | 32 eigene (2 FF-Merges AP-31/AP-34, 0 Merge-Commits) | 200 → 232 | 0.31.0 → 0.34.1 | ~22 (AP-31 ~14: 6 Impl + 6 Task-Review + 1 Fix + 1 Final/opus; AP-34 ~8: 3 Impl + 3 Task-Review + 1 Fix + 1 Final/opus) | 12 feat / 3 fix (+ 17 docs) | ~1100 ins. Code (launcher/ + userpaths + Tests; Gesamt-Diff inkl. Doku/Site/Wheels größer) | Playwright (AP-45 12 Checks, 7 Screenshots, Kennzahlen-HTML) + Controller-E2E (launcher core / echtes app.py, AP-31 2-Instanzen-Port-Fallback, run.sh --tray) ✓ | Session 8 (Linux): **AP-45** fertig + v0.32.1; **AP-31-Kern** (Multi-User Pro-Nutzer-Pfade + dynamischer Port, `core/userpaths.py`) v0.33.0 und **AP-34-Kern** (Tray-Icon-Launcher `launcher/`, pystray/Pillow, Ein-Klick via `run.ps1 -Action tray`) v0.34.0 — **beide via Subagent-Driven Development**. **Final-opus-Reviews fingen Integrationslücken außerhalb des Task-Diffs** (AP-31: Launcher-Abbruch bei belegtem Port → gefixt). Daneben: AP-Board lesbarer (5×5-Gitter + zweizeilige Kacheln), Oberfläche-Screenshots neu (komplexer 6-Hop-Pfad), Betriebsseite „Terminalserver", `docs/projekt-kennzahlen.html` (98 % Umsetzung, 89 % Coverage). **Nachschärfung v0.34.1:** AP-34 live auf Linux-Desktop nutzbar gemacht — Linux-Tray-Menü via AppIndicator/GTK (PyGObject<3.52; venv-3.14-vs-System-3.12-ABI gelöst), Info-Dialog (`about.py`, eigener Prozess, primär-Monitor-zentriert via xrandr), sauberes Beenden (atexit/Signal → keine Waisen). 8 Sessions an nur 3 Kalendertagen → v0.1.0 → v0.34.1. |
| 9 | 2026-06-28 | Opus 4.8 (1M) Hauptschleife; Subagenten **haiku** (Transkription/mechanisch) / **sonnet** (Task-Reviews + Routes/Frontend) / **opus** (Final-Whole-Branch-Reviews) | ~708k (`/context` Endstand 707.8k bei 71 %) | 36 eigene (0 Merges) | 232 → 262 | 0.34.1 → 0.39.0 (5× MINOR) | ~48 (AP-31-Rest/50/51/52/53 via SDD: Implementer + Task-Reviewer je Task, mehrere Fixer, 5× Final/opus; Header + Doku-Drift-Fix inline ohne Subagenten) | 15 feat / 1 fix (+17 docs, 1 style, 1 build, 1 test) | 4687 ins. / 83 Dateien (Code-only 701 ins. / 25 Dateien; Rest gener. SVG/Site/Wheels) | Chrome (App + Doku via Tray-Launcher gestartet) ✓; Oracle nur skip-guarded (kein Live-Server) | Session 9 (Linux): **5 APs** — AP-31-Rest (waitress-WSGI-Server), AP-50/51 (Unique-Constraints/Index → korrekte 1-1-Fan-out-Klassifikation), AP-52 (Multi-Schema, ein wählbares Schema + `/api/schemas`), AP-53 (Oracle-Verbindung, python-oracledb Thin-Mode/Service-Name) → **v0.39.0** via SDD. Daneben **Kopfzeilen-Redesign** (Brand zentriert in Sidebar-Breite, Demo-Verbindung als Default, „Verbindungen…"-Button raus) + **große Doku-/Architektur-Aufräumung** (Roadmap/Board/Gantt auf AP-50–53 + AP-31/34-Status; Architektur Flask→**waitress** + Terminal-Server ins Bild; Alt-Bild archiviert; arch-3 vom Kanten-Knäuel zur klaren **5-Schichten-Architektur** neu). **Lehre:** Release-Task muss Übersichten + Architektur-Diagramme enumerieren — die Drift über AP-50/51/52 fiel erst dem Nutzer auf (Insight `2026-06-28-release-task-muss-uebersichten-mitziehen.md`). App-Start = Tray (`run.sh --tray`, Memory). |
| 10 | 2026-06-28 | Opus 4.8 (1M) Hauptschleife; Subagenten **haiku** (Model-Task, mechanisch) / **sonnet** (Loader/Route/UI/Release-Impl + alle Task-Reviews + Follow-up-Fix) / **opus** (Final-Whole-Branch-Review) | ~300k (Schätzung; `/context`-Endstand nicht abgerufen — eine Feature-Session, Hauptschleife durch SDD schlank) | 10 eigene (0 Merges) | 262 → 272 | 0.39.0 → 0.40.0 (1× MINOR) | ~14 (Tier-2-SDD: 5 Implementer + 5 Task-Reviewer + 1 Task-4-Fix + 1 Task-4-Re-Review + 1 Final/opus + 1 Follow-up-Fix) | 4 feat / 2 fix (+ 4 docs) | Gesamt 1065 ins. / 42 Dateien; **Code-only 154 ins. / 9 del / 8 Dateien** (core/web/tests/config); Rest gener. SVG/Site | Chrome + Playwright (System-python3; `colRows`-Tooltip-Guard inkl. `"`-Injection-Wert) ✓; SQLite (keine Kommentare) + Fake-Inspector; **kein Live-DB mit Kommentaren** | Session 10 (Linux): **Tier-2 Tabellen-/Spaltenkommentare** → **v0.40.0** via SDD (1 Feature, 5 Tasks + Follow-up). Reflection liest `Column.comment`/`Table.comment` (robust ggü. SQLite: kein `comment`-Key, `get_table_comment`→`NotImplementedError`); `/api/schema`-Serialisierung; UI-Hover-Tooltips (Detailliste + UML). **Final-opus-Review fing eine Attribut-Injection** (`esc()` escaped kein `"` im `title="…"`) — betraf die 4 neuen Stellen **und** eine pre-existing `jt-step`-title → neuer Helfer `escAttr()`. Insight `2026-06-28-esc-ist-kein-attribut-escaper.md`. Doku/Roadmap/Board/Gantt + gh-pages durchgezogen; Arch-Diagramme bewusst unverändert (kein neues Modul/Endpoint). **Session 4 (Windows) weiter offen.** |
| 11 | 2026-06-28 | Opus 4.8 (1M) Hauptschleife; Subagenten **sonnet** (alle Implementer + Task-Reviewer) / **opus** (Final-Whole-Branch-Reviews) / Explore (1×, Generator-Aufrufflächen); Playwright/Chromium (System-python3) für UI-Smokes | ~790k (Schätzung; letzter `/context` 631.8k bei 63 % vor AP-C+D + Handoff) | 35 (0 Merges; 815bb05^..c843c5d) | 272 → 308 | 0.40.0 → 0.43.4 (**7 Releases**: 3× MINOR 0.41/0.42/0.43 + 4× PATCH 0.43.1–0.43.4) | ~43 (Tier-3 5T + Aggregat-Ops 4T + COUNT 3T + AP-A 2T + AP-B 2T + AP-C+D 2T: je Implementer + Task-Reviewer + 1 Final/opus pro AP; GROUP-BY-Fix inline ohne Subagenten via systematic-debugging+TDD) | 10 feat / 2 fix (+ ~21 docs) | Gesamt 5381 ins. / 58 Dateien; **Code-only 825 ins. / 211 del / 8 Dateien** (core/web/tests); Rest gener. SVG/Site/JSON | Chrome (App via Tray) + Playwright-UI-Smokes je UI-AP ✓ (CSS-Breite/Position via `getBoundingClientRect`, Legenden-Text); SQLite-Demo | Session 11 (Linux): **7 Releases**. (1) Aggregat-Kette vollendet — **Tier-3 GROUP BY/Aggregate** (v0.41.0), **HAVING + ORDER-BY-auf-Aggregaten** (v0.42.0), **COUNT(\*)/COUNT(DISTINCT)** (v0.43.0, Route unverändert), **GROUP-BY-Ableitungs-Fix** (v0.43.1, Aggregat allein in HAVING/ORDER BY erzwingt GROUP BY; systematic-debugging+TDD). (2) **UI-Umbau-Block** für den **SQL-Builder** (Brain-Dump → AP-A…F zerlegt): **AP-A** Umbenennung Join-Builder→SQL-Builder (v0.43.2, alles inkl. Bezeichner; Endpoint bleibt), **AP-B** Layout/Klausel-Sektionen+Aktionsleiste (v0.43.3, Variante C via ASCII-Mockups), **AP-C+D** Join-Typ inline + 1-N-Erklärung in Graph-Legende (v0.43.4). **Lehre:** Diff-Review bestätigt Code, aber CSS-Spezifität (`.sb-jt` 150px) + Jinja-Template-Caching (Legende erst nach App-Neustart) fängt nur der Browser-Smoke (Insight `2026-06-28-ui-diff-review-vs-browser-smoke.md`). Offen im Block: **AP-E** (Move ↑/↓) + **AP-F** (Analyzer-Vorschläge). |
| 12 | 2026-06-28 | Opus 4.8 (1M) Hauptschleife; Subagenten **sonnet** (Implementer + Task-Reviewer) / **opus** (Final-Whole-Branch-Reviews) / **Explore** (1×, 4-Bereiche-Recherche für neue APs); Playwright/Chromium (System-python3) für UI-Smokes + Form-Screenshots | ~680k (Schätzung; `/context` 650k bei 65 % vor Handoff) | 29 (0 Merge-Commits, 8 FF-Branches; 6caff79..c1d7df5) | 308 → 329 | 0.43.4 → 0.46.0 (**6 Releases**: 3× MINOR 0.44/0.45/0.46 + 3× PATCH 0.45.1–0.45.3) | ~19 (AP-E/AP-F/AP-59/AP-54 je Implementer + Task-Reviewer + Final/opus; 3 Fix-Subagenten; AP-58/AP-60 inline als Controller; 1 Explore) | 6 feat / 6 fix (+ 17 docs) | Gesamt 3927 ins. / 52 Dateien; **Code-only 289 ins. / 39 del / 10 Dateien** (core/web/tests/config); Rest gener. SVG/Site/JSON | Chrome + Playwright-UI-Smokes je UI-AP ✓ (gerenderte CSS-Eigenschaften via `getBoundingClientRect`/`getComputedStyle`, Legenden-/Button-Texte); Connection-Form per Screenshot (Oracle+MSSQL); SQLite-Demo; Cross-Schema nur Unit-Test (kein Live-Multi-Schema-Backend) | Session 12 (Linux): **6 Releases v0.43.4→v0.46.0**. (1) SQL-Builder-UI-Block vollendet: **AP-E** Zeilen-Move ↑/↓ (v0.44.0) + **AP-F** Analyzer-Optimierungs-Vorschläge (4 schema-freie AST-Heuristiken, eigene Kategorie; v0.45.0) → AP-A…F komplett. (2) Layout-Fixes: **AP-58** HAVING-Layout (Sektion hatte nie eigenes CSS; v0.45.1), **AP-59** 2-Spalten-Raster (Sektions-Label = „+ Label"-Button, erste Zeile auf gleicher Linie; v0.45.2). (3) **AP-60** Connection-Form-Ausrichtung (feste Label-Spalte, lange MSSQL-Labels umbrechen; v0.45.3). (4) Erste Migrations-Scheibe **AP-54** Cross-Schema-FK-Diagnose (read-only `ref_schema`+Info-Panel; Gate für AP-57; v0.46.0). Dazwischen **gesamter Backlog dokumentiert** (AP-55/56/57, AP-61/62, AP-63·S1-3) + 2 Konzept-Dokumente unter `docs/concepts/`. **Lehre:** vor einem teuren, schwer testbaren Feature erst ein billiges read-only Diagnose-AP, das den Bedarf empirisch klärt (AP-54 gated AP-57; Insight `2026-06-28-cheap-diagnostic-gates-expensive-feature.md`). HCMX-Kernerkenntnis: Cross-Produkt-Links sind fachliche IDs, keine FKs → Hebel ist implied-FK (AP-55) + Subsetting (AP-56), nicht Cross-Schema-Joins. |

## Details Session 1

- **Modell-Mix:** Hauptschleife Opus 4.8 (1M) ≈ 665k Output-Token. Subagenten
  (v1-SDD-Phase) gemischt: **haiku** für mechanische Transkriptions-Tasks
  (Modell/Loader-Stubs/Graph), **sonnet** für Integration + Task-Reviews,
  **opus** für die Final-Whole-Branch-Review. Σ subagent_tokens grob ~0,6–0,7 Mio
  (Schätzung; nicht exakt aus `/context` ableitbar).
- **Review-Fang-Quote (Bugs vor dem Browser):** ~7 echte Bugs in Task-/Final-Reviews
  gefangen — Duplikat-Join beim Filter-Weave (linearer Pfad statt Baum),
  Engine-Dispose-Leak im Fehlerpfad, nicht-deterministische Anker-Wahl,
  KeyError→500 statt 400, unbeschränkte Pfad-Enumeration, fehlende Spalten-
  Validierung, ungenutztes Logging.
- **Browser-entdeckt (Escape):** ~2 — kryptische Fehlermeldung bei leerem
  Connection-Feld (UX), PowerShell relativer Programmpfad in run.ps1.
- **Features:** v1-Kern (Reflection→FK-Graph→k-Pfade→read-only SQL), Filter-UI,
  Graph-Viz (Cytoscape, lokal), implied FKs, 3-Panel-Layout + Splitter,
  Detail-Sub-Tabs (Definition/Daten/SQL), Datenvorschau, Views, Verbindungs-Manager
  (4 DB-Typen), run.sh-Menü + run.ps1, portable Demo-CMDB.
- **Abgeleitet:** ~169 Tokens-ges./Commit-Hundertstel … grob **~22k Token/Commit**,
  **~81 Tests / 665k Token ≈ 12 Tests je 100k Token**, **fix/feat-Quote 5/16 ≈ 0,31**.

## Details Session 2

- **Modell-Mix:** Hauptschleife Opus 4.8 (1M). Subagenten: **sonnet** für
  Playwright-Verifikation + Screenshot-Aufnahme + Backend-Implementierung
  (AP-5-Ausführung), **general-purpose/opus** (geerbt) für die Doku-Build- und
  gh-pages-Deploy-Subagenten.
- **Arbeitspakete:** AP-1 (Graph-Interaktion/UML-Karte), AP-2 (Verbinden-Fehler
  entschärft), AP-3 (SQL-Optionen-Paket), AP-4 (mehrere SELECT-Spalten),
  AP-5 (Ausgabebereich + SELECT ausführen), AP-6 (Zeilen-Steuerung), AP-7
  (feiner Zoom + Slider), AP-8 (Reset-Fix), AP-9 (Ergebnisliste maximiert).
  Dazu Offline-Wheelhouse (Windows), AppImage/Poster/GitHub-Pages-Setup,
  Doku-Site-Feinschliff.
- **Verifikation:** Playwright e2e (u. a. 21/21 PASS für AP-6/7/8) + 7 neue
  Oberflächen-Screenshots (1400×900) + lokale Startseiten-Screenshots zur
  Layout-Abnahme; alle UI-Features im Browser getrieben, nicht nur unit-getestet.
- **Tests:** 81 → 111 (Δ +30; nur Backend — AP-7/8/9 waren reines Frontend ohne
  pytest-Abdeckung, daher via Playwright verifiziert).
- **Versionierung:** 0.1.0 → 0.2.0 → 0.3.0 → 0.3.1 (3× minor-ähnlich + 1 patch).
  Erkenntnis: `sync_version.py` deckt Doku-Versionsanzeige (icon-rail.js,
  zensical.toml) + Poster (make_poster.py) **nicht** ab → diese zeigten lange
  noch 0.1.0/81 Tests. Behoben + als Insight/Memory festgehalten.
- **Abgeleitet (mit Token-Schätzung ~800k):** grob **~31k Token/Commit**,
  **30 Test-Δ / 800k Token ≈ 3,8 Tests je 100k Token** (deutlich niedriger als
  Session 1 — Session 2 war feature-/UI-/doku-lastig statt test-getriebener
  Kernaufbau), **fix/feat-Quote ≈ 0,14** (Commit-Ebene).

## Details Session 3

- **Modell-Mix:** Hauptschleife Opus 4.8 (1M), **ohne Subagenten/Workflows** — alle
  APs inline umgesetzt. UI-Verifikation mit **Playwright + Chromium** (ad-hoc ins
  venv installiert, nicht in `requirements`).
- **Remote-Divergenz:** Lokal v0.3.0, Remote bereits v0.3.1 (Session 2). Erst beim
  Push erkannt → Rebase der 2 lokalen Commits auf `origin/master` + **Umnummerierung**
  der geplanten APs (AP-9 war remote schon anders vergeben). Lehre als Memory:
  vor Arbeit `git fetch` + Divergenz prüfen.
- **Arbeitspakete:** AP-14 (Python-3.14-Wheelhouse cp314), AP-11 (Composite FK voll),
  AP-10 (Topbar-Verbindungen), AP-13 (UI-Politur), AP-15 (`run.ps1` abbruchsicher/NO-CDN),
  AP-12 (MSSQL-Backend), AP-20 (Copy-Icon), AP-21 (Balkenhöhe). Backlog AP-16…25 dokumentiert.
- **Tests:** 111 → 118 (Δ +7; viel UI-/Infra-Arbeit ohne pytest-Abdeckung → per Playwright verifiziert).
- **Versionierung:** 0.3.1 → 0.10.0. Regel etabliert: **1.0.0 nur auf Ansage**, sonst Feature → minor / Fix → patch.
- **Geräte-Scope:** Windows-only; Linux-Arbeiten (Doku-Site bauen, `run.sh`, AppImage,
  realer MSSQL-Test) bewusst auf die Abend-Session am anderen Rechner verschoben.

## Details Session 4

- **Modell-Mix:** Hauptschleife Opus 4.8 (1M), **ohne Subagenten/Workflows** — alle APs
  inline (wie Session 3). Lief auf **Windows**; UI im Browser (Chrome) getrieben.
- **Token-Erfassung:** Kein `/context`-Endstand notiert → Token-Gesamt **n/a**. Lehre für
  künftige Windows-Sessions: Endstand vor dem Handoff abrufen.
- **Arbeitspakete:** AP-23 (Join-Builder-Maske vereinheitlicht) + UI-Politur (Copy-Icon in
  SELECT-Box, Default-Graphbreite, Resize-Autofit), AP-16 (Graph-Layout auf **dagre**
  lokal gebündelt statt cose; `cytoscape-dagre` evaluiert + wieder entfernt), **App-Rename**
  „Lucent DB Explorer" → „LucentTools DB Explorer", AP-26 (Audit-Prozess `docs/audits/`),
  AP-18 (Multi-Tabellen-Join als bereits implementiert verifiziert), AP-28/AP-32 (UI-Fixes),
  AP-27 (Insights-Ort/Prozess), AP-17 (Release-ZIP `tools/build_release.py` → GitHub-Releases).
- **Deployment-Schwerpunkt (PowerShell 5.1 / RDS):** `run.ps1` reines ASCII + UTF-8-BOM,
  Start-Abbruch behoben, `-DebugMode`, `threaded=True`. Releases v0.11.2 + v0.11.3 online.
- **Tests:** 118 → 118 (Δ ±0; reine UI-/Build-/Doku-Arbeit ohne pytest-Abdeckung → per
  Browser verifiziert).
- **Versionierung:** 0.10.0 → 0.11.0 (minor) → 0.11.1 → 0.11.2 → 0.11.3 (3 Patches).
- **LOC ehrlich:** 4507 Insertions, davon 3809 die gebündelte `dagre.min.js` (Vendored-Lib,
  nicht selbst geschrieben) → **Code-only ~698 Insertions / 32 Dateien**.

## Details Session 6

- **Modell-Mix:** Hauptschleife Opus 4.8 (1M). Subagenten konsequent nach Aufgabe:
  **haiku** für Transkriptions-Tasks (Plan enthielt vollständigen Code), **sonnet** für
  Task-Reviews + Integration (Routen, Frontend), **opus** für die beiden finalen
  Whole-Branch-Reviews. Zwei Features je als eigenständiges SDD (Brainstorm → Spec →
  Plan → 6 bzw. 7 Tasks → Final-Review → Merge).
- **Arbeitspakete:** AP-30 (N-1-Stern: Auto-Weaving der Select-/ORDER-BY-/Filter-Tabellen
  + Fan-out-Warnung) → v0.17.0; AP-25 Scheibe 1 (read-only SQL-Analyzer via sqlglot:
  parsen/klassifizieren, gelesen/geschrieben, Warnungen, Graph-Highlight; 2 Modi) → v0.18.0.
- **Review-Fang-Quote:** Per-Task-Reviews fingen u. a. einen vom Plan übersehenen 3.
  `filter_tables=`-Keyword-Aufrufer (AP-30) und mehrere Test-Hygiene-Punkte. **Die finale
  opus-Review (AP-25) fing 3 echte Defekte, die die 100 % grüne Suite passiert hatten:**
  PostgreSQL/MSSQL-500 (Dialektname nicht sqlglot-kompatibel; SQLite-only-Tests maskierten),
  NO_WHERE-False-Negative (Subquery-WHERE), UNKNOWN_COLUMN-False-Positive (case-sensitiv).
  Siehe Insight `2026-06-27-finalreview-faengt-sqlite-blindspot.md`.
- **Unicode-Lehre (2. Session in Folge):** haiku lässt das schließende `„ … “` (U+201C)
  fallen → ASCII `"`; Controller byte-verifiziert + fixt manuell.
- **Doku/Deploy:** Architekturbild (Diagramm 1+3+Prosa) um den Analyzer erweitert;
  `zensical.toml`-Versionsdrift (v0.17.0) gefangen; gh-pages 2× deployed (v0.17.0, v0.18.0).
- **Abgeleitet (~473k Hauptschleifen-Token):** grob **~18k Token/Commit**,
  **~236k Token/MINOR-Feature** (2 Features), **Test-Δ +33 / 473k ≈ 7 Tests je 100k Token**.
  Niedrigerer Token/Commit als Session 1–2, weil die teure Arbeit (Implementierung +
  Reviews) in Subagenten lag und die Hauptschleife v. a. orchestrierte.
- **Offen:** Session 4 (Windows, v0.10→0.11.3) weiterhin nicht nachgetragen.
