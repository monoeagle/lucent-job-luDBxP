#!/usr/bin/env bash
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

case "${1:-}" in
  --setup-venv) setup_venv ;;
  --version)    ./"$VENV"/bin/python -c "import config; print(config.APP_VERSION)" ;;
  --clean)      rm -rf "$VENV" "$STAMP"; setup_venv ;;
  --skip-setup) ./"$VENV"/bin/python app.py ;;
  *)            setup_venv; ./"$VENV"/bin/python app.py ;;
esac
