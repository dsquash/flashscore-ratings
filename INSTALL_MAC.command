#!/bin/bash
# Flashscore Ratings — macOS installer
# Double-click once. Checks what's already installed and skips it.
# All scripts go into "_DO NOT TOUCH_/". Your match data stays safe.

set -u

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$INSTALL_DIR/_DO NOT TOUCH_"

cd "$INSTALL_DIR" || exit 1

GITHUB_OWNER="dsquash"
GITHUB_REPO="flashscore-ratings"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${BRANCH}"
GDRIVE_FOLDER_ID="1OwZoHfrUxtAZtS042g63Pqw0eSqP31Ti"

PYTHON_PKG_URL="https://www.python.org/ftp/python/3.12.8/python-3.12.8-macos11.pkg"
PYTHON_ORG_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

# Scripts downloaded to _DO NOT TOUCH_/
SCRIPT_FILES=(
    "launcher.py" "run.py" "refresh_stats.py" "updater.py"
    "populate_lineup.jsx" "reset_lineup.jsx" "refresh_comps.jsx"
    "save_template_state.jsx" "Lineup Panel.jsx"
    "version.txt" "CHANGELOG.md"
)

# Launcher files that stay at root (not in _DO NOT TOUCH_/)
ROOT_FILES=(
    "INSTALL_MAC.command" "START_MAC.command" "RUN_TERMINAL.command"
)

# ── UI helpers ──────────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
    BLUE=$'\033[38;5;75m'; GREEN=$'\033[38;5;42m'
    RED=$'\033[38;5;203m'; YELLOW=$'\033[38;5;220m'
else
    BOLD=''; DIM=''; RESET=''; BLUE=''; GREEN=''; RED=''; YELLOW=''
fi

LOG="$INSTALL_DIR/.install_log.txt"
: > "$LOG"

banner() {
    clear 2>/dev/null || printf '\033[2J\033[H'
    echo ""
    printf "  ${BOLD}${BLUE}%s${RESET}\n" "Flashscore Ratings — Setup"
    printf "  ${DIM}%s${RESET}\n" "Checking your Mac..."
    echo ""
}

ok()   { printf "  ${GREEN}✓${RESET}  %s\n" "$1"; }
skip() { printf "  ${BLUE}–${RESET}  ${DIM}%s (already installed)${RESET}\n" "$1"; }
bad()  { printf "  ${RED}✗${RESET}  %s\n" "$1"; }
info() { printf "     ${DIM}%s${RESET}\n" "$1"; }

spin() {
    local pid="$1" label="$2"
    local width=22 pos=0 dir=1
    printf '\033[?25l'
    while kill -0 "$pid" 2>/dev/null; do
        local left right
        left=$(printf '%*s' "$pos" "")
        right=$(printf '%*s' "$((width - pos))" "")
        printf "\r  [%s·%s]  ${DIM}%s${RESET}\033[K" "$left" "$right" "$label"
        pos=$((pos + dir))
        [ $pos -ge $width ] && dir=-1
        [ $pos -le 0 ]     && dir=1
        sleep 0.05
    done
    printf '\033[?25h'
    wait "$pid"
    local rc=$?
    printf "\r\033[K"
    return $rc
}

run_step() {
    local label="$1"; shift
    ( "$@" ) >>"$LOG" 2>&1 &
    local pid=$!
    if spin "$pid" "$label"; then
        ok "$label"
        return 0
    else
        bad "$label"
        return 1
    fi
}

abort() {
    echo ""
    bad "${1:-Installation failed}"
    echo ""
    info "See full log: $LOG"
    echo ""
    read -r -p "  Press Enter to close..."
    exit 1
}

# ── Start ───────────────────────────────────────────────────────────
banner

# Create _DO NOT TOUCH_ folder if needed
mkdir -p "$SCRIPTS_DIR"

# ══════════════════════════════════════════════════════════════════
# STEP 1 — Python with Tk 8.6
# Stock /usr/bin/python3 ships Tk 8.5 which breaks the UI on Mac.
# ══════════════════════════════════════════════════════════════════
check_tk_ok() {
    local py="$1"
    [ -z "$py" ] || [ ! -x "$py" ] && return 1
    "$py" -c "
import tkinter as tk, sys
r = tk.Tk()
v = r.tk.call('info', 'patchlevel')
r.destroy()
p = v.split('.')
sys.exit(0 if int(p[0]) > 8 or (int(p[0]) == 8 and int(p[1]) >= 6) else 1)
" 2>/dev/null
}

PY_BIN=""
for C in \
    "$PYTHON_ORG_BIN" \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
    /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 \
    /usr/local/bin/python3.12 /usr/local/bin/python3
do
    if check_tk_ok "$C"; then
        PY_BIN="$C"
        break
    fi
done

if [ -n "$PY_BIN" ]; then
    skip "Python"
else
    info "Installing Python from python.org (one-time, ~40 MB)..."
    echo ""
    PKG_TMP="/tmp/flashscore-python.pkg"
    run_step "Downloading Python installer" curl -fsSL "$PYTHON_PKG_URL" -o "$PKG_TMP" \
        || abort "Couldn't download Python. Check your internet connection."

    info "macOS will ask for your password to install Python..."
    echo ""
    if ! osascript -e "do shell script \"installer -pkg '$PKG_TMP' -target /\" with administrator privileges" >>"$LOG" 2>&1; then
        abort "Python installation was cancelled or failed."
    fi
    rm -f "$PKG_TMP" 2>/dev/null

    if [ -x "/Applications/Python 3.12/Install Certificates.command" ]; then
        "/Applications/Python 3.12/Install Certificates.command" >>"$LOG" 2>&1 || true
    fi

    if check_tk_ok "$PYTHON_ORG_BIN"; then
        PY_BIN="$PYTHON_ORG_BIN"
        ok "Python installed"
    else
        abort "Python was installed but something went wrong."
    fi
fi

# Pin Python path for START_MAC.command and Lineup Panel.jsx
echo "$PY_BIN" > "$SCRIPTS_DIR/.python_path"

# ══════════════════════════════════════════════════════════════════
# STEP 2 — pip packages
# ══════════════════════════════════════════════════════════════════
check_packages() {
    "$PY_BIN" -c "import playwright, httpx, PIL, gdown, ttkbootstrap" 2>/dev/null
}

if check_packages; then
    skip "Python packages (playwright, httpx, pillow, gdown, ttkbootstrap)"
else
    install_packages() {
        "$PY_BIN" -m pip install --quiet --upgrade pip 2>/dev/null || true
        "$PY_BIN" -m pip install --quiet playwright httpx pillow gdown ttkbootstrap \
            || "$PY_BIN" -m pip install --quiet --user playwright httpx pillow gdown ttkbootstrap
    }
    run_step "Installing Python packages" install_packages \
        || abort "Couldn't install Python packages. Check $LOG for details."
fi

# ══════════════════════════════════════════════════════════════════
# STEP 3 — Chromium
# ══════════════════════════════════════════════════════════════════
check_chromium() {
    for base in \
        "$HOME/Library/Caches/ms-playwright" \
        "$HOME/Library/Application Support/ms-playwright" \
        "$HOME/.cache/ms-playwright"
    do
        if [ -d "$base" ] && find "$base" -name "Chromium.app" -maxdepth 6 2>/dev/null | grep -q .; then
            return 0
        fi
    done
    return 1
}

if check_chromium; then
    skip "Chromium browser"
else
    run_step "Installing Chromium" "$PY_BIN" -m playwright install chromium \
        || abort "Couldn't install Chromium. Check $LOG for details."
fi

# ══════════════════════════════════════════════════════════════════
# STEP 4 — Migrate old structure (one-time, if upgrading from flat layout)
# ══════════════════════════════════════════════════════════════════
migrate_old_files() {
    # Preserve sofifa_overrides.json (user data) — copy only if not in _DO NOT TOUCH_ yet
    if [ -f "$INSTALL_DIR/sofifa_overrides.json" ] && [ ! -f "$SCRIPTS_DIR/sofifa_overrides.json" ]; then
        cp "$INSTALL_DIR/sofifa_overrides.json" "$SCRIPTS_DIR/sofifa_overrides.json" 2>/dev/null
    fi
    # Preserve flashscore_output (user's match data)
    if [ -d "$INSTALL_DIR/flashscore_output" ] && [ ! -d "$SCRIPTS_DIR/flashscore_output" ]; then
        mv "$INSTALL_DIR/flashscore_output" "$SCRIPTS_DIR/" 2>/dev/null
    fi
    # Remove old script files from root
    for OLD_F in "launcher.py" "run.py" "refresh_stats.py" "updater.py" \
                 "populate_lineup.jsx" "reset_lineup.jsx" "refresh_comps.jsx" \
                 "save_template_state.jsx" "Lineup Panel.jsx" \
                 "sofifa_overrides.json" "version.txt" "CHANGELOG.md" \
                 ".python_path" ".install_log.txt" "lineup_debug.txt"; do
        rm -f "$INSTALL_DIR/$OLD_F" 2>/dev/null
    done
    rm -rf "$INSTALL_DIR/__pycache__" 2>/dev/null
    return 0
}

# Only run migration if any old-style script files exist at root
if [ -f "$INSTALL_DIR/launcher.py" ] || [ -f "$INSTALL_DIR/run.py" ]; then
    run_step "Migrating files to new folder structure" migrate_old_files \
        || info "Migration had some issues — continuing anyway."
fi

# ══════════════════════════════════════════════════════════════════
# STEP 5 — Scripts from GitHub
# ══════════════════════════════════════════════════════════════════
LOCAL_VER="$(cat "$SCRIPTS_DIR/version.txt" 2>/dev/null | tr -d '[:space:]')"
REMOTE_VER="$(curl -fsSL "${RAW_BASE}/version.txt" 2>/dev/null | tr -d '[:space:]')"

FILES_OK=1
for F in "launcher.py" "run.py" "refresh_stats.py"; do
    [ ! -f "$SCRIPTS_DIR/$F" ] && FILES_OK=0 && break
done

if [ "$FILES_OK" -eq 1 ] && [ -n "$LOCAL_VER" ] && [ -n "$REMOTE_VER" ] && [ "$LOCAL_VER" = "$REMOTE_VER" ]; then
    skip "Scripts (v${LOCAL_VER})"
else
    if [ -n "$LOCAL_VER" ] && [ -n "$REMOTE_VER" ] && [ "$LOCAL_VER" != "$REMOTE_VER" ]; then
        info "Update: v${LOCAL_VER} → v${REMOTE_VER}"
    fi

    download_scripts() {
        # Script files → _DO NOT TOUCH_/
        for REL in "${SCRIPT_FILES[@]}"; do
            local enc url
            enc=$(printf '%s' "$REL" | sed 's/ /%20/g')
            url="${RAW_BASE}/${enc}"
            curl -fsSL "$url" -o "$SCRIPTS_DIR/$REL" || return 1
        done
        # sofifa_overrides.json: only download if it doesn't exist (preserve user data)
        if [ ! -f "$SCRIPTS_DIR/sofifa_overrides.json" ]; then
            curl -fsSL "${RAW_BASE}/sofifa_overrides.json" -o "$SCRIPTS_DIR/sofifa_overrides.json" 2>/dev/null || true
        fi
        # Launcher files → INSTALL_DIR (root)
        for REL in "${ROOT_FILES[@]}"; do
            local enc url
            enc=$(printf '%s' "$REL" | sed 's/ /%20/g')
            url="${RAW_BASE}/${enc}"
            curl -fsSL "$url" -o "$INSTALL_DIR/$REL" || true  # non-fatal
        done
        chmod +x "$INSTALL_DIR"/*.command 2>/dev/null
        return 0
    }

    LABEL="Downloading scripts"
    [ -n "$REMOTE_VER" ] && LABEL="Downloading scripts (v${REMOTE_VER})"
    run_step "$LABEL" download_scripts \
        || abort "Download failed — check your internet connection."
fi

# ══════════════════════════════════════════════════════════════════
# STEP 6 — After Effects template from Google Drive
# ══════════════════════════════════════════════════════════════════
TEMPLATE_AEP="$INSTALL_DIR/Match Ratings - Template.aep"
TEMPLATE_FOLDER="$INSTALL_DIR/Match Ratings - Template folder"

if [ -f "$TEMPLATE_AEP" ] || [ -d "$TEMPLATE_FOLDER" ]; then
    skip "After Effects template"
else
    fetch_template() {
        "$PY_BIN" -m gdown --folder "$GDRIVE_FOLDER_ID" -O "$INSTALL_DIR" --quiet
    }
    if ! run_step "Downloading After Effects template" fetch_template; then
        info "Template download failed — download manually from Google Drive if needed."
    fi
fi

# ══════════════════════════════════════════════════════════════════
# STEP 7 — Write config file for Lineup Panel.jsx
# Tells the AE panel where _DO NOT TOUCH_/ is, regardless of where
# AE installed the panel JSX.
# ══════════════════════════════════════════════════════════════════
echo "$SCRIPTS_DIR" > "$HOME/.flashscore_ratings"
ok "AE panel config written"

# ══════════════════════════════════════════════════════════════════
# STEP 8 — After Effects panel (Lineup Panel.jsx)
# ══════════════════════════════════════════════════════════════════
PANEL_SRC="$SCRIPTS_DIR/Lineup Panel.jsx"

AE_DIRS=()
shopt -s nullglob 2>/dev/null || true
for AE_DIR in "/Applications/Adobe After Effects "*; do
    [ -d "$AE_DIR" ] && AE_DIRS+=("$AE_DIR")
done

if [ ! -f "$PANEL_SRC" ] || [ ${#AE_DIRS[@]} -eq 0 ]; then
    : # No AE or no panel — skip silently
else
    ALL_INSTALLED=1
    for AE_DIR in "${AE_DIRS[@]}"; do
        [ ! -f "$AE_DIR/Scripts/ScriptUI Panels/Lineup Panel.jsx" ] && ALL_INSTALLED=0 && break
    done

    if [ "$ALL_INSTALLED" -eq 1 ]; then
        skip "After Effects panel"
    else
        install_ae_panel() {
            local NEEDS_ADMIN=0 ADMIN_TARGETS=()
            for AE_DIR in "${AE_DIRS[@]}"; do
                local DST="$AE_DIR/Scripts/ScriptUI Panels"
                mkdir -p "$DST" 2>/dev/null
                if ! cp "$PANEL_SRC" "$DST/" 2>/dev/null; then
                    NEEDS_ADMIN=1
                    ADMIN_TARGETS+=("$DST")
                fi
            done
            if [ "$NEEDS_ADMIN" -eq 1 ]; then
                local CMD=""
                for DST in "${ADMIN_TARGETS[@]}"; do
                    CMD="${CMD}cp \"$PANEL_SRC\" \"$DST/\" ; "
                done
                osascript -e "do shell script \"$CMD\" with administrator privileges" 2>/dev/null
            fi
            return 0
        }
        run_step "Installing After Effects panel" install_ae_panel \
            || info "AE panel: copy 'Lineup Panel.jsx' from '_DO NOT TOUCH_/' manually if needed."
    fi
fi

# ── Done ────────────────────────────────────────────────────────────
echo ""
printf "  ${GREEN}${BOLD}All set!${RESET}\n"
echo ""
printf "  ${DIM}Double-click ${RESET}${BOLD}START_MAC.command${RESET}${DIM} to launch the app.${RESET}\n"
echo ""
read -r -p "  Press Enter to close..."

osascript -e 'tell application "Terminal" to close (every window whose tty contains "'"$(tty | sed 's|/dev/||')"'")' 2>/dev/null &
osascript -e 'tell application "iTerm" to close current window' 2>/dev/null &
exit 0
