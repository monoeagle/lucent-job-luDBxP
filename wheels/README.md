# Offline-Wheelhouse (Windows)

Gebündelte Python-Wheels für die **Offline-Einrichtung unter Windows** (keine
PyPI-/Internet-Freigabe nötig). Gesamtgröße ~9,4 MB.

## Verwendung
Sobald dieser Ordner vorhanden ist, installiert `run.ps1` **automatisch offline**:
```powershell
.\run.ps1 -Action setup-venv     # nutzt --no-index --find-links wheels\
.\run.ps1                        # Menü → "Nur Umgebung einrichten"
```
`run.ps1` verlangt dann **Python 3.14 (64-bit, Standard-Build — NICHT free-threaded)** — die
kompilierten Wheels (SQLAlchemy, psycopg2-binary, pyodbc, oracledb, pillow, greenlet, markupsafe,
cffi) sind `cp314-cp314-win_amd64`. **cryptography** liegt als **abi3**-Wheel
(`cp311-abi3-win_amd64`) vor — es läuft auf jedem Standard-CPython ≥3.11 (inkl. 3.14). Die übrigen
sind plattformunabhängig (`py3-none-any`).

> **Wichtig:** Das cryptography-**`cp314t`**-Wheel (Suffix `t` = *free-threaded*/no-GIL) passt NICHT
> zum Standard-3.14-Interpreter → `pip` meldet „from versions: none". Immer die **abi3**-Variante
> nehmen (`cp311-abi3`), nicht `cp314t`.

## Voraussetzung
Nur **Python 3.14 (64-bit)** muss auf der Windows-Maschine installiert sein
(Installer von python.org, ~30 MB — separat, kein pip-Nachladen).

## Inhalt (Laufzeit-Dependencies aus requirements.txt + transitiv)
Flask, Werkzeug, Jinja2, click, itsdangerous, MarkupSafe, blinker, colorama
(click-Abhängigkeit unter Windows), SQLAlchemy (+ greenlet), networkx,
psycopg2-binary, PyMySQL, pyodbc, **oracledb (+ cryptography [abi3] + cffi + pycparser)**,
sqlglot, waitress, pystray (+ Pillow, six, python-xlib), typing-extensions.

## Inhalt (Test-Dependencies aus requirements-dev.txt + transitiv)
pytest (+ pluggy, iniconfig, packaging, pygments). colorama wird hier
mitbenutzt, ist aber bereits im Laufzeit-Set enthalten.

## Aktualisieren / andere Python-Version
Für eine andere Python-Version oder neue Abhängigkeiten die Wheels neu ziehen
(auf einer Maschine mit Internet). `requirements-dev.txt` zieht inklusive der
Laufzeit-Wheels und pytest in einem Rutsch:
```bash
pip download -r requirements-dev.txt --platform win_amd64 \
  --python-version 314 --implementation cp \
  --abi cp314 --abi abi3 --abi none \
  --only-binary=:all: -d wheels/
```
(`--python-version`/`--abi cp314` auf die Ziel-Version anpassen, z. B. 313/315.)
**`--abi abi3 --abi none` sind zwingend** — sonst werden abi3-Wheels (cryptography) und
plattformunabhängige Wheels (pycparser, py3-none-any) NICHT mitgezogen; genau daran scheiterte
zuvor der Offline-Install (fehlendes cryptography).

## Hinweis
- `pytest` und seine Abhängigkeiten sind enthalten — `run.ps1 -Action tests`
  installiert die Test-Umgebung offline (`--no-index --find-links wheels\`).
- Linux: nutzt das AppImage (`run.sh --appimage`) für einen offline-fähigen Build;
  diese Windows-Wheels sind dort nicht verwendbar.
