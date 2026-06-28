# Outer Joins & Waisen (LEFT/RIGHT/FULL)

Im SQL-Builder lässt sich **pro Join-Station** der Typ wählen — **INNER**
(Standard), **LEFT**, **RIGHT**, **FULL**. Outer Joins behalten Zeilen einer
Seite **auch ohne Partner** auf der anderen Seite (die fehlenden Spalten werden
`NULL`). Solche unverknüpften Zeilen heißen hier **Waisen**.

Neben jeder Join-Station zeigt ein **Waisen-Chip** (z. B. `⚠ LEFT/FULL`), welche
Join-Typen an *dieser* Stelle das Ergebnis **tatsächlich verändern**. Diese Seite
erklärt, was die Typen bewirken — und einen Stolperstein, der leicht verwirrt.

---

## Was die Typen bewirken

Pfad `A → B` (A = FROM/Treiber-Tabelle, B wird gejoint, Bedingung `A.x = B.y`):

| Typ | Behält … | Zeigt Waisen … |
|---|---|---|
| **INNER** | nur Zeilen mit Treffer auf **beiden** Seiten | keine |
| **LEFT** | **alle A-Zeilen**, auch ohne B-Treffer | A-Zeilen ohne B (B-Spalten `NULL`) |
| **RIGHT** | **alle B-Zeilen**, auch ohne A-Treffer | B-Zeilen ohne A |
| **FULL** | alle A- **und** alle B-Zeilen | beide Seiten |

In der **Ergebnistabelle** werden `NULL`-Zellen hervorgehoben — so fallen die
Waisen-Zeilen sofort auf.

---

## Der Stolperstein: LEFT ändert manchmal *nichts*

> **Beobachtung:** „Ich stelle den 2. Join auf **LEFT**, der Chip sagte vorher
> Waisen — aber die Tabelle unten ändert sich nicht."

Das ist **kein Fehler**, sondern echte SQL-Semantik. Ob ein Outer Join Waisen
ins Ergebnis bringt, hängt vom **ganzen Pfad** ab, nicht nur vom einzelnen Join.
Zwei Gründe lassen LEFT/RIGHT wirkungslos bleiben:

### 1. Die Waise ist von der FROM-Tabelle aus unerreichbar

Beispiel-Pfad **`Cluster → Datacenter → Network`**:

```sql
SELECT "Cluster"."ClusterID", "Network"."NetworkID"
FROM "Cluster"
JOIN "Datacenter" ON "Cluster"."DatacenterID" = "Datacenter"."DatacenterID"
LEFT JOIN "Network" ON "Datacenter"."DatacenterID" = "Network"."DatacenterID"
```

In der Demo-CMDB gibt es ein **`Datacenter` „DC-Empty" ohne Network** — isoliert
betrachtet also eine Waise für `Datacenter → Network`. Trotzdem ändert `LEFT`
hier **nichts**: Das Statement startet bei `FROM "Cluster"`, und **kein Cluster
zeigt auf DC-Empty**. Die akkumulierte linke Seite (`Cluster ⋈ Datacenter`)
enthält DC-Empty also gar nicht — `LEFT JOIN "Network"` hat keine Zeile, der er
ein `NULL`-Network anhängen könnte.

### 2. Nachfolgende INNER-Joins filtern die Waisen wieder heraus

Setzt man in einer **Kette** einen mittleren Join auf LEFT, aber die folgenden
bleiben INNER, verschwinden die gerade erzeugten `NULL`-Zeilen sofort wieder:
Der nächste `JOIN … ON <vorige>.spalte = …` findet auf `NULL` keinen Treffer und
wirft die Zeile raus. **Damit eine LEFT-Waise im Endergebnis ankommt, müssen die
nachfolgenden Joins sie ebenfalls behalten** (auch LEFT/FULL).

---

## Wie der Waisen-Chip das berücksichtigt

Der Chip prüft **nicht** den Join isoliert, sondern **zählt das echte Ergebnis**:
für jede Join-Station vergleicht er die Zeilenzahl mit `LEFT`/`RIGHT`/`FULL`
gegen `INNER` (die übrigen Stationen auf ihrem aktuellen Stand). Er erscheint
**nur**, wenn der Typ die Zeilenzahl **wirklich** ändert. So sind **Chip und
Tabelle immer konsistent**:

| Pfad | Chip an der Station | LEFT-Wirkung im Ergebnis |
|---|---|---|
| `Cluster → Datacenter → Network` | **keiner** | 16 → 16 Zeilen (keine Änderung) |
| `Cluster → Datastore` (direkt) | `⚠ LEFT/FULL` | 6 → 8 Zeilen (EMPTY-Cluster mit `NULL`) |

---

## So machst du Waisen sichtbar

1. **Pfad wählen, auf dem die Waise erreichbar ist.** Willst du Cluster ohne
   Datastore sehen, nimm den direkten Pfad `Cluster → Datastore` (LEFT) — nicht
   einen Umweg, auf dem die Cluster bereits über andere Joins „gefüllt" werden.
2. **In einer Kette nachfolgende Joins ebenfalls auf LEFT/FULL** setzen, damit die
   `NULL`-Zeilen bis ins Endergebnis durchlaufen.
3. **Auf den Chip achten:** Steht an einer Station kein Chip, ändert dort *kein*
   Outer-Join-Typ das Ergebnis — Umschalten ist dann wirkungslos (korrekt so).

> **Merksatz:** Ein Outer Join zeigt nur die Waisen, die (a) von der FROM-Tabelle
> aus **erreichbar** sind und (b) von **allen nachfolgenden** Joins behalten werden.
> Der Waisen-Chip nimmt dir diese Prüfung ab — er zählt das echte Ergebnis.
