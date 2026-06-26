# Datenmodell

## Interne Modell-Klassen (`core/model.py`)

Lucent DB Explorer arbeitet mit einem rein im Speicher gehaltenen Modell der
Datenbankstruktur. Es gibt keine persistente eigene Datenbank — alles wird bei
jedem API-Aufruf frisch aus der Zieldatenbank reflektiert.

<img src="../images/mermaid/referenz-datenmodell-1.svg" alt="Diagramm 1 aus referenz/datenmodell.md">

### Schema

Das Wurzelobjekt nach einer Reflection-Operation. Enthält:

- `tables: list[Table]` — alle reflektierten Tabellen
- `views: list[View]` — alle reflektierten Views
- `has_column(table, column)` — Validierungsmethode für API-Aufrufe

### Table

| Attribut | Typ | Beschreibung |
|---|---|---|
| `name` | `str` | Tabellenname |
| `columns` | `list[Column]` | Alle Spalten |
| `foreign_keys` | `list[ForeignKey]` | Deklarierte FKs |
| `primary_key` | `set[str]` | Primärschlüssel-Spaltennamen |

### Column

| Attribut | Typ | Beschreibung |
|---|---|---|
| `name` | `str` | Spaltenname |
| `type` | `str` | Datentyp als String (z. B. `INTEGER`, `VARCHAR`) |

### ForeignKey

Trägt **ein oder mehrere** Spaltenpaare — einspaltige und zusammengesetzte
(composite) FKs haben dieselbe Form.

| Attribut / Property | Typ | Beschreibung |
|---|---|---|
| `ref_table` | `str` | Referenzierte Tabelle |
| `column_pairs` | `tuple[tuple[str, str], ...]` | `(Quellspalte, Zielspalte)`-Paare; 1 = einspaltig, n = composite |
| `columns` | `tuple[str, ...]` | Quellspalten (Property) |
| `ref_columns` | `tuple[str, ...]` | Zielspalten (Property) |
| `is_composite` | `bool` | `True` bei mehr als einem Paar (Property) |

`ForeignKey.single(column, ref_table, ref_column)` baut einen einspaltigen FK.
Ein composite FK wird als `JOIN … ON a.x = b.x AND a.y = b.y` gejoint; zwei
*separate* einspaltige FKs zwischen denselben Tabellen bleiben alternative
Join-Wege.

### View

| Attribut | Typ | Beschreibung |
|---|---|---|
| `name` | `str` | View-Name |
| `columns` | `list[Column]` | Spalten |
| `definition` | `str` | SQL-Definition (CREATE VIEW … AS …) |

## FK-Graph

Der FK-Graph (`core/graph.py`) ist ein gerichteter NetworkX-Graph:

- **Knoten** — Tabellennamen
- **Kanten** — Foreign-Key-Beziehungen (gerichtet: Quell-Tabelle → Ziel-Tabelle)
- **Kantenattribut `implied`** — `True` für heuristisch erkannte FKs

Der Graph wird bei jedem `/api/graph`- und `/api/joinpath`-Aufruf neu gebaut.
Er enthält keine Views — nur Tabellen mit FK-Beziehungen.

## API-Ausgabeformat: /api/schema

```json
{
  "tables": [
    {
      "name": "orders",
      "columns": [
        {"name": "id", "type": "INTEGER", "pk": true},
        {"name": "customer_id", "type": "INTEGER", "pk": false}
      ],
      "foreign_keys": [
        {"columns": ["customer_id"], "ref_table": "customers", "ref_columns": ["id"]}
      ],
      "ddl": "CREATE TABLE orders (...)"
    }
  ],
  "views": [
    {
      "name": "active_orders",
      "columns": [...],
      "definition": "SELECT ... FROM orders WHERE ..."
    }
  ]
}
```
