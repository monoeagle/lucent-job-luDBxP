# Ein Komponenten-Refactor kann eine CSS-Layout-Invariante lautlos verlieren — nur der echte Render zeigt es

**Datum:** 2026-07-02 (Session 18)
**Kontext:** AP-69·A — `attachLineGutter` (Analyzer-Textarea) wurde zur geteilten Komponente
`sqlEditor` verallgemeinert und über alle vier SQL-Flächen ausgerollt (v0.67.0). Nach dem Release
fiel dem Nutzer per Screenshot auf: auf der **markierten Fehlerzeile war der Text unsichtbar** — der
rote Markierungs-Balken verdeckte ihn komplett.

## Beobachtung

Die Ursache war eine **verlorene CSS-Invariante**: die alte `#an_sql`-Regel hatte
`position: relative`, wodurch die Textarea *über* der absolut positionierten Backdrop-Ebene (die die
Zeilen-Markierung trägt) lag. Bei der Verallgemeinerung zu `.sqled-textarea` ging genau dieses
`position/z-index` verloren → die positionierte Backdrop malte fortan *über* der statischen Textarea,
und der **opake** Fehlerzeilen-Balken verdeckte den Text. Nicht-markierte Zeilen blieben sichtbar
(transparente Backdrop-Bänder), nur die eine opake Zeile fraß ihren Text — deshalb fiel es nicht
sofort auf.

Bemerkenswert: **vier Kontrollen sahen den Bug nicht.**
1. Die vollständige **pytest-Suite** (459) — CSS/Rendering ist dort gar nicht abgedeckt.
2. Die **Per-Fläche-Playwright-Smokes** — sie prüften *Präsenz* + `readonly` + Zeilennummern, aber
   nie „hat die Fehlerzeile *sichtbaren Text*". Ein grüner Smoke ≠ korrektes Bild.
3. Die **Task-Reviews** (Diff-basiert) — die Regression steht in *keinem* Diff-Hunk, sie ist eine
   **emergente Stapel-/Render-Eigenschaft** zweier CSS-Regeln (Backdrop absolut, Textarea nicht mehr
   positioniert).
4. Der **adversariale Whole-Branch-Review (Opus)** — er las den Diff genau, prüfte Scroll-Sync „by
   construction" und segnete das Layering ab, ohne den tatsächlichen Render mit einer Fehlerzeile
   *mit Text* zu erzeugen.

## Lehre

**Bei einem „X wird zur geteilten Komponente"-Refactor die *impliziten* Eigenschaften der Vorlage
mit-migrieren — besonders CSS-Layout-Invarianten (position/z-index/overflow/background), die nicht
in der offensichtlichen API stehen.** Ein Diff, der eine benannte Regel (`#an_sql`) durch eine
generische (`.sqled-textarea`) ersetzt, sieht vollständig aus, verliert aber leicht eine
„unscheinbare" Deklaration, die die Vorlage überhaupt funktionieren ließ. Vor dem Löschen der
alten Regel: **Deklaration für Deklaration abgleichen**, was übernommen werden muss.

**Und: Rendering-/Layout-Bugs sind weder test- noch diff- noch review-fangbar — nur ein echter
Render der *konkret betroffenen Interaktion* zeigt sie.** „Fehlerzeile markiert" muss man mit
*Text auf dieser Zeile* rendern und *hinschauen*. Präsenz-Assertions („Element existiert, ist
read-only") sind ein Teilbeweis; die visuelle Invariante („Text auf der markierten Zeile ist
lesbar") ist eine eigene, eigenständig zu prüfende Zusage. Das schärft die Session-16/17-Linie
(*echter Container/Screenshot findet, was grüne Tests nicht sehen*) auf die Frontend-Achse:
**der Screenshot ist der Bug-Detektor, den auch der beste Diff-Review nicht ersetzt.**

## Konsequenz

- Beim Refactor einer stilbehafteten Komponente: die Alt-CSS-Regel **neben** die neue legen und jede
  Deklaration bewusst übernehmen/verwerfen (nicht „sinngemäß neu schreiben").
- UI-Smokes um **Sichtbarkeits-/Kontrast-Assertions der Kern-Interaktion** ergänzen, nicht nur
  Präsenz — und im Zweifel **einen Screenshot der konkreten Interaktion** in die Verifikation nehmen
  (hier: Fehlerzeile mit Text → ist der Text sichtbar?).
- Diese Klasse Bug explizit in die Whole-Branch-Review-Prompts aufnehmen: „prüfe emergente
  Render-/Stapel-Eigenschaften, nicht nur den Diff" — der Opus-Review verließ sich auf
  „by construction" statt auf einen Render.
