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
     alt="3-Panel-Layout: Objekt-Browser links mit 13 Tabellen und 2 Views, Join-Builder-Tab in der Mitte, Schema-Graph rechts mit allen FK-Kanten.">

Nach „Schema laden" füllen sich Objekt-Browser (13 Tabellen, 2 Views) und der
Schema-Graph gleichzeitig. Der Join-Builder-Tab ist standardmäßig aktiv.
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

## Join-Builder — Pfadliste + SQL-Ergebnis + Graph-Highlight

<img src="../images/screenshots/Screenshot_04_luDBxP.jpg"
     alt="Join-Builder: Start VirtualMachine.VMID, Ziel Datacenter.DatacenterID. Fünf alternative Pfade als anklickbare Liste. SQL-Block darunter. Im Graph sind VirtualMachine, Host und Datacenter rot hervorgehoben.">

Nach „Join-Pfad bauen" listet der Join-Builder alle k-kürzesten Pfade (bis zu 5)
als anklickbare Hyperlinks. Der kürzeste Pfad ist vorausgewählt; das generierte
parametrisierte SQL erscheint direkt darunter. Im Schema-Graph werden die
beteiligten Tabellen und Kanten farblich hervorgehoben.

---

## Join-Builder — parallele Tab-Ansicht

<img src="../images/screenshots/Screenshot_05_luDBxP.jpg"
     alt="Gleiche Join-Builder-Ansicht wie zuvor, jedoch mit einem zusätzlichen VirtualMachine-Detail-Tab geöffnet — beide Tabs koexistieren in der Tab-Leiste.">

Tabellen-Detail-Tabs und der Join-Builder-Tab koexistieren in der Tab-Leiste.
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
     alt="AP-1-Feature: Doppelklick auf VirtualMachine im Graph öffnet eine UML-Karte im Graph-Panel mit allen Spalten (VMID PK, Name, …). Eine zweite Karte für Host zeigt das Ziel. Join-Builder wurde automatisch mit VirtualMachine.HostID → Host.HostID befüllt. Graph zeigt den Pfad rot hervorgehoben.">

**Neu in AP-1:** Doppelklick auf einen Graph-Knoten öffnet eine **UML-Tabellenkarte**
direkt im Graph-Panel mit allen Spalten, Typen und PK-Markierungen. Eine Spalte
anklicken setzt die Quelle; Doppelklick auf eine zweite Tabelle + Spaltenwahl
setzt das Ziel. Sobald Quelle und Ziel gesetzt sind:

- `/api/joinpath` wird automatisch aufgerufen
- Der Join-Pfad wird im Graph **rot hervorgehoben**
- Der **Join-Builder-Tab füllt sich automatisch** mit den gewählten Tabellen und
  Spalten (Zweiweg-Sync Graph ↔ Join-Builder)

Die Statuszeile am unteren Graph-Rand zeigt die aktuelle Auswahl
(`Quelle: VirtualMachine.HostID → Ziel: Host.HostID`) und bietet einen
„Auswahl zurücksetzen"-Button.

---

## Join-Builder — aktuelle Funktionen (Stand v0.31.0)

Über die obigen Screenshots hinaus bietet der Join-Builder inzwischen:

- **Start ⇄ Ziel tauschen** per ⇄-Knopf neben den Ziel-Dropdowns (Tabelle + Spalte;
  baut sofort neu) — die warnungsfreie Richtung ist oft die umgekehrte.
- **Pfad-Auswahl-Indikator:** Die Kandidatenpfade tragen `[*]` (aktiv) / `[ ]` statt
  Bullets; jeder Join-Schritt hat einen **Richtungs-Chip** grün `N-1` / gelb `1-N`.
  Eine kompakte Kachel oben rechts erklärt `1-N` (Fan-out → siehe
  [Fan-out-Warnung](fanout-warnung.md)).
- **Join-Typ pro Schritt** (INNER/LEFT/RIGHT/FULL) über der SQL-Ausgabe; ein
  **Waisen-Chip** zeigt datengetrieben, welcher Typ hier *tatsächlich* zusätzliche
  Zeilen bringt (siehe [Outer Joins & Waisen](outer-joins.md)).
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
**N-1/1-N** = Join-Richtung, **grün/amber** = Start/Ziel. Join-Pfad- und
Analyzer-Markierungen sind wechselseitig exklusiv.

## SQL-Analyzer

Der **SQL-Analyzer**-Tab parst ein eingefügtes Statement **read-only** (nie
ausgeführt) via sqlglot und zeigt: Typ, **Komplexitäts-Score** (A–E),
Struktur-Zähler, Spalten, **Joins (Typ + ON)**, **Filter/GROUP BY/HAVING/ORDER BY**,
gelesene/geschriebene Tabellen sowie Warnungen/Lints (u. a. `SELECT *`, `LIKE '%…'`,
Funktion-auf-Spalte, sowie `SUSPICIOUS_ALIAS` für vertippte Join-Schlüsselwörter).
Die JOIN-Kanten des Statements werden im Graph gezeichnet. Mit aktiver Verbindung
zusätzlich `UNKNOWN_TABLE`/`UNKNOWN_COLUMN`.
