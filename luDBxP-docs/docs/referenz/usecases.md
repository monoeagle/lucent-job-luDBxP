# UseCases

## UC-1: Join-Pfad zwischen zwei Tabellen berechnen

**Ziel:** Vom Schema einer unbekannten Datenbank schnell ein korrektes
JOIN-Statement von Tabelle A nach Tabelle B erzeugen.

**Ablauf:**

1. Datenbankverbindung eingeben → Schema laden
2. Im Join-Builder Start-Tabelle + Start-Spalte wählen
3. Ziel-Tabelle + Ziel-Spalte wählen
4. „Join-Pfad berechnen" klicken
5. Das generierte SQL in die eigene Query übernehmen

**Ausgabe:** Parametrisiertes SQL mit allen nötigen JOINs. Bis zu 5 alternative
Pfade (k-kürzeste Pfade) werden angezeigt, falls mehrere Routen existieren.

> **Join-Typ pro Schritt:** Über der SQL-Ausgabe lässt sich für **jede Join-Station**
> der Typ wählen — **INNER** (Standard), **LEFT**, **RIGHT**, **FULL**. So bleiben z. B.
> mit **LEFT** die Zeilen der Start-/Treiber-Tabelle erhalten, auch wenn eine
> Folgetabelle kein Match hat. Eine Änderung baut SQL und Ergebnis neu. Warum LEFT
> manchmal *nichts* ändert (unerreichbare/gefilterte Waisen) und was der Waisen-Chip
> bedeutet, erklärt [Outer Joins & Waisen](outer-joins.md).

> **Fan-out-Warnung:** Enthält ein Pfad einen absteigenden (1-N) Schritt, zeigt
> der Builder eine gelbe ⚠-Zeile, weil das Ergebnis Zeilen vervielfachen kann.
> Was das genau bedeutet und wann es zu erwarten ist, erklärt
> [Fan-out-Warnung (1-N)](fanout-warnung.md) mit durchgerechneten Beispielen.

> **Mehr als zwei Tabellen:** Ein Pfad verbindet Start und Ziel über **beliebig viele
> Zwischentabellen** (mehrere Join-Stationen) — z. B. in der Demo-CMDB
> `Network → Datacenter → Host → VirtualMachine → VMDisk → Datastore → Replication`
> (6 JOINs). Über „Filter +" benötigte Tabellen werden als zusätzliche Stationen in den
> Pfad eingewebt (siehe UC-2). Eine Abfrage hat dabei genau **eine** Start- und **eine**
> Ziel-Tabelle; mehrere voneinander unabhängige Ziele in einer Abfrage sind nicht vorgesehen.

<img src="../images/screenshots/Screenshot_04_luDBxP.jpg"
     alt="Join-Builder-Ergebnis: VirtualMachine → Datacenter, 5 Pfade, SQL-Block, Graph-Highlight in Rot.">

---

## UC-2: Gefilterte Abfrage erstellen

**Ziel:** Ein JOIN mit einer WHERE-Bedingung über eine Zwischentabelle erzeugen.

**Ablauf:**

1. Join-Pfad wie in UC-1 definieren
2. Über „Filter +" eine Filterzeile hinzufügen:
   - Tabelle auswählen (aus dem Pfad oder erreichbaren Tabellen)
   - Spalte auswählen
   - Operator wählen (`=`, `!=`, `<`, `>`, `LIKE`, `IS NULL`, …)
   - Wert eingeben
3. Mehrere Filter werden mit UND verknüpft

**Ausgabe:** SQL mit `WHERE`-Klausel. Der **angezeigte und kopierte** SELECT ist
**direkt lauffähig** — die Filterwerte sind als Literale eingesetzt (z. B.
`WHERE "Cluster"."ClusterID" = 1`), sodass er sich ohne Nacharbeit in einen externen
SQL-Editor einfügen lässt. Intern führt das Tool die Abfrage **parametrisiert**
(`:p0` + gebundene Werte) read-only aus — injection-sicher; die `:p0`-Form taucht in der
Oberfläche nicht mehr auf.

---

## UC-3: FK-Graph erkunden

**Ziel:** Die Beziehungsstruktur einer unbekannten Datenbank visuell verstehen.

**Ablauf:**

1. Schema laden → Graph-Panel rechts zeigt alle Tabellen und FKs
2. Knoten können verschoben werden (Force-directed Layout)
3. Nach Berechnung eines Join-Pfads: der gewählte Pfad wird farblich hervorgehoben

**Implizite FKs:** Checkbox „Implizite FKs einbeziehen" aktivieren → der Graph
zeigt gestrichelte Kanten für heuristisch erkannte Beziehungen (Name-Matching
auf Primärschlüssel-Spalten).

---

## UC-4: Tabellen-Daten vorab prüfen

**Ziel:** Bevor man eine Query schreibt, die ersten Zeilen einer Tabelle sehen.

**Ablauf:**

1. Im Objekt-Browser links auf eine Tabelle oder View klicken
2. Tab „Daten" wählen → erste 100 Zeilen werden geladen

**Hinweis:** Nur `SELECT … LIMIT 100` — kein Schreibzugriff, Objektname gegen
reflektiertes Schema validiert.

---

## UC-5: Verbindung zu einer Produktionsdatenbank speichern

**Ziel:** Häufig genutzte Verbindungen nicht jedes Mal neu eingeben müssen.

**Ablauf:**

1. Tools → Verbindungen öffnen
2. DB-Typ wählen, Felder ausfüllen, Verbindung testen
3. Name vergeben und speichern

**Hinweis:** Das Passwort wird nicht gespeichert — nur Typ, Host, Port,
Datenbankname und Benutzer werden in `config.json` abgelegt.

---

## UC-6: Schema ohne deklarierte FKs erschließen (Implizite FKs)

**Ziel:** Join-Pfade in einer Legacy-Datenbank finden, die keine FK-Constraints
definiert.

**Ablauf:**

1. `demo_cmdb_nofk.db` verbinden (oder eigene FK-freie DB)
2. Schema laden — der Graph zeigt zunächst nur isolierte Knoten
3. Checkbox „Implizite FKs einbeziehen" aktivieren
4. Graph aktualisiert sich mit gestrichelten Kanten → Join-Pfade berechnen wie gewohnt

**Heuristik:** Spaltennamen der Form `<tabelle>_id` oder `<tabelle>id` werden
auf einspaltigen Primärschlüssel einer anderen Tabelle abgebildet, wenn die
Typen kompatibel sind.

---

## UC-7: Ein SQL-Statement read-only analysieren

**Ziel:** Ein beliebiges SQL-Statement verstehen, ohne es auszuführen — Aufbau,
gelesene/geschriebene Tabellen, Filter/Sortierung und mögliche Stolpersteine.

**Ablauf:**

1. Tools → **SQL-Analyzer** öffnen
2. Statement einfügen (z. B. einen im Join-Builder gebauten SELECT) → **Analysieren**

**Ausgabe:** Das Statement wird via **sqlglot** geparst — **nie ausgeführt** — und der
AST ausgewertet:

- **Typ** (SELECT/INSERT/…/DDL) und ein **Komplexitäts-Score** (Note A–E, gewichtet aus
  Joins/Subqueries/CTEs/UNION/Window/CASE).
- **Struktur-Zähler:** Tabellen · Joins · Subqueries · CTEs · UNION · Window · Aggregate · CASE.
- **Klauseln:** Spalten, Joins (Typ + ON-Bedingung), **Filter (WHERE)**, GROUP BY/HAVING,
  **Sortierung (ORDER BY)**, DISTINCT/LIMIT.
- **Gelesen / Geschrieben:** die beteiligten Tabellen; mit aktiver Verbindung zusätzlich
  Prüfung gegen das echte Schema (`UNKNOWN_TABLE`/`UNKNOWN_COLUMN`).
- **Warnungen/Lints:** `WRITE_STATEMENT`, `NO_WHERE`, `CARTESIAN_JOIN` sowie die statischen
  Hinweise `SELECT *`, `LIKE '%…'` (nicht index-nutzbar) und Funktion-auf-Spalte-in-WHERE.

**Graph:** Die beteiligten Tabellen werden im Schema-Graph markiert (gelesen = blau) und die
**JOIN-Kanten des Statements hervorgehoben** — so ist der Pfad des SELECTs sofort sichtbar.

**Hinweis:** Funktioniert mit und ohne Verbindung; schema-abhängige Prüfungen nur mit
aktiver Verbindung. Es wird ausschließlich gelesen/analysiert — kein Schreibzugriff.
