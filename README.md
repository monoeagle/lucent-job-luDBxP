# Lucent DB Explorer

Visueller Join-Pfad-Builder. Liest ein DB-Schema per Reflection, baut einen
FK-Graphen und generiert aus Start-/Ziel-Spalte (+ Filtern) read-only SQL.

## Start
```bash
bash run.sh            # Setup + Start (http://127.0.0.1:5057)
bash run.sh --version
```

## Tests
```bash
./venv/bin/python -m pytest
```

## Bekannte Einschränkungen (v1)

- **Composite foreign keys:** Schemas with multi-column FKs are joined on only the first column pair in v1; single-column FKs are fully supported.
- **Database backends:** Postgres support is implemented via SQLAlchemy but is only covered by automated tests against SQLite in v1.
