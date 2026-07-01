#!/usr/bin/env python3
"""
build_docs.py — LucentTools DB Explorer Doku-Pipeline.

Ein Einstiegspunkt fuer den kompletten Doku-Build:
    1. Inline-Mermaid-Bloecke aus .md nach mermaid-sources/ extrahieren
    2. Alle .mmd nach docs/images/mermaid/*.svg rendern (via mmdc)
    3. generate_project_activity.py → frischer Heatmap-Datensatz
    4. zensical build → static site nach site/

Nutzung:
    python3 build_docs.py                  # voller Build
    python3 build_docs.py --serve          # build + lokaler HTTP-Server
    python3 build_docs.py --serve --port 8046
    python3 build_docs.py --check          # nur Doku-Struktur pruefen
    python3 build_docs.py --no-mermaid     # Mermaid-Schritte ueberspringen
    python3 build_docs.py --no-activity    # Activity-JSON-Refresh skippen
    python3 build_docs.py --ci             # strikt (Exit-Code bei Warnungen)
"""
from __future__ import annotations
import argparse
import http.server
import shutil
import socketserver
import subprocess
import sys
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent
DOCS_DIR    = BASE_DIR / "docs"
SITE_DIR    = BASE_DIR / "site"
TOOLS_DIR   = BASE_DIR / "tools"
MMD_SOURCES = BASE_DIR / "mermaid-sources"
MERMAID_OUT = DOCS_DIR / "images" / "mermaid"
CONFIG_FILE = BASE_DIR / "zensical.toml"

GREEN  = "\033[0;32m"
CYAN   = "\033[0;36m"
YELLOW = "\033[1;33m"
RED    = "\033[0;31m"
RESET  = "\033[0m"


def step(msg: str) -> None:
    print(f"\n{CYAN}▸ {msg}{RESET}")


def ok(msg: str) -> None:
    print(f"{GREEN}  ✓ {msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  ⚠ {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"{RED}  ✗ {msg}{RESET}")


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    """Subprocess mit sichtbarem Command. Liefert returncode."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd or BASE_DIR)
    if check and result.returncode != 0:
        fail(f"Exit-Code {result.returncode}")
        sys.exit(result.returncode)
    return result.returncode


# ─── Vorbedingungen ──────────────────────────────────────────────────────────


def check_zensical() -> None:
    """Zensical via sys.executable -m, damit das aktive venv genutzt wird."""
    try:
        subprocess.run(
            [sys.executable, "-m", "zensical", "--version"],
            capture_output=True, check=True,
        )
    except subprocess.CalledProcessError:
        fail("Zensical nicht im aktiven Python-Env gefunden.")
        print(f"  Installieren mit: {sys.executable} -m pip install zensical")
        sys.exit(1)


def check_structure(strict: bool = False) -> int:
    step("Doku-Struktur pruefen")
    errors = 0

    for required in [CONFIG_FILE, DOCS_DIR, DOCS_DIR / "index.md",
                     DOCS_DIR / "stylesheets" / "extra.css"]:
        if not required.exists():
            fail(f"fehlt: {required.relative_to(BASE_DIR)}")
            errors += 1

    md_files = list(DOCS_DIR.rglob("*.md")) if DOCS_DIR.exists() else []
    ok(f"{len(md_files)} Markdown-Dateien")

    if MMD_SOURCES.is_dir():
        mmds = list(MMD_SOURCES.glob("*.mmd"))
        ok(f"{len(mmds)} Mermaid-Sources")
    else:
        warn("mermaid-sources/ fehlt — Mermaid-Pipeline wird leer laufen")

    if errors:
        fail(f"{errors} Probleme")
        if strict:
            sys.exit(1)
        return errors
    ok("Struktur OK")
    return 0


# ─── Pipeline-Schritte ───────────────────────────────────────────────────────


def step_extract_mermaid() -> None:
    script = TOOLS_DIR / "extract_mermaid_blocks.py"
    if not script.is_file():
        warn("extract_mermaid_blocks.py fehlt — uebersprungen")
        return
    step("Mermaid-Bloecke extrahieren (idempotent)")
    run([sys.executable, str(script)])
    ok("Inline-Mermaid-Bloecke synchronisiert")


def step_render_mermaid() -> None:
    script = TOOLS_DIR / "render_mermaid.sh"
    if not script.is_file():
        warn("render_mermaid.sh fehlt — uebersprungen")
        return
    if not MMD_SOURCES.is_dir() or not list(MMD_SOURCES.glob("*.mmd")):
        warn("Keine .mmd-Quellen — Rendering uebersprungen")
        return
    step("Mermaid-Sources zu SVG rendern")
    run(["bash", str(script)])
    ok("SVGs in docs/images/mermaid/")


def step_generate_activity() -> None:
    script = TOOLS_DIR / "generate_project_activity.py"
    if not script.is_file():
        warn("generate_project_activity.py fehlt — uebersprungen")
        return
    step("Aktivitaets-JSON aus git log generieren")
    rc = run([sys.executable, str(script)], check=False)
    if rc == 0:
        ok("project-activity.json aktualisiert")
    else:
        warn(f"generate_project_activity.py exit {rc} (nicht-fatal)")


def step_generate_roadmap() -> None:
    script = TOOLS_DIR / "generate_roadmap_svg.py"
    if not script.is_file():
        warn("generate_roadmap_svg.py fehlt — uebersprungen")
        return
    step("Roadmap-Swimlane-SVG generieren")
    rc = run([sys.executable, str(script)], check=False)
    if rc == 0:
        ok("projekt-roadmap.svg aktualisiert")
    else:
        warn(f"generate_roadmap_svg.py exit {rc} (nicht-fatal)")


def step_zensical_build() -> None:
    step("Zensical-Build (site/)")
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    run([sys.executable, "-m", "zensical", "build"])
    if not (SITE_DIR / "index.html").is_file():
        fail("site/index.html nicht erzeugt")
        sys.exit(1)
    ok(f"site/ unter {SITE_DIR}")


# ─── Serve ───────────────────────────────────────────────────────────────────


def serve(port: int) -> None:
    if not SITE_DIR.is_dir():
        fail("site/ fehlt — vorher Build laufen lassen")
        sys.exit(1)

    step(f"HTTP-Server auf Port {port}")
    print(f"  {GREEN}http://127.0.0.1:{port}{RESET}  (Ctrl+C zum Beenden)")

    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(
        *a, directory=str(SITE_DIR), **k
    )
    try:
        with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print()
        ok("Server beendet")


# ─── Entry-Point ─────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LucentTools DB Explorer Docs — voller Build inkl. Mermaid + Activity-JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--serve",       action="store_true", help="Nach Build HTTP-Server starten")
    parser.add_argument("--port",        type=int, default=8046, help="Port fuer --serve (Default: 8046)")
    parser.add_argument("--check",       action="store_true", help="Nur Struktur pruefen, kein Build")
    parser.add_argument("--ci",          action="store_true", help="Strict-Mode (Exit-Code bei Warnungen)")
    parser.add_argument("--no-mermaid",  action="store_true", help="Mermaid-Pipeline ueberspringen")
    parser.add_argument("--no-activity", action="store_true", help="Activity-JSON-Refresh ueberspringen")
    args = parser.parse_args()

    check_zensical()
    check_structure(strict=args.ci)

    if args.check:
        return

    if not args.no_mermaid:
        step_extract_mermaid()
        step_render_mermaid()

    if not args.no_activity:
        step_generate_activity()

    step_generate_roadmap()

    step_zensical_build()

    if args.serve:
        serve(args.port)
        return

    print()
    ok(f"Build fertig — site/ unter {SITE_DIR}")
    print(f"  Browser-Test: {CYAN}python3 build_docs.py --serve{RESET}")


if __name__ == "__main__":
    main()
