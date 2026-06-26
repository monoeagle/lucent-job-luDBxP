# Audit — dagre / cytoscape-dagre (2026-06-26)

**Anlass:** AP-16 (Graph entzerren) — Einbinden eines hierarchischen Layouts.
**Geprüfte Artefakte:** lokal gebündelte JS unter `web/static/lib/`
- `dagre.min.js` (dagre 0.8.5, Browserify-Bundle inkl. lodash + graphlib) — **bleibt eingebunden**
- `cytoscape-dagre.js` (cytoscape-dagre 2.5.0, Webpack-UMD) — evaluiert, danach **entfernt**
  (ungenutzt: das Layout wird direkt über `window.dagre` getrieben, der Adapter kann keine
  Knickpunkte rendern)

**Bezug:** Download-Quelle unpkg (dagre@0.8.5, cytoscape-dagre@2.5.0), nach
`web/static/lib/` gespeichert; NO-CDN — keine `<script src="https://…">` im Template.

## Ergebnis: ✅ unbedenklich
Reine lokale Layout-Berechnung. Kein Netzwerk, keine dynamische Codeausführung,
keine Exfiltration, kein CDN-Verstoß.

## Befunde je Checklisten-Punkt
- **Netzwerk:** keine Treffer für `fetch`/`XMLHttpRequest`/`WebSocket`/`EventSource`/`sendBeacon`/`.ajax`.
- **Dynamische Codeausführung:** kein `eval(`, kein `new Function(`/`(0,eval)`, keine
  `setTimeout`/`setInterval`-String-Argumente, kein `importScripts`.
- **Smuggling/Obfuskation:** kein `Blob(`/`createObjectURL`/`Worker(`/`atob`/`btoa`.
- **Externe URLs:** nur in **Kommentaren** (Doku-Links z. B. `ecma-international.org`,
  `stackexchange`) — keine ausführbaren Endpunkte.
- **Module:** `require(...)` ausschließlich **Browserify-/Webpack-intern** (relative IDs
  `./_baseForOwn` bzw. numerische Modul-IDs). `cytoscape-dagre` nimmt im Browser den
  UMD-Zweig `factory(root["dagre"])` (Zeile 9) — **kein** Modul-Nachladen.
- **lodash `nodeUtil`:** versucht in Node `require('util')`, ist aber **try/catch-gekapselt**
  → im Browser No-op, kein Effekt.
- **Globale Schreibzugriffe:** `window.dagre` (dagre-UMD) und — solange eingebunden —
  `window.cytoscapeDagre` + Registrierung des `dagre`-Layouts auf cytoscape. Erwartet/plausibel.
- **NO-CDN:** Libs liegen lokal, Einbindung via `/static/lib/…`.

## Falsch-Positive (zur Einordnung)
- `=function(` (Methodendefinitionen) traf case-insensitiv auf `Function(` — unkritisch.
- „the new function" u. ä. sind Doku-Kommentare in lodash.

## Reproduktion
Siehe [README.md](README.md) — Snippets 1–3, ausgeführt gegen `web/static/lib/dagre.min.js`
(und seinerzeit `cytoscape-dagre.js`). Verifikation des Laufzeitverhaltens zusätzlich via
Playwright (keine Konsolen-/Page-Fehler, nur lokale Requests auf `/static/…` und `/api/…`).

## Folgeentscheidung
`cytoscape-dagre.js` wurde nach dem Audit als ungenutzt **gelöscht**; im Repo verbleibt nur
`dagre.min.js`. Damit reduziert sich die Audit-Fläche auf eine Lib.
