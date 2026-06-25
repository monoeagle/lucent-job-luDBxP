# Installation

## Systemvoraussetzungen

| Anforderung | Minimum |
|---|---|
| Python | 3.10+ |
| Betriebssystem | Linux, macOS, Windows |
| Bash | für `run.sh` (Linux/macOS) |
| PowerShell | für `run.ps1` (Windows) |

## Klonen und Einrichten

```bash
git clone <repo-url>
cd lucent-job-luDBxP
bash run.sh           # interaktives Menü → „Setup" wählen
```

Das Menü legt automatisch eine virtuelle Umgebung (`venv/`) an und installiert alle Abhängigkeiten.

### Direkte Einrichtung (ohne Menü)

```bash
bash run.sh --setup-venv
```

## Python-Abhängigkeiten

Die Kerndependencies werden automatisch installiert:

| Paket | Zweck |
|---|---|
| Flask ≥ 3.0 | Web-Framework |
| SQLAlchemy ≥ 2.0 | Datenbankzugriff (read-only) |
| networkx ≥ 3.0 | FK-Graph + Pfadfindung |
| psycopg2-binary | PostgreSQL-Treiber |
| PyMySQL | MySQL / MariaDB-Treiber |
| pyodbc | MS SQL Server-Treiber |

## Datenbank-Treiber

**SQLite** ist ohne zusätzliche Pakete verfügbar (in Python enthalten).

**PostgreSQL** — Treiber `psycopg2-binary` ist in `requirements.txt` enthalten.

**MySQL / MariaDB** — Treiber `PyMySQL` ist in `requirements.txt` enthalten.

**MS SQL Server** — Treiber `pyodbc` ist enthalten; zusätzlich ist system-seitiges
unixODBC + der Microsoft ODBC Driver for SQL Server (`msodbcsql`) erforderlich.

## Dokumentation einrichten

Die Dokumentation hat eine eigene virtuelle Umgebung:

```bash
cd luDBxP-docs
bash run_luDBxP_docs.sh         # installiert .venv-docs + Zensical automatisch
```

### Voraussetzungen für Mermaid-Diagramme

Für das Rendern der Architekturdiagramme wird Node.js + npx benötigt
(zieht beim ersten Lauf `@mermaid-js/mermaid-cli` + Chromium nach):

```bash
node --version    # Node.js 18+ empfohlen
npx --version
```

Ohne mmdc werden die Diagramme im Browser über das lokal gebundelte
`mermaid.min.js` gerendert (kein CDN-Zugriff).
