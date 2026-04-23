#!/bin/bash
# Flashscore Ratings — terminal runner (no UI)
# Use this if the main UI doesn't start for any reason.

set -u

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$APP_DIR/_DO NOT TOUCH_"

export PYTHONIOENCODING="utf-8"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

# Read pinned Python path
PY_BIN=""
if [ -f "$SCRIPTS_DIR/.python_path" ]; then
    PY_BIN="$(cat "$SCRIPTS_DIR/.python_path")"
    [ ! -x "$PY_BIN" ] && PY_BIN=""
fi

if [ -z "$PY_BIN" ]; then
    for C in \
        /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        /usr/bin/python3
    do
        if [ -x "$C" ]; then PY_BIN="$C"; break; fi
    done
fi

if [ -z "$PY_BIN" ]; then
    echo "Python not found. Run INSTALL_MAC.command first."
    read -r -p "Press Enter to close..."
    exit 1
fi

clear 2>/dev/null || true
echo ""
echo "  Flashscore Ratings — Terminal Mode"
echo "  ------------------------------------"
echo ""

LAST_URL_FILE="$SCRIPTS_DIR/flashscore_output/last_url.txt"

URL=""
if [ "${1:-}" != "" ]; then
    URL="$1"
elif [ -f "$LAST_URL_FILE" ]; then
    URL="$(cat "$LAST_URL_FILE")"
    echo "  Using saved URL: $URL"
    echo ""
    read -r -p "  Press Enter to use it, or paste a new URL: " INPUT
    if [ -n "$INPUT" ]; then URL="$INPUT"; fi
fi

if [ -z "$URL" ]; then
    read -r -p "  Paste Flashscore match URL: " URL
fi

if [ -z "$URL" ]; then
    echo "  No URL given — aborting."
    read -r -p "  Press Enter to close..."
    exit 1
fi

echo ""
echo "  ▶ Running full scrape..."
echo ""

exec "$PY_BIN" "$SCRIPTS_DIR/run.py" "$URL"
