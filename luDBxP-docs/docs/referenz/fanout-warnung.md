# Fan-out-Warnung (1-N)

Unter manchen Join-Pfaden zeigt der SQL-Builder eine gelbe Hinweiszeile:

> ⚠ Ast „Datastore" ist 1-N (absteigend) — kann Zeilen vervielfachen.

Diese Warnung ist **nicht blockierend** — das erzeugte SQL ist syntaktisch
korrekt und läuft. Sie sagt nur: *Die Zeilenzahl im Ergebnis spiegelt keine
echte 1:1-Beziehung wider, sondern ein Vielfaches.* Diese Seite erklärt das
Wann und Warum an durchgerechneten Beispielen aus der Demo-CMDB.

---

## FK-Richtung: Eltern-Seite (1) und Kind-Seite (N)

Jede Fremdschlüssel-Beziehung hat eine Richtung. Die Tabelle, die den FK
**hält**, ist die **Kind-Seite (N, „viele")**; die Tabelle, auf die er
**zeigt**, ist die **Eltern-Seite (1, „eins")**.

In der Demo-CMDB gilt z. B.:

| FK (Kind hält) | zeigt auf (Eltern) | Bedeutung |
|---|---|---|
| `Host.ClusterID` | `Cluster.ClusterID` | viele Hosts : ein Cluster |
| `Datastore.ClusterID` | `Cluster.ClusterID` | viele Datastores : ein Cluster |
| `Cluster.DatacenterID` | `Datacenter.DatacenterID` | viele Cluster : ein Datacenter |
| `VirtualMachine.HostID` | `Host.HostID` | viele VMs : ein Host |

Ein Join-Schritt kann diese Beziehung in **zwei** Richtungen durchlaufen:

- **Aufsteigend (N → 1):** von der Kind- zur Eltern-Seite — z. B. `Host → Cluster`.
  Viele Kinder fallen auf **eine** Eltern-Zeile zusammen. Das *reduziert* eher,
  vervielfacht nie. **Keine Warnung.**
- **Absteigend (1 → N):** von der Eltern- zur Kind-Seite — z. B. `Cluster → Datastore`.
  Eine Eltern-Zeile „explodiert" in **mehrere** Kind-Zeilen. **Das ist der
  Auslöser der Warnung** — und zwar pro absteigendem Ast einzeln.

> Technisch: Der Pfadfinder markiert einen Schritt `a → b` als absteigend
> (`to_many`), wenn **`b` den Fremdschlüssel hält**. Genau dann gibt es eine
> Warnungszeile, die die Kind-Tabelle (`b`) benennt.

---

## Beispiel 1 — ein absteigender Ast

Pfad **`Host → Cluster → Datastore`** (das Beispiel aus dem Screenshot):

```sql
SELECT "Host"."ClusterID", "Datastore"."ClusterID"
FROM "Host"
JOIN "Cluster"   ON "Host"."ClusterID"    = "Cluster"."ClusterID"
JOIN "Datastore" ON "Cluster"."ClusterID" = "Datastore"."ClusterID"
```

- `Host → Cluster` ist **aufsteigend** (Host hält den FK) → keine Warnung.
- `Cluster → Datastore` ist **absteigend** (Datastore hält den FK) → ⚠ Warnung auf „Datastore".

### Mit Zahlen

**Cluster** — eine Zeile:

| ClusterID |
|---|
| C1 |

**Host** — 2 Hosts in C1:

| HostID | ClusterID |
|---|---|
| H1 | C1 |
| H2 | C1 |

**Datastore** — 3 Datastores in C1:

| DsID | ClusterID |
|---|---|
| D1 | C1 |
| D2 | C1 |
| D3 | C1 |

Der JOIN paart **jede** Host-Zeile mit **jeder** Datastore-Zeile desselben
Clusters:

| Host | Cluster | Datastore |
|---|---|---|
| H1 | C1 | D1 |
| H1 | C1 | D2 |
| H1 | C1 | D3 |
| H2 | C1 | D1 |
| H2 | C1 | D2 |
| H2 | C1 | D3 |

**2 Hosts × 3 Datastores = 6 Zeilen** — obwohl es real nur 2 Hosts und 3
Datastores gibt. Keine dieser Zeilen drückt eine echte „Host-hat-Datastore"-
Beziehung aus: die existiert im Schema gar nicht direkt. Das Tool verbindet
beide nur über den **gemeinsamen Cluster**, und dort entsteht je Cluster ein
**kartesisches Produkt**. Bei 50 Hosts und 40 Datastores pro Cluster wären das
schon 2 000 Zeilen pro Cluster.

---

## Beispiel 2 — mehrere absteigende Äste multiplizieren sich

Die Warnung erscheint **pro absteigendem Schritt**. Ein Pfad mit zwei solchen
Schritten zeigt zwei Zeilen, z. B.:

> ⚠ Ast „Network" ist 1-N (absteigend) — kann Zeilen vervielfachen.
> ⚠ Ast „VirtualMachine" ist 1-N (absteigend) — kann Zeilen vervielfachen.

Pfad **`Datacenter → Network → VirtualMachine → Host → Cluster`**:

- `Datacenter → Network` — absteigend (Network hält FK) → ⚠
- `Network → VirtualMachine` — absteigend (VM hält FK) → ⚠
- `VirtualMachine → Host` — **aufsteigend** (VM hält FK, wir gehen zur Eltern-Seite) → ok
- `Host → Cluster` — **aufsteigend** → ok

Wenn an **einem** Datacenter z. B. 5 Networks hängen und an jedem Network 20 VMs,
liefert der Pfad pro Datacenter `5 × 20 = 100` Zeilen — die absteigenden Äste
multiplizieren ihre Mengen miteinander. Hängen mehrere absteigende Äste am
**selben** Knoten (ein Stern), multiplizieren sich auch deren Mengen
gegenseitig (quasi-kartesisch).

---

## Beispiel 3 — längeren Pfad erkennen und verkürzen oder filtern

Manchmal wählt der Builder einen **längeren** Pfad mit einem 1-N-Schritt, obwohl
ein kürzerer, warnungsfreier daneben in der Liste steht. Klassiker:

```
Network 1-N VirtualMachine N-1 Host N-1 Cluster N-1 Datacenter
⚠ Ast „VirtualMachine" ist 1-N (absteigend) — kann Zeilen vervielfachen.
```
```sql
SELECT "Network"."NetworkID", "Datacenter"."DatacenterID"
FROM "Network"
JOIN "VirtualMachine" ON "Network"."NetworkID" = "VirtualMachine"."NetworkID"
JOIN "Host"           ON "VirtualMachine"."HostID" = "Host"."HostID"
JOIN "Cluster"        ON "Host"."ClusterID" = "Cluster"."ClusterID"
JOIN "Datacenter"     ON "Cluster"."DatacenterID" = "Datacenter"."DatacenterID"
```

**So liest du ihn:** Der einzige absteigende Schritt ist `Network → VirtualMachine`
— dort vervielfacht es sich (jede Network-Zeile mal Anzahl ihrer VMs). Ab
`VirtualMachine` aufwärts ist alles N-1 (jede VM hat genau ein Host/Cluster/
Datacenter), also keine weitere Multiplikation. **Ergebnis:** eine Zeile **je VM**
(die ein Netz hat), die `Datacenter`-Spalte wiederholt sich — *nicht* eine Zeile je
Network.

**Zwei Auswege:**

1. **Kette verkürzen (bevorzugt).** `Network` und `Datacenter` sind **direkt**
   verbunden (`Network.DatacenterID → Datacenter`). Der erste Kandidat in der Liste
   ist `Network → Datacenter` (rein N-1, **keine** Warnung). Brauchst du
   `VirtualMachine` für deine Frage gar nicht, nimm den kürzeren Pfad — der VM-Umweg
   erzeugt nur Fan-out ohne Mehrwert.
2. **Expliziten Filter setzen — auf die „Viele"-Tabelle.** Der Filter muss die
   Tabelle **unmittelbar hinter der 1-N-Kante** (`VirtualMachine`) auf ≤1 Zeile je
   Network eindampfen, sonst löst er das Fan-out nicht auf. Ein Filter auf `Host`,
   `Cluster` oder `Datacenter` (den N-1-Schwanz) **hilft nicht** gegen die
   Multiplikation — er schränkt nur ein, welche Gruppen erscheinen. Willst du eine
   Übersicht je Network, **aggregiere** statt zu filtern:
   `COUNT(DISTINCT "VirtualMachine"."VMID") … GROUP BY "Network"."NetworkID"`.

> **Faustregel beim Anblick einer 1-N-Warnung:** Zuerst fragen *„brauche ich den
> absteigenden Ast überhaupt — oder gibt es einen kürzeren Pfad ohne ihn?"*; erst
> wenn ja, einen Filter auf genau die multiplizierte Tabelle setzen (oder
> aggregieren). Mit dem **⇄-Knopf** (Start/Ziel tauschen) prüfst du schnell, ob die
> umgekehrte Richtung hinauf zeigt und damit warnungsfrei ist.

---

## Warum in der Demo-CMDB fast *jeder* Pfad warnt

Die Demo-CMDB ist ein **Stern (Hub-and-Spoke)** um `Datacenter` und `Cluster`:
fast alle übrigen Tabellen sind Kinder dieser beiden Hubs (`Cluster`, `Host`,
`Network`, `Datastore` hängen unter `Datacenter`; `Host`, `Datastore` unter
`Cluster`; `VirtualMachine` unter `Host`). Sobald ein Pfad an einem Hub
**vorbei nach unten** in einen Spoke führt, enthält er einen absteigenden
Schritt — und bekommt eine Warnung. Deshalb ist im SQL-Builder an praktisch
jedem Kandidatenpfad eine ⚠-Zeile zu sehen. Das ist **erwartetes Verhalten**,
kein Defekt: Sterntopologien erzeugen fast zwangsläufig Fan-out, sobald man
zwei Spokes über ihren gemeinsamen Hub verbindet.

---

## Warum beide Richtungen warnen — und eines trotzdem N-1 ist

Ein häufiger Stolperstein: Man wählt **Start Datastore → Ziel Host**, sieht eine
Warnung, dreht auf **Start Host → Ziel Datastore** um — und es warnt *immer noch*.
Müsste beim Umdrehen nicht eine der beiden Richtungen N-1 (sicher) werden?

**Antwort: Eines *ist* N-1 — in jedem Pfad.** Es wird nur nicht beschriftet,
weil die Warnung ausschließlich den riskanten, absteigenden Schritt markiert.
Der kürzeste Pfad zwischen den beiden lautet in beiden Richtungen
`… → Cluster → …`:

| Richtung | Schritt 1 | Schritt 2 |
|---|---|---|
| Datastore → Host | `Datastore → Cluster` = **N-1** (sicher) | `Cluster → Host` = **1-N** ⚠ |
| Host → Datastore | `Host → Cluster` = **N-1** (sicher) | `Cluster → Datastore` = **1-N** ⚠ |

In **jedem** Pfad ist also genau ein Schritt aufsteigend (N-1) und einer
absteigend (1-N). Es ist **nicht** „alles 1-N" — der N-1-Teil schweigt nur,
weil er ungefährlich ist.

Dass in *beiden* Richtungen eine Warnung erscheint, liegt daran, dass
`Datastore` und `Host` **Geschwister** unter dem gemeinsamen Hub `Cluster` sind
(beide halten einen FK auf `Cluster`, keiner auf den anderen). Um zwei
Geschwister zu verbinden, muss man **immer** zum Hub hoch (N-1, sicher) und dann
ins andere Geschwister hinab (1-N, Fan-out). Beim Umdrehen **wandert** die
Warnung deshalb nur auf die andere Tabelle — sie verschwindet nicht.

> **Wann das Umdrehen die Warnung *wegnimmt*:** nur bei einer direkten
> Eltern-Kind-Kante ohne Hub dazwischen. `Host → Cluster` (Ziel = Eltern) ist
> rein N-1 → keine Warnung; `Cluster → Host` (Ziel = Kind) ist 1-N → Warnung.
> Da kippt es sauber, weil kein gemeinsamer Hub im Spiel ist.

Im SQL-Builder ist diese Mischung direkt ablesbar: **jeder Join trägt einen
Richtungs-Chip** — grün `N-1` (sicher) oder gelb `1-N` (Fan-out) — sowohl in
der Pfad-Liste als auch als Label an der hervorgehobenen Kante im Schema-Graph.

## Was tun?

Die Warnung heißt **nicht** „falsches SQL", sondern „prüfe, ob die Zeilenzahl
deiner Absicht entspricht". Je nach Ziel:

1. **Existenz/Zugehörigkeit gefragt** („welche Datastores liegen im Cluster von
   Host H1?") → den absteigenden Zweig getrennt abfragen, nicht zwei Spokes
   über den Hub kreuzen.
2. **Zählen statt Auflisten** → `COUNT(DISTINCT "Datastore"."DsID")` mit
   `GROUP BY "Host"."HostID"`, damit das Produkt nicht roh durchschlägt.
3. **Nur die nächste Eltern-Ebene nötig** → einen kürzeren Pfad wählen, der
   ausschließlich aufsteigt (N → 1), falls die alternativen k-Pfade einen
   solchen anbieten.
4. **Kreuzprodukt ist gewollt** (z. B. „jede Host-Datastore-Kombination im
   Cluster") → alles in Ordnung, Warnung bewusst ignorieren.

> **Merksatz:** Aufsteigen (N → 1) ist immer sicher. Absteigen (1 → N)
> vervielfacht. Verbindet ein Pfad zwei Kind-Tabellen über einen gemeinsamen
> Hub, entsteht je Hub-Zeile ein kartesisches Produkt der beiden Kind-Mengen.
