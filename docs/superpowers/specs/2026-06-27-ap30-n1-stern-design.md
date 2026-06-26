# AP-30 — N-1-Stern-Abfrage (ein Start, mehrere Lookup-Ziele)

**Datum:** 2026-06-27
**Status:** Design freigegeben (Brainstorming)
**Scope-Entscheidung:** 2026-06-26 (siehe `todo.md`) — Umsetzung zugeschnitten auf den N-1-Stern-Fall.

## Ziel

Ein Start zieht in **einem** read-only SELECT Attribute aus **mehreren Eltern-/Lookup-Tabellen**
(z. B. VM + Host-Name + OS-Name + VLAN). Es entsteht **kein** Zeilen-Fan-out: jede Lookup-Tabelle
wird als Ast eines Join-Baums eingewebt, die Zeilenzahl bleibt die der Start-Tabelle.

## Befund: Infrastruktur existiert größtenteils

Verifiziert gegen den realen Code (Konvention „Spec gegen echten Code prüfen"):

- `core/pathfinder.py::find_paths` webt über `filter_tables` **bereits** Zusatztabellen als Äste
  eines Join-Baums (nicht nur einen linearen Pfad).
- `core/sqlgen.py::generate_sql` rendert **bereits** Selektionen aus mehreren Tabellen.
- Das Frontend (`web/static/js/app.js`) hat **bereits** „Spalten +" (`extra_selects`) zum Hinzufügen
  von Spalten aus beliebigen Tabellen.

**Die echte Lücke:** `extra_selects` (und `order_by`) werden serverseitig **pro Pfad stillschweigend
verworfen**, wenn ihre Tabelle nicht zufällig auf dem Start→Ziel-Pfad liegt
(`web/routes.py:308-312` bzw. `:314-318`). Es gibt **keinen** Weg, eine Lookup-Tabelle gezielt in den
Baum zu zwingen — außer dem Hack, einen Dummy-Filter darauf zu setzen.

## Getroffene Entscheidungen

1. **Eingabe des Sterns:** Bestehendes „Spalten +" wiederverwenden. Jede Tabelle, aus der eine Spalte
   (oder ein ORDER-BY / Filter) gewählt wird, wird automatisch in den Join-Baum gewebt. Kein neues
   UI-Konzept; das stille Verwerfen entfällt.
2. **Fan-out (1-N-Kind-Äste):** **Warnen, aber erlauben.** SQL wird trotzdem generiert; pro Pfad eine
   nicht-blockierende Warnung pro absteigendem Ast.
3. **Ziel-Feld:** Bleibt **Pflicht** (kleine Scheibe, rückwärtskompatibel). Weitere Lookups kommen über
   „Spalten +"/ORDER BY/Filter dazu und werden mitgewebt. Ein „echter" Stern ohne Ziel ist
   ausdrücklich **nicht** Teil dieser Scheibe.

## Architektur / Änderungen

### 1. `core/pathfinder.py` — Pflicht-Tabellen einweben

- Parameter `filter_tables` wird zu `required_tables` verallgemeinert (reine Umbenennung; das Weben
  ist bereits generisch — es webt jede übergebene Tabelle als Ast ein).
- Die Web-Schicht bildet die Vereinigung und übergibt sie (Layering bleibt sauber: `core/` kennt nur
  „diese Tabellen müssen im Baum sein").
- Ist eine `required_table` nicht erreichbar, wird weiterhin `NoPathError` geworfen (jetzt mit klarer
  Meldung) — statt die Spalte still zu verwerfen.

### 2. `core/pathfinder.py` — Fan-out als Fakt am `JoinStep`

- `JoinStep` erhält ein Feld `to_many: bool = False`.
- In `_join_step` wird es aus der gewählten `JoinEdge`-Orientierung gesetzt:
  Ein Schritt `links → rechts` ist `to_many`, wenn **rechts** den FK hält
  (`chosen_option.table_a == rechts`) → Eltern→Kind, absteigend, Zeilen-Fan-out möglich.
  Ein reiner N-1-Stern hat ausschließlich `to_one`-Schritte.
- `_join_step` wählt dazu die `JoinEdge`-**Option** (deterministisch, min. orientierte Paare) und
  liest danach Paare **und** Orientierung daraus — bisher wurden nur die Paare zurückgegeben.
- **Kein Einfluss auf die erzeugte SQL.** `core/` bleibt Flask-frei; das Feld ist nur ein auswertbarer
  Fakt.

### 3. `web/routes.py` — Vereinigung bilden, kein stilles Verwerfen, Warnungen

- `required_tables = {Filter-Tabellen} ∪ {extra_selects-Tabellen} ∪ {order_by-Tabellen}` bilden und an
  `find_paths` übergeben.
- Das **stille Pro-Pfad-Verwerfen** von `extra_selects` (`:308-312`) **und** `order_by` (`:314-318`)
  entfällt — die Tabellen liegen nach dem Weben garantiert im Baum. Eine unerreichbare Tabelle führt
  dadurch konsistent zu `NoPathError` statt stillem Verschlucken.
- Pro Pfad eine `warnings`-Liste in die JSON-Antwort aufnehmen: für jeden `to_many`-Schritt eine
  Meldung (z. B. „Ast *Tabelle* ist 1-N — kann Zeilen vervielfachen"). Generierung/Ausführung läuft
  normal weiter. Web-Schicht ist die richtige Stelle für die nutzerseitige Formulierung.

### 4. `web/static/js/app.js` — Warnungen anzeigen

- Der Request ändert sich **nicht**: „Spalten +" sendet `extra_selects` bereits korrekt; der Server
  webt diese Tabellen jetzt ein.
- Einzige UI-Änderung: die neuen Pro-Pfad-`warnings` aus der Antwort rendern (Warn-Zeile/Badge an der
  Pfadkarte).

### 5. Tests

- **pathfinder:** Select-/ORDER-BY-Tabelle abseits des Hauptpfads wird als Ast eingewebt; unerreichbare
  Pflicht-Tabelle → `NoPathError`; `to_many` korrekt für auf- und absteigende Schritte.
- **routes:** Spalte aus Lookup-Tabelle erscheint jetzt im SELECT (kein stilles Verwerfen);
  ORDER-BY-Tabelle wird gewebt; Antwort enthält `warnings` bei absteigenden Ästen; Generierung läuft
  trotz Warnung durch.
- **sqlgen:** unverändert; ggf. Test, dass `JoinStep.to_many` die SQL nicht verändert.

### 6. Version & Doku

- **minor**-Bump via `./venv/bin/python sync_version.py --minor` (Feature).
- Changelog + Doc-Mirror, Roadmap/Board/Gantt (AP-30 als erledigt enumerieren — kein Sammel-Eintrag),
  Test-Zahlen/Badges, Site-Build (Linux). Je-AP-Commit ohne KI-Signatur.

## Bewusste Verhaltensänderung

Eine Spalte (oder ORDER BY / Filter) aus einer **nicht erreichbaren** Tabelle führt künftig zu einem
`NoPathError` statt zu stillem Verschlucken. Das ist gewollt (kein stilles Verwerfen mehr), ist aber
eine Verhaltensänderung gegenüber dem aktuellen Stand.

## Nicht in dieser Scheibe (YAGNI)

- „Echter" Stern ohne Ziel-Feld (Start als Wurzel ohne Hauptpfad).
- Automatisches Blockieren absteigender Äste oder automatisches DISTINCT bei Fan-out.
- Explizites „Lookup-Tabellen"-UI getrennt von „Spalten +".
