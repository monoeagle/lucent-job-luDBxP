"""Build a clean delivery ZIP (runtime only, no dev/AI traces) for a release.

Assembles an allow-listed subset of the repo into a staging directory and zips
it. Everything not needed to RUN the app is left out: git history, tests, the
documentation sources, internal docs (handoffs/insights/audits), tooling,
CLAUDE.md, caches. This is the AP-17 "Delivery" idea, delivered as a release
artifact.

Run from anywhere:
    python tools/build_release.py
Output:
    build/<Name>-<version>/        (staging tree)
    build/<Name>-<version>.zip     (release asset)
"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config  # noqa: E402

PKG_BASENAME = "LucentTools-DB-Explorer"   # readable, ASCII (filename-safe)

# Allow-list: ONLY what the app needs to run.
# run.ps1 (Windows) is bundled UNSIGNED; the operator signs it in place after
# extracting (ExecutionPolicy requires a signed script). run.sh (Linux) has no
# code-signing gate.
INCLUDE_FILES = [
    "app.py", "config.py", "strings.py", "config.json",
    "requirements.txt", "run.ps1", "run.sh",
]
INCLUDE_DIRS = ["core", "web", "wheels", "sample_data"]

# Pruned anywhere in the copied trees.
PRUNE_DIRS = {"__pycache__", ".pytest_cache"}
PRUNE_SUFFIXES = (".pyc", ".pyo")


def _ignore(_dir, names):
    return [n for n in names
            if n in PRUNE_DIRS or n.endswith(PRUNE_SUFFIXES)]


def _start_text(ver):
    return (
        f"LucentTools DB Explorer v{ver}\n"
        "==============================\n\n"
        "Launcher: run.ps1 (Windows) ist enthalten, aber UNSIGNIERT. Nach dem\n"
        "Entpacken signieren (die ExecutionPolicy verlangt ein signiertes Skript),\n"
        "dann ausfuehren.\n\n"
        "Schnellstart (Windows):\n"
        "  1. Python 3.14 (64-bit) installieren (falls noch nicht vorhanden).\n"
        "  2. run.ps1 in diesem Ordner signieren.\n"
        "  3. PowerShell hier oeffnen und ausfuehren:  .\\run.ps1\n"
        "  4. Browser oeffnen:   http://127.0.0.1:5057\n\n"
        "Hinweise:\n"
        "  - Installation laeuft OFFLINE aus wheels\\ (kein Internet noetig).\n"
        "  - Port 5057 muss frei sein.\n"
        "  - Read-only: die App liest nur Schema-Metadaten und erzeugt SQL-Text.\n\n"
        "Linux:  ./run.sh  (im Paket enthalten)\n"
    )


def main():
    ver = config.APP_VERSION
    pkg = f"{PKG_BASENAME}-{ver}"
    build = os.path.join(ROOT, "build")
    stage = os.path.join(build, pkg)
    zip_path = os.path.join(build, f"{pkg}.zip")

    if os.path.exists(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)

    missing = []
    for f in INCLUDE_FILES:
        src = os.path.join(ROOT, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(stage, f))
        else:
            missing.append(f)
    for d in INCLUDE_DIRS:
        src = os.path.join(ROOT, d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(stage, d), ignore=_ignore)
        else:
            missing.append(d + "/")

    with open(os.path.join(stage, "START-HIER.txt"), "w", encoding="utf-8") as fh:
        fh.write(_start_text(ver))

    if os.path.exists(zip_path):
        os.remove(zip_path)
    n_files = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fn in os.walk(stage):
            dn[:] = [d for d in dn if d not in PRUNE_DIRS]
            for f in fn:
                if f.endswith(PRUNE_SUFFIXES):
                    continue
                full = os.path.join(dp, f)
                rel = os.path.relpath(full, stage)
                z.write(full, os.path.join(pkg, rel))  # top-level folder in zip
                n_files += 1

    size_mb = os.path.getsize(zip_path) / 1_000_000
    print(f"Paket : {pkg}")
    print(f"Dateien: {n_files}")
    print(f"ZIP   : {zip_path}  ({size_mb:.1f} MB)")
    if missing:
        print("WARN  : nicht gefunden (uebersprungen): " + ", ".join(missing))
    return zip_path


if __name__ == "__main__":
    main()
