# Audit-Sessions — LucentTools DB Explorer

Zweck: **ausschließen, dass eingebundener Code unerwünschtes Verhalten zeigt** —
Netzwerk-Nachladen, Exfiltration, dynamische Codeausführung, CDN-Verstöße. Gilt
besonders für **extern bezogene/gebündelte Libraries** (z. B. `web/static/lib/`)
und für **KI-erzeugten Code**.

> **Entwicklerintern.** Dieses Verzeichnis dokumentiert den Audit-Prozess und gehört
> **nicht ins Delivery** (vgl. AP-17). Eine *neutrale* Sicherheits-Aussage für die
> öffentliche Doku (alle Assets lokal, kein CDN, kein Laufzeit-Netzwerk) kann separat
> auf der Zensical-Site stehen — **ohne** KI-/Prozessbezug.

## Wann auditieren (Auslöser)
- **Vor** dem Einbinden jeder neuen Library (insb. heruntergeladene/gebündelte JS).
- Stichprobenartig bei umfangreicherem **KI-erzeugtem** Code.
- Ergebnis ist **verpflichtend** als datierte Datei hier abzulegen: `YYYY-MM-DD-<thema>.md`.

## Checkliste (muss alles ✔ sein)
- [ ] **Kein Netzwerk:** kein `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`,
      `navigator.sendBeacon`, `.ajax`.
- [ ] **Keine dynamische Codeausführung:** kein `eval(`, `new Function(`/`= Function(`,
      `(0,eval)`, `setTimeout`/`setInterval` mit **String**-Argument, `importScripts`.
- [ ] **Kein Smuggling/Obfuskation:** kein `Blob(`, `createObjectURL`, `Worker(`,
      `atob`/`btoa`, auffälliges `fromCharCode`/Hex-Escapes.
- [ ] **Keine externen URLs** als ausführbare Ziele (nur in Kommentaren/Doku zulässig);
      kein `http(s)://` / `ws(s)://` in geladenen Endpunkten.
- [ ] **Keine Persistenz/DOM-Inject ohne Grund:** `document.write`, `document.cookie`,
      `localStorage`/`sessionStorage`, `location.*`, `.src =` bewusst prüfen.
- [ ] **Module nur intern:** `require(...)` nur bundle-/Browserify-intern (relative IDs),
      kein Laden externer Module zur Laufzeit; `child_process`/`process.env` nicht im Browserpfad.
- [ ] **NO-CDN:** Lib liegt lokal unter `web/static/lib/`, im Template `<script src="/static/...">`,
      **kein** `<script src="https://…">`.
- [ ] **Globale Schreibzugriffe** dokumentiert und plausibel (z. B. `window.<lib>`,
      Plugin-Registrierung) — keine versteckten Globals.

## Reproduzierbar (ripgrep-Snippets)
Aus dem Projekt-Root gegen die zu prüfende Datei / `web/static/lib/`:

```bash
# 1) Netzwerk + dynamischer Code + Smuggling (sollte leer / nur Kommentare sein)
rg -n -i 'XMLHttpRequest|fetch\s*\(|WebSocket|EventSource|sendBeacon|\.ajax|\beval\s*\(|new Function\s*\(|=\s*Function\(|\(0,\s*eval\)|importScripts|child_process|process\.env|atob\(|btoa\(|Blob\(|createObjectURL|Worker\(|document\.write\s*\(|\.cookie|setTimeout\(\s*["'\'']|setInterval\(\s*["'\'']' web/static/lib/<datei>

# 2) Externe URLs / Modul-Requests (Treffer manuell prüfen: Kommentar vs. Code)
rg -n -i 'https?://|wss?://|require\s*\(\s*["'\'']' web/static/lib/<datei>

# 3) NO-CDN im Template
rg -n 'src="https?://|href="https?://' web/templates/
```

Treffer sind **manuell** zu bewerten: Doku-URLs in Kommentaren und `=function(`
(Methodendefinitionen, case-insensitive Fehltreffer auf `Function(`) sind unkritisch.

## Index der Audits
- [2026-06-26 — dagre / cytoscape-dagre](2026-06-26-dagre-cytoscape-dagre.md) — Graph-Layout-Lib (AP-16)
