# Design — AP-65·B Analyzer Zeilennummern-Gutter + Fehlerzeilen-Highlight

**Datum:** 2026-07-01
**Kontext:** LucentTools DB Explorer, AP-65 (Analyzer-Zeilen & Fehlerstelle). Stufe B des
Konzepts `docs/concepts/2026-06-29-analyzer-line-numbers-error-location.md`. Baut auf Stufe A /
A-Härtung / A-Härtung 2 auf (Parse-Fehler tragen bereits `parse_error_line`).

## Problem

Das Analyzer-Eingabefeld ist ein schlichtes `<textarea id="an_sql">` ohne Zeilennummern. Bei
einem Parse-Fehler nennt die Ergebnisanzeige zwar „Zeile N", aber der Nutzer muss die Zeile im
Textfeld manuell abzählen. Ein `<textarea>` kann nativ weder eine Zeilennummern-Spalte noch den
Hintergrund einer einzelnen Zeile darstellen.

## Scope

**Rein Frontend** (Vanilla-JS + CSS). Kein Backend-Change: `AnalysisResult.parse_error_line`
existiert seit AP-65·A und `/api/analyze` serialisiert es bereits. Keine neuen Python-Tests; die
bestehende Suite (438 passed / 10 skipped) bleibt unberührt.

**Nicht-Scope:** keine Auto-Korrektur, kein Syntax-Highlighting des SQL, kein Ersatz der
Textarea durch einen contenteditable-Editor, keine Lint-Zeilenbezüge (das ist Stufe C / AP-65·C).

## Architektur — 3 Schichten, Textarea bleibt Source of Truth

`#an_sql` wird beim Aufbau des Analyzer-Tabs in einen Container `<div class="an-editor">`
gewickelt, der drei deckungsgleiche Schichten enthält:

- **`.an-gutter`** (`aria-hidden="true"`) — Zeilennummern-Spalte links, feste Breite,
  `overflow: hidden`, nur vertikal scroll-synchron zur Textarea.
- **`.an-backdrop`** (`aria-hidden="true"`) — absolut hinter der Textarea positioniert, enthält
  eine leere Zeilen-`<div>` pro logischer Textzeile. Die Fehlerzeile trägt die Klasse
  `.an-line-error` (farbiger Hintergrund). Beidachsig scroll-synchron.
- **`<textarea id="an_sql" wrap="off">`** — transparenter Hintergrund, liegt oben (z-index),
  bleibt der einzige Wert-Träger; `runAnalyze` liest weiterhin `.value`. `white-space: pre`
  (kein Soft-Wrap) → **1 logische Zeile = 1 visuelle Zeile**; lange Zeilen erzeugen horizontalen
  Scroll statt Umbruch. Das macht das Row-Alignment zwischen den Schichten tragfähig.

Alle drei Schichten teilen exakt dieselbe Metrik: Monospace-`font-family`, `font-size`,
`line-height`, `padding` (oben/unten identisch), `box-sizing: border-box`. Nur so decken sich die
Zeilen pixelgenau.

## Kapselung

Ein selbstständiger, testbarer Baustein `attachLineGutter(textarea)` (in `web/static/js/app.js`,
Analyzer-Abschnitt) baut die Container-Struktur um die übergebene Textarea und liefert ein kleines
Interface zurück:

- `setErrorLine(n)` — `n` = 1-basierte Zeilennummer oder `null`. Setzt/entfernt `.an-line-error`
  auf der Backdrop-Zeile `n` und scrollt die Textarea so, dass die Zeile sichtbar ist. `null`
  oder außerhalb des gültigen Bereichs → alle Highlights entfernt.
- `refresh()` — baut Gutter + Backdrop-Zeilen aus dem aktuellen Textarea-Wert neu (Zeilenzahl =
  `value.split("\n").length`, mindestens 1).

Intern registriert der Baustein Listener: Textarea-`input` → `refresh()` + Highlight löschen;
Textarea-`scroll` → Gutter/Backdrop synchronisieren (`gutter.scrollTop = textarea.scrollTop`;
`backdrop.scrollTop = textarea.scrollTop`; `backdrop.scrollLeft = textarea.scrollLeft`).

`openAnalyzer` ruft `attachLineGutter` einmal beim Tab-Aufbau und hält die Referenz am Panel.
`renderAnalyzeResult` ruft `setErrorLine(res.parse_error_line ?? null)` — bei Erfolg (kein
`parse_error`) `setErrorLine(null)`.

## Datenfluss

1. Nutzer tippt → `input` → Gutter + Backdrop passen die Zeilenzahl an, ein evtl. bestehender
   Fehler-Highlight wird gelöscht (das SQL hat sich geändert).
2. Nutzer scrollt die Textarea → Gutter (vertikal) und Backdrop (beide Achsen) folgen synchron.
3. „Analysieren" → `/api/analyze` → bei Parse-Fehler mit `parse_error_line = L` bekommt
   Backdrop-Zeile `L` die Klasse `.an-line-error`, die Textarea scrollt `L` in den sichtbaren
   Bereich. Bei erfolgreichem Parse wird der Highlight entfernt.

## Edge-Cases

- **Leere Eingabe:** Gutter zeigt „1", Backdrop hat eine Zeile, kein Highlight.
- **No-Wrap-Highlight-Breite:** Die Backdrop-Zeilen erhalten `min-width: 100%` (bzw. dehnen sich
  über die volle Scrollbreite), damit der farbige Hintergrund auch bei horizontalem Scroll die
  ganze Zeile abdeckt.
- **`parse_error_line` außerhalb des aktuellen Textbereichs** (Nutzer hat nach dem letzten Klick
  editiert, dann erneut analysiert mit weniger Zeilen): `setErrorLine` prüft `1 <= n <= rows` und
  ignoriert ungültige Werte lautlos (kein Highlight statt falscher Zeile).
- **Kein `parse_error_line`** (z. B. leere Eingabe, oder erfolgreicher Parse): `setErrorLine(null)`.

## Tests

Kein Python-Change → die pytest-Suite bleibt bei 438 passed / 10 skipped (Regressions-Guard).

Frontend-Verifikation via Playwright-DOM-Smoke (System-`python3`, wie in Projekt-Konvention):

- Mehrzeiliges SQL eingeben → `.an-gutter` enthält die korrekten Zeilennummern (1..N), N =
  Zeilenzahl.
- Scroll-Sync: Textarea vertikal scrollen → `gutter.scrollTop == textarea.scrollTop`.
- Kaputtes Statement analysieren (unclosed Quote in Zeile L) → die Backdrop-Zeile mit Index L−1
  trägt `.an-line-error`; genau eine Zeile ist markiert.
- Nach einem Edit (`input`) ist kein `.an-line-error` mehr vorhanden.
- Screenshot-Sichtprüfung des Gutters + der hervorgehobenen Zeile (Alignment).

## Betroffene Dateien

- `web/static/js/app.js` — `attachLineGutter(textarea)` (neu), `openAnalyzer` (Verdrahtung),
  `renderAnalyzeResult` (`setErrorLine`-Aufruf).
- `web/static/css/app.css` — `.an-editor` / `.an-gutter` / `.an-backdrop` / `.an-line-error` +
  geteilte Metrik-Regeln für `#an_sql`.

## Randbedingungen

- NO-CDN: reines Markup/CSS, keine externe Editor-Lib.
- Read-only: der Analyzer führt weiterhin nichts aus; der Gutter ist reine Anzeige.
- `aria-hidden` auf Gutter + Backdrop (dekorativ; die Textarea bleibt das zugängliche Feld).
