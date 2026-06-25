# Architektur

## Systemüberblick

Lucent DB Explorer verbindet ein Browser-Frontend direkt mit einer
Live-Datenbankverbindung über eine Flask-API. Der Core-Layer kapselt die
gesamte Datenbanklogik — das Frontend berührt niemals direkt die Datenbank.

<img src="../images/mermaid/referenz-architektur-3.svg" alt="Systemüberblick: UI · Flask-API · Core-Layer">

## Schichten

Lucent DB Explorer folgt einem zweischichtigen Aufbau: ein `core/`-Layer für
die gesamte Datenbanklogik und ein `web/`-Layer für die Flask-API und das
Frontend.

<img src="../images/mermaid/referenz-architektur-1.svg" alt="Diagramm 1 aus referenz/architektur.md">

## Datenfluss: Join-Pfad-Berechnung

<img src="../images/mermaid/referenz-architektur-2.svg" alt="Diagramm 2 aus referenz/architektur.md">

## Wichtige Design-Entscheidungen

### Read-only

Der gesamte Core-Layer führt ausschließlich `SELECT`-Abfragen aus.
Schreiboperationen (INSERT/UPDATE/DELETE/DDL) sind nicht implementiert.
Objektnamen werden gegen das reflektierte Schema validiert, bevor eine
Abfrage ausgeführt wird.

### Lokale Assets

Alle JavaScript-Bibliotheken (Cytoscape.js, Mermaid) sind lokal im Projekt
gebundelt. Kein CDN-Zugriff zur Laufzeit.

### Parametrisierte Abfragen

Der SQL-Generator erzeugt immer parametrisierte Platzhalter (`?` / `:param`).
Werte werden niemals direkt in die SQL-Zeichenkette eingebettet.

### Implizite FKs

Die Heuristik (`core/implied.py`) vergleicht Spaltennamen mit Primärschlüsseln
anderer Tabellen (z. B. `user_id` → `user.id`). Nur kompatible Typen werden
berücksichtigt. Die Ergebnisse werden im Graph als gestrichelte Kanten
dargestellt und sind per Checkbox deaktivierbar.
