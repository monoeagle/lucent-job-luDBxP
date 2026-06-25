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
