# Arbeitspakete — Lucent DB Explorer

Offene APs (erledigte wandern nach `todo-erledigt.md`).

## AP-1 — Interaktive Pfad-Auswahl direkt im Graph (UML-Tabelle)
**Idee:** Im Schema-Graph **Doppelklick** auf eine Tabelle → darunter (oder
eingebettet) öffnet sich die **UML-Tabellenansicht** (Spalten/Typen/PK). Dort
**selektiert man eine Spalte als Quelle**. Dasselbe für eine zweite Tabelle als
**Ziel**. Danach **aktualisiert sich der Graph live** und zeigt den Join-Pfad.

Als Nebeneffekt öffnet sich **links der Join-Builder automatisch** und füllt
Start-/Ziel-Felder (und Spalten-Selects) **automatisch** mit der Graph-Auswahl,
sodass man die gewählten Selects auch im Formular sieht.

**Skizze der Schritte:**
- Doppelklick-Handler auf Cytoscape-Knoten → UML-Tabellenkarte einblenden
  (Spalten anklickbar).
- Erste Spaltenwahl = Quelle, zweite (andere Tabelle) = Ziel; visuelle Markierung.
- Bei vollständiger Quelle+Ziel: `/api/joinpath` rufen, Graph-Highlight + Join-
  Builder-Tab öffnen und Start/Ziel/Spalten-Selects setzen (zweiweg-Sync
  Graph ↔ Join-Builder).
- Betroffen: `web/static/js/app.js` (Graph-Interaktion, Join-Builder-Sync),
  ggf. CSS für die eingebettete UML-Karte.

## AP-2 — „Verbinden" liefert nur „failed to fetch" (Bug, zu verifizieren)
**Symptom:** Klick auf „Verbinden" / im Verbindungs-Formular → Browser zeigt
nur „failed to fetch".

**Verdacht (zuerst prüfen):** Der Dev-Server lief nicht (beim Session-Handoff
gestoppt); ein offenes altes Browser-Tab erreicht `127.0.0.1:5057` dann nicht
→ generisches „failed to fetch". Nach Server-Neustart erneut testen.

**Falls auch mit laufendem Server reproduzierbar:** echten Fehler eingrenzen —
Netzwerk-Tab (welche URL/Status), CORS, oder eine Exception im Endpoint
(`/api/connect`). Read-only-SELECT/Treiber-Pfad prüfen.
