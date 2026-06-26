# Insight 2026-06-26 — Lucent DB Explorer: Erweiterungen + Doku-Drift (Session 2)

Nicht-offensichtliche Erkenntnisse aus AP-1…AP-9 (v0.1.0 → v0.3.1) und dem
Doku-/Startseiten-Feinschliff.

## 1. Versions-Drift sitzt an mehr Stellen als `sync_version.py` kennt
`sync_version.py` ändert nur `config.APP_VERSION` + `lucent-hub.yml`. Die
**angezeigte** Version stammt aber zusätzlich aus hartkodierten Stellen, die der
Bump nicht anfasst — sie zeigten noch `0.1.0 / 81 Tests`, obwohl die App längst
0.3.1 war:

- `luDBxP-docs/docs/javascripts/icon-rail.js` — `APP_VERSION` + Testzahl/-datum
  (Doku-Header „Lucent DB Explorer vX.Y.Z" + Status-Badge). **Das war „die js"
  mit dem alten Titel.**
- `luDBxP-docs/zensical.toml` — `site_description` enthält „· vX.Y.Z".
- `tools/make_poster.py` — `APP_VERSION` + `POSTER_DATE`.
- **Laufender Flask-Server** liest `config` nur beim Start → nach jedem Bump
  **neu starten**, sonst meldet `/api/info` die alte Version.

Die Web-App selbst hat **keine** hartkodierte Version — der Info-Tab liest live
aus `/api/info`. Lehre: Bei „falsche Version im UI" zuerst klären, *welche*
Fläche (App-Info vs. Doku-Site-Header vs. Poster) — die Quellen sind verschieden.
Behoben durch `APP_VERSION`/`TEST_COUNT`/`TEST_DATE`-Konstanten in icon-rail.js.

## 2. Mermaid: viele kantenlose Knoten brauchen erzwungene Geometrie
Eine Übersicht aus 23 Knoten **ohne Kanten** in einem `flowchart LR`-Subgraph
rendert als **eine breite Reihe** → beim Einpassen auf Seitenbreite winzig
(Seitenverhältnis ~28:1). `direction TB` im Subgraph allein stapelt nicht, weil
es ohne Kanten nicht greift. Lösbar nur durch erzwungene Geometrie:

1. Knoten je Spalte mit **unsichtbaren Links** vertikal stapeln:
   `D1 ~~~ D2 ~~~ … ~~~ D8`.
2. Die Spalten-Subgraphs **selbst** horizontal verlinken: `S1 ~~~ S2 ~~~ S3` —
   sonst stapelt dagre die drei Subgraphs **vertikal** (Bild wurde 7493 px hoch).

Ergebnis: sauberes 3-Spalten-Raster, jedes Paket einzeln lesbar.

## 3. Bild im Flex-Container: fit-by-height verhindert Scrollen
Ein hohes/„bandartiges" Bild rechts neben einem Diagramm: `width:100%` skaliert
auf die **Containerbreite** → die Höhe läuft über → Scrollbalken. Richtig ist
fit-by-**height**: `max-height:100% + object-fit:contain + overflow:hidden` auf
einem Flex-Container mit `align/justify:center`. Dann skaliert das Bild auf die
verfügbare **Höhe** und ist über alle Viewports vollständig sichtbar, nie
scrollbar (verifiziert 1600×1000 / 1366×768 / 1280×720, je `overflowing:false`).

## 4. read-only bewusst aufgeweicht (seit v0.2.0)
Das generierte Join-SELECT wird seit AP-5 auch **ausgeführt** (Ergebnistabelle).
Leitplanken: SQL **serverseitig** aus validierten Join-Parametern via
`generate_sql` (kein client-geliefertes SQL), parametrisiert, harte Zeilen-
Obergrenze (`config.MAX_RESULT_ROWS`). Zweiter Ausführungsort neben der
Datenvorschau. Endpoint `POST /api/joinpath/run`; gemeinsame Bau-Logik in
`_parse_joinpath_params` + `_make_path_gen` (von beiden Endpoints geteilt).

## 5. Per-AP-Versionierung vs. geteilte Frontend-Dateien
AP-6/7/8 änderten alle dieselben Dateien (`app.js`/`app.css`) ineinander
verschachtelt. Ohne interaktives `git add -p` (in dieser Umgebung gesperrt)
lassen sich solche Änderungen nicht sauber pro AP committen → zu **einem**
v0.3.0-Release gebündelt. Lehre: **jede AP committen, bevor die nächste
beginnt**, dann bleibt Version ↔ AP 1:1.

## 6. Harness: Hintergrund-Server mit `&` stirbt am Tool-Call-Ende
`nohup ./venv/bin/python app.py &` in einem Bash-Tool-Call wird beendet, sobald
der Call zurückkehrt. Persistenter Dev-Server braucht `run_in_background`
(eigener Task), nicht `&`.

## 7. `origin/master` bekommt Fremd-Commits → immer fetch+rebase vor dem Push
Mehrfach wurde der `git push origin master` **abgelehnt** (non-fast-forward),
weil zwischendurch ein Commit von außerhalb der Session auf dem Remote landete
(z. B. `9d55a9c build: Offline-Wheelhouse vervollstaendigen`). Lösung: vor jedem
master-Push `git fetch origin master && git rebase origin/master` (disjunkte
Dateien → konfliktfrei), **nie** force-pushen. Im Deploy-Subagenten als fester
Schritt verankert. Lehre: Das Repo ist nicht exklusiv — der Remote-Stand kann
sich zwischen zwei eigenen Commits ändern.

## 8. Deploy-Workflow (master + gh-pages) — der eingespielte Pfad
gh-pages trägt den **Inhalt von `site/` im Root** + `.nojekyll` (kein
`site/`-Unterordner). Sauberer Deploy ohne Working-Tree-Störung: temporärer
`git worktree add -B gh-pages origin/gh-pages`, Inhalt durch frische `site/`
ersetzen (`find … -mindepth 1 ! -name .git -exec rm -rf` + `cp -a site/.`),
`touch .nojekyll`, committen, pushen, Worktree entfernen. Die generierte `site/`
ist **auch in master** getrackt (bewusst, damit Kollegen sie ohne Pages sehen).
Doku-Build immer über `bash run_luDBxP_docs.sh --build` (eigene `.venv-docs` mit
Zensical; rendert Mermaid via mmdc, regeneriert Activity-JSON, baut `site/`).

## 9. Diagramm-Orientierung: dieselbe Übersicht braucht zwei Formate
Das AP-Übersichtsdiagramm wird an zwei Stellen gezeigt, mit **gegensätzlichen
Platzanforderungen**:
- **Doku-Startseite (schmales Band rechts):** **hochkant** — 3 Spalten ×
  ~8 Zeilen passt in die schmale, hohe Bandfläche.
- **A0-Poster (breiter Streifen):** `make_poster.py` platziert Diagramme über die
  **volle Inhaltsbreite**. Ein hochkant-Diagramm wird dort riesig (frisst die
  halbe Poster-Höhe, verdrängt das Screenshot-Raster). Lösung: eine
  **transponierte, querformatige** Variante (3 Phasen als **Zeilen** statt
  Spalten → Aspekt ~4.4:1) nur fürs Poster rendern (`flowchart TB` mit
  `direction LR`-Subgraphs). Die Docs-`.mmd` bleibt hochkant; die Poster-Variante
  lebt im Scratch und wird nach `mail/diagramm-ap-ueberblick.jpg` gerendert.
- **Höhen-Aufteilung im Poster:** der Faktor `diag_band_max = (… ) * 0.62`
  in `make_poster.py` deckelt die Diagramm-Bänder auf ~62 % der Restfläche,
  damit die Screenshots groß bleiben. Eine Zahl zum Justieren.
Lehre: „voll-breit platzieren" + hochkant-Diagramm = Layout-Sprengung; das Format
des Diagramms muss zur Zielfläche passen, nicht nur der Inhalt.
