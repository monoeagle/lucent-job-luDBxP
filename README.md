# LucentTools DB Explorer

Visueller Join-Pfad-Builder. Liest ein DB-Schema per Reflection, baut einen
FK-Graphen und generiert aus Start-/Ziel-Spalte (+ Filtern) read-only SQL.

## Start

**Linux/macOS** — ohne Argument erscheint ein interaktives Menü:
```bash
bash run.sh            # Menü (Start, Setup, Tests, Demo-DB, Version …)
```

**Windows (PowerShell):**
```powershell
.\run.ps1              # gleiches Menü
```

Direkte (nicht-interaktive) Aktionen via Flag — z. B. für den Hub:
```bash
bash run.sh --start        # App starten (http://127.0.0.1:5057)
bash run.sh --skip-setup   # schneller Start ohne Setup-Check
bash run.sh --version
# Windows: .\run.ps1 -Action start | skip-setup | version | tests | demo-db | clean | setup-venv
```

## Tests
```bash
bash run.sh --tests          # oder: ./venv/bin/python -m pytest
```

## Bekannte Einschränkungen (v1)

- **Composite foreign keys:** Schemas with multi-column FKs are joined on only the first column pair in v1; single-column FKs are fully supported.
- **Database backends:** Postgres support is implemented via SQLAlchemy but is only covered by automated tests against SQLite in v1.
