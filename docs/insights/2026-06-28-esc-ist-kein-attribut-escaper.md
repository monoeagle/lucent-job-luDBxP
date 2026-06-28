# Insight: `esc()` (textContent→innerHTML) ist KEIN Attribut-Escaper

**Datum:** 2026-06-28 (Session 10, Tier-2)
**Kontext:** Tier-2 rendert Tabellen-/Spaltenkommentare in `title="…"`-Tooltips.

## Beobachtung

Der Frontend-Helfer `esc()` in `web/static/js/app.js` escaped via
`div.textContent = s; return div.innerHTML`. Diese Text-Node-Serialisierung
kodiert `&`, `<`, `>` — **aber nicht `"`**. Das ist korrekt für Text-Inhalt
(`>…<`), aber **unsicher in einem doppelt-gequoteten Attribut**:

```js
`title="${esc(comment)}"`   // comment = 'Fach-"Notiz"'
// → title="Fach-"Notiz""   → Attribut bricht am ersten " auf (Injection)
```

## Warum es durchrutschte

- Der **Implementer** folgte dem Plan, der `esc()` vorschrieb — der Plan-Autor
  (Controller) nahm an, `esc()` decke Attribute ab. Tat es nicht.
- Der **Task-Reviewer** prüfte „geht `esc()` durch?" → ja. Die Frage war falsch
  gestellt: nicht *ob* escaped wird, sondern *für welchen Kontext*.
- Der **Playwright-Test** nutzte einen Kommentar ohne `"` → grün trotz Bug.
- Erst die **finale Whole-Branch-Review (opus)** stellte die richtige Frage
  („escaped `esc()` ein `"` im Attribut-Kontext?") und fand den Bug — **plus**
  eine pre-existing Stelle (`jt-step`-title) mit demselben Muster.

## Lehre

1. **Kontext-spezifisches Escaping:** Text-Escaper ≠ Attribut-Escaper. Für
   gequotete Attribute braucht es zusätzlich `"`→`&quot;`. Lösung hier:
   `escAttr(s) = esc(s).replace(/"/g, "&quot;")` an allen `title="${…}"`-Stellen
   mit interpolierten Daten.
2. **Test muss den Angriffswert enthalten:** ein Escaping-Test mit harmlosem
   Wert beweist nichts. Den problematischen Charakter (`"`) explizit einbauen.
3. **Review-Frage präzise stellen:** „wird escaped?" ist zu schwach; „wird für
   *diesen* Kontext (Attribut/HTML/JS/URL) korrekt escaped?" ist die richtige.
4. **Final-Review verdient den teuren Modell-Slot:** zum zweiten Mal (vgl.
   `2026-06-27-finalreview-faengt-sqlite-blindspot.md`) fing erst die
   Whole-Branch-Review einen echten Defekt hinter grünen Tests + sauberen
   Task-Reviews — diesmal sogar einen Alt-Bug außerhalb des Feature-Scopes.

## Restrisiko / Exploitability

Die gerenderten Werte sind Schema-Identifier (Tabellen-/Spaltennamen,
Join-Step-Labels) bzw. DB-gepflegte Kommentare. Ausnutzbar nur bei
**feindlichem DB-Schema** — schwache Voraussetzung für ein lokales,
read-only Single-User-Tool. Trotzdem gefixt (trivial, sobald `escAttr`
existiert). Andere `title='…'`/`title="${literal}"`-Stellen sind Literale →
kein Bug.
