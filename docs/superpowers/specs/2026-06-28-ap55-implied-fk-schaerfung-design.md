# AP-55 — Implied-FK-Schärfung — Design

**Datum:** 2026-06-28
**Status:** Spec (genehmigt im Brainstorming)
**Aufwand:** M
**Vorgänger-Konzept:** `docs/concepts/2026-06-28-legacy-db-migration-tooling.md` (Abschnitt AP-55)

## Ziel

**Logische** Links zwischen Tabellen — gemeinsame IDs ohne FK-Constraint — über **Namenskonventionen** auffindbar machen. Der eigentliche Hebel für die HCMX-Cross-Produkt-Beziehungen, die als fachliche IDs (nicht als FKs) modelliert sind.

Heute matcht `core/implied.py` nur **exakt** „Spaltenname == Single-Column-PK-Name". Der klassische Legacy-Fall `bestellung.kunde_id → Kunde(id)` (Namen nicht identisch) wird **nicht** gefunden. AP-55 schließt diese Lücke per Suffix→Tabellenname-Matching mit Normalisierung und staffelt jeden Treffer über einen **Confidence-Score**.

## Code-Befunde (Ist-Stand verifiziert vor Planung)

1. **Heutige Heuristik ist exakt-Name-only** (`core/implied.py:48–56`): Spalte matcht nur, wenn ihr Name identisch zu einem Single-Column-PK-Namen einer anderen Tabelle ist.
2. **Cross-Schema-implied ist blockiert:** `Table` (`core/model.py:48`) trägt **kein** Schema-Tag; eine `Schema`-Reflection enthält nur die Tabellen *eines* Schemas (AP-52, einzeln wählbar). AP-54 hat `ref_schema` nur an `ForeignKey` gehängt, nicht an `Table`. Schema-übergreifendes implied-Matching braucht Multi-Schema-Reflection — dieselbe ungebaute Voraussetzung wie AP-57.
3. **AP-54-Diagnose-Muster** (`web/routes.py:150` + `web/static/js/app.js:223–230`): `/api/schema` berechnet die Diagnose serverseitig und shippt sie als JSON-Feld; das Info-Panel rendert eine `<ul class="objlist">` + Count-Zeile. AP-55 schließt exakt daran an.

## Real baubare Scheibe

Stärkere Namensmuster-Heuristik + diskreter Confidence-Score + Info-Panel-Liste — **innerhalb des einen reflektierten Schemas**. Cross-Schema-implied wird dokumentierter Carryover (AP-57-Gate).

## 1. Datenmodell (`core/implied.py`)

`ImpliedFK` bekommt zwei **rückwärtskompatible** Felder (frozen dataclass, Defaults → `build_graph` bleibt unberührt, da es nur `table/column/ref_table/ref_column` liest):

```python
@dataclass(frozen=True)
class ImpliedFK:
    table: str
    column: str
    ref_table: str
    ref_column: str
    confidence: str = "hoch"            # "hoch" | "mittel" | "niedrig"
    reason: str = "exakter PK-Name"     # kurzer Match-Grund (DE)
```

Normalisierung als **Modul-Konstanten** (das ist die „konfigurierbare Muster"-Anforderung des Konzepts — realisiert als benannte, dokumentierte Konstanten, **kein** Runtime-Config-Format; bewusster Scope-Cut, YAGNI für ein Per-DB-Reverse-Eng-Tool):

- `_ID_SUFFIXES = ("id", "uuid", "guid")` — erkannte ID-Endungen
- `_normalize(name)` → lowercase + nur alphanumerisch (`Customer_ID` / `customerId` / `CUSTOMER_ID` → `customerid`)
- Singular/Plural: Tabellen-Stamm zusätzlich ohne `s`/`es`-Endung vergleichen

## 2. Matching-Algorithmus + Confidence-Stufen

Bestehende Guards bleiben: `A ≠ B`, kein bereits **deklarierter** FK auf `(column → target)`, **kompatibler Basistyp** (`_base_type`), Ziel-PK ist **Single-Column**.

Pro Spalte `c` in Tabelle `A` werden die Strategien in dieser Reihenfolge probiert; die **erste** treffende Stufe gewinnt (keine Doppel-Kanten für dieselbe `(A.c → B)`):

| # | Strategie | Bedingung | Confidence | reason |
|---|---|---|---|---|
| 1 | **Exakter PK-Name** (heutiges Verhalten) | `c.name` == Single-Column-PK-Name von `B` | **hoch** | `exakter PK-Name` |
| 2 | **Suffix → Tabellenname, konventioneller PK** | `c` endet auf ID-Suffix → Stamm `s`; `_normalize(B.name)` == `s`; `B`-PK normalisiert ∈ {`id`, `uuid`, `guid`, `s`+`id`} | **mittel** | `Suffix→Tabelle (kunde_id→Kunde)` |
| 3 | **Wie 2, aber Plural/Singular-Normalisierung nötig** | Stamm matcht `B.name` erst nach `s`/`es`-Abgleich | **niedrig** | `Suffix→Tabelle (Plural)` |

**False-Positive-Bremsen:**

- Stamm muss **≥ 2 Zeichen** sein (sonst matcht `id` jede Tabelle).
- Spalte muss tatsächlich auf ein bekanntes ID-Suffix enden (Strategie 2/3), und der **Ziel-PK** muss eine erkannte generische ID-Form sein — verhindert, dass beliebige gleichnamige Spalten matchen.
- Ergebnis **deterministisch sortiert** nach `(table, column, ref_table)` → stabile Tests + UI.

**Ambiguität:** Matcht ein Stamm mehrere Tabellen, gewinnt die höhere Stufe (exakt-normalisiert vor Plural). Bei echtem Gleichstand auf derselben Stufe (selten) werden beide Kanten emittiert und sind damit ehrlich als mehrdeutig sichtbar.

**Beispiele:**

- `bestellung.kunde_id` → `Kunde(id)` → **mittel**
- `Order.CustomerID` → `Customer(CustomerID)` → **hoch** (Strategie 1)
- `order.customer_id` → `Customers(id)` → **niedrig** (Plural)
- `order.customer_id` → `Customer(name)` → **kein Treffer** (PK keine generische ID)

## 3. Route + Info-Panel-UI

**Server (`web/routes.py`, `/api/schema`):** analog zu `cross_schema_fks` ein neues Feld in die JSON-Antwort:

```python
implied_fks=[
    {"from_table": i.table, "column": i.column,
     "to_table": i.ref_table, "to_column": i.ref_column,
     "confidence": i.confidence, "reason": i.reason}
    for i in find_implied_fks(schema)
],
```

Wird **immer** mitgeliefert (Diagnose, wie die Cross-Schema-Liste) — unabhängig von der Graph-Checkbox `include_implied`. Der Graph-Pfad (`build_graph(..., include_implied)`) bleibt **unverändert** (boolesche Kanten) → minimaler Blast-Radius.

**Frontend (`web/static/js/app.js`, Info-Panel):** eine Count-Zeile + ein `objlist`-Block neben dem bestehenden Cross-Schema-Block:

```
Implizite FKs (geraten)   7
```
```
Implizite (geratene) Foreign Keys
• bestellung.kunde_id → Kunde.id   [mittel]  · Suffix→Tabelle (kunde_id→Kunde)
• order.customer_id → Customers.id [niedrig] · Suffix→Tabelle (Plural)
```

Die Stufe als kleines Badge (`[hoch]`/`[mittel]`/`[niedrig]`), klar beschriftet „geraten, kein FK". Bestehender Hinweis-Satz zur Checkbox bleibt.

## 4. Tests

**`tests/test_implied.py`** (pytest, konstruierte `Schema`-Objekte, kein DB-Backend):

- Strategie 1: exakter PK-Name → `confidence == "hoch"`
- Strategie 2: `kunde_id` → `Kunde(id)` → `"mittel"`
- Strategie 3: `customer_id` → `Customers(id)` (Plural) → `"niedrig"`
- **Bewusste Nicht-Treffer:** inkompatibler Typ; Stamm < 2 Zeichen; Ziel-PK keine generische ID; bereits deklarierter FK; Self-Tabelle; Suffix fehlt
- Determinismus: Sortier-Reihenfolge stabil
- Rückwärtskompat: `build_graph(..., include_implied=True)` baut weiter Kanten (Default-Felder)

**Route-Test (`tests/test_index_page.py` o. ä.):** `/api/schema` liefert `implied_fks` mit `confidence`/`reason`.

**Browser-Smoke (Playwright, System-python3):** Demo-SQLite verbinden → Info-Tab → die `implied_fks`-Liste rendert mit Badge (gerenderte Eigenschaft prüfen). App-Neustart vor Smoke (Route-/Template-Änderung).

## 5. Scope-Cuts (bewusst)

- **Cross-Schema-implied:** Carryover (blockiert auf Multi-Schema-Reflection, AP-57-Gate).
- **Konfigurierbare Muster:** als Code-Konstanten realisiert, **kein** Runtime-Config-Format (YAGNI).
- **Graph-Kanten-Styling nach Stufe:** nicht gebaut (nur Info-Panel-Liste).
- **Auto-Anlegen von FKs:** nie — reine Vorschlags-/Diagnose-Ebene.

## 6. Release / Doku (nach Implementierung)

- `sync_version.py --minor` (Feature) + icon-rail `APP_VERSION`/`TEST_COUNT`
- Roadmap/Board/Gantt: AP-55 Offen → Erledigt (jedes Item namentlich)
- CLAUDE.md „Bekannte Einschränkungen": implied-FK-Schärfung-Block ergänzen
- zensical-Mirror + gh-pages-Deploy
- Deutsch / NO-CDN / SDD-Final-Review nicht weglassen
