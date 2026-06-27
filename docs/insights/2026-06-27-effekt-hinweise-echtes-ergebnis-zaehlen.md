# Effekt-Hinweise müssen das echte Ergebnis zählen, nicht isoliert proben

**Session 7 (Linux), 2026-06-27, AP-36…49, v0.18.0 → v0.31.0.**

## Erkenntnis

Ein UI-Hinweis, der vorhersagt „diese Auswahl ändert das Ergebnis", muss den
**echten, kontextvollen Effekt** messen — nicht eine vereinfachte Teil-Eigenschaft
in Isolation. Sonst entstehen **Falsch-Positive**, die das Vertrauen in den Hinweis
zerstören.

## Konkreter Fall (AP-47)

Der Waisen-Chip am Join-Typ sollte zeigen, wo `LEFT`/`RIGHT`/`FULL` zusätzliche
(unverknüpfte) Zeilen bringt. **Erste Umsetzung:** pro Join-Station eine isolierte
`NOT EXISTS`-Probe („gibt es A-Zeilen ohne B?"). Sah plausibel aus, war aber
**falsch im Pfad-Kontext**:

- **Unerreichbarkeit:** `Cluster → Datacenter → Network` — es gibt ein `Datacenter`
  ohne `Network` (isolierte Waise), aber **kein Cluster zeigt darauf**. Von
  `FROM Cluster` aus ist die Waise nie in der akkumulierten linken Seite → `LEFT`
  ändert nichts.
- **Downstream-Filterung:** Ein mittlerer `LEFT JOIN` erzeugt `NULL`-Zeilen, die der
  nächste `INNER JOIN … ON <NULL> = …` sofort wieder herauswirft.

Der Nutzer stellte LEFT ein, der Chip versprach Waisen — die Tabelle änderte sich
nicht. **Zu Recht**, aber der Chip log.

**Fix:** `/api/orphan_check` **zählt jetzt das echte Ergebnis** — `COUNT(*)` mit
`LEFT/RIGHT/FULL` an Schritt k vs. `INNER` (übrige Schritte auf aktuellem Stand).
Der Chip erscheint nur, wenn die Zeilenzahl sich wirklich ändert. Chip und Tabelle
sind seither konsistent (verifiziert: kurzer Pfad keine Chips & 16→16; direkter
Pfad Chip & 6→8).

## How to apply

- Bei „würde X das Ergebnis ändern?"-Hinweisen: **die echte Query (oder ein COUNT
  davon) ausführen und vergleichen**, statt eine lokale Heuristik zu raten. Read-only
  COUNT-Proben sind billig genug für ein Explorations-Tool.
- Kontext zählt: Erreichbarkeit von der Treiber-Tabelle **und** nachfolgende
  Operationen können einen lokal-wahren Effekt global zunichtemachen.
- Demo-Daten brauchen die Sonderfälle (hier: gezielte **Waisen** über viele
  Tabellen), damit das Feature überhaupt sichtbar/testbar ist.

## Nebenerkenntnisse

- **Toleranter Parser ≠ Validator:** sqlglot parst `LEFTI JOIN` als *Tabellen-Alias*
  → kein Syntaxfehler. Tippfehler im Schlüsselwort sind nur per **Heuristik**
  (Edit-Distanz zum Keyword) fangbar, nicht per striktem Parsen.
- **Fehlermeldungen enthalten ANSI-Codes:** sqlglot unterstreicht das Fehler-Token
  mit `\x1b[..m` → im Browser Müll. Vor der Anzeige **strippen**.
- **CY.center() statt CY.fit():** Beim Verkleinern des Graph-Bereichs den Zoom
  **behalten** und nur re-zentrieren wirkt ruhiger als ein Zoom-Sprung durch fit().
