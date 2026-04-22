#!/bin/bash
# Flashscore Ratings - macOS launcher
set -u

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR" || exit 1

export PYTHONIOENCODING="utf-8"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

# Use the Python pinned by INSTALL_MAC.command (has Tk 8.6 for proper UI).
PY_BIN=""
if [ -f "$APP_DIR/.python_path" ]; then
    PY_BIN="$(cat "$APP_DIR/.python_path")"
    [ ! -x "$PY_BIN" ] && PY_BIN=""
fi

# Fallbacks if pin is missing or stale
if [ -z "$PY_BIN" ]; then
    for C in \
        /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        /usr/bin/python3
    do
        if [ -x "$C" ]; then
            PY_BIN="$C"
            break
        fi
    done
fi

if [ -z "$PY_BIN" ]; then
    echo "Python not found. Run INSTALL_MAC.command first."
    read -r -p "Press Enter to close..."
    exit 1
fi

# Launch the app silently (GUI takes over)
exec "$PY_BIN" "$APP_DIR/launcher.py"
