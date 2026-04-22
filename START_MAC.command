#!/bin/bash
# Flashscore Ratings — macOS launcher
set -u

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR" || exit 1

export PYTHONIOENCODING="utf-8"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

# Use the Python pinned by the installer (has proper Tk for clean UI).
# Fall back to first python3 found if the pin file is missing.
PY_BIN=""
if [ -f "$APP_DIR/.python_path" ]; then
    PY_BIN="$(cat "$APP_DIR/.python_path")"
    [ ! -x "$PY_BIN" ] && PY_BIN=""
fi

if [ -z "$PY_BIN" ]; then
    for C in /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 \
             /usr/local/bin/python3.12 /usr/local/bin/python3 python3; do
        if command -v "$C" >/dev/null 2>&1; then
            PY_BIN="$(command -v "$C")"
            break
        fi
    done
fi

if [ -z "$PY_BIN" ]; then
    echo "Python not found. Run INSTALL_MAC.command first."
    read -p "Press Enter to close…"
    exit 1
fi

# Launch the app silently (GUI takes over)
exec "$PY_BIN" "$APP_DIR/launcher.py"
