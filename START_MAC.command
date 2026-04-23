#!/bin/bash
# Flashscore Ratings — macOS launcher
# Double-click this to open the app.

set -u

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$APP_DIR/_DO NOT TOUCH_"

export PYTHONIOENCODING="utf-8"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

# Read pinned Python path set by INSTALL_MAC.command
PY_BIN=""
if [ -f "$SCRIPTS_DIR/.python_path" ]; then
    PY_BIN="$(cat "$SCRIPTS_DIR/.python_path")"
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
    osascript -e 'display alert "Python not found" message "Please run INSTALL_MAC.command first." as warning'
    exit 1
fi

if [ ! -f "$SCRIPTS_DIR/launcher.py" ]; then
    osascript -e 'display alert "App files not found" message "Please run INSTALL_MAC.command first." as warning'
    exit 1
fi

exec "$PY_BIN" "$SCRIPTS_DIR/launcher.py"
