# Design: AP-A — Umbenennung „Join-Builder" → „SQL-Builder"

**Datum:** 2026-06-28
**Status:** Genehmigt (Brainstorming abgeschlossen)
**Kontext:** Erstes AP eines UI/UX-Umbau-Blocks für den Builder. Reine, durchgängige Umbenennung
(sichtbarer Text + interne Bezeichner + Doku), bewusst zuerst, damit alle folgenden Builder-APs
(Layout, Join-Typ-Inline, 1-N-Legende, Zeilen-Move, Analyzer-Vorschläge) auf den neuen Namen
referenzieren.

## Ziel

Das Werkzeug, das bisher „Join-Builder" heißt, soll durchgängig **„SQL-Builder"** heißen — der
Name beschreibt besser, was es tut (es erzeugt read-only SQL, nicht nur Join-Pfade). Die
Umbenennung ist vollständig: sichtbarer Text, interne Code-Bezeichner und die user-facing Doku.

## Scope

**In Scope (umbenennen):**
- **Sichtbarer Text** (`web/static/js/app.js`):
  - Seitenmenü-Eintrag „Join-Builder" → „SQL-Builder".
  - Tab-Titel „Join-Builder" → „SQL-Builder".
  - Button „Join-Pfad bauen" → **„Generieren"**.
- **Interne Bezeichner** (`web/static/js/app.js` + `web/static/css/app.css`), durchgängiges Mapping:

  | Alt | Neu |
  |---|---|
  | `JoinBuilder` (z. B. `openJoinBuilder`, Kommentare) | `SqlBuilder` (`openSqlBuilder`) |
  | `joinbuilder` (Tab-ID, `data-action`, `.tab`/`.panel`-Selektoren) | `sqlbuilder` |
  | CSS-Klassen `jb-*` (z. B. `jb-controls`, `jb-swap`, `jb-fanout-hint`, `jb-join-types`, `jb-agg`, `jb-check`, `jb-limit`, `jb-dialect`, `jb-result-bar`, `jb-ctrl-h`, `jb-ctrl-w`) | `sb-*` |
  | Element-IDs `jb_*` (z. B. `jb_distinct`, `jb_limit`, `jb_dialect`, `jb_join_types`, `jb_fanout_hint`, `jb_rows`, `jb_refresh`, `jb_rows_info`, `jb_result_bar`) | `sb_*` |
  | JS-State-Vars `JB_*` (z. B. `JB_LAST`, `JB_PATH_IDX`, `JB_JOIN_TYPES`, `JB_JOIN_OPTS`, `JB_DISTINCT_CACHE`, `JB_ORPHANS_CACHE`) | `SB_*` |

  Jede `jb-*`-CSS-Klasse wird **in beiden** Dateien gemeinsam umbenannt (Template-String in
  `app.js` *und* Regel in `app.css`), sonst bricht das Styling.
- **Doku (aktuell/vorwärtsgerichtet):** `CLAUDE.md` sowie die Oberflächen-/Architektur-/Struktur-
  Referenzseiten unter `luDBxP-docs/docs/` (u. a. `referenz/oberflaeche.md`, `referenz/architektur.md`,
  `referenz/fanout-warnung.md`, `referenz/outer-joins.md`, `entwicklung/projektstruktur.md`,
  `entwicklung/testing.md`, `projekt/roadmap.md` — vorwärtsgerichtete Erwähnungen) → „SQL-Builder".
  Das Architektur-Diagramm wird in der Mermaid-Quelle (`luDBxP-docs/mermaid-sources/*.mmd`)
  umbenannt und beim Site-Build neu gerendert.

**Out of Scope (bewusst NICHT umbenennen):**
- **Der API-Endpoint `/api/joinpath` und `web/routes.py`** — stabiler Backend-Vertrag; „joinpath" ist
  nicht „joinbuilder". Kein Backend-Code wird angefasst.
- **Historische Changelog-Einträge** (`CHANGELOG.md`, `luDBxP-docs/docs/entwicklung/changelog.md`)
  und der historische Commit-/Aktivitäts-Verlauf (`project-activity.json`): sie protokollieren
  vergangene Releases unter dem damaligen Namen und bleiben unverändert (historischer Record).
- Keine Verhaltens-, Layout- oder Funktionsänderung — ausschließlich Namen.

## Verifizierter Ist-Stand

- Vorkommen in `app.js`: `joinbuilder` ×6, `openJoinBuilder` ×4, `JoinBuilder` ×7, `jb-*` ×13
  (distinct), `jb_*` ×37, `JB_*` ×50. In `app.css`: `jb-*`-Klassen (u. a. `jb-ctrl-h`, `jb-ctrl-w`,
  die in `app.css` definiert und in `app.js` dynamisch gesetzt werden).
- **Kein Test** (`tests/`) und **kein Template** (`web/templates/`) referenziert „Join-Builder",
  „joinbuilder", `jb_` oder `jb-` → die Umbenennung hat **keinen Python-/Test-Impact**; die
  pytest-Zahl bleibt **308 passed, 2 skipped**.

## Komponenten & Änderungen

### 1. `web/static/js/app.js`
Mechanische Ersetzung gemäß Mapping-Tabelle, plus die drei sichtbaren Strings. Reihenfolge der
Ersetzungen ist egal, solange das Ergebnis konsistent ist. Wichtig: Element-IDs (`jb_*`) und ihre
`$("…")`-Lookups, CSS-Klassen (`jb-*`) und ihre `querySelector`/`classList`-Nutzung, sowie
State-Vars (`JB_*`) müssen **paarweise** stimmen.

### 2. `web/static/css/app.css`
Alle `jb-*`-Regeln → `sb-*`. Muss mit den Klassen-Strings in `app.js` exakt korrespondieren.

### 3. Doku
Sichtbare „Join-Builder"-Erwähnungen in den oben genannten aktuellen Referenz-/Übersichtsseiten →
„SQL-Builder"; Architektur-Mermaid-Quelle umbenennen. Historische Changelog-Einträge unangetastet.

## Rückwärtskompatibilität / Risiko

Keine API- oder Datenänderung. Das einzige Risiko ist ein **übersehener Bezeichner** (z. B. eine
`jb_*`-ID im Markup umbenannt, aber der `$("jb_…")`-Lookup nicht — oder umgekehrt), was die UI still
bricht. Gegenmittel: nach der Ersetzung **`grep -nE "jb[-_]|JB_|JoinBuilder|joinbuilder"` über
`app.js` + `app.css` muss leer sein** (außer ggf. dem Wort in einem bewusst belassenen Kontext —
hier gibt es keinen), und ein **Browser-Smoke-Test** (SQL-Builder öffnen, Verbindung, „Generieren"
baut einen Pfad, keine Konsolenfehler, Styling intakt).

## Teststrategie

- **Kein neuer pytest-Test** (keine Python-Änderung); volle Suite bleibt grün (**308/2**) als
  Regressionswächter.
- **Statische Verifikation:** `node --check web/static/js/app.js` (Syntax) + die Grep-Bedingung oben
  (null Reste).
- **Browser-Smoke (Controller, Playwright):** SQL-Builder-Tab öffnet unter dem neuen Namen; Menü-/
  Tab-Label „SQL-Builder"; Button „Generieren" erzeugt einen Pfad + SQL; keine Konsolenfehler; die
  umbenannten CSS-Klassen greifen (Layout unverändert).

## Release

Reines UI/Doku, kein Core/Endpoint → **Patch-Bump 0.43.1 → 0.43.2** via `sync_version.py --patch`.
Changelog (Root + Mirror) „Changed: Join-Builder in SQL-Builder umbenannt …", CLAUDE.md/Roadmap
nachziehen, Test-Badge unverändert (308), Site-Build + (nutzer-gated) gh-pages-Deploy. Architektur-
Diagramme: nur Beschriftung „Join-Builder"→„SQL-Builder" in der Mermaid-Quelle, keine
Strukturänderung.
