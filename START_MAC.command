#!/bin/bash
# Flashscore Ratings — macOS launcher (stock Python)
set -u

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR" || exit 1

export PYTHONIOENCODING="utf-8"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

PY_BIN="/usr/bin/python3"

if [ ! -x "$PY_BIN" ]; then
    echo "Python not found. Run INSTALL_MAC.command first."
    read -p "Press Enter to close…"
    exit 1
fi

# Launch the app silently (GUI takes over)
exec "$PY_BIN" "$APP_DIR/launcher.py"
