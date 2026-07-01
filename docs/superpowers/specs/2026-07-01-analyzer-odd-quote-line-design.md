# Design — Analyzer Pro-Zeile-Ungerade-Quote-Heuristik

**Datum:** 2026-07-01
**Kontext:** LucentTools DB Explorer, AP-65-Serie (Analyzer-Fehler-UX). Follow-up aus
Session 16 (Handoff `docs/handoffs/2026-06-30-0145.md`), empirisch vorverifiziert.

## Problem

Bei einem nicht geschlossenen Anführungszeichen wirft sqlglot einen `TokenError`
ohne strukturierte Position. Der heutige `TokenError`-Zweig in
`core/sqlanalyze.py::_parse_error_location` lokalisiert über `_unclosed_quote_offset`
das am **Statement-Ende** offene Quote und markiert dieses. Bei einem *verschobenen*
Quote (Quote fehlt weiter oben, danach folgen wieder balancierte Quotes) zeigt das
EOF-Quote in die falsche Zeile — die eigentliche Fehlerzeile liegt höher.

## Kern-Einsicht (empirisch verifiziert)

Ein fehlendes Quote erzeugt in genau der betroffenen Zeile eine **ungerade** Anzahl
dieses Quote-Zeichens. Korrekt gepaarte Quotes und verdoppelte `""`-Escapes tragen je
eine **gerade** Zahl bei und bleiben neutral. Da die Gesamtzahl bei einem unclosed
Quote ungerade ist, hat eine ungerade Anzahl von Zeilen eine ungerade Zählung — der
verlässliche, häufige Fall ist **genau eine** solche Zeile.

**Grenze:** Die Heuristik findet die **Zeile**, nie die **Spalte**. Bei einem
*fehlenden* Quote gibt es keine echte Zeichenposition (Beispiel: `main"."x"` müsste
`"main"."x"` sein → das fehlende Quote sitzt am Zeilenanfang, nicht dort, wo eine
Links-nach-rechts-Paarung hinzeigen würde). Diese Ehrlichkeits-Grenze wird explizit
kommuniziert, nicht kaschiert.

## Verhalten

Nur im `TokenError`-Zweig mit unclosed Quote (`_unclosed_quote_offset(sql)` liefert
`off != None`; Quote-Zeichen `q = sql[off]`).

Neuer reiner Helper `_odd_quote_line(sql, q)`:
- Zählt je Zeile das Vorkommen von `q`.
- Gibt die **1-basierte Zeilennummer** der **einzigen** Zeile mit ungerader Zählung
  zurück; bei 0 oder ≥2 ungeraden Zeilen `None` (mehrdeutig → kein Rateschluss).

Redirect-Bedingung: `_odd_quote_line` liefert eine Zeile **und** diese ≠ EOF-Quote-Zeile.

- **Redirect (Bedingung erfüllt):**
  - `parse_error_line` = ungerade Zeile
  - `parse_error_col = None`
  - `parse_error_context` = voller Zeilentext (ohne `\n`)
  - `parse_error_highlight = ""`, `parse_error_highlight_pos = -1` (kein Zeichen-Mark)
  - `parse_error_hint` = „Vermutlich fehlt ein `<q>` in Zeile N — die genaue Position
    ist nicht bestimmbar (fehlendes Anführungszeichen)."
- **Sonst** (kein/mehrdeutiger Treffer, oder Zeile == EOF-Zeile): unverändert heutiges
  EOF-Verhalten (bestehende Tests bleiben grün, keine Spalten-Änderung).

Der echte Gewinn ist der Fall „Quote fehlt oben, weiter unten wieder balancierte
Quotes": EOF zeigt fälschlich nach unten, die Heuristik nach oben.

## Betroffene Dateien (kleine, ehrliche Scheibe)

- `core/sqlanalyze.py` — Helper `_odd_quote_line` + Redirect-Logik im TokenError-Zweig
  von `_parse_error_location`.
- `web/static/js/app.js` (~Zeile 547) — `, Spalte Y` weglassen, wenn
  `parse_error_col == null` (sonst rendert die UI „Spalte null"). `highlight == ""`
  ⇒ `i == -1` ⇒ ganze Zeile ohne Mark (bestehende JS-Logik trägt das bereits).

## Tests

- **Helper-Unit-Test** `_odd_quote_line`: balanciert → `None`; genau eine ungerade
  Zeile → deren Nummer; zwei ungerade Zeilen → `None`; `""`-Escape zählt gerade.
- **Redirect-Fall:** unclosed Quote in oberer Zeile, danach balancierte Quotes →
  `parse_error_line` = obere Zeile, `parse_error_col is None`,
  `parse_error_highlight == ""`, `parse_error_highlight_pos == -1`, Hint nennt die Zeile.
- **Nicht-Regression:** die bestehenden Parse-Error-Tests
  (`test_parse_error_tokenerror_unclosed_quote_short/_multiline`, ParseError-Fälle,
  valides SQL) bleiben unverändert grün — keine Spalten-/Mark-Änderung dort.

## Nicht-Ziele / Randbedingungen

- Kein DB-Zugriff, read-only, NO-CDN unberührt.
- Keine Spalten-Rekonstruktion (bewusst weggelassen — nicht bestimmbar).
- Mehrdeutige Fälle (≥2 ungerade Zeilen, z. B. legitimer mehrzeiliger String plus
  echter Fehler) fallen bewusst auf das heutige EOF-Verhalten zurück.
