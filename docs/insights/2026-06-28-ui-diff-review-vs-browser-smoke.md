# Insight 2026-06-28 — UI-Änderungen: Diff-Review bestätigt Code, aber CSS-Spezifität + Template-Caching fängt nur der Browser-Smoke (Session 11)

## Kontext
Session 11 zog den UI-Umbau-Block AP-A…AP-D durch (Umbenennung, Layout, Join-Typ-inline,
1-N-Legende; v0.43.2–v0.43.4). Mehrere Frontend-APs hatten **saubere Diff-Reviews (Spec ✅/
Approved, keine Findings)** — und scheiterten trotzdem zuerst im **Controller-Browser-Smoke**.

## Erkenntnis
Ein Diff-Review (egal wie gründlich, auch opus) prüft **Code-Korrektheit im Text**. Zwei Klassen
von UI-Bugs sind dort **strukturell unsichtbar** und brauchen einen echten Render im Browser:

1. **CSS-Spezifität.** AP-C definierte `.sb-jt { width:auto }` für ein kompaktes Inline-Select.
   Im Browser blieb es **150px breit**, weil `.sqlbuilder select { width:var(--sb-ctrl-w) }`
   (Klasse+Typ = 0,0,1,1) die Ein-Klassen-Regel (0,0,1,0) schlägt. Der Diff sah „korrekt" aus; nur
   das gerenderte `getBoundingClientRect().width` deckte es auf. Fix: `.sqlbuilder select.sb-jt`
   (0,0,2,1). → **Bei neuen Element-Klassen, die eine vorhandene Typ-Regel überschreiben sollen,
   die Spezifität bewusst erhöhen (Eltern-Klasse + Typ + eigene Klasse), nicht nur eine Klasse.**

2. **Jinja-Template-Caching.** AP-D änderte die Legende in `web/templates/index.html`. Der laufende
   Server (waitress, **non-debug**) cached kompilierte Templates (`auto_reload` defaultet auf
   `app.debug`) → die Legende blieb auf dem **alten** Stand, bis die App neu gestartet wurde.
   `app.js`/`app.css` (statische Dateien) sind dagegen **live**. → **Template-Änderungen brauchen
   App-Neustart; nur JS/CSS sind ohne Neustart wirksam.** (Ergänzt die bestehende Memory-Regel
   „routes.py/core erst nach Neustart" um `templates/`.)

## Konsequenz / Pattern
- **Browser-Smoke ist für jede sichtbare UI-Änderung Pflicht** (nicht optional), und er muss
  **gerenderte Eigenschaften** prüfen (Breite/Position via `getBoundingClientRect`, sichtbarer
  Legenden-Text), nicht nur DOM-Existenz.
- **Vor dem UI-Smoke die App neu starten**, wenn eine **Template-Datei** (`web/templates/`)
  geändert wurde — sonst testet man gegen das gecachte alte Template (Session 11 erst „Legende
  fehlt"-FAIL, nach Neustart grün).
- Diff-Review und Browser-Smoke sind **komplementär**, nicht redundant: der eine fängt Logik/
  Verdrahtung/Injection, der andere Spezifität/Layout/Caching.

Etabliert in Session 11 (AP-C: `.sb-jt`-150px; AP-D: Legende erst nach Neustart sichtbar).
