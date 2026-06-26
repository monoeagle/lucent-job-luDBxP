# Insight 2026-06-26 — PS-5.1-Deployment + dagre-Kanten (Session 4)

Nicht-offensichtliche Erkenntnisse aus AP-16/23/26/27/28/32, dem App-Rename, der
Release-Auslieferung und dem ersten Server-Test (Terminal Server, PowerShell 5.1).

## 1. UTF-8 ohne BOM ist unter Windows PowerShell 5.1 eine Falle
**Problem:** `run.ps1` warf auf dem Server „unexpected )/}" an Funktions-Klammern.
**Ursache:** Die Datei enthielt Em-Dashes `—` (U+2014) und war **UTF-8 ohne BOM**. PS 5.1
liest BOM-lose `.ps1` als **cp1252** → die 3-Byte-UTF-8-Sequenzen werden als 3 falsche
Zeichen interpretiert, was Strings/Quoting zerlegt; der Parser meldet den Folgefehler erst
an der nächsten `)`/`}`. Mit-Verursacher: ein früherer Bulk-Rename hatte die Datei via
`WriteAllText(..., UTF8Encoding($false))` neu geschrieben und so das BOM gestrippt.
**Lehre:** `run.ps1` **reines ASCII + UTF-8-BOM** halten; Edits über `WriteAllText` mit
`UTF8Encoding($true)`, danach Bytes (`EF BB BF`) + Parser prüfen. Das Edit-Tool kann das
BOM unbemerkt entfernen. (Als Memory + Handoff festgehalten.)

## 2. native stderr + `$ErrorActionPreference='Stop'` = Abbruch in PS 5.1
**Problem:** „Starten wird mit der Warnung 'This is a development server …' abgebrochen."
**Ursache:** Das ist nur eine Werkzeug-**Warnung** auf **stderr** — aber unter
`$ErrorActionPreference='Stop'` wertet PS 5.1 native stderr als terminierenden Fehler.
**Lehre:** Um native Befehle, die nach stderr schreiben, lokal entschärfen:
`$ErrorActionPreference` für den Aufruf auf `Continue` (try/finally). Nicht jede rote
Zeile ist ein Fehler.

## 3. dagre minimiert Kreuzungen — aber nur mit seinen Knickpunkten
**Problem:** Gewünscht „möglichst keine Linienkreuzung". dagre lieferte 1 Kreuzung; alle
Ranker-Varianten ebenfalls 1.
**Ursache:** Die letzte Kreuzung ist eine **rang-überspringende (transitive) Kante**, die
dagre intern mit **Knickpunkten** um Zwischenknoten routet. Wir zeichneten aber gerade
Linien → die Gerade „schneidet die Ecke ab" und kreuzt. Rendert man die Kante über dagres
`edge.points` (curve-style `segments`), sind es nachweislich **0 Kreuzungen**.
**Lehre/Abwägung:** Technisch lösbar, aber die geknickten Kanten sahen als Zickzack
schlechter aus → **bewusst gerade Linien + 1 Kreuzung** (Nutzerentscheidung). Außerdem:
cytoscapes `segment-distances` nutzt die **entgegengesetzte** Perpendikular-Richtung — beim
Umrechnen absoluter Punkte das Vorzeichen negieren.

## 4. Verifikation schlägt Vermutung — per Playwright messen statt schätzen
Kreuzungen (Segment-Schnitt-Zähler), Slider-Position/Graph-Überlappung, Scroll-Verhalten
(`scrollHeight` vs `clientHeight`), Audit-Greps — alles **gemessen**, nicht „sieht gut aus".
Das fing u. a. den Grid-Fallback (dagre nicht registriert, weil Jinja-Template gecached war,
Server-Neustart nötig) und die gespiegelten Segment-Kanten zuverlässig ab.

## 5. Auslieferung als Release-Artefakt statt Repo-Unterordner
Ein **bereinigtes ZIP** an einem GitHub-Release (Allow-Liste in `tools/build_release.py`)
löst „nicht das ganze Repo klonen" sauberer als ein `delivery/`-Ordner: ein Download, kein
`.git`, keine Dev-/KI-Spuren (AP-17). `run.ps1` liegt **unsigniert** bei; der Operator
signiert nach dem Entpacken.
