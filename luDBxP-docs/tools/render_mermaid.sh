#!/usr/bin/env bash
# Rendert alle Mermaid-Sources (.mmd) nach SVG via @mermaid-js/mermaid-cli (mmdc).
# Idempotent: ueberschreibt vorhandene SVGs.
#
# Usage:
#   ./tools/render_mermaid.sh              # alle Sources
#   ./tools/render_mermaid.sh index-1      # nur eine bestimmte
#
# Pattern (analog CSC):
#   mermaid-sources/<section>-<page>-<num>.mmd  → docs/images/mermaid/<section>-<page>-<num>.svg
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCES="$DOCS_ROOT/mermaid-sources"
TARGET="$DOCS_ROOT/docs/images/mermaid"

mkdir -p "$TARGET"

filter="${1:-*}"

count=0
for src in "$SOURCES"/${filter}*.mmd; do
    [ -f "$src" ] || continue
    name=$(basename "$src" .mmd)
    out="$TARGET/$name.svg"
    echo "  → $name"
    # Gantt-Diagramme bekommen mehr Breite (mehr Tage = mehr Spalten).
    if grep -q "^gantt" "$src"; then
        render_w=2400
    else
        render_w=1200
    fi
    # mmdc-Exit NICHT pipen (sonst maskiert | tail den Fehler unter set -e und
    # ein veraltetes SVG bleibt unbemerkt stehen). In Logdatei schreiben und
    # den echten Exit-Code prüfen.
    log="$TARGET/.mmdc-$name.log"
    if npx --yes -p @mermaid-js/mermaid-cli mmdc \
        -i "$src" \
        -o "$out" \
        -b transparent \
        -w "$render_w" > "$log" 2>&1; then
        tail -1 "$log"; rm -f "$log"
    else
        echo "  ✗ mmdc-Render fehlgeschlagen für $name:" >&2
        tail -8 "$log" >&2
        rm -f "$log"
        exit 1
    fi
    # Post-process: width="100%" durch viewBox-Breite ersetzen, sodass die SVG
    # eine intrinsische Pixel-Breite hat (sonst kollabiert sie in <img>-Tags
    # ohne expliziten Container, z.B. in der Lightbox).
    if [ -f "$out" ]; then
        vb_w=$(grep -oP 'viewBox="[^"]*"' "$out" | head -1 | grep -oP '[\d.]+' | sed -n '3p' | cut -d. -f1)
        if [ -n "$vb_w" ]; then
            sed -i "0,/width=\"100%\"/s//width=\"${vb_w}\"/" "$out"
        fi
    fi
    count=$((count + 1))
done

echo ""
echo "✓ $count Diagramme gerendert nach $TARGET/"
