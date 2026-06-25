#!/usr/bin/env bash
# Lucent DB Explorer launcher.
# Run with no argument for an interactive menu; pass a flag for direct,
# non-interactive actions (the hub calls --skip-setup / --setup-venv).
set -euo pipefail
cd "$(dirname "$0")"

VENV=venv
PY=python3
STAMP=.req_stamp

pick_python() {
  for v in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$v" >/dev/null 2>&1; then PY="$v"; return; fi
  done
}

setup_venv() {
  pick_python
  [ -d "$VENV" ] || "$PY" -m venv "$VENV"
  NEW_HASH="$(md5sum requirements.txt | cut -d' ' -f1)"
  if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$NEW_HASH" ]; then
    ./"$VENV"/bin/pip install -r requirements.txt
    echo "$NEW_HASH" > "$STAMP"
  fi
}

# --- Actions (shared by the flags and the menu) ---------------------------
do_start()      { setup_venv; ./"$VENV"/bin/python app.py || true; }
do_setup_venv() { setup_venv; }
do_skip_setup() { ./"$VENV"/bin/python app.py || true; }
do_clean()      { rm -rf "$VENV" "$STAMP"; setup_venv; }
do_version()    { ./"$VENV"/bin/python -c "import config; print(config.APP_VERSION)"; }

do_tests() {
  setup_venv
  ./"$VENV"/bin/pip install -q -r requirements-dev.txt
  ./"$VENV"/bin/python -m pytest
}

do_demo_db() {
  pick_python
  "$PY" sample_data/build_demo_db.py
}

# --- Interactive menu -----------------------------------------------------
show_menu() {
  echo ""
  echo "  Lucent DB Explorer"
  echo "  =================="
  echo "  1) App starten (Setup, falls nötig)"
  echo "  2) Nur Umgebung einrichten (venv + pip)"
  echo "  3) App schnell starten (ohne Setup-Check)"
  echo "  4) Umgebung neu aufbauen (clean)"
  echo "  5) Tests ausführen"
  echo "  6) Demo-DB neu erzeugen"
  echo "  7) Version anzeigen"
  echo "  0) Beenden"
  echo ""
}

menu_loop() {
  while true; do
    show_menu
    read -rp "  Auswahl: " choice || { echo; exit 0; }
    case "$choice" in
      1) do_start ;;
      2) do_setup_venv; echo "  Umgebung bereit." ;;
      3) do_skip_setup ;;
      4) do_clean; echo "  Umgebung neu aufgebaut." ;;
      5) do_tests ;;
      6) do_demo_db ;;
      7) do_version ;;
      0) exit 0 ;;
      *) echo "  Ungültige Auswahl: $choice" ;;
    esac
  done
}

# --- Dispatch -------------------------------------------------------------
case "${1:-MENU}" in
  --setup-venv) do_setup_venv ;;
  --version)    do_version ;;
  --clean)      do_clean ;;
  --skip-setup) do_skip_setup ;;
  --tests)      do_tests ;;
  --demo-db)    do_demo_db ;;
  --start|"")   do_start ;;
  MENU)         menu_loop ;;
  --help|-h)
    echo "Usage: run.sh [--start|--setup-venv|--skip-setup|--clean|--tests|--demo-db|--version]"
    echo "       run.sh            (no argument: interactive menu)"
    ;;
  *) echo "Unbekannte Option: $1 (siehe --help)"; exit 1 ;;
esac
