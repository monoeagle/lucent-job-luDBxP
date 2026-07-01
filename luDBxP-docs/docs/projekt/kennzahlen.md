# Projekt-Kennzahlen

Stand **v0.64.2** · 2026-07-01 · Branch `master` · Python/Flask · read-only Join-Pfad-Builder.

Die <span class="kz-tag kz-tag--m">gemessen</span>-Werte (Version, Tests, Coverage, Docstrings, Commits, Sessions)
sind am 2026-06-30 neu erhoben (aus `git`, `pytest --cov` und AST-Zählung). Die
<span class="kz-tag kz-tag--s">Baseline</span>-Werte (COCOMO, LOC) stammen vom 2026-06-27 (v0.34.0) und wurden
bewusst nicht neu vermessen.

<div class="kz-cards">

<div class="kz-card">
  <div class="kz-lbl">Umsetzung (Roadmap)</div>
  <div class="kz-val kz-good">≈ 89 <small>%</small></div>
  <div class="kz-note">Kern/Produkt-APs (AP&#8209;1…60) umgesetzt · offener Backlog: AP&#8209;56/57, AP&#8209;61/62, AP&#8209;19/35</div>
</div>

<div class="kz-card">
  <div class="kz-lbl">Tempo</div>
  <div class="kz-val">467 <small>Commits</small></div>
  <div class="kz-note">16 Sessions an 7 Kalendertagen (25.06.–01.07.)</div>
</div>

<div class="kz-card">
  <div class="kz-lbl">Testabdeckung</div>
  <div class="kz-val kz-good">88 <small>%</small></div>
  <div class="kz-note">445 Tests grün (11 skipped Oracle/MSSQL/PG) · 2060 Statements</div>
</div>

<div class="kz-card">
  <div class="kz-lbl">Doku-Abdeckung</div>
  <div class="kz-val kz-good">93 <small>% Module</small></div>
  <div class="kz-note">26/28 Module · 62 % öffentl. API (60/96 Funktionen/Klassen)</div>
</div>

<div class="kz-card">
  <div class="kz-lbl">Technische Schulden</div>
  <div class="kz-val kz-good">≈ 0 <small>%</small></div>
  <div class="kz-note">pyflakes: 0 Fehler · 2 Info (ungenutzte <code>exc</code> in routes.py)</div>
</div>

<div class="kz-card">
  <div class="kz-lbl">Read-Only-Garantie</div>
  <div class="kz-val kz-good">0 <small>Mutationen</small></div>
  <div class="kz-note">nur SELECT · kein INSERT/UPDATE/DELETE/DDL</div>
</div>

<div class="kz-card">
  <div class="kz-lbl">Costs (COCOMO)</div>
  <div class="kz-val kz-acc">~242 <small>k €</small></div>
  <div class="kz-note">organic, 7,6 kSLOC · real: solo + KI · <em>Baseline v0.34.0</em></div>
</div>

<div class="kz-card">
  <div class="kz-lbl">LOC (handgeschrieben)</div>
  <div class="kz-val">3.249 <small>Py-Code</small></div>
  <div class="kz-note">+ 2.330 Test · + 2.013 Frontend (JS/CSS/HTML) · <em>Baseline v0.34.0</em></div>
</div>

</div>

## Umsetzungsstand — Arbeitspakete

Abgeschlossen ≈ 59 · offener Backlog ≈ 5 — über die Spanne AP&#8209;1…63 (ohne AP&#8209;17 *gestrichen* und
AP&#8209;19 *Meta*). Autoritative, gepflegte Liste: [Roadmap](roadmap.md).

<div class="kz-stack">
  <div class="kz-seg-done" style="width:89%">89 % fertig</div>
  <div class="kz-seg-plan" style="width:11%">11 %</div>
</div>

**✅ Fertig (≈ 59):** Core (Modell/Loader/FK-Graph/Pathfinder/SQL-Generator/Flask-API) · `AP-11` Composite-FK ·
`AP-25/39/48/49` SQL-Analyzer · `AP-30` N-1-Stern · `AP-36…47` Join-Builder-Ausbau · `AP-50/51` 1-1-Fan-out ·
`AP-52` Multi-Schema · `AP-53` Oracle · Tier-2/3 + Aggregat-Kette (GROUP BY/HAVING/COUNT) · `AP-A…F` SQL-Builder-UI ·
`AP-54` Cross-Schema-FK-Diagnose · `AP-55` Implied-FK-Schärfung · `AP-63·S1–S3+Trigger-FF` Objekt-Kategorien … (volle Liste in der [Roadmap](roadmap.md)).

**⬜ Offener Backlog (≈ 5):** `AP-56` Subset-Export · `AP-57` Cross-Schema-Joins (zurückgestellt/bedingt) ·
`AP-61/62` Demo/Passwort-UX · `AP-19` Meta-Pattern · `AP-35` Windows-`run.ps1`-Fix.

## Kennzahlen-Übersicht

| Kennzahl | Wert | Detail / Quelle | Art |
|---|---|---|---|
| Umsetzung (Roadmap) | ≈ 89 % | ≈ 59 erledigt · ≈ 5 offener Backlog (AP-56/57, AP-61/62, AP-19/35) · Quelle: `roadmap.md` | gemessen |
| Commits | 467 | 2026-06-25 → 07-01 · 7 Kalendertage · 16 Sessions · FF-Merges je AP (SDD-Branches) | gemessen |
| Aktuelle Version | v0.64.2 | SemVer je AP (`sync_version.py`) · von 0.1.0 in 16 Sessions | gemessen |
| Testabdeckung | 88 % | 2060 Statements, 241 ungedeckt · `pytest --cov` (core/web/launcher/config/app) | gemessen |
| Tests | 445 | alle grün · 11 skipped (optionale Oracle/MSSQL/PG-Live-Tests) · ~10 s Laufzeit | gemessen |
| Doku-Abdeckung (Module) | 93 % | 26/28 Python-Module mit Modul-Docstring (AST-Zählung) | gemessen |
| Doku-Abdeckung (öffentl. API) | 62 % | 60/96 öffentliche Funktionen/Klassen mit Docstring · gesamt 93/143 ≈ 65 % | gemessen |
| Effort (COCOMO) | ~20 PM | organic · E = 2,4·KSLOC^1,05 · T ≈ 7,8 Monate Kalender | Baseline |
| Costs (COCOMO) | ~242.000 € | Overhead 2,4 · ~60 k€/J · ohne Overhead ~101.000 € | Baseline |
| LOC Python (Produkt) | 3.249 | core 1.579 · web 664 · launcher 133 · root 187 · *Baseline v0.34.0, seither gewachsen* | Baseline |
| LOC Tests | 2.330 | pytest (`tests/`) · ~0,7× des Produktcodes · *Baseline v0.34.0* | Baseline |
| LOC Frontend | 2.013 | vanilla JS (`app.js`) + CSS + Jinja-Template · NO-CDN, lokal gebündelt · *Baseline v0.34.0* | Baseline |

## Testabdeckung nach Modul/Layer

<div class="kz-bars">
  <div class="kz-barrow"><span class="kz-k">core/ (Geschäftslogik)</span><div class="kz-bar"><span style="width:91%"></span></div><span class="kz-p">91 %</span></div>
  <div class="kz-barrow"><span class="kz-k">web/ (Flask-Routes)</span><div class="kz-bar"><span style="width:87%"></span></div><span class="kz-p">87 %</span></div>
  <div class="kz-barrow"><span class="kz-k">launcher/core.py</span><div class="kz-bar"><span style="width:89%"></span></div><span class="kz-p">89 %</span></div>
  <div class="kz-barrow"><span class="kz-k kz-muted">launcher/ GUI-Schale (Tray)</span><div class="kz-bar"><span style="width:72%"></span></div><span class="kz-p kz-muted">~72 % *</span></div>
  <div class="kz-barrow"><span class="kz-k kz-strong">GESAMT</span><div class="kz-bar"><span style="width:88%"></span></div><span class="kz-p kz-good">88 %</span></div>
</div>

\* `tray.py`/`__main__.py` sind die pystray-GUI-Schale: Import- und Definitions-Ebene sind gedeckt (~72 %), aber die
**GUI-Runtime** (pystray-Event-Loop, Tray-Icon) ist headless nicht ausführbar. Die testbare Logik liegt im getesteten
`launcher/core.py` (89 %, per Controller-E2E zusätzlich gegen echtes `app.py` verifiziert).

## Code-Qualität (pyflakes, Produktcode)

| Schweregrad | Anzahl | Befund |
|---|---|---|
| error | 0 | — |
| warning | 0 | — |
| info | 2 | ungenutzte `exc`-Variable in 2 `except`-Blöcken (`web/routes.py`) |
| **Summe** | **2** | kosmetisch · keine Funktions-/Importfehler |

!!! note "Hinweise zur Methodik"
    **Umsetzung** = Produkt-Arbeitspakete aus `roadmap.md`: Spanne AP&#8209;1…63 **ohne** AP&#8209;17 (gestrichen)
    und AP&#8209;19 (`.pattern_transfer` = übergeordnetes Meta-/Destillat-AP) → ≈ 57 erledigt, ≈ 7 offener Backlog.
    Die autoritative Liste ist die [Roadmap](roadmap.md).

    **Effort/Costs (COCOMO)** = Basic-COCOMO „organic" über ≈ 7,6 kSLOC handgeschriebenen Code (a=2,4·b=1,05·c=2,5·d=0,38);
    EUR-Annahmen explizit (Overhead 2,4, ~60 k€/J) — Modellwert, kein Ist (real: ein Entwickler + KI). **Baseline v0.34.0.**

    **Testabdeckung** = `pytest --cov` über die App-Pakete (Frontend-JS und die pystray-GUI sind nicht Teil des
    Python-Coverage-Nenners). **Doku-Abdeckung** (AST-Zählung): 93 % der Module mit Modul-Docstring, auf öffentlicher
    API-Ebene 62 % — die Lücken sind private-helfer-nahe bzw. selbsterklärende kleine Funktionen.

    **Read-Only-Garantie**: das Werkzeug liest nur Schema-Metadaten und erzeugt/führt SELECT aus — keine DB-Mutation
    (Projekt-Invariante).
