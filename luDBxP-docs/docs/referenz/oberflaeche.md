# Oberfläche

Galerie der wichtigsten Screens — Klick auf ein Bild öffnet die Lightbox-Ansicht
(Zoom, Vor/Zurück-Navigation, ESC zum Schließen).

---

## Startscreen — vor der Verbindung

<img src="../images/screenshots/Screenshot_01_luDBxP.jpg"
     alt="Startscreen: LucentTools DB Explorer vor dem Verbinden. Verbindungsfeld in der Topbar, leerer Objekt-Browser links, leerer Schema-Graph rechts.">

Der Startscreen zeigt das 3-Panel-Grundgerüst: Topbar mit Verbindungsfeld und
„Verbinden"-Button, leerer Objekt-Browser links (TABELLEN 0 / VIEWS 0), leeres
Graph-Panel rechts. Das Verbindungsfeld ist mit dem Demo-Datenbankpfad
`sqlite:///sample_data/demo_cmdb.db` vorbelegt.

Direkt daneben liegt ein **Dropdown für gespeicherte Verbindungen** (SQL-Developer-typisch):
Eine Auswahl daraus verbindet sofort mit der gewählten Verbindung. Das Dropdown
ist mit dem Verbindungs-Tab synchronisiert (gleiche Liste, gespiegelte Auswahl);
passwortlose Verbindungen (SQLite oder Server ohne Authentifizierung) verbinden
direkt, sonst öffnet sich der Verbindungs-Tab vorbefüllt zum Ergänzen des Passworts.

---

## 3-Panel-Layout nach dem Verbinden

<img src="../images/screenshots/Screenshot_02_luDBxP.jpg"
     alt="3-Panel-Layout: Objekt-Browser links mit 13 Tabellen und 2 Views, SQL-Builder-Tab in der Mitte, Schema-Graph rechts mit allen FK-Kanten.">

Nach „Schema laden" füllen sich Objekt-Browser (13 Tabellen, 2 Views) und der
Schema-Graph gleichzeitig. Der SQL-Builder-Tab ist standardmäßig aktiv.
Der Graph zeigt alle Tabellen als Knoten und die Foreign-Key-Beziehungen als
gerichtete Kanten.

Ein **Suchfeld** über dem Objekt-Browser filtert die Tabellen-/View-Listen live
nach Namen. Die **Sidebar-Breite** ist über einen linken Splitter per Drag
verschiebbar (analog zum Graph-Splitter). Der Button **„Neu anordnen"** im
Graph-Kopf würfelt das Layout neu; bei dichten Schemas vergrößern sich die
Knotenabstände automatisch, damit sich Knoten weniger überlappen.

---

## Tabellen-Detail — Sub-Tabs

<img src="../images/screenshots/Screenshot_03_luDBxP.jpg"
     alt="Tabellen-Detail der Cluster-Tabelle: Sub-Tabs Definition / Daten / SQL. Spalten ClusterID (PK), Name, DatacenterID mit Typen. Foreign-Key-Liste darunter.">

Ein Klick auf eine Tabelle im Objekt-Browser öffnet ein Detail-Tab. Unter
**Definition** stehen Spalten mit Typ und PK-Markierung sowie die deklarierten
Foreign Keys. Weitere Sub-Tabs: **Daten** (erste 100 Zeilen als Tabelle),
**SQL** (DDL-Statement der Tabelle).

---

## SQL-Builder — Pfadliste + SQL-Ergebnis + Graph-Highlight

<img src="../images/screenshots/Screenshot_04_luDBxP.jpg"
     alt="SQL-Builder: Start Cluster.ClusterID, Ziel Replication.ReplicationID. Mehrere alternative Pfade als anklickbare Liste mit N-1/1-N-Richtungs-Chips; ausgewählt (mit [*] markiert) ist die komplexe 6-Hop-Variante Cluster → ResourcePool → VMPlacement → VirtualMachine → VMDisk → Datastore → Replication. Darunter pro Join-Schritt ein Join-Typ-Dropdown (INNER) mit Waisen-Hinweis LEFT/FULL, das mehrzeilige SELECT (inkl. Composite-Key ON … AND …) und die Ergebnistabelle mit sortierbaren Spaltenköpfen. Im Schema-Graph ist der gesamte Pfad rot hervorgehoben (Start Cluster grün, Ziel Replication), rechts UML-Karten für Start- und Ziel-Tabelle.">

Nach „Generieren" listet der SQL-Builder alle k-kürzesten Pfade (bis zu 5)
als anklickbare Hyperlinks — jeder Schritt trägt einen **Richtungs-Chip** (grün N-1
aufsteigend / amber 1-N absteigend, kann Zeilen vervielfachen). Der gewählte Pfad ist
mit **`[*]`** markiert; hier ist bewusst eine **komplexe Mehrhop-Variante** ausgewählt.
Der **Join-Typ** (INNER/LEFT/RIGHT/FULL) ist pro Schritt inline in der aktiven
Pfadzeile wählbar; ein Waisen-Hinweis zeigt, welcher Typ das Ergebnis tatsächlich ändert. Das generierte,
parametrisierte SQL (mehrzeilig, Composite-Keys ausgerichtet) erscheint darunter,
gefolgt von der Ergebnistabelle. Im Schema-Graph werden die beteiligten Tabellen und
Kanten farblich hervorgehoben.

**Interaktive Ergebnistabelle (AP-45):** Ein Klick auf einen **Spaltenkopf** öffnet ein Menü mit
**Sortieren ASC/DESC**, **Als Filter…** und **Spalte entfernen**. Sortieren ergänzt eine
Sortierzeile und baut neu, „Als Filter" legt eine vorbefüllte Filterzeile an, „Spalte entfernen"
entfernt Zusatzspalten (Start-/Ziel-Spalten definieren den Pfad und sind geschützt). Sobald ein
**Filterwert gesetzt** ist (getippt oder aus dem Dropdown gewählt), wird sofort neu gebaut — die
`WHERE`-Bedingung erscheint umgehend im SQL und im Ergebnis.

**Zwei verschiedene „DISTINCT" — nicht verwechseln:**

| | erscheint im generierten SQL? | Zweck |
|---|---|---|
| **`DISTINCT`-Checkbox** (neben LIMIT/Dialekt) | **ja** — `SELECT DISTINCT …` | doppelte Ergebniszeilen unterdrücken |
| **Filter-Wertdropdown** (`/api/distinct`) | **nein** | Komfort-Lookup: zeigt die echten Werte der Spalte als Auswahlliste |

Das **Filter-Wertdropdown** ist eine **separate Hintergrundabfrage** auf *eine* Tabelle/Spalte
(`SELECT DISTINCT col FROM tabelle WHERE col IS NOT NULL ORDER BY col`, begrenzt auf
`config.DISTINCT_LIMIT`). Sie beantwortet nur die Frage „welche Werte gibt es in dieser Spalte?"
und füllt damit die Vorschlagsliste (`<datalist>`) des Wertfelds. Sie fließt **nicht** in das
angezeigte/kopierbare Join-SQL ein — dort steht weiterhin nur deine eigentliche Abfrage
(Join + deine Filter). Freitext bleibt jederzeit möglich.

---

## SQL-Builder — parallele Tab-Ansicht

<img src="../images/screenshots/Screenshot_05_luDBxP.jpg"
     alt="Gleiche SQL-Builder-Ansicht wie zuvor, jedoch mit einem zusätzlichen VirtualMachine-Detail-Tab geöffnet — beide Tabs koexistieren in der Tab-Leiste.">

Tabellen-Detail-Tabs und der SQL-Builder-Tab koexistieren in der Tab-Leiste.
Mehrere Tabellen können gleichzeitig geöffnet bleiben; ein Klick auf den Tab
wechselt die Ansicht ohne den Graph-Zustand zu verlieren.

---

## Schema-Graph mit impliziten FKs

<img src="../images/screenshots/Screenshot_06_luDBxP.jpg"
     alt="Schema-Graph mit aktivierter Checkbox 'implizite FKs'. Gestrichelte lila Kanten zeigen heuristisch erkannte Beziehungen (Spaltenname-vs-PK-Matching) zusätzlich zu den deklarierten FK-Kanten.">

Die Checkbox **„implizite FKs"** in der Topbar aktiviert die SchemaSpy-Heuristik:
Spalten, deren Name auf einen Primärschlüssel einer anderen Tabelle schließen
lässt, werden als gestrichelte Kanten eingezeichnet. Nützlich für Datenbanken
ohne deklarierte Foreign Keys (z. B. `demo_cmdb_nofk.db`).

---

## AP-1: Interaktive Pfad-Auswahl direkt im Graph

<img src="../images/screenshots/Screenshot_07_luDBxP.jpg"
     alt="AP-1-Feature: Doppelklick auf VirtualMachine im Graph öffnet eine UML-Karte im Graph-Panel mit allen Spalten (VMID PK, Name, …). Eine zweite Karte für Host zeigt das Ziel. SQL-Builder wurde automatisch mit VirtualMachine.HostID → Host.HostID befüllt. Graph zeigt den Pfad rot hervorgehoben.">

**Neu in AP-1:** Doppelklick auf einen Graph-Knoten öffnet eine **UML-Tabellenkarte**
direkt im Graph-Panel mit allen Spalten, Typen und PK-Markierungen. Eine Spalte
anklicken setzt die Quelle; Doppelklick auf eine zweite Tabelle + Spaltenwahl
setzt das Ziel. Sobald Quelle und Ziel gesetzt sind:

- `/api/joinpath` wird automatisch aufgerufen
- Der Join-Pfad wird im Graph **rot hervorgehoben**
- Der **SQL-Builder-Tab füllt sich automatisch** mit den gewählten Tabellen und
  Spalten (Zweiweg-Sync Graph ↔ SQL-Builder)

Die Statuszeile am unteren Graph-Rand zeigt die aktuelle Auswahl
(`Quelle: VirtualMachine.HostID → Ziel: Host.HostID`) und bietet einen
„Auswahl zurücksetzen"-Button.

---

## SQL-Builder — aktuelle Funktionen (Stand v0.44.0)

Über die obigen Screenshots hinaus bietet der SQL-Builder inzwischen:

- **Layout — vier Klausel-Sektionen + Aktionsleiste:** Die Klausel-Builder
  (Filter, Sortierung, Spalten, HAVING) sind als vier eigenständige, immer
  sichtbare Abschnitte mit beschrifteter Überschrift und je einem kompakten
  „+"-Button dargestellt. Die Ausgabe-Optionen (DISTINCT, LIMIT, Dialekt) und
  der „Generieren"-Button befinden sich in einer getrennten Aktionsleiste am
  unteren Rand. Nur Markup/CSS — alle Element-IDs und das generierte SQL sind
  unverändert.
- **Start ⇄ Ziel tauschen** per ⇄-Knopf neben den Ziel-Dropdowns (Tabelle + Spalte;
  baut sofort neu) — die warnungsfreie Richtung ist oft die umgekehrte.
- **Pfad-Auswahl-Indikator:** Die Kandidatenpfade tragen `[*]` (aktiv) / `[ ]` statt
  Bullets; jeder Join-Schritt hat einen **Richtungs-Chip** grün `N-1` / gelb `1-N`.
- **Join-Typ pro Schritt** (INNER/LEFT/RIGHT/FULL): Die Dropdowns sitzen direkt inline
  in der aktiven Kandidatenpfad-Zeile, neben den Richtungs-Chips. Es gibt keine
  separate Join-Typ-Zeile mehr. Ein **Waisen-Chip** zeigt datengetrieben, welcher Typ
  hier *tatsächlich* zusätzliche Zeilen bringt (siehe [Outer Joins & Waisen](outer-joins.md)).
- **Zeilen-Reihenfolge per ↑/↓ (AP-E):** Sortier-Zeilen (ORDER BY) und Spalten-Zeilen
  tragen kleine ↑/↓-Buttons zum Verschieben innerhalb ihrer Sektion. Die Reihenfolge
  bestimmt die erzeugte SQL: ORDER BY = Sortier-Priorität, Spalten = SELECT-/GROUP-BY-
  Reihenfolge. Das ↑ der ersten und das ↓ der letzten Zeile sind deaktiviert; das
  Verschieben wird mit „Generieren" angewandt. WHERE/HAVING haben bewusst kein Move
  (ihre Reihenfolge ist kosmetisch).
- **Lesbares, mehrzeiliges SQL** (eine Spalte/JOIN/ON-Bedingung pro Zeile,
  ausgerichtete `=`); das angezeigte/kopierte SELECT ist **direkt lauffähig**
  (Filterwerte eingesetzt, endet mit `;`) — intern wird parametrisiert read-only
  ausgeführt.
- **Ergebnistabelle:** Statuszeile *Zeilen · Join-Typ · Fan-out*; **NULL-Zellen**
  (Outer-Join-/Waisen-Zeilen) hervorgehoben.
- **Detailkarten:** Sind Start/Ziel gewählt (auch per Dropdown), rückt der Graph nach
  oben und darunter erscheinen die Tabellen-Detailkarten für Start/Ziel; ohne Auswahl
  bleibt der Graph zentriert.

## Schema-Graph — Legende

Oben links erklärt eine kleine Legende die Hervorhebungen: **blau** = Analyzer
(gelesen/Joins), **rot** = Analyzer (geschrieben), **orange** = Join-Pfad,
**N-1/1-N** = Join-Richtung (N-1 sicher / 1-N kann Zeilen vervielfachen),
**grün/amber** = Start/Ziel. Join-Pfad- und Analyzer-Markierungen sind
wechselseitig exklusiv. Die Fan-out-Bedeutung (1-N vervielfacht Zeilen / N-1
sicher) wird in der Legende erklärt; der SQL-Builder zeigt keine separate
Fan-out-Kachel mehr.

## SQL-Analyzer

Der **SQL-Analyzer**-Tab parst ein eingefügtes Statement **read-only** (nie
ausgeführt) via sqlglot und zeigt: Typ, **Komplexitäts-Score** (A–E),
Struktur-Zähler, Spalten, **Joins (Typ + ON)**, **Filter/GROUP BY/HAVING/ORDER BY**,
gelesene/geschriebene Tabellen sowie Warnungen/Lints (u. a. `SELECT *`, `LIKE '%…'`,
Funktion-auf-Spalte, sowie `SUSPICIOUS_ALIAS` für vertippte Join-Schlüsselwörter).
Die JOIN-Kanten des Statements werden im Graph gezeichnet. Mit aktiver Verbindung
zusätzlich `UNKNOWN_TABLE`/`UNKNOWN_COLUMN`.

**Optimierungs-Vorschläge (AP-F):** ein eigener, von den Warnungen getrennter
Abschnitt mit vier schema-freien AST-Heuristiken — überflüssiges `DISTINCT` neben
`GROUP BY`, `ORDER BY` ohne `LIMIT`, `OR` im Top-Level-`WHERE` (kann Indexnutzung
verhindern) und eine Nicht-`EXISTS`-Unterabfrage in `WHERE` (oft besser als
JOIN/EXISTS). Read-only, nur Hinweise — der Analyzer schreibt nichts um.
