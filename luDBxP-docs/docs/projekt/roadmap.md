# Roadmap

## Phasen-Timeline

<img src="../images/mermaid/projekt-roadmap-1.svg" alt="Arbeitspaket-Roadmap (Gantt)">

---

## Offene Arbeitspakete

### AP-1 — Interaktive Pfad-Auswahl direkt im Graph

**Idee:** Im Schema-Graph **Doppelklick** auf eine Tabelle → eingebettete
**UML-Tabellenansicht** (Spalten/Typen/PK). Dort eine Spalte als **Quelle**
wählen, in einer zweiten Tabelle die **Ziel-Spalte** — danach aktualisiert
sich der Graph live und zeigt den Join-Pfad.

**Nebeneffekt:** Der Join-Builder-Tab öffnet sich automatisch und füllt
Start-/Ziel-Felder aus der Graph-Auswahl (Zweiweg-Sync Graph ↔ Join-Builder).

**Betroffene Dateien:**

- `web/static/js/app.js` — Doppelklick-Handler, UML-Karte, Sync-Logik
- CSS für die eingebettete UML-Karte

---

### AP-2 — Bug: „Verbinden" liefert „failed to fetch" (zu verifizieren)

**Symptom:** Klick auf „Verbinden" → Browser zeigt nur „failed to fetch".

**Verdacht:** Dev-Server lief nicht (bei Session-Handoff gestoppt) → offenes
Browser-Tab erreicht `127.0.0.1:5057` nicht → generisches Fehlerbild.

**Vorgehen:**
1. Server neu starten (`bash run.sh --start`)
2. Im Browser neu verbinden
3. Falls weiterhin reproduzierbar: Netzwerk-Tab (URL/Status), CORS prüfen,
   Exception im `/api/connect`-Endpoint eingrenzen

---

## Erledigte Arbeitspakete (v0.1.0)

Alle in v0.1.0 implementierten Features sind in `todo-erledigt.md` aufgelistet.
Detaillierter Stand: [Changelog](../entwicklung/changelog.md).
