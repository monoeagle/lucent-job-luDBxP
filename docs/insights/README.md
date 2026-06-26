# Insights — LucentTools DB Explorer

**Insight** = eine *nicht-offensichtliche* Erkenntnis aus der Arbeit am Projekt:
eine Stolperfalle, ein überraschendes Verhalten, eine bewusste Designentscheidung
mit ihrem *Warum*. Reflexion, nicht Bedienungsanleitung.

> **Entwicklerintern.** Insights enthalten Prozess-/KI-Spuren und gehören **nicht
> ins Delivery** (vgl. AP-17) und **nicht** auf die öffentliche Zensical-Site
> (`luDBxP-docs/`). Sie leben hier in `docs/` neben `handoffs/` und `audits/`.

## Abgrenzung: Insight vs. öffentliche Doku
| | Insight (`docs/insights/`) | Öffentliche Doku (`luDBxP-docs/docs/`) |
|---|---|---|
| Inhalt | *Warum* / Erkenntnis / Stolperfalle / Entscheidung | *Was* / *Wie benutze ich es* |
| Zielgruppe | Entwickler-/Projekt-intern | End-/Fachnutzer, externe Entwickler |
| Prozess-/KI-Bezug | erlaubt | **nie** |
| Beispiel | „Filter-Einwebung muss ein Baum sein, sonst Duplikat-JOINs" | „UC-2: Gefilterte Abfrage erstellen" |

Faustregel: Was ein *Nutzer* zum Bedienen braucht → öffentliche Doku
(`referenz/`, `grundlagen/`, `entwicklung/`). Was ein *Entwickler* beim nächsten
Mal wissen sollte, um nicht in dieselbe Falle zu treten → Insight.

## Konvention
- **Dateiname:** `YYYY-MM-DD-<kurz-slug>.md` (datiert, kebab-case).
- **Überschrift:** `# Insight YYYY-MM-DD — <Titel> (Session N)`.
- **Aufbau:** kurze Einleitung (Kontext/Umfang), dann nummerierte Abschnitte je
  Erkenntnis — jeweils mit **Problem → Ursache → Lehre**.
- **Wann:** beim Sessionwechsel/Handoff oder nach substanzieller Arbeit die
  nicht-offensichtlichen Erkenntnisse festhalten (verwandt mit `docs/handoffs/`).

## Optional: in die öffentliche Doku überführen
Reift ein Insight zu allgemein gültigem Nutzer-/Entwicklerwissen, kann der
**neutralisierte** Kern (ohne Prozess-/KI-Bezug) in die Zensical-Site wandern
(z. B. eine Einschränkung nach `referenz/`). Das Original-Insight bleibt hier.

## Index
- [2026-06-25 — Aufbau (Session 1)](2026-06-25-lucent-db-explorer-aufbau.md) — Filter-Baum, Pfad-Validierung u. a.
- [2026-06-26 — Erweiterungen + Doku-Drift (Session 2)](2026-06-26-erweiterungen-und-doku-drift.md) — Versions-Drift jenseits von `sync_version.py` u. a.
