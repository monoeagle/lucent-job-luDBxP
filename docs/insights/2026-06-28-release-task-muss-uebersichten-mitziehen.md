# Release-Task muss Übersichten + Architektur-Diagramme mitziehen (nicht nur Changelog/Badges)

**Datum:** 2026-06-28 (Session 9)

## Beobachtung

Über drei aufeinanderfolgende SDD-APs (AP-50/51/52) aktualisierte die jeweilige
„Doku & Release"-Task brav **Changelog + Mirror, Badges (`icon-rail.js`),
`zensical.toml`** und (bei AP-52) das passende Architektur-Diagramm — aber **nicht**
`roadmap.md`, den **Gantt** (`projekt-roadmap-1.mmd`) und das **Board**
(`entwicklung-arbeitspakete-1.mmd`). Die Drift summierte sich über drei Releases,
bis der Nutzer sie sah: *„roadmap und ap bild sind nicht aktuell?"*. Zusätzlich
zeigten die **Architektur-Diagramme** noch „Flask" als Server, obwohl der
Normalbetrieb seit AP-31 (v0.35) auf **waitress** läuft — und Gantt/Board führten
AP-31/AP-34 noch unter „geplant", obwohl ihre Kerne längst erledigt waren.

## Ursache

Die `ludbxp-release-deploy-steps`-Memory **listet** Roadmap/Gantt/Board und die
Architektur-Diagramme als manuelle Release-Schritte — aber die in `writing-plans`
erzeugte „Doku & Release"-Task **enumerierte sie nicht**. Was nicht als
Checkbox-Schritt im Plan steht, fällt im SDD-Durchlauf hinten runter: der
Implementer-Subagent macht genau die Schritte des Briefs, nicht mehr. Übersichts-
Flächen sind außerdem die klassische Doku-Drift-Falle (vgl. globale Konvention
„Übersichten enumerieren jedes Item").

## Konsequenz / Fix

- AP-53s Release-Task enthielt explizit einen Schritt **„Roadmap/Board/Gantt
  mitziehen"** (jedes AP namentlich) + den arch-3-DB-Knoten — und wurde sauber
  ausgeführt. Vorher wurde die Drift in einem eigenen „Doku-Drift geschlossen"-
  Commit nachgeräumt (inkl. Architektur Flask→waitress, Alt-Bild archiviert,
  arch-3 vom Kanten-Knäuel zur klaren 5-Schichten-Architektur neu gestaltet).
- **Lehre für `writing-plans`:** Die per-AP „Doku & Release"-Task muss **jede
  Übersichtsfläche und jedes betroffene Architektur-Diagramm namentlich als
  eigenen Schritt** führen — nicht nur Changelog/Badges/zensical. Konkret immer
  prüfen: `roadmap.md`, `projekt-roadmap-1.mmd` (Gantt), `entwicklung-arbeitspakete-1.mmd`
  (Board), `referenz-architektur-*.mmd`. Nach dem Site-Build die gerenderten
  SVGs **inhaltlich gegenprüfen** (AP-Nummer vorhanden? Server-/Backend-Name aktuell?).
- **Architektur-Diagramme driften auf Feature-Ebene**, nicht nur bei neuen
  Modulen: ein Backend-Wechsel (Flask→waitress) oder ein neues Endpoint gehört
  ins Bild. Bei Überblicks-Diagrammen Übersicht (arch-3) und Detail (arch-1
  Modulkarte, arch-2 Sequenz) trennen, statt alles in ein Bild zu quetschen —
  ein Knäuel ist genauso „falsch" wie veraltet.

## Nebenbefund

Ein Plan-Typo bei den erwarteten Testzahlen (Task addierte real +3 statt geplant
+2) ließ einen Task-Reviewer fälschlich „Critical: Testzahl" melden. Lehre:
Reviewern beim Dispatch die **korrigierte Baseline** mitgeben, sobald sich die
real gelaufene Zahl vom Plan unterscheidet — sonst entstehen Fehlalarme.
