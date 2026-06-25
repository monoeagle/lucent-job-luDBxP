#!/usr/bin/env python3
"""
Extrahiert ALLE ```mermaid Code-Bloecke aus den .md-Files unter docs/ und
ersetzt sie durch <img>-Referenzen auf pre-renderte SVGs.

Naming: <pfad-flach>-<n>.mmd  (z.B. grundlagen-architektur-1.mmd)

Ablauf:
  1. .mmd-Dateien nach mermaid-sources/ schreiben
  2. ```mermaid ...``` Block in MD durch <img>-Tag ersetzen
  3. tools/render_mermaid.sh aufrufen (rendert alle .mmd zu .svg)
"""
from __future__ import annotations
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SOURCES = ROOT / "mermaid-sources"
SOURCES.mkdir(exist_ok=True)

# Pattern: ```mermaid\n <content> \n``` (greedy=False)
MERMAID_RE = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)


def slug_for(md_path: Path) -> str:
    """grundlagen/architektur.md → grundlagen-architektur"""
    rel = md_path.relative_to(DOCS).with_suffix("")
    return "-".join(rel.parts)


def img_relpath(md_path: Path, svg_name: str) -> str:
    """Relativer img-Pfad von md_path nach docs/images/mermaid/<svg_name>"""
    depth = len(md_path.relative_to(DOCS).parts) - 1  # 0 = root, 1 = nested
    prefix = "../" * depth if depth else ""
    return f"{prefix}images/mermaid/{svg_name}"


def _highest_existing_index(slug: str) -> int:
    """
    Idempotenz-Helper: scant mermaid-sources/<slug>-N.mmd und gibt das hoechste
    existierende N zurueck (0 wenn nichts existiert).

    Vorher zaehlte das Tool jedes Mal ab 1, was beim Mix aus bereits extrahierten
    img-Tags + neuen ```mermaid-Bloecken die bestehenden SVGs ueberschrieben hat.
    """
    pat = re.compile(rf"^{re.escape(slug)}-(\d+)\.mmd$")
    best = 0
    if SOURCES.exists():
        for f in SOURCES.iterdir():
            m = pat.match(f.name)
            if m:
                n = int(m.group(1))
                if n > best:
                    best = n
    return best


def process_file(md_path: Path) -> int:
    text = md_path.read_text(encoding="utf-8")
    matches = list(MERMAID_RE.finditer(text))
    if not matches:
        return 0

    slug = slug_for(md_path)
    # Idempotenz: neue Blocks beginnen ab next-free-index. Existierende mmd/svg
    # mit kleineren Indizes (= bereits extrahiert in einem frueheren Lauf) bleiben
    # unangetastet, ihre img-Tags in der MD verweisen weiter auf sie.
    start_n = _highest_existing_index(slug) + 1
    new_text = text
    # Von hinten ersetzen, damit Indizes stabil bleiben
    for idx, m in enumerate(reversed(matches), start=1):
        # Block-Nummerierung in Schreibrichtung (start_n, start_n+1, ...)
        n = start_n + (len(matches) - idx)
        mermaid_src = m.group(1).rstrip() + "\n"
        mmd_name = f"{slug}-{n}.mmd"
        svg_name = f"{slug}-{n}.svg"

        # .mmd schreiben
        (SOURCES / mmd_name).write_text(mermaid_src, encoding="utf-8")

        # img-Tag bauen
        rel = img_relpath(md_path, svg_name)
        alt = f"Diagramm {n} aus {md_path.relative_to(DOCS)}"
        img_tag = f'<img src="{rel}" alt="{alt}">'

        new_text = new_text[: m.start()] + img_tag + new_text[m.end():]

    md_path.write_text(new_text, encoding="utf-8")
    return len(matches)


def main() -> None:
    total_files = 0
    total_blocks = 0
    for md in sorted(DOCS.rglob("*.md")):
        n = process_file(md)
        if n > 0:
            total_files += 1
            total_blocks += n
            print(f"  • {md.relative_to(DOCS)}: {n} Block(s)")

    print(f"\n✓ {total_blocks} Mermaid-Blocks aus {total_files} Dateien extrahiert")
    print(f"  Sources in: {SOURCES}")

    # Render alle SVGs
    print("\n→ Rendere SVGs ...")
    subprocess.run(
        ["bash", str(ROOT / "tools/render_mermaid.sh")],
        check=True,
    )


if __name__ == "__main__":
    main()
