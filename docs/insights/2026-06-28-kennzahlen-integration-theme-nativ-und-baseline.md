# Insight: Ein Kennzahlen-Artefakt integrieren — theme-nativ + ehrlich datiert

**Datum:** 2026-06-28 (Session 13)
**Auslöser:** Nutzer-Wunsch „die Projekt-Kennzahlen-HTML in die Doku integrieren" — erst als Link, dann (auf Nachfrage) theme-nativ.

## Worum es ging

Es existierte ein eigenständiges Dashboard `docs/projekt-kennzahlen.html` (dunkles, voll selbst-gestyltes HTML). Der Auftrag war zunächst „in die Doku integrieren". Naheliegend: die Datei in den Site-`docs/`-Ordner kopieren und einen Nav-Eintrag darauf setzen — zensical kopiert `.html` verbatim, der Link funktioniert. Das wurde gebaut. Auf Nachfrage des Nutzers („nicht nur verlinken, sondern integrieren, dem Design der Doku anpassen") folgte der eigentliche Umbau.

## Zwei Lehren

### 1. „Integrieren" ≠ „verlinken" — theme-nativ statt Style-Insel

Eine standalone-HTML mit eigenem `<head>/<style>` zu verlinken ist *Einbetten*, nicht *Integrieren*: die Seite ignoriert das Site-Theme (kein Light/Dark, keine Nav/TOC-Chrome, eigene Farben). **Echte Integration** = eine Markdown-Seite (`projekt/kennzahlen.md`), deren visuelle Bausteine (Karten, Balken, Tags) über die **Theme-CSS-Variablen** (`--md-default-bg-color--light`, `--md-default-fg-color`, `--md-accent-fg-color`, plus `[data-md-color-scheme="slate"]`-Overrides) gebaut sind. Dann:
- passt sie sich Light/Dark automatisch an,
- lebt in der Site-Chrome (Header, Sidebar, TOC, Footer),
- nutzt native Markdown-Tabellen + Admonitions statt nachgebauter HTML-Tabellen.

Raw-HTML-Blöcke (für Karten/Balken) gehen in Markdown durch — aber `markdown="0"`-Attribute leaken als literale Attribute ins Output (entfernen). CSS gehört in die bestehende `extra.css` mit `.md-typeset`-Präfix, in derselben Design-Sprache wie der Rest (hier: 1px-Border, 6px-Radius, dezenter Shadow — abgeschaut von `.adb-home-arch`).

### 2. Ein „Kennzahlen"-Artefakt ist ein Schnappschuss und driftet — vor Integration prüfen

Die Datei war als „die Projekt-Kennzahlen" beschrieben, war aber faktisch ein **statischer v0.34.0-Schnappschuss** (227 Tests statt 338, AP-1…49 statt …63, 8 statt 13 Sessions) — kein Fetch, alles hartkodiert. Sie unverändert zu publizieren hätte überholte Zahlen veröffentlicht. Richtig war:
- **vor** dem Integrieren den Ist-Stand prüfen (statt blind kopieren),
- die **verifizierbaren** Headline-Zahlen neu erheben (Version, Tests, Coverage via `pytest --cov`, Docstring-% via AST, Commits via `git rev-list --count`, Sessions, AP-Stand) und einsetzen,
- die **nicht** neu vermessenen Werte (COCOMO, LOC) ehrlich als „**Baseline v0.34.0**" markieren statt sie als aktuell auszugeben.

Gemischt-aktuelle Seiten sind ok, solange jede Zahl ihren Stand trägt. Stilles Mitschleppen alter Zahlen ist die Falle.

## Konsequenz / Pattern

- Beim Auftrag „X integrieren" zuerst fragen: *Ist X aktuell? Ist X im Ziel-Design?* — nicht nur *Wie verlinke ich X?*
- Statische Kennzahlen driften wie Doku-Versionen. Im Release-Memory (`[[ludbxp-release-deploy-steps]]`) ist die Kennzahlen-Seite jetzt als wiederkehrender Nachzieh-Schritt vermerkt (verifizierbare Werte je Release neu erheben).
- Verwandt: dieselbe „Spec/Beschreibung ≠ Ist-Stand"-Disziplin wie beim Code (CLAUDE.md: „Spec gegen den echten Code prüfen"). Hier: „Artefakt-Beschreibung gegen den echten Artefakt-Inhalt prüfen".
