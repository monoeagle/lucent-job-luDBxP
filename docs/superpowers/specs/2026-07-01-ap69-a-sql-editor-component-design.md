# AP-69 Slice A — Gemeinsame SQL-Editor-Komponente (Design)

**Datum:** 2026-07-01 · **Status:** freigegeben (Brainstorm), Plan folgt
**Betrifft:** `web/` (Frontend: `static/js/app.js`, `static/css/app.css`, ggf. `templates/index.html`) — kein `core/`-Code.

## Problem / Ziel

Die SQL-Flächen der App sind heute uneinheitlich: der **Analyzer-Input** ist ein `<textarea>` mit
3-Schicht-Zeilennummern-Editor (`attachLineGutter`, AP-65·B, hell), die **Ausgaben** sind schlichte
dunkle `<pre>`-Blöcke **ohne** Zeilennummern (generiertes SQL `sql_out`, Detail-„SQL"-Tab `viewdef`
für Trigger/Routine/View/Matview/Tabellen-DDL, Subset-Pro-Tabelle-SQL `sql`).

Ziel: **eine gemeinsame SQL-Editor-Komponente** für ALLE SQL-Flächen — mehrzeilig, mit
Zeilennummern, einheitlich **dunkler „Code"-Look**. Editierbar beim Analyzer (Cursor, heller Text),
**read-only gedimmt** überall sonst (kein Cursor, matterer Text, nicht editierbar). „Die selbe
Komponente, nur grau" (Nutzerwunsch).

## Entscheidungen (aus dem Brainstorm)

1. **Einheitlich dunkel, read-only gedimmt** (nicht: hell/grau, nicht: heutige Zwei-Farben).
2. **Klassen umbenennen** `.an-*` → `.sqled-*` (geteilter, neutraler Name).
3. **Subset-Pro-Tabelle-SQL wird mit umgestellt** (Konsistenz, „alle SQL-Felder").
4. **YAGNI:** kein Syntax-Highlighting, keine Autocomplete. Nur Zeilennummern + Mehrzeiligkeit +
   dunkel + read-only-Dimmen.

## Architektur / Komponente

### `sqlEditor(opts)` — Factory in `static/js/app.js`
Verallgemeinert das bestehende `attachLineGutter`. **Erzeugt** die DOM-Struktur selbst (statt eine
vorhandene Textarea zu umschließen), damit Aufrufer sie überall gleich einsetzen können.

```js
// Signatur
sqlEditor({ value = "", readOnly = false, rows = 14 }) -> {
  el,                    // Wurzel-<div class="sqled-editor">, vom Aufrufer eingehängt
  getValue(),            // -> string (textarea.value)
  setValue(str),         // setzt Wert + refresht Gutter/Backdrop
  setErrorLine(n|null),  // nur sinnvoll bei readOnly=false (Analyzer); no-op sonst
}
```

**Struktur (wie heute, neutrale Klassen):**
`div.sqled-editor` > `div.sqled-gutter > div.sqled-gutter-inner` (Zeilennummern `div.sqled-num`)
+ `div.sqled-area > (div.sqled-backdrop > div.sqled-backdrop-inner` mit `div.sqled-line` je Zeile`)
+ `textarea`. `wrap="off"`, Monospace, dunkel.

**Verhalten:**
- `readOnly=false`: editierbar, resizable (wie heute der Analyzer). `setErrorLine` markiert die Zeile
  (`.sqled-line--error`) + scrollt sie in den Blick (heutige Logik aus `attachLineGutter`
  übernommen). Der Analyzer setzt bei `input` die Fehlerzeile zurück.
- `readOnly=true`: `textarea.readOnly = true`, Klasse `sqled-editor--readonly` (Text gedimmt, kein
  Caret). **Höhe wächst mit dem Inhalt** bis zu einem Max (`max-height`, dann Scroll) — kein winziges
  Scrollfeld für kurze Statements. `setErrorLine` ist no-op.

`attachLineGutter` entfällt; sein Innenleben (Gutter-Refresh, Scroll-Sync, Fehlerzeile) lebt in
`sqlEditor` weiter.

### CSS (`static/css/app.css`)
Die heutigen `.an-editor/.an-gutter/.an-gutter-inner/.an-gutter-num/.an-edit-area/.an-backdrop/
.an-backdrop-inner/.an-line/.an-line-error`-Regeln + die dunklen `.sql_out`/`.viewdef`-Stile wandern
in **`.sqled-*`** zusammen (ein dunkles Thema). Neuer Modifier `.sqled-editor--readonly`
(gedimmter Text, kein Cursor, `resize:none`). Die Analyzer-Fehlerzeile wird `.sqled-line--error`.
`.an-parse-error` (Fehler-Auszug im Analyzer-Ergebnis) **bleibt** unverändert — das ist kein
SQL-Editor, sondern ein hervorgehobener Fehlerkontext.

### Umstellung der vier Flächen (`static/js/app.js`)
1. **Analyzer** (`openAnalyzer`, ~713/718): `<textarea id="an_sql">` + `attachLineGutter` →
   `sqlEditor({ readOnly:false, rows:14 })`; `panel._gutter` behält `setErrorLine` (gleiche API).
2. **Generiertes SQL** (`sql_out`, Aufbau ~474, Setzen 1447/914/1570, Copy 2199):
   `<pre id="sql_out">` → read-only `sqlEditor`. Ein Modul-Handle `SQL_OUT` hält die Instanz;
   Setz-Stellen nutzen `SQL_OUT.setValue(...)` statt `.textContent`; der Copy-Handler (`setupSqlCopy`,
   2197ff.) liest `SQL_OUT.getValue()` statt `$("sql_out").textContent`. Der Copy-Button (`#sql_copy`)
   + `.sql-wrap` bleiben; der Editor ersetzt nur das `<pre>` darin.
3. **Detail-„SQL"-Tab** (`viewdef`, Aufbau 410, Setzen 411): `<pre class="viewdef">` → read-only
   `sqlEditor`, Wert `sqlText || "(keine Definition)"`. Gilt für alle Detail-Arten
   (Trigger/Matview/Routine/View/Tabellen-DDL), da sie denselben SQL-Tab teilen.
4. **Subset-Pro-Tabelle-SQL** (`renderSubset`-Liste, ~746): jedes `<pre class="sql">` → read-only
   `sqlEditor`. (Kurze Statements; DOM-seitig unkritisch.)

## Tests / Verifikation

App-JS ist Browser-Code — **kein pytest**. Verifikation per **Playwright-Smoke** (System-`python3`,
Projekt-Konvention) gegen die laufende App, plus Screenshot zur Sichtprüfung:
- Analyzer: Editor editierbar, Zeilennummern sichtbar, Fehlerzeile nach fehlerhaftem SQL markiert.
- Generiertes SQL: nach Join-Auswahl read-only Editor mit Zeilennummern, **nicht** editierbar
  (`readOnly`), Copy-Button kopiert den Text (`getValue`).
- Detail-„SQL"-Tab einer View/Routine: read-only Editor mit dem Definitionstext.
- Screenshot des Analyzers + eines read-only Feldes (dunkel, gedimmt).

Die volle pytest-Suite muss unbeeinflusst grün bleiben (459 passed / 11 skipped) — reine
Frontend-Änderung.

## Betroffene Dateien (Überblick)

- `web/static/js/app.js` — `sqlEditor`-Factory (aus `attachLineGutter`), 4 Umstell-Stellen,
  `SQL_OUT`-Handle, Copy-Handler.
- `web/static/css/app.css` — `.an-*`/`.sql_out`/`.viewdef` → `.sqled-*` (dunkel) + `--readonly`.
- `web/templates/index.html` — nur falls dort SQL-Markup fest steht (prüfen; vermutlich nichts).

## Risiken / offene Punkte

- **Scroll-Sync & Höhe read-only:** die read-only Auto-Höhe (Inhalt bis Max) darf den Scroll-Sync
  (Gutter/Backdrop folgen `scrollTop/Left`) nicht brechen — im Plan an einem langen Definitionstext
  prüfen.
- **`app.js` ist groß (2207 Z.):** die Komponente bleibt eine lokale Factory (kein Modul-Split) —
  minimaler, fokussierter Eingriff, keine unnötige Umstrukturierung.
- **Neustart-Reibung:** Template/Route unverändert → JS/CSS sind live; App-Neustart nur nötig, falls
  doch `index.html`/Routes berührt werden (voraussichtlich nicht).
