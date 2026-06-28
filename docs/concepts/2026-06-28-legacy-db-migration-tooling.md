# Konzept & Arbeitspakete — Legacy-DB-Migration / Reverse-Engineering

**Datum:** 2026-06-28
**Status:** Konzept / Backlog (AP-54…AP-57)
**Auslöser:** Ablösung von OpenText/Micro-Focus **Hybrid Cloud Management (HCMX)** (Lineage HP CSA → HPE → Micro Focus → OpenText) durch eine neue, auf **OpenTofu** basierende Automatisierung mit eigenem Marketplace-Portal.

## 1. Use-Case (warum diese APs)

Die neue Datenbank entsteht **auf der grünen Wiese** (freie Gestaltung). Der LucentTools DB Explorer wird **nicht** für die neue DB gebraucht, sondern als **Reverse-Engineering-Werkzeug für die Alt-DBs**: die Zusammenhänge der HCMX-Datenbanken verstehen, um einen **referenziell sauberen Export** zu bauen und zu bestimmen, **wie die Daten in das neue Modell überführt** werden (es werden nicht 100 % der Server neu installiert — Produktionsdaten müssen mit).

Damit ist das Tool ein **Daten-Archäologie-/Migrations-Mapping-Werkzeug**: „wo liegen welche Geschäftsdaten und wie hängen sie zusammen".

## 2. Architektur-Erkenntnis (prägt alle APs)

HCMX ist **keine Monolith-DB**, sondern eine Suite lose gekoppelter Produkte (CSA = Service-Katalog/Subscriptions hinter dem Marketplace Portal, Operations Orchestration = Workflow-Engine, IdM, ggf. uCMDB/SMAX), **jedes mit eigener DB/eigenem Schema**, integriert über **REST/Web-Services — nicht über SQL**.

Daraus folgt die zentrale Erkenntnis, die die Priorisierung bestimmt:

| Beziehungs-Ebene | Verknüpfung | Vom Tool heute auffindbar? |
|---|---|---|
| **Innerhalb** eines Produkts (CSA: Subscription → Instance → Component → Property) | **deklarierte FKs** | **Ja** — Ein-Schema-Reflection (AP-52), Join-Pfade + Export-SELECT funktionieren |
| **Zwischen** Produkten (CSA-Subscription ↔ OO-Run ↔ uCMDB-CI) | **fachliche IDs / Namenskonventionen**, **keine** FK-Constraints | **Nein** — und volle Cross-Schema-*FK*-Joins würden es **auch nicht** finden, weil es keine FKs sind |

**Konsequenz:** Der naheliegende Wunsch „Cross-Schema-Joins" ist für diesen Use-Case **nicht** der Hebel. Die produkt-übergreifenden Links sind logisch (gemeinsame IDs), nicht referenziell. Der passende Hebel ist **implied-FK-Erkennung über Namen** (AP-55), und der größte echte Mehrwert für „sauberer Export" ist **referenziell-konsistentes Subsetting** (AP-56). Volle Cross-Schema-Joins (AP-57) werden **zurückgestellt** und nur dann gebaut, wenn die Diagnose (AP-54) zeigt, dass die Ziel-DB überhaupt echte Cross-Schema-FKs hat (HCMX-Erwartung: nein).

Abgrenzung zweier oft verwechselter Operationen:
- **Join-Pfad A→B** (heutiges Tool): ein SELECT, das zwei Spalten über den FK-Pfad verbindet.
- **Entitäts-Hülle / Subsetting** (AP-56): „Zeile X **und alle abhängigen Zeilen** (Eltern *und* Kinder, rekursiv)" → vollständiger, referenziell konsistenter Export-Datensatz. Andere Operation, nicht im Join-Builder erzwingen.

## 3. Arbeitspakete

Sequenzierung: **AP-54 zuerst** (Faktenlage, schafft Entscheidungsgrundlage für AP-57). **AP-55** und **AP-56** sind unabhängig und liefern den eigentlichen Migrationsnutzen. **AP-57** ist bedingt/zurückgestellt.

```
AP-54 (Diagnose) ──► entscheidet ──► AP-57 (volle Cross-Schema-Joins, bedingt)
AP-55 (implied-FK)  unabhängig
AP-56 (Subset-Export) unabhängig ◄── größter Migrationsnutzen
```

---

### AP-54 — Cross-Schema-FK-Diagnose (read-only)

**Ziel:** Empirisch sichtbar machen, ob die reflektierte DB **FKs über Schema-Grenzen** hat — beantwortet endgültig, ob die volle Cross-Schema-Stufe (AP-57) überhaupt nötig ist. Kleinste sinnvolle Scheibe.

**Was ich tun würde:**
- `core/model.py::ForeignKey` um optionales `referred_schema: str = ""` erweitern (rückwärtskompatibel, Default leer).
- `core/loaders/sqlalchemy_loader.py:70`: `fk.get("referred_schema")` **mitnehmen** statt zu verwerfen (SQLAlchemy liefert es bereits im FK-Dict; aktuell ignoriert).
- `core/`-pure Funktion `cross_schema_fks(schema_objs) -> tuple[...]`: meldet je FK, dessen `referred_schema` ≠ dem Schema der haltenden Tabelle ist (Kantenliste `a.tab.col → x.tab.col`).
- Read-only Anzeige: entweder kleiner Block im Schema-/Analyzer-Bereich oder ein eigener, sehr schlanker Endpoint `/api/cross_schema_check`. **Nur Anzeige**, kein Join.
- **Tests:** pytest gegen konstruierte `Schema`/`ForeignKey`-Objekte mit gesetztem `referred_schema` (kein echtes DB-Backend nötig) + optional skip-guarded gegen ein Multi-Schema-Postgres (Podman).

**Nicht-Scope:** kein Join über Schemas, kein Multi-Schema-Reflection-Merge.
**Aufwand:** **S** (klein). **Abhängigkeit:** keine. **Nutzen:** Entscheidungs-Gate für AP-57.

---

### AP-55 — Implied-FK-Schärfung für Cross-Produkt-Linkerkennung

**Ziel:** **Logische** Links (gemeinsame IDs ohne FK-Constraint) zwischen Tabellen — auch zwischen Produkten/Schemas — über **Namenskonventionen** auffindbar machen. Der eigentliche Hebel für die HCMX-Cross-Produkt-Beziehungen.

**Was ich tun würde:**
- `core/implied.py` lesen und die bestehende Heuristik (`include_implied`, Spaltenname-vs-PK-Matching) verstehen.
- Erweitern um **konfigurierbare Muster**: `<Entity>ID`, `<Entity>_ID`, `<Entity>UUID`, gängige Präfix-/Suffix-Konventionen; toleranter gegen unterschiedliche Schreibweisen zwischen Produkten.
- **Confidence-Score** je implizierter Kante; in der UI klar als „heuristisch, kein FK" markieren (bestehende implied-Kanten-Darstellung im Graph nutzen).
- Falls AP-54 schon Schema-getaggte Tabellen liefert: implied-Matching **schema-übergreifend** erlauben.
- **Tests:** pytest gegen konstruierte Schemas mit verschiedenen Namenskonventionen (Treffer + bewusste Nicht-Treffer, um False-Positives zu begrenzen).

**Nicht-Scope:** kein automatisches „Anlegen" von FKs; reine Vorschlags-/Visualisierungs-Ebene.
**Aufwand:** **M** (mittel). **Abhängigkeit:** profitiert von AP-54 (Schema-Tagging), aber nicht zwingend.

---

### AP-56 — Entitäts-Hülle / Subset-Export (transitive FK-Closure)

**Ziel:** „Gib mir Zeile X **und alle referenziell abhängigen Zeilen** (Eltern via FK nach oben, Kinder via FK nach unten, rekursiv)" → **referenziell konsistenter Export-Datensatz**. Das ist klassisches **Database-Subsetting** (vgl. Jailer) und der größte echte Mehrwert für „sauberer Export".

**Was ich tun würde:**
- Neues `core/subset.py`: ausgehend von `(Tabelle, Filter/PK-Wert)` über den bestehenden FK-Graphen (`core/graph.py`) die **transitive Hülle** berechnen — Eltern *und* Kinder, mit **Zyklus-Schutz** und **Tiefenlimit**.
- **Read-only:** erzeugt eine **Sequenz von SELECTs** (pro Tabelle, mit `IN`-Listen der gesammelten Schlüssel) bzw. ein Export-Skript; Ausgabe als SQL/CSV/JSON. **Kein** Schreiben, kein DELETE/anonymisieren (das macht die ETL-Schicht).
- Graph-Wiederverwendung: derselbe FK-Graph wie der Pathfinder, aber die Operation ist **„Closure" statt „Pfad A→B"**.
- **UI:** neuer Modus „Entität exportieren" — Start-Tabelle + Filter (z. B. `SubscriptionID = 123`) → **Vorschau** der einbezogenen Tabellen + Zeilenzahlen → Export.
- **Tests:** pytest gegen die Demo-CMDB (Closure-Korrektheit, Zyklen, Tiefenlimit, Eltern+Kinder).

**Nicht-Scope:** kein Schreiben in die Ziel-DB, keine Transformation/Anonymisierung (bewusst der ETL-Schicht überlassen).
**Aufwand:** **L** (groß) — eigenes Modul + UI. **Abhängigkeit:** keine (nutzt den bestehenden Graphen).

---

### AP-57 — Cross-Schema-Joins (volle Stufe) — **zurückgestellt / bedingt**

**Ziel:** Tabellen aus **mehreren Schemas in EINEM Join-SELECT** verbinden (per-Tabelle-Schema-Qualifizierung, `Sales.Customer` JOIN `Production.Product`).

**Trigger:** **Nur bauen, wenn AP-54 echte Cross-Schema-FKs in der Ziel-DB nachweist.** HCMX-Erwartung: nein → dann entfällt das AP.

**Was ich tun würde (mentales Modell aus der AdventureWorks-Diskussion):**
- **Model:** `Table.schema`, `ForeignKey.referred_schema` (Identität per **(Schema, Tabelle)** statt bloßem Namen — sonst kollidieren z. B. zwei `Customer`).
- **Loader:** Multi-Schema-Reflection + Merge zu **einem** Graphen.
- **Graph/Pathfinder:** Knoten-Identität (Schema, Tabelle); Cross-Schema-FK ist graphentheoretisch nur eine Kante wie jede andere.
- **sqlgen:** **per-Tabelle**-Schema statt **einem globalen** `schema`-String (heute: `generate_sql(…, schema="X")` qualifiziert *alle* Tabellen gleich — `core/sqlgen.py:159+`).
- **Route/UI:** Mehrfach-Schema-Auswahl statt Einzel-Dropdown.
- **Tests:** real nur gegen echtes **Postgres/MSSQL/Oracle** (Podman) verifizierbar — SQLite kann die Konstellation nicht abbilden.

**Aufwand:** **XL** (sehr groß) — Datenmodell-Umbau quer durch Model/Loader/Graph/Pathfinder/sqlgen/Route/UI. **Abhängigkeit:** AP-54 (Gate).

## 4. Empfohlene Reihenfolge für die Migration

1. **AP-54** bauen *oder* die fertige Diagnose-Query (Oracle/MSSQL/PG) gegen die HCMX-DB laufen lassen → Faktenlage Cross-Schema-FK.
2. Parallel die Alt-DB **pro Produkt-Schema** mit dem heutigen Stand (AP-52) erkunden, Export-SELECTs je Entität generieren.
3. **AP-56** (Subset-Export) bauen, sobald manuelles Slicing zu mühsam wird — größter Hebel für referenziell sauberen Export.
4. **AP-55** (implied-FK) für die Cross-Produkt-Verknüpfung über Namens-IDs.
5. **AP-57** nur, falls AP-54 echte Cross-Schema-FKs findet.

> Greenfield-Hinweis: Das CSA/OO-Schema ist ein **Implementierungsdetail eines Produkts, das abgelöst wird**. Nicht die *Struktur* übernehmen, sondern die **Geschäftsentitäten** (Katalog-Items, Subscriptions, Owner, deployte Ressourcen + Zustand) extrahieren und auf das neue, frei gestaltete Modell mappen. Cross-Produkt-Stitch passiert in der **ETL-/Staging-Schicht** über fachliche Keys.
