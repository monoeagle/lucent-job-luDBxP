# Lucent DB Explorer — Design (v1)

- **Status:** freigegeben (Brainstorming abgeschlossen 2026-06-25)
- **Slug/Ordner:** `lucent-job-luDBxP`
- **`name`:** `luDBxP`
- **`display_name`:** „Lucent DB Explorer"
- **Typ:** Flask-Web-App (`lucent-job-*`), abgeleitet aus `claude-architecture-template` + `-mpp`-Flask-Linie
- **Port (vorläufig):** 5057 — vor erstem Hub-Start gegen die Hub-Registry prüfen

---

## 1. Zweck & Scope

Ein Flask-Web-Tool, das aus einem reflektierten Datenbank-Schema einen **Foreign-Key-Graphen** baut.
Der Benutzer wählt eine **Start-Spalte → Ziel-Spalte** plus optionale **Filterbedingungen**
(`tabelle.spalte = wert`). Das Tool berechnet den kürzesten Join-Pfad, webt die Filter-Tabellen
ein und generiert das passende `SELECT … JOIN … WHERE` als **read-only SQL-Text**.

Die Perspektive ist bewusst „Wie komme ich von Objekt A zu Objekt B?", nicht „Wie sieht mein
Datenmodell aus?" (Abgrenzung zu SchemaSpy).

### In Scope (v1)
- FK-Graph aus Live-DB-Reflection (SQLAlchemy)
- Join-Pfad-Builder (Start → Ziel)
- Filterobjekte (WHERE-Bedingungen über beliebige erreichbare Tabellen)
- SQL-Generierung (read-only Textausgabe)
- *k*-kürzeste-Pfade mit deterministischem Tie-Break

### Explizit NICHT in Scope (spätere Iterationen)
- Grafische Graph-Darstellung (Cytoscape.js / React Flow) — Idee 3
- LLM-/Text2SQL-Unterstützung und LLM-Pfad-Ranking — Idee 4
- Ausführung von Queries / Ergebnisvorschau / Result-Grid
- Loader für SchemaSpy, manuelles JSON/YAML, SQL-DDL (nur Interface-Stubs)
- MySQL / MSSQL (v1 nur SQLite + Postgres)

---

## 2. Architektur & Projektstruktur

`lucent-job-*` Flask-Web-App. **Nicht** PyQt6-Desktop (das `lucent-app-python.pattern` gilt hier
nur sinngemäß für Querschnitt: `config.py`, `strings.py`, `core/settings.py`, `core/log.py`,
`sync_version.py`, `run.sh`, Test-Setup). Alle Frontend-Libs werden **lokal gebundelt** — keine CDNs
(globale Konvention).

```
lucent-job-luDBxP/
├── app.py                  # Flask entry (create_app-Factory)
├── config.py               # Konstanten, Pfade, APP_VERSION (nur via sync_version.py)
├── config.json             # Runtime-Settings (JSON, user-editierbar)
├── strings.py              # i18n DE/EN via t(key)
├── core/
│   ├── settings.py         # JSON-Config Persistence (Singleton)
│   ├── log.py              # Unified Logging
│   ├── model.py            # Dataclasses: Schema, Table, Column, FKEdge
│   ├── schema_loader.py    # ABC: SchemaLoader.load() -> Schema
│   ├── loaders/
│   │   ├── sqlalchemy_loader.py   # v1 voll: SQLite + Postgres Reflection
│   │   ├── manual_loader.py       # Stub (NotImplementedError, später)
│   │   ├── schemaspy_loader.py    # Stub
│   │   └── ddl_loader.py          # Stub
│   ├── graph.py            # NetworkX-Graph aus FKs bauen
│   ├── pathfinder.py       # k-kürzeste Pfade + Filter-Tabellen einweben
│   └── sqlgen.py           # Join-Kette → SELECT/JOIN/WHERE-Text
├── web/
│   ├── routes.py           # Flask-Blueprint: /api/schema, /api/joinpath
│   ├── templates/          # Jinja2 (Formular-UI)
│   └── static/
│       ├── css/            # lokal
│       ├── js/             # lokal
│       └── lib/            # lokal gebundelte Third-Party-Libs (keine CDN)
├── tests/
│   ├── conftest.py         # pytest-Fixtures (temp SQLite-Schema)
│   ├── fixtures/           # SQL-Schema für Fixture-DB
│   └── test_*.py
├── requirements.txt        # flask, sqlalchemy, networkx
├── requirements-dev.txt    # pytest
├── lucent-hub.yml          # type: web, port: 5057
├── run.sh                  # Setup/Run (venv, pip-Stamp-Cache, --skip-setup schnell)
├── sync_version.py         # Versions-Sync (config.py + lucent-hub.yml)
├── pytest.ini
├── CLAUDE.md               # nach CLAUDE_md.pattern
├── CHANGELOG.md
├── README.md
└── .gitignore
```

**Schichtregel:** `core/` importiert **kein** Flask. `web/` ruft `core/` auf, nie umgekehrt.
`config.py` ist global read-only nach Startup; `core/settings.py` managed die Runtime-JSON-Config.

### Module — Verantwortung / Schnittstelle / Abhängigkeit

| Modul | Was | Schnittstelle | Hängt ab von |
|---|---|---|---|
| `model.py` | Datentypen | `Schema`, `Table`, `Column`, `FKEdge` (frozen dataclasses) | — |
| `schema_loader.py` | Loader-Vertrag | `SchemaLoader.load() -> Schema` (ABC) | `model` |
| `sqlalchemy_loader.py` | Live-Reflection | `load()` reflektiert via SQLAlchemy MetaData | `model`, SQLAlchemy |
| `graph.py` | FK-Graph | `build_graph(Schema) -> nx.Graph` | `model`, networkx |
| `pathfinder.py` | Pfadsuche | `find_paths(graph, start, target, filters, k) -> list[JoinPath]` | `graph`, networkx |
| `sqlgen.py` | SQL-Text | `generate_sql(JoinPath, selects, filters) -> str` | `model` |
| `web/routes.py` | HTTP-API | Blueprint-Endpunkte | alle `core/`-Module |

---

## 3. Datenfluss

1. **Connection-String** (z. B. `sqlite:///inventory.db`, `postgresql://…`) → `sqlalchemy_loader`
   reflektiert Tabellen, Spalten, Foreign Keys → `Schema`-Objekt.
2. `graph.py` baut einen **ungerichteten NetworkX-Graphen**: **Knoten = Tabelle**,
   **Kante = FK-Beziehung**. Auf jeder Kante als Attribut: die beteiligten Join-Spalten
   (`local_col`, `remote_col`) + Richtung der ursprünglichen FK.
3. UI (Jinja-Formular): Benutzer wählt Start-`tabelle.spalte`, Ziel-`tabelle.spalte`,
   0..n Filter (`tabelle.spalte` + Operator + Wert).
4. `pathfinder.find_paths`:
   - kürzester Pfad Start-Tabelle → Ziel-Tabelle,
   - jede Filter-Tabelle, die nicht auf dem Pfad liegt, wird über ihren kürzesten
     Verbindungspfad zum bisherigen Join-Set eingewoben,
   - Rückgabe: bis zu *k* alternative `JoinPath`-Objekte.
5. `sqlgen.generate_sql`: erzeugt deterministisches SQL aus den Edge-Join-Bedingungen
   (`JOIN … ON …`) + `WHERE` aus den Filtern (parametrisierte Platzhalter).
6. Anzeige: SQL-Text + Pfad-Zusammenfassung („3 Tabellen, 2 Joins") + Liste der Alternativ-Pfade.

---

## 4. Der Knackpunkt — mehrere mögliche Join-Pfade

Der eigentliche fachliche Aufwand (vom Auftraggeber selbst benannt). v1-Ansatz **ohne LLM**:

- **Primär:** kürzester Pfad (wenigste Joins) via `networkx.shortest_path`.
- **Deterministischer Tie-Break:** bei gleich langen Pfaden lexikografisch nach
  Tabellennamen-Sequenz sortieren → dieselbe Eingabe liefert immer dasselbe SQL (testbar).
- **Alternativen sichtbar:** `pathfinder` liefert die *k* kürzesten Pfade
  (`networkx.shortest_simple_paths`, abgeschnitten auf *k*). Die UI listet sie; der Benutzer
  kann zwischen ihnen umschalten.
- **Erweiterungspunkt:** Das spätere LLM-Pfad-Ranking (Idee 4) dockt genau an dieser Stelle an —
  es sortiert die von `pathfinder` gelieferten Kandidaten nach fachlicher Plausibilität, ersetzt
  die Pfadsuche aber nicht.

---

## 5. Fehlerbehandlung & Sicherheit

- **Kein Pfad** zwischen Start und Ziel → klare Meldung („Keine Join-Verbindung gefunden"),
  kein leeres/kaputtes SQL.
- **DB-Connection-Fehler** → sauber abgefangen, nutzerfreundliche Meldung, **kein Stacktrace**
  ans Frontend; Details nur ins Log.
- **Read-only by design:** Das Tool führt **niemals** SQL aus. Es gibt keinen Execution-Pfad,
  keinen DB-Write, kein Result-Grid in v1.
- **Keine SQL-Injection im generierten Text:** Filterwerte werden als **parametrisierte
  Platzhalter** generiert (named params), Werte separat ausgewiesen — nicht roh in den
  SQL-String konkateniert.
- **Zyklische FKs:** NetworkX-Pfadsuche terminiert auf ungerichtetem Graphen sauber; keine
  Endlosschleifen.

---

## 6. Testing (TDD)

**Fixture:** temporäre SQLite-DB mit einem VMware-/CMDB-artigen Schema und echten Foreign Keys:

```
Networks(NetworkID PK, VLAN)
VirtualMachines(VMID PK, NetworkID FK→Networks, OSID FK→OperatingSystems, ClusterID FK→VMwareCluster)
OperatingSystems(OSID PK, OS_Family)
VMwareCluster(ClusterID PK)
```

Die Fixture wird über `sqlalchemy_loader` reflektiert — derselbe Pfad wie in Produktion,
kein separater Manual-Loader nötig.

**Testfälle (Auswahl):**
- Graph-Aufbau: korrekte Knoten/Kanten + Join-Spalten auf den Kanten.
- Pfadfindung: `Networks → VMwareCluster` ergibt erwartete Tabellensequenz.
- Tie-Break-Determinismus: gleiche Eingabe → identisches SQL über mehrere Läufe.
- SQL-String: erwartetes `SELECT/JOIN/ON/WHERE` (Snapshot/Assertion).
- Filter-Einwebung: Filter auf `OperatingSystems.OS_Family='Windows'` zieht die OS-Tabelle
  in die Join-Kette.
- No-Path-Fehler: getrennte Komponenten → saubere Fehlermeldung.
- *k*-Alternativen: bei mehreren Pfaden werden ≥2 Kandidaten geliefert.

---

## 7. Querschnitts-Konventionen (aus Pattern-Library)

- **Assets lokal bundeln** — keine CDNs (globale Konvention). Third-Party-JS/CSS nach
  `web/static/lib/` bzw. `web/static/css/`.
- **i18n** DE/EN über `strings.py` / `t(key)`.
- **Version** nur via `sync_version.py` ändern, nie `config.py` manuell.
- **`run.sh`** mit den Standard-Modi (`--setup-venv`, `--skip-setup`, `--clean`, `--version`);
  `--skip-setup` startet schnell (kein pip-Check), für Hub `run_command`.
- **Code/Kommentare Englisch, UI DE/EN, Doku Deutsch.**
- **Session-Handoff/KPI** (`session-handoff-kpi.pattern`) ab Session 1 anlegen → saubere KPIs
  von Anfang an.

---

## 8. Offene Punkte (vor/bei Implementierung klären)

1. **Web-Port 5057** vor erstem Hub-Start gegen die Hub-Registry prüfen (keine bekannte
   `lucent-job`-Web-Port-Range vorliegend).
2. **Connection-Handling in der UI:** Eingabe-Feld für Connection-String vs. vorkonfiguriert in
   `config.json`. v1-Default: Feld im Formular, optional Default aus `config.json`.

---

## 9. Roadmap nach v1 (nicht Teil dieser Spec)

- v2: Grafische Graph-Darstellung (Cytoscape.js, lokal gebundelt) mit farblich markiertem Pfad.
- v3: Weitere Loader (SchemaSpy-Import, manuelles JSON/YAML, SQL-DDL).
- v4: LLM-Text2SQL + LLM-Pfad-Ranking (lokales Modell / Open WebUI).
- später: MySQL/MSSQL, Query-Ausführung mit Ergebnisvorschau (read-only, LIMIT-Guards).
</content>
</invoke>
