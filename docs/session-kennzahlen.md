# Session-Kennzahlen — Lucent DB Explorer

Eine Zeile je Session (Schema: `.pattern/session-handoff-kpi.pattern`).
Macht den Projektverlauf auswertbar (Tokens/Commit, Tokens/Feature, Tests-Δ je 100k Tokens, Modell-Mix).

| # | Datum | Modell | Tokens ges. (Hauptschleife) | Commits (Merges) | Tests (von→bis) | Version | Subagent-Dispatches | feat/fix | LOC (insert/Dateien) | Geräte-verifiziert | Notiz |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-06-25 | Opus 4.8 (1M) Hauptschleife; Subagenten haiku/sonnet/opus | 664.8k (`/context` Endstand; Messages 644.9k / Tools 13.2k) | 30 (1 FF-Merge) | 0 → 81 | (neu) → 0.1.0 | ~28 (v1-SDD: ~10 Implementer + ~10 Reviewer + ~6 Fixer + 1 Final-Review/opus) | 16 / 5 | 5065 / 64 | Browser (Chrome) + Playwright e2e ✓ | Session 1: neues Projekt von Null; Flask-Web statt PyQt6-Pattern |
| 2 | 2026-06-26 | Opus 4.8 (1M) Hauptschleife; Subagenten sonnet (Verify/Screenshots) + general-purpose/opus (Deploy) | ~800k (Schätzung; Session lief in Auto-Compaction, `/context`-Endstand nicht abgerufen) | 26 (31→56; 1 fremd: 9d55a9c) | 81 → 111 | 0.1.0 → 0.3.1 | ~25 (Pre-Compaction: AP-1/2-SDD + Wheelhouse + Docs; Post-Compaction ~7: Verify + Screenshots + 4× Deploy) | 7 / 1 (Commit-Ebene; AP-8/AP-2-Fixes gebündelt) | 11267 / 98 (inkl. gener. SVG/JSON/Screenshots/Wheels) | Playwright e2e (21/21 + 7 Screenshots) + Chrome ✓ | Session 2: AP-1…AP-9; read-only-Ausführung eingeführt; Doku-Versions-Drift (icon-rail.js/zensical/poster) behoben; Startseite 2-spaltig + AP-Band 3-spaltig |
| 3 | 2026-06-26 | Opus 4.8 (1M) Hauptschleife; **keine Subagenten** (alles inline); Playwright/Chromium zur UI-Verifikation | ~640k (Schätzung; letzter `/context` 584.7k bei 58 %) | 10 eigene (56→69; +7 Session-2-Commits beim Rebase integriert) | 111 → 118 | 0.3.1 → 0.10.0 | 0 | 6 / 1 (+ 8 docs, 1 build) | ~1419 ins. / 101 Dateien (inkl. der integrierten Session-2-Commits) | Playwright/Chromium (AP-10/13/20/21: Clipboard-, Höhen-, Filter-, Splitter-Checks) ✓ | Session 3: Remote-Divergenz → Rebase + AP-Umnummerierung; Python-3.14-Wheelhouse (cp314); AP-10/11/13/20/21 komplett + AP-12-Backend/AP-15-Windows; Backlog AP-16…25 dokumentiert; **Windows-only** (Linux abends) |
| 5 | 2026-06-27 | Opus 4.8 (1M) Hauptschleife; Subagenten general-purpose/opus (Doku-Reconcile + UI-Screenshots) | ~799k (`/context` Endstand 799.2k bei 80 %) | 17 eigene (0 Merges; ab Pull 05de9a5) | 118 → 138 | 0.11.3 → 0.16.0 | 2 | feature-lastig (5 APs) | 3468 ins. / 68 Dateien (inkl. gener. SVG/Screenshots/Site) | Chrome + Playwright + **echtes MSSQL 2022** (podman) ✓ | Session 5 (Linux): AP-15/33/14/29/12 → v0.16.0; Python 3.14 via uv; MSSQL real getestet; Backlog konsolidiert (AP-17 gestrichen, AP-22/24 entschieden, AP-30 rescoped); Doku/Pages durchgehend deployed. **Session 4 (Windows, v0.10→0.11.3) noch nachzutragen.** |

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
