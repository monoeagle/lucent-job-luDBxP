# Arbeitspakete — Lucent DB Explorer

Offene APs (erledigte wandern nach `todo-erledigt.md`).

## AP-2 — „Verbinden" liefert nur „failed to fetch" (Bug, zu verifizieren)
**Symptom:** Klick auf „Verbinden" / im Verbindungs-Formular → Browser zeigt
nur „failed to fetch".

**Verdacht (zuerst prüfen):** Der Dev-Server lief nicht (beim Session-Handoff
gestoppt); ein offenes altes Browser-Tab erreicht `127.0.0.1:5057` dann nicht
→ generisches „failed to fetch". Nach Server-Neustart erneut testen.

**Falls auch mit laufendem Server reproduzierbar:** echten Fehler eingrenzen —
Netzwerk-Tab (welche URL/Status), CORS, oder eine Exception im Endpoint
(`/api/connect`). Read-only-SELECT/Treiber-Pfad prüfen.
