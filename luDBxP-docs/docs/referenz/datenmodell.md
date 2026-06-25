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

| Attribut | Typ | Beschreibung |
|---|---|---|
| `column` | `str` | Quellspalte |
| `ref_table` | `str` | Referenzierte Tabelle |
| `ref_column` | `str` | Referenzierte Spalte |
| `implied` | `bool` | `True` wenn heuristisch erkannt |

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
        {"column": "customer_id", "ref_table": "customers", "ref_column": "id"}
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
