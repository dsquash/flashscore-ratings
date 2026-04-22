#!/bin/bash
# ============================================================
#   Flashscore Ratings — Installer (macOS)
#   Downloads only Mac-relevant files from GitHub + AE template.
# ============================================================

set -u

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$INSTALL_DIR" || exit 1

GITHUB_OWNER="dsquash"
GITHUB_REPO="flashscore-ratings"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${BRANCH}"

GDRIVE_FOLDER_ID="1OwZoHfrUxtAZtS042g63Pqw0eSqP31Ti"

# Files downloaded on macOS. Intentionally excludes Windows-only:
#   INSTALL.bat, START HERE.bat
MAC_FILES=(
    "launcher.py"
    "run.py"
    "refresh_stats.py"
    "updater.py"
    "populate_lineup.jsx"
    "reset_lineup.jsx"
    "refresh_comps.jsx"
    "save_template_state.jsx"
    "Lineup Panel.jsx"
    "sofifa_overrides.json"
    "INSTALL_MAC.command"
    "START_MAC.command"
    "CHANGELOG.md"
    "version.txt"
)

echo ""
echo " ============================================================"
echo "   Flashscore Ratings — Installer (macOS)"
echo " ============================================================"
echo ""

# ── Check / Install Python 3 ─────────────────────────────────
PY_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
fi

if [ -z "$PY_BIN" ]; then
    echo " [INFO] Python 3 not found. Attempting automatic install..."
    echo ""
    if command -v brew >/dev/null 2>&1; then
        echo " Installing Python 3.12 via Homebrew..."
        brew install python@3.12
        command -v python3 >/dev/null 2>&1 && PY_BIN="python3"
    else
        echo " [INFO] Homebrew not found."
        echo "        Install Homebrew first: https://brew.sh"
        echo "        Or install Python manually: https://www.python.org/downloads/macos/"
        echo ""
        read -p " Install Homebrew automatically now? [y/N]: " ans
        if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            if [ -x /opt/homebrew/bin/brew ]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            elif [ -x /usr/local/bin/brew ]; then
                eval "$(/usr/local/bin/brew shellenv)"
            fi
            brew install python@3.12
            command -v python3 >/dev/null 2>&1 && PY_BIN="python3"
        fi
    fi
fi

if [ -z "$PY_BIN" ]; then
    echo ""
    echo " [ERROR] Python 3 still not available."
    echo "         Install it from https://www.python.org/downloads/macos/ and re-run."
    read -p "Press Enter to exit..."
    exit 1
fi
echo " [OK] Python found: $($PY_BIN --version)"

# ── Download only Mac-relevant files from GitHub ─────────────
echo ""
echo " [1/4] Downloading Mac files from GitHub..."
FAILED=0
for REL in "${MAC_FILES[@]}"; do
    # URL-encode spaces in filenames
    ENC=$(printf '%s' "$REL" | sed 's/ /%20/g')
    URL="${RAW_BASE}/${ENC}"
    OUT="$INSTALL_DIR/$REL"
    if curl -fsSL "$URL" -o "$OUT"; then
        echo "   ✓ $REL"
    else
        echo "   ✗ $REL  (failed)"
        FAILED=$((FAILED+1))
    fi
done

if [ $FAILED -gt 0 ]; then
    echo " [WARNING] $FAILED file(s) failed to download. Check internet / repo path."
fi
echo " [OK] App files installed."

# Make .command scripts executable (curl strips +x bit)
chmod +x "$INSTALL_DIR"/*.command 2>/dev/null

# ── Download AE template from Google Drive ───────────────────
echo ""
echo " [2/4] Downloading After Effects template from Google Drive..."
$PY_BIN -m pip install --quiet --break-system-packages gdown 2>/dev/null \
  || $PY_BIN -m pip install --quiet gdown
if $PY_BIN -m gdown --folder "$GDRIVE_FOLDER_ID" -O "$INSTALL_DIR" --quiet 2>/dev/null; then
    echo " [OK] After Effects template downloaded."
else
    echo " [WARNING] Could not download AE template automatically."
    echo "           Download it manually from:"
    echo "           https://drive.google.com/drive/folders/$GDRIVE_FOLDER_ID"
fi

# ── Install Python packages + Chromium ───────────────────────
echo ""
echo " [3/4] Installing Python packages..."
$PY_BIN -m pip install --quiet --break-system-packages playwright httpx pillow 2>/dev/null \
  || $PY_BIN -m pip install --quiet playwright httpx pillow
$PY_BIN -m playwright install chromium

# ── Install AE extension (both stable + Beta, admin fallback) ─
echo ""
echo " [4/4] Installing After Effects extension..."
PANEL_SRC="$INSTALL_DIR/Lineup Panel.jsx"
INSTALLED_AE=0
NEEDS_ADMIN=0
ADMIN_TARGETS=()

AE_FOLDERS=()
shopt -s nullglob 2>/dev/null || true
for AE_DIR in "/Applications/Adobe After Effects "*; do
    [ -d "$AE_DIR" ] && AE_FOLDERS+=("$AE_DIR")
done

if [ -f "$PANEL_SRC" ] && [ ${#AE_FOLDERS[@]} -gt 0 ]; then
    for AE_DIR in "${AE_FOLDERS[@]}"; do
        PANEL_DST="$AE_DIR/Scripts/ScriptUI Panels"
        [ ! -d "$PANEL_DST" ] && mkdir -p "$PANEL_DST" 2>/dev/null

        if cp "$PANEL_SRC" "$PANEL_DST/" 2>/dev/null; then
            echo " [OK] Extension installed: $AE_DIR"
            INSTALLED_AE=1
        else
            NEEDS_ADMIN=1
            ADMIN_TARGETS+=("$PANEL_DST")
        fi
    done

    # One admin prompt that covers all folders needing elevation
    if [ $NEEDS_ADMIN -eq 1 ]; then
        echo ""
        echo " [INFO] Admin password required to install panel into AE."
        CP_CMDS=""
        for DST in "${ADMIN_TARGETS[@]}"; do
            CP_CMDS="$CP_CMDS cp \"$PANEL_SRC\" \"$DST/\" ; "
        done
        if osascript -e "do shell script \"$CP_CMDS\" with administrator privileges" >/dev/null 2>&1; then
            for DST in "${ADMIN_TARGETS[@]}"; do
                if [ -f "$DST/Lineup Panel.jsx" ]; then
                    echo " [OK] Extension installed (admin): $DST"
                    INSTALLED_AE=1
                else
                    echo " [WARNING] Copy failed: $DST"
                fi
            done
        else
            echo " [WARNING] Admin copy was cancelled or failed."
            echo "           Run manually in Terminal:"
            for DST in "${ADMIN_TARGETS[@]}"; do
                echo "             sudo cp \"$PANEL_SRC\" \"$DST/\""
            done
        fi
    fi
elif [ ! -f "$PANEL_SRC" ]; then
    echo " [INFO] Lineup Panel.jsx not found, skipping AE extension."
else
    echo " [INFO] After Effects not found in /Applications."
    echo "        Copy \"Lineup Panel.jsx\" manually to:"
    echo "        /Applications/Adobe After Effects <version>/Scripts/ScriptUI Panels/"
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo " ============================================================"
echo "   DONE! Everything is installed."
echo ""
echo "   To get started:"
echo "     1. Open After Effects and load the .aep template"
echo "     2. Double-click START_MAC.command to launch the app"
echo ""
echo "   For help, reach out to Marian Grosu."
echo " ============================================================"
echo ""
read -p "Press Enter to close..."
