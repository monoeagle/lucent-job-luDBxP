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

## Windows (PowerShell)

Unter Windows übernimmt `run.ps1` dieselbe Rolle wie `run.sh` (gleiches Menü):

```powershell
.\run.ps1                    # interaktives Menü
.\run.ps1 -Action setup-venv # nur Umgebung einrichten
.\run.ps1 -Action start      # App starten → http://127.0.0.1:5057
```

## Offline-Einrichtung (ohne Internet)

Für Maschinen **ohne PyPI-/Internet-Freigabe** liegt ein **Offline-Wheelhouse**
bei: der Ordner `wheels/` enthält alle Laufzeit-Abhängigkeiten als Windows-Wheels
(`cp312-win_amd64`, ~7,8 MB). Ist `wheels/` vorhanden, installiert `run.ps1`
**automatisch offline** (`pip --no-index --find-links wheels`):

```powershell
.\run.ps1 -Action setup-venv   # läuft ohne Internet aus wheels\
```

- **Voraussetzung:** Python **3.12 (64-bit)** muss installiert sein (Installer von
  python.org, ~30 MB — einmalig, kein pip-Nachladen). Die kompilierten Wheels sind
  `cp312`; `run.ps1` verlangt im Offline-Modus daher Python 3.12.
- Andere Python-Version oder Aktualisierung: siehe `wheels/README.md`
  (`pip download …`-Rezept).
- **Linux:** für einen vollständig offline-fähigen Build dient das AppImage
  (`bash run.sh --appimage`), das Python + alle Abhängigkeiten bündelt.

!!! note "Betrieb ist ohnehin offline-fähig"
    Zur Laufzeit lädt die App **nichts** nach: alle Frontend-Assets (Cytoscape.js
    u. a.) sind lokal gebündelt, es gibt **keine CDN-Aufrufe**. Nur die *erstmalige*
    Einrichtung (`pip install`) benötigt die Pakete — entweder aus `wheels/`
    (offline) oder von PyPI (online).

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
unixODBC + der Microsoft **ODBC Driver 18 for SQL Server** (`msodbcsql18`)
erforderlich (Windows: Microsoft-Installer; Linux: unixODBC + msodbcsql18). Driver 18
verschlüsselt standardmäßig — bei selbstsigniertem Server-Zertifikat in der Verbindung
`TrustServerCertificate=yes` (oder `Encrypt=no`) setzen. Der ODBC-Treibername ist
überschreibbar (z. B. `ODBC Driver 17 for SQL Server`). Fehlt der Treiber, meldet die
App das klar statt einer rohen pyodbc-Fehlermeldung.

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
