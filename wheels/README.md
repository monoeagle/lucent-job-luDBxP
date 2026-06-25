# Offline-Wheelhouse (Windows)

Gebündelte Python-Wheels für die **Offline-Einrichtung unter Windows** (keine
PyPI-/Internet-Freigabe nötig). Gesamtgröße ~7,8 MB.

## Verwendung
Sobald dieser Ordner vorhanden ist, installiert `run.ps1` **automatisch offline**:
```powershell
.\run.ps1 -Action setup-venv     # nutzt --no-index --find-links wheels\
.\run.ps1                        # Menü → "Nur Umgebung einrichten"
```
`run.ps1` verlangt dann **Python 3.12 (64-bit)** — die kompilierten Wheels
(SQLAlchemy, psycopg2-binary, pyodbc, greenlet, markupsafe) sind `cp312-win_amd64`.
Die übrigen sind plattformunabhängig (`py3-none-any`).

## Voraussetzung
Nur **Python 3.12 (64-bit)** muss auf der Windows-Maschine installiert sein
(Installer von python.org, ~30 MB — separat, kein pip-Nachladen).

## Inhalt (Laufzeit-Dependencies aus requirements.txt + transitiv)
Flask, Werkzeug, Jinja2, click, itsdangerous, MarkupSafe, blinker,
SQLAlchemy (+ greenlet), networkx, psycopg2-binary, PyMySQL, pyodbc,
typing-extensions.

## Aktualisieren / andere Python-Version
Für eine andere Python-Version oder neue Abhängigkeiten die Wheels neu ziehen
(auf einer Maschine mit Internet):
```bash
pip download -r requirements.txt --platform win_amd64 \
  --python-version 312 --implementation cp --only-binary=:all: -d wheels/
```
(`--python-version` auf die Ziel-Version anpassen, z. B. 311/313.)

## Hinweis
- `pytest` (requirements-dev.txt) ist NICHT enthalten — Tests laufen offline nur,
  wenn pytest separat bereitgestellt wird.
- Linux: nutzt das AppImage (`run.sh --appimage`) für einen offline-fähigen Build;
  diese Windows-Wheels sind dort nicht verwendbar.
