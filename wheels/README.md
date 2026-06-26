# Offline-Wheelhouse (Windows)

Gebündelte Python-Wheels für die **Offline-Einrichtung unter Windows** (keine
PyPI-/Internet-Freigabe nötig). Gesamtgröße ~9,4 MB.

## Verwendung
Sobald dieser Ordner vorhanden ist, installiert `run.ps1` **automatisch offline**:
```powershell
.\run.ps1 -Action setup-venv     # nutzt --no-index --find-links wheels\
.\run.ps1                        # Menü → "Nur Umgebung einrichten"
```
`run.ps1` verlangt dann **Python 3.14 (64-bit)** — die kompilierten Wheels
(SQLAlchemy, psycopg2-binary, pyodbc, greenlet, markupsafe) sind `cp314-win_amd64`.
Die übrigen sind plattformunabhängig (`py3-none-any`).

## Voraussetzung
Nur **Python 3.14 (64-bit)** muss auf der Windows-Maschine installiert sein
(Installer von python.org, ~30 MB — separat, kein pip-Nachladen).

## Inhalt (Laufzeit-Dependencies aus requirements.txt + transitiv)
Flask, Werkzeug, Jinja2, click, itsdangerous, MarkupSafe, blinker, colorama
(click-Abhängigkeit unter Windows), SQLAlchemy (+ greenlet), networkx,
psycopg2-binary, PyMySQL, pyodbc, typing-extensions.

## Inhalt (Test-Dependencies aus requirements-dev.txt + transitiv)
pytest (+ pluggy, iniconfig, packaging, pygments). colorama wird hier
mitbenutzt, ist aber bereits im Laufzeit-Set enthalten.

## Aktualisieren / andere Python-Version
Für eine andere Python-Version oder neue Abhängigkeiten die Wheels neu ziehen
(auf einer Maschine mit Internet). `requirements-dev.txt` zieht inklusive der
Laufzeit-Wheels und pytest in einem Rutsch:
```bash
pip download -r requirements-dev.txt --platform win_amd64 \
  --python-version 314 --abi cp314 --implementation cp --only-binary=:all: -d wheels/
```
(`--python-version`/`--abi` auf die Ziel-Version anpassen, z. B. 313/315.)

## Hinweis
- `pytest` und seine Abhängigkeiten sind enthalten — `run.ps1 -Action tests`
  installiert die Test-Umgebung offline (`--no-index --find-links wheels\`).
- Linux: nutzt das AppImage (`run.sh --appimage`) für einen offline-fähigen Build;
  diese Windows-Wheels sind dort nicht verwendbar.
