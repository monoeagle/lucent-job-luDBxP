#!/usr/bin/env bash
# LucentTools DB Explorer launcher.
# Run with no argument for an interactive menu; pass a flag for direct,
# non-interactive actions (the hub calls --skip-setup / --setup-venv).
set -euo pipefail
cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

VENV=venv
PY=python3
STAMP=.req_stamp
VENV_PY="$VENV/bin/python"
VENV_PIP="$VENV/bin/pip"
PORT=5057

# Offline-Wheelhouse (gebundelte Wheels). run.ps1 installiert daraus STRIKT
# offline (Windows-Ziel = air-gapped RDS, Python 3.14 → cp314/win_amd64-Wheels).
# Auf Linux sind diese Wheels nicht nutzbar; daher hier adaptiv (siehe
# install_requirements): offline, wenn ein plattform-kompatibles Wheelhouse
# vorliegt, sonst Online-Install mit deutlicher Warnung.
WHEELS="$SCRIPT_DIR/wheels"

# ── AppImage-Variablen ────────────────────────────────────────────────────────
APPIMAGE_BUILD="$SCRIPT_DIR/build/appimage"
APPIMAGES_OUT_DIR="/home/meagle/Dokumente/_Projects/AppImages"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
APPIMAGETOOL="$SCRIPT_DIR/.tools/appimagetool"

# ── Konsolen-Helfer (für AppImage-Build-Output) ───────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'
_ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
_warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
_fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }
_info() { echo -e "  ${CYAN}→${NC} $1"; }
_hdr()  { echo -e "\n${BOLD}=== $1 ===${NC}\n"; }

pick_python() {
  for v in python3.14 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$v" >/dev/null 2>&1; then PY="$v"; return; fi
  done
}

# AP-15: venv-Integritaet pruefen, nicht nur Existenz. Ein mittendrin
# abgebrochenes `python -m venv` hinterlaesst ggf. ein Verzeichnis ohne
# funktionsfaehigen Interpreter — das wuerde ein blosses [ -d ] uebersehen.
venv_healthy() {
  [ -x "$VENV_PY" ] && "$VENV_PY" -c 'import sys' >/dev/null 2>&1
}

# AP-15: sind alle Laufzeit-Pakete installiert und konsistent?
# Zweistufig, weil `pip check` allein nicht ausreicht: es prueft nur die
# Konsistenz des bereits Installierten und ist auf einem LEEREN venv vacuously
# gruen. Daher zusaetzlich pruefen, dass jede in requirements.txt gelistete
# Distribution wirklich vorhanden ist (importlib.metadata, PEP-503-normalisiert).
# Faengt sowohl einen abgebrochenen pip-Install (Stamp fehlt) als auch ein
# frisch gebautes, noch leeres venv mit passendem Alt-Stamp.
requirements_installed() {
  [ -x "$VENV_PIP" ] || return 1
  "$VENV_PIP" check >/dev/null 2>&1 || return 1
  "$VENV_PY" - requirements.txt <<'PY'
import sys, re, importlib.metadata as md
ok = True
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    name = re.split(r"[<>=!~;\[\s]", line, 1)[0].strip()
    if not name:
        continue
    try:
        md.version(name)
    except md.PackageNotFoundError:
        ok = False
        break
sys.exit(0 if ok else 1)
PY
}

# AP-15: Port-Check (Paritaet zu run.ps1 Test-PortFree). 0 = frei.
port_free() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ! ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE ":${p}\$"
  elif command -v lsof >/dev/null 2>&1; then
    ! lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 0   # kein Check moeglich → Port als frei annehmen
  fi
}

# AP-15 / NO-CDN (adaptiv): Erst STRIKT offline aus dem lokalen Wheelhouse
# versuchen (--no-index --dry-run-Probe, kein Netz). Deckt das Wheelhouse die
# Anforderungen fuer diese Plattform ab → Offline-Install. Sonst — z. B.
# win_amd64-Wheels auf Linux — lauter Fallback auf Online-pip. So bleibt der
# NO-CDN-Pfad erhalten und schaltet automatisch, sobald ein passendes
# Linux-Wheelhouse vorliegt; kein stilles Online-Nachladen.
install_requirements() {
  local reqfile="$1"
  if [ -d "$WHEELS" ]; then
    _info "Pruefe lokales Wheelhouse fuer $reqfile (--no-index Dry-Run, kein Netz)..."
    if "$VENV_PIP" install --no-index --find-links "$WHEELS" --dry-run -r "$reqfile" >/dev/null 2>&1; then
      _ok "alle benoetigten Wheels lokal vorhanden — Offline-Install (kein Netz): $reqfile"
      "$VENV_PIP" install --no-index --find-links "$WHEELS" -r "$reqfile"
      return
    fi
    _warn "Wheelhouse deckt $reqfile auf dieser Plattform nicht ab (z. B. win_amd64-Wheels auf Linux)."
  else
    _warn "Kein Wheelhouse (wheels/) vorhanden."
  fi
  _warn "Fallback: Online-Install aus PyPI fuer $reqfile (Offline-Pfad nicht verfuegbar)."
  "$VENV_PIP" install -r "$reqfile"
}

# AP-15: idempotenter, selbstheilender Setup-Schritt. Prueft jede Vorbedingung
# und zieht nur das Fehlende nach. Der Stamp wird erst NACH erfolgreichem
# Install + pip-check geschrieben (atomar): bricht der Install ab, bleibt der
# Stamp aus, sodass der naechste Lauf ihn wiederholt.
ensure_venv() {
  _hdr "Umgebung pruefen"

  if venv_healthy; then
    _ok "venv funktionsfaehig"
  else
    if [ -d "$VENV" ]; then
      _warn "venv unvollstaendig/kaputt — wird neu aufgebaut"
      rm -rf "$VENV"
    fi
    pick_python
    _info "venv anlegen ($PY)..."
    "$PY" -m venv "$VENV"
    venv_healthy || _fail "venv-Erstellung fehlgeschlagen."
    # Frisches venv hat keine Pakete: alten Stamp invalidieren, sonst greift
    # unten faelschlich der "Stamp passt"-Zweig (pip check ist auf einem leeren
    # venv vacuously gruen) und es wird NICHT installiert.
    rm -f "$STAMP"
    _ok "venv angelegt"
  fi

  local new_hash old_hash need_install=0
  new_hash="$(md5sum requirements.txt | cut -d' ' -f1)"
  old_hash=""
  [ -f "$STAMP" ] && old_hash="$(tr -d '[:space:]' < "$STAMP")"
  if [ "$new_hash" != "$old_hash" ]; then
    _info "requirements.txt geaendert (oder Erstinstallation)"
    need_install=1
  elif ! requirements_installed; then
    _warn "Pakete unvollstaendig (pip check) — Reparatur-Install"
    need_install=1
  else
    _ok "Laufzeit-Pakete vollstaendig"
  fi

  if [ "$need_install" -eq 1 ]; then
    rm -f "$STAMP"   # erst nach Erfolg wieder schreiben
    install_requirements requirements.txt
    requirements_installed || _fail "Pakete nach Install weiterhin inkonsistent (pip check)."
    echo "$new_hash" > "$STAMP"
    _ok "Laufzeit-Pakete installiert"
  fi
}

start_app() {
  _hdr "App starten"
  venv_healthy || _fail "venv nicht funktionsfaehig — bitte zuerst 'bash run.sh --setup-venv'."
  if ! port_free "$PORT"; then
    _warn "Port $PORT ist bereits belegt — laeuft schon eine Instanz? Start abgebrochen."
    return 0
  fi
  if [ "${DEBUG_MODE:-0}" = "1" ]; then
    export LUCENT_DEBUG=1
    _info "Debug-Modus aktiv (LUCENT_DEBUG=1)"
  fi
  _info "Starte http://127.0.0.1:$PORT/  (Strg+C zum Beenden)"
  local code=0
  "$VENV_PY" app.py || code=$?
  [ "$code" -ne 0 ] && _warn "App beendet mit Exit-Code $code"
  return "$code"
}

# --- Actions (shared by the flags and the menu) ---------------------------
do_start()      { ensure_venv; start_app; }
do_setup_venv() { ensure_venv; _ok "Umgebung bereit."; }
do_skip_setup() {
  venv_healthy || _fail "venv fehlt/kaputt — bitte zuerst 'bash run.sh --setup-venv'."
  start_app
}
do_clean() {
  _hdr "Umgebung neu aufbauen"
  [ -d "$VENV" ] && { _info "venv entfernen..."; rm -rf "$VENV"; }
  rm -f "$STAMP"
  ensure_venv
  _ok "Umgebung neu aufgebaut."
}
do_version() {
  venv_healthy || _fail "venv nicht funktionsfaehig — bitte zuerst 'setup-venv'."
  "$VENV_PY" -c "import config; print(config.APP_VERSION)"
}

do_tests() {
  ensure_venv
  _hdr "Tests"
  if "$VENV_PY" -c 'import pytest' >/dev/null 2>&1; then
    _ok "Test-Abhaengigkeiten vorhanden"
  else
    install_requirements requirements-dev.txt
  fi
  "$VENV_PY" -m pytest
}

do_demo_db() {
  _hdr "Demo-DB erzeugen"
  pick_python
  "$PY" sample_data/build_demo_db.py
}

# ── AppImage-Build ────────────────────────────────────────────────────────────

_ensure_appimagetool() {
  if [ -x "$APPIMAGETOOL" ]; then return 0; fi
  _info "appimagetool wird heruntergeladen..."
  mkdir -p "$(dirname "$APPIMAGETOOL")"
  curl -fsSL "$APPIMAGETOOL_URL" -o "$APPIMAGETOOL"
  chmod +x "$APPIMAGETOOL"
  _ok "appimagetool installiert unter .tools/"
}

_bundle_python_standalone() {
  local appdir="$1"
  local venv_dir="$2"

  local py_ver
  py_ver=$("$venv_dir/bin/python3" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  local real_py
  real_py="$(readlink -f "$venv_dir/bin/python3")"
  local py_base
  py_base=$("$venv_dir/bin/python3" -c 'import sys; print(sys.base_prefix)')

  _info "Python ${py_ver} standalone buendeln..."

  mkdir -p "$appdir/python/bin"
  mkdir -p "$appdir/python/lib/python${py_ver}"

  cp "$real_py" "$appdir/python/bin/python3"
  chmod +x "$appdir/python/bin/python3"
  ln -sf python3 "$appdir/python/bin/python"

  _info "Python stdlib kopieren..."
  cp -r "${py_base}/lib/python${py_ver}/"* "$appdir/python/lib/python${py_ver}/" 2>/dev/null || true

  _info "Site-packages kopieren..."
  if [ -d "$venv_dir/lib/python${py_ver}/site-packages" ]; then
    cp -r "$venv_dir/lib/python${py_ver}/site-packages" "$appdir/python/lib/python${py_ver}/"
  fi

  # libpython3.x.so
  for pattern in \
    "/usr/lib/x86_64-linux-gnu/libpython${py_ver}"*.so* \
    "/usr/lib/libpython${py_ver}"*.so* \
    "${py_base}/lib/libpython${py_ver}"*.so*; do
    for lib in $pattern; do
      [ -f "$lib" ] && cp -L "$lib" "$appdir/python/lib/" 2>/dev/null || true
    done
  done

  _info "System-Bibliotheken buendeln..."
  for libname in libssl libcrypto libffi libz libsqlite3 libncurses libtinfo libreadline libbz2 liblzma libexpat libmpdec; do
    for f in /usr/lib/x86_64-linux-gnu/${libname}*.so*; do
      [ -f "$f" ] && cp -L "$f" "$appdir/python/lib/" 2>/dev/null || true
    done
  done

  _info "Shared-Library-Abhaengigkeiten scannen (ldd)..."
  local _deplist
  _deplist=$(find "$appdir/python" -name "*.so*" -type f \
    -exec ldd {} 2>/dev/null \; \
    | grep "=> /" | awk '{print $3}' | sort -u || true)
  local _copied=0
  for dep in $_deplist; do
    [ -f "$dep" ] || continue
    local _bn
    _bn=$(basename "$dep")
    case "$_bn" in
      libc.so*|libm.so*|libdl.so*|librt.so*|libpthread.so*) continue ;;
      ld-linux*|libgcc_s.so*|libstdc++.so*)                  continue ;;
      libnss_*|libresolv.so*|libnsl.so*|libutil.so*)         continue ;;
      linux-vdso.so*)                                         continue ;;
    esac
    if [ ! -f "$appdir/python/lib/$_bn" ]; then
      cp -L "$dep" "$appdir/python/lib/" 2>/dev/null && _copied=$((_copied + 1)) || true
    fi
  done
  for _syslib in libc.so* libm.so* libdl.so* librt.so* libpthread.so* \
                 ld-linux* libgcc_s.so* libstdc++.so* \
                 libnss_* libresolv.so* libnsl.so* libutil.so*; do
    rm -f "$appdir/python/lib/"$_syslib 2>/dev/null || true
  done
  _info "$_copied zusaetzliche Shared Libraries gebundelt"
  _ok "Python ${py_ver} standalone gebundelt"
}

cmd_appimage() {
  _hdr "LucentTools DB Explorer AppImage Build"

  if [ ! -d "$SCRIPT_DIR/$VENV" ]; then
    _fail "venv nicht vorhanden — bitte zuerst 'bash run.sh --setup-venv' ausfuehren"
  fi

  _ensure_appimagetool

  local app_version
  app_version=$("./$VENV/bin/python3" -c "import config; print(config.APP_VERSION)" 2>/dev/null \
    || echo "0.1.0")

  local appdir="$APPIMAGE_BUILD/LucentDBExplorer.AppDir"
  local appimage_name="LucentDBExplorer-${app_version}-x86_64.AppImage"
  local output="$SCRIPT_DIR/build/${appimage_name}"

  _info "AppDir vorbereiten..."
  rm -rf "$appdir"
  mkdir -p "$appdir/usr/share/icons/hicolor/256x256/apps"
  mkdir -p "$appdir/usr/share/applications"
  mkdir -p "$appdir/app"

  _info "App-Sourcen kopieren..."
  cp "$SCRIPT_DIR/app.py"      "$appdir/app/"
  cp "$SCRIPT_DIR/config.py"   "$appdir/app/"
  cp "$SCRIPT_DIR/config.json" "$appdir/app/"
  cp "$SCRIPT_DIR/strings.py"  "$appdir/app/"
  cp -r "$SCRIPT_DIR/core"     "$appdir/app/"
  cp -r "$SCRIPT_DIR/web"      "$appdir/app/"
  mkdir -p "$appdir/app/sample_data"
  for db in "$SCRIPT_DIR/sample_data/"*.db; do
    [ -f "$db" ] && cp "$db" "$appdir/app/sample_data/" || true
  done
  find "$appdir/app" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

  _bundle_python_standalone "$appdir" "$SCRIPT_DIR/$VENV"

  _info "Icon kopieren..."
  if [ -f "$SCRIPT_DIR/lucent-db-explorer.svg" ]; then
    cp "$SCRIPT_DIR/lucent-db-explorer.svg" \
       "$appdir/usr/share/icons/hicolor/256x256/apps/lucent-db-explorer.svg"
    cp "$SCRIPT_DIR/lucent-db-explorer.svg" "$appdir/lucent-db-explorer.svg"
  else
    cat > "$appdir/lucent-db-explorer.svg" << 'SVGEOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="40" fill="#0D1B2A"/>
  <ellipse cx="128" cy="86" rx="58" ry="16" fill="none" stroke="#4A9EFF" stroke-width="3.5"/>
  <line x1="70" y1="86" x2="70" y2="162" stroke="#4A9EFF" stroke-width="3.5"/>
  <line x1="186" y1="86" x2="186" y2="162" stroke="#4A9EFF" stroke-width="3.5"/>
  <ellipse cx="128" cy="162" rx="58" ry="16" fill="none" stroke="#4A9EFF" stroke-width="3.5"/>
  <circle cx="210" cy="64" r="7" fill="#00D4FF"/>
  <circle cx="46"  cy="64" r="7" fill="#00D4FF"/>
  <line x1="128" y1="70" x2="210" y2="64" stroke="#00D4FF" stroke-width="1.8"/>
  <line x1="128" y1="70" x2="46"  y2="64" stroke="#00D4FF" stroke-width="1.8"/>
</svg>
SVGEOF
    cp "$appdir/lucent-db-explorer.svg" \
       "$appdir/usr/share/icons/hicolor/256x256/apps/lucent-db-explorer.svg"
  fi

  cat > "$appdir/lucent-db-explorer.desktop" << DEOF
[Desktop Entry]
Type=Application
Name=LucentTools DB Explorer
Comment=Database schema explorer with graph visualization
Exec=AppRun
Icon=lucent-db-explorer
Categories=Development;Database;
Terminal=false
DEOF
  cp "$appdir/lucent-db-explorer.desktop" "$appdir/usr/share/applications/"

  cat > "$appdir/AppRun" << 'RUNEOF'
#!/usr/bin/env bash
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
HERE="$(dirname "$SELF")"

PORT=5057
DATA_DIR="$HOME/.lucent-db-explorer"

for arg in "$@"; do
  case "$arg" in
    --port=*)     PORT="${arg#--port=}" ;;
    --data-dir=*) DATA_DIR="${arg#--data-dir=}" ;;
  esac
done

# Schreibbares Arbeitsverzeichnis: App-Sourcen beim Erststart kopieren
# (AppDir ist read-only; config.py leitet BASE_DIR aus __file__ ab →
#  läuft die App aus APP_WORK, ist config.json/Logs darin schreibbar)
APP_WORK="${DATA_DIR}/app"
if [ ! -f "$APP_WORK/app.py" ]; then
  echo "[AppImage] Erstinstallation: App-Dateien nach ${APP_WORK} kopieren..."
  mkdir -p "$APP_WORK"
  cp -r "${HERE}/app/"* "$APP_WORK/"
fi

mkdir -p "$APP_WORK/Logs"

export PATH="${HERE}/python/bin:${PATH}"
export PYTHONHOME="${HERE}/python"
export LD_LIBRARY_PATH="${HERE}/python/lib:${LD_LIBRARY_PATH:-}"
PY_VER=$(ls -1 "${HERE}/python/lib/" | grep "^python3\." | head -1 | sed "s/python//")
export PYTHONPATH="${HERE}/python/lib/python${PY_VER}/site-packages"

cleanup() { [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null; exit 0; }
trap cleanup SIGTERM SIGINT

cd "$APP_WORK"
"${HERE}/python/bin/python3" app.py &
SERVER_PID=$!

echo "[AppImage] Warte auf http://127.0.0.1:${PORT}/ ..."
for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${PORT}/" > /dev/null 2>&1; then
    echo "[AppImage] Server bereit."
    break
  fi
  sleep 0.5
done

xdg-open "http://127.0.0.1:${PORT}/" 2>/dev/null || true

wait "$SERVER_PID"
RUNEOF
  chmod +x "$appdir/AppRun"

  mkdir -p "$SCRIPT_DIR/build"
  _info "AppImage erzeugen (${appimage_name})..."
  ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$appdir" "$output" 2>&1 | tail -5 \
    || ARCH=x86_64 "$APPIMAGETOOL" "$appdir" "$output" 2>&1 | tail -5
  _ok "AppImage erstellt: ${BOLD}${output}${NC}"

  mkdir -p "$APPIMAGES_OUT_DIR"
  cp "$output" "$APPIMAGES_OUT_DIR/"
  _ok "Kopiert nach ${BOLD}${APPIMAGES_OUT_DIR}/${appimage_name}${NC}"

  cat > "$APPIMAGES_OUT_DIR/LucentDBExplorer.yml" << YMLEOF
name: lucent-db-explorer
display_name: "LucentTools DB Explorer"
version: "${app_version}"
description: "Database schema explorer with graph visualization"
port: 5057
health_endpoint: /
theme_color: "#4A9EFF"
category: "development"
auto_start: false
appimage: "${appimage_name}"
YMLEOF
  _ok "Sidecar: ${BOLD}${APPIMAGES_OUT_DIR}/LucentDBExplorer.yml${NC}"
}

# --- Interactive menu -----------------------------------------------------
show_menu() {
  echo ""
  echo "  LucentTools DB Explorer"
  echo "  =================="
  echo "  1) App starten (Setup, falls nötig)"
  echo "  2) Nur Umgebung einrichten (venv + pip)"
  echo "  3) App schnell starten (ohne Setup-Check)"
  echo "  4) Umgebung neu aufbauen (clean)"
  echo "  5) Tests ausführen"
  echo "  6) Demo-DB neu erzeugen"
  echo "  7) Version anzeigen"
  echo "  8) AppImage bauen"
  echo "  0) Beenden"
  echo ""
}

menu_loop() {
  while true; do
    show_menu
    read -rp "  Auswahl: " choice || { echo; exit 0; }
    # AP-15: ein fehlgeschlagener Schritt (_fail → exit) darf das Menue nicht
    # beenden. Die Aktion laeuft in einer Subshell; deren Abbruch faengt das
    # `|| _warn` ab (bash-Pendant zum try/catch in run.ps1).
    case "$choice" in
      1) ( do_start )      || _warn "Abgebrochen." ;;
      2) ( do_setup_venv ) || _warn "Abgebrochen." ;;
      3) ( do_skip_setup ) || _warn "Abgebrochen." ;;
      4) ( do_clean )      || _warn "Abgebrochen." ;;
      5) ( do_tests )      || _warn "Abgebrochen." ;;
      6) ( do_demo_db )    || _warn "Abgebrochen." ;;
      7) ( do_version )    || _warn "Abgebrochen." ;;
      8) ( cmd_appimage )  || _warn "Abgebrochen." ;;
      0) exit 0 ;;
      *) echo "  Ungültige Auswahl: $choice" ;;
    esac
  done
}

# --- Dispatch -------------------------------------------------------------
# --debug (Pendant zu run.ps1 -DebugMode) ist mit --start/--skip-setup
# kombinierbar; aus der Argumentliste herausfiltern, Rest = Aktion.
DEBUG_MODE=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --debug|-d) DEBUG_MODE=1 ;;
    *)          ARGS+=("$a") ;;
  esac
done
set -- "${ARGS[@]+"${ARGS[@]}"}"

case "${1:-MENU}" in
  --appimage)   cmd_appimage ;;
  --setup-venv) do_setup_venv ;;
  --version)    do_version ;;
  --clean)      do_clean ;;
  --skip-setup) do_skip_setup ;;
  --tests)      do_tests ;;
  --demo-db)    do_demo_db ;;
  --start|"")   do_start ;;
  MENU)         menu_loop ;;
  --help|-h)
    echo "Usage: run.sh [--start|--setup-venv|--skip-setup|--clean|--tests|--demo-db|--version|--appimage] [--debug]"
    echo "       run.sh            (kein Argument: interaktives Menue)"
    echo "       --debug           Flask-Debug-Modus (LUCENT_DEBUG=1), mit --start/--skip-setup"
    ;;
  *) echo "Unbekannte Option: $1 (siehe --help)"; exit 1 ;;
esac
