#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
# run_luDBxP_docs.sh – LucentTools DB Explorer Dokumentation
#
# Eigenes .venv-docs, unabhängig von anderen venvs.
# Wird vom Hub als Kindprozess gestartet oder manuell ausgeführt.
#
# Verwendung:
#   ./run_luDBxP_docs.sh                   → Live-Server (Port 8046)
#   ./run_luDBxP_docs.sh --port=8046       → Live-Server auf Port 8046
#   ./run_luDBxP_docs.sh --build           → Statisches HTML nach site/
#   ./run_luDBxP_docs.sh --check           → Nur Struktur prüfen
#   ./run_luDBxP_docs.sh --clean           → .venv-docs löschen und neu
# ══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv-docs"
PYTHON="python3"
PORT=8046

# ── Flags parsen ──────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --port=*)  PORT="${arg#*=}" ;;
    --build)   BUILD=true ;;
    --check)   CHECK=true ;;
    --clean)   CLEAN=true ;;
  esac
done

# ── Farben ────────────────────────────────────────────────────
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${CYAN}  ▸ $*${NC}"; }
success() { echo -e "${GREEN}  ✓ $*${NC}"; }
warn()    { echo -e "${YELLOW}  ⚠ $*${NC}"; }
error()   { echo -e "${RED}  ✗ $*${NC}"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   LucentTools DB Explorer – Dokumentation     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── --clean ───────────────────────────────────────────────────
if [[ "${CLEAN:-}" == "true" ]]; then
  [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR" && success ".venv-docs gelöscht."
fi

# ── Python prüfen ─────────────────────────────────────────────
command -v "$PYTHON" &>/dev/null || error "python3 nicht gefunden."
PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PY_VERSION gefunden"

# ── .venv-docs erstellen ──────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  info "Erstelle .venv-docs …"
  "$PYTHON" -m venv "$VENV_DIR"
  success ".venv-docs erstellt."
fi

source "$VENV_DIR/bin/activate"
info ".venv-docs aktiviert"

# ── Zensical installieren ─────────────────────────────────────
if ! pip show zensical &>/dev/null 2>&1; then
  info "Installiere Zensical …"
  pip install --quiet --upgrade pip
  pip install --quiet zensical
  success "Zensical installiert."
else
  success "Zensical bereits vorhanden."
fi

ZEN_VER=$(zensical --version 2>/dev/null | head -1 || echo "unbekannt")
info "Zensical: $ZEN_VER"
echo ""

# ── Aktion ausführen ──────────────────────────────────────────
cd "$SCRIPT_DIR"

if [[ "${CHECK:-}" == "true" ]]; then
  python3 build_docs.py --check

elif [[ "${BUILD:-}" == "true" ]]; then
  [ -d "$SCRIPT_DIR/site" ] && rm -rf "$SCRIPT_DIR/site"
  info "Baue statische Dokumentation …"
  python3 build_docs.py
  echo -e "   Öffnen: ${CYAN}file://$SCRIPT_DIR/site/index.html${NC}"

else
  [ -d "$SCRIPT_DIR/site" ] && rm -rf "$SCRIPT_DIR/site"
  info "Starte Live-Server auf Port $PORT …"
  echo ""
  echo -e "   ${GREEN}http://127.0.0.1:$PORT${NC}  (Ctrl+C zum Beenden)"
  echo ""
  python3 build_docs.py --serve --port "$PORT"
fi
