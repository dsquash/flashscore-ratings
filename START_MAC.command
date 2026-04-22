#!/bin/bash
# ============================================================
#   Flashscore Ratings — Launcher (macOS)
# ============================================================

set -u

# Always run from the folder this script lives in
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR" || exit 1

# Force UTF-8 so output/prints render correctly
export PYTHONIOENCODING="utf-8"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

echo ""
echo " ============================================================"
echo "   Flashscore Ratings — Starting..."
echo " ============================================================"
echo ""

# ── Step 1: Python available? ────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
    echo " [ERROR] Python 3 is not installed or not on PATH."
    echo "         Run INSTALL_MAC.command first."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi
echo " [OK] Python found: $(python3 --version)"

# ── Step 2: Required packages present? ───────────────────────
if ! python3 -c "import playwright, httpx, PIL" >/dev/null 2>&1; then
    echo " [INFO] Installing missing Python packages..."
    python3 -m pip install --quiet --break-system-packages playwright httpx pillow 2>/dev/null \
      || python3 -m pip install --quiet playwright httpx pillow
    python3 -m playwright install chromium
fi
echo " [OK] Packages installed."

# ── Step 3: AE panel installed? (best-effort, non-fatal) ─────
PANEL_SRC="$APP_DIR/Lineup Panel.jsx"
if [ -f "$PANEL_SRC" ]; then
    for AE_DIR in "/Applications/Adobe After Effects "*; do
        if [ -d "$AE_DIR" ]; then
            PANEL_DST="$AE_DIR/Scripts/ScriptUI Panels"
            [ ! -d "$PANEL_DST" ] && mkdir -p "$PANEL_DST" 2>/dev/null
            if [ -d "$PANEL_DST" ] && [ ! -f "$PANEL_DST/Lineup Panel.jsx" ]; then
                cp "$PANEL_SRC" "$PANEL_DST/" 2>/dev/null && \
                  echo " [OK] AE panel installed: $AE_DIR"
            fi
        fi
    done
fi

# ── Step 4: Launch app ───────────────────────────────────────
echo ""
echo " Launching app..."
echo ""
python3 "$APP_DIR/launcher.py"
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -ne 0 ]; then
    echo " [WARNING] App exited with code $EXIT_CODE"
    read -p "Press Enter to close..."
fi
