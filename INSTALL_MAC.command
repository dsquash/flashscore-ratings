#!/bin/bash
# Flashscore Ratings - macOS installer (self-contained, no Homebrew)

set -u

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$INSTALL_DIR" || exit 1

GITHUB_OWNER="dsquash"
GITHUB_REPO="flashscore-ratings"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${BRANCH}"
GDRIVE_FOLDER_ID="1OwZoHfrUxtAZtS042g63Pqw0eSqP31Ti"

# Official python.org Python 3.12 (universal2, Tk 8.6 built-in)
PYTHON_PKG_URL="https://www.python.org/ftp/python/3.12.8/python-3.12.8-macos11.pkg"
PYTHON_ORG_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

MAC_FILES=(
    "launcher.py" "run.py" "refresh_stats.py" "updater.py"
    "populate_lineup.jsx" "reset_lineup.jsx" "refresh_comps.jsx" "save_template_state.jsx"
    "Lineup Panel.jsx" "sofifa_overrides.json"
    "INSTALL_MAC.command" "START_MAC.command"
    "CHANGELOG.md" "version.txt"
)

# ── UI helpers ─────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
    BLUE=$'\033[38;5;75m'; GREEN=$'\033[38;5;42m'; RED=$'\033[38;5;203m'
else
    BOLD=''; DIM=''; RESET=''; BLUE=''; GREEN=''; RED=''
fi

LOG="$INSTALL_DIR/.install_log.txt"
: > "$LOG"

banner() {
    clear 2>/dev/null || printf '\033[2J\033[H'
    echo ""
    printf "  ${BOLD}${BLUE}%s${RESET}\n" "Flashscore Ratings"
    printf "  ${DIM}%s${RESET}\n" "Setting up on your Mac..."
    echo ""
}

ok()   { printf "  ${GREEN}OK${RESET}    %s\n" "$1"; }
bad()  { printf "  ${RED}FAIL${RESET}  %s\n" "$1"; }
info() { printf "        ${DIM}%s${RESET}\n" "$1"; }

spin() {
    # Football bouncing left-right while <pid> runs
    local pid="${1:-}"
    local label="${2:-}"
    local width=22
    local pos=0
    local dir=1
    printf '\033[?25l'
    while kill -0 "$pid" 2>/dev/null; do
        local left right
        left=$(printf '%*s' "$pos" "")
        right=$(printf '%*s' "$((width - pos))" "")
        printf "\r  [%s*%s]  ${DIM}%s${RESET}\033[K" "$left" "$right" "$label"
        pos=$((pos + dir))
        if [ $pos -ge $width ]; then dir=-1; fi
        if [ $pos -le 0 ];     then dir=1;  fi
        sleep 0.05
    done
    printf '\033[?25h'
    wait "$pid"
    local rc=$?
    printf "\r\033[K"
    return $rc
}

step() {
    local label="${1:-step}"; shift || true
    if [ "${1:-}" = "--" ]; then shift; fi
    ( "$@" ) >>"$LOG" 2>&1 &
    local pid=$!
    if spin "$pid" "${label}..."; then
        ok "$label"
        return 0
    else
        bad "$label failed"
        return 1
    fi
}

abort() {
    echo ""
    bad "${1:-aborted}"
    echo ""
    info "Full log: $LOG"
    echo ""
    read -r -p "  Press Enter to close..."
    osascript -e 'tell application "Terminal" to close (every window whose tty contains "'"$(tty | sed 's|/dev/||')"'")' 2>/dev/null &
    exit 1
}

# ── Start ───────────────────────────────────────────────────────
banner

# ── Find a Python with Tk >= 8.6 ────────────────────────────────
# Stock /usr/bin/python3 ships Tk 8.5 which renders the UI badly on Mac.
# Prefer python.org's Python 3.12 (ships Tk 8.6). Install if missing.

check_tk_ok() {
    local py="$1"
    [ -z "$py" ] && return 1
    [ ! -x "$py" ] && return 1
    "$py" -c "import tkinter as tk; r=tk.Tk(); v=r.tk.call('info','patchlevel'); r.destroy(); import sys; p=v.split('.'); sys.exit(0 if int(p[0])>8 or (int(p[0])==8 and int(p[1])>=6) else 1)" 2>/dev/null
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

if [ -z "$PY_BIN" ]; then
    info "Your Mac's Python has an old Tk that would break the UI."
    info "Getting the official Python from python.org (one-time, ~40 MB)."
    echo ""

    # Download pkg
    PKG_TMP="/tmp/flashscore-python.pkg"
    if ! curl -fsSL "$PYTHON_PKG_URL" -o "$PKG_TMP"; then
        abort "Couldn't download Python installer. Check your internet."
    fi

    # Install with admin password prompt (native macOS dialog)
    info "macOS will ask for your password to finish the install."
    echo ""
    if ! osascript -e "do shell script \"installer -pkg '$PKG_TMP' -target /\" with administrator privileges" >>"$LOG" 2>&1; then
        abort "Python installer didn't finish. Try again when ready."
    fi

    rm -f "$PKG_TMP" 2>/dev/null

    # Install certificates bundle that python.org ships separately
    if [ -x "/Applications/Python 3.12/Install Certificates.command" ]; then
        "/Applications/Python 3.12/Install Certificates.command" >>"$LOG" 2>&1 || true
    fi

    if check_tk_ok "$PYTHON_ORG_BIN"; then
        PY_BIN="$PYTHON_ORG_BIN"
        ok "Python installed"
    else
        abort "Python installed but something's off."
    fi
else
    ok "Python ready"
fi

# Pin Python path for START_MAC.command
echo "$PY_BIN" > "$INSTALL_DIR/.python_path"

# ── 2. Download files ───────────────────────────────────────────
download_all() {
    for REL in "${MAC_FILES[@]}"; do
        local enc url out
        enc=$(printf '%s' "$REL" | sed 's/ /%20/g')
        url="${RAW_BASE}/${enc}"
        out="$INSTALL_DIR/$REL"
        curl -fsSL "$url" -o "$out" || return 1
    done
    chmod +x "$INSTALL_DIR"/*.command 2>/dev/null
    return 0
}
step "Downloading the latest version" -- download_all \
    || abort "Download failed - check your internet connection"

# ── 3. Python packages + Chromium ───────────────────────────────
install_deps() {
    "$PY_BIN" -m pip install --quiet --upgrade pip 2>/dev/null || true
    "$PY_BIN" -m pip install --quiet playwright httpx pillow gdown \
      || "$PY_BIN" -m pip install --quiet --user playwright httpx pillow gdown
    "$PY_BIN" -m playwright install chromium
}
step "Preparing the tools (can take a minute)" -- install_deps \
    || abort "Couldn't set up dependencies"

# ── 4. AE template from Google Drive ────────────────────────────
fetch_template() {
    "$PY_BIN" -m gdown --folder "$GDRIVE_FOLDER_ID" -O "$INSTALL_DIR" --quiet
}
if step "Getting the After Effects template" -- fetch_template; then
    :
else
    info "Skipped - you can download the template manually later."
fi

# ── 5. AE panel install ─────────────────────────────────────────
install_ae_panel() {
    local PANEL_SRC="$INSTALL_DIR/Lineup Panel.jsx"
    [ ! -f "$PANEL_SRC" ] && return 0

    local AE_FOLDERS=()
    shopt -s nullglob 2>/dev/null || true
    for AE_DIR in "/Applications/Adobe After Effects "*; do
        [ -d "$AE_DIR" ] && AE_FOLDERS+=("$AE_DIR")
    done
    [ ${#AE_FOLDERS[@]} -eq 0 ] && return 0

    local NEEDS_ADMIN=0
    local ADMIN_TARGETS=()
    for AE_DIR in "${AE_FOLDERS[@]}"; do
        local PANEL_DST="$AE_DIR/Scripts/ScriptUI Panels"
        [ ! -d "$PANEL_DST" ] && mkdir -p "$PANEL_DST" 2>/dev/null
        if ! cp "$PANEL_SRC" "$PANEL_DST/" 2>/dev/null; then
            NEEDS_ADMIN=1
            ADMIN_TARGETS+=("$PANEL_DST")
        fi
    done

    if [ $NEEDS_ADMIN -eq 1 ]; then
        local CP_CMDS=""
        for DST in "${ADMIN_TARGETS[@]}"; do
            CP_CMDS="$CP_CMDS cp \"$PANEL_SRC\" \"$DST/\" ; "
        done
        osascript -e "do shell script \"$CP_CMDS\" with administrator privileges" 2>/dev/null
    fi
    return 0
}

PANEL_SRC="$INSTALL_DIR/Lineup Panel.jsx"
AE_COUNT=0
shopt -s nullglob 2>/dev/null || true
for AE_DIR in "/Applications/Adobe After Effects "*; do
    [ -d "$AE_DIR" ] && AE_COUNT=$((AE_COUNT+1))
done

if [ -f "$PANEL_SRC" ] && [ $AE_COUNT -gt 0 ]; then
    printf "  ${BLUE}..${RESET}  Installing the After Effects panel...\033[K\r"
    if install_ae_panel; then
        printf "\r\033[K"
        ok "After Effects panel installed"
    else
        printf "\r\033[K"
        info "AE panel install skipped - copy Lineup Panel.jsx manually if needed."
    fi
fi

# ── Done ────────────────────────────────────────────────────────
echo ""
printf "  ${GREEN}${BOLD}%s${RESET}\n" "All set!"
echo ""
printf "  ${DIM}%s${RESET}\n" "What's next:"
echo "    1. Open After Effects and load the template"
printf "    2. Double-click ${BOLD}%s${RESET} to launch the app\n" "START_MAC.command"
echo ""
read -r -p "  Press Enter to close..."

osascript -e 'tell application "Terminal" to close (every window whose tty contains "'"$(tty | sed 's|/dev/||')"'")' 2>/dev/null &
osascript -e 'tell application "iTerm" to close current window' 2>/dev/null &
exit 0
