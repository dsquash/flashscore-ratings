#!/bin/bash
# Flashscore Ratings — macOS installer (stock Python, no Homebrew)

set -u

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$INSTALL_DIR" || exit 1

GITHUB_OWNER="dsquash"
GITHUB_REPO="flashscore-ratings"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${BRANCH}"
GDRIVE_FOLDER_ID="1OwZoHfrUxtAZtS042g63Pqw0eSqP31Ti"

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
    echo "  ${BOLD}${BLUE}⚽  Flashscore Ratings${RESET}"
    echo "  ${DIM}Setting up on your Mac…${RESET}"
    echo ""
}

ok()   { printf "  ${GREEN}✓${RESET}  %s\n" "$1"; }
bad()  { printf "  ${RED}✗${RESET}  %s\n" "$1"; }
info() { printf "     ${DIM}%s${RESET}\n" "$1"; }

spin() {
    # Football ⚽ bouncing left–right while <pid> runs
    local pid=$1 label="$2"
    local width=22
    local pos=0
    local dir=1
    printf '\033[?25l'  # hide cursor
    while kill -0 "$pid" 2>/dev/null; do
        local left right
        left=$(printf '%*s' "$pos" "")
        right=$(printf '%*s' "$((width - pos))" "")
        printf "\r  [%s⚽%s]  ${DIM}%s${RESET}\033[K" "$left" "$right" "$label"
        pos=$((pos + dir))
        if [ $pos -ge $width ]; then dir=-1; fi
        if [ $pos -le 0 ];     then dir=1;  fi
        sleep 0.05
    done
    printf '\033[?25h'  # show cursor
    wait "$pid"
    local rc=$?
    printf "\r\033[K"
    return $rc
}

step() {
    local label="$1"; shift
    [ "$1" = "--" ] && shift
    ( "$@" ) >>"$LOG" 2>&1 &
    local pid=$!
    if spin "$pid" "$label…"; then
        ok "$label"
        return 0
    else
        bad "$label failed"
        return 1
    fi
}

abort() {
    echo ""
    bad "$1"
    echo ""
    info "Full log: $LOG"
    echo ""
    read -p "  Press Enter to close…"
    osascript -e 'tell application "Terminal" to close (every window whose tty contains "'$(tty | sed 's|/dev/||')'")' 2>/dev/null &
    exit 1
}

# ── Start ───────────────────────────────────────────────────────
banner

# ── Use stock macOS Python ──────────────────────────────────────
PY_BIN="/usr/bin/python3"

if [ ! -x "$PY_BIN" ]; then
    info "macOS needs to install the Command Line Tools first."
    info "A system dialog will pop up — click Install and wait."
    echo ""
    xcode-select --install 2>/dev/null
    abort "Please run this installer again after Command Line Tools finish installing."
fi

# Trigger CLT prompt if python3 exists but is a stub
if ! "$PY_BIN" -c "import sys" >/dev/null 2>&1; then
    info "macOS needs to finish setting up developer tools."
    xcode-select --install 2>/dev/null
    abort "Please run this installer again after Command Line Tools finish installing."
fi

ok "Python ready"

# 2. Download files
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
    || abort "Download failed — check your internet connection"

# 3. Python packages (+ Chromium) — user-level install, no sudo
install_deps() {
    "$PY_BIN" -m pip install --quiet --user --break-system-packages playwright httpx pillow gdown 2>/dev/null \
      || "$PY_BIN" -m pip install --quiet --user playwright httpx pillow gdown
    "$PY_BIN" -m playwright install chromium
}
step "Preparing the tools (can take a minute)" -- install_deps \
    || abort "Couldn't set up dependencies"

# 4. AE template from Google Drive
fetch_template() {
    "$PY_BIN" -m gdown --folder "$GDRIVE_FOLDER_ID" -O "$INSTALL_DIR" --quiet
}
if step "Getting the After Effects template" -- fetch_template; then
    :
else
    info "Skipped — you can download the template manually later."
fi

# 5. AE panel install (stable + Beta, admin fallback)
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
    printf "  ${BLUE}⣾${RESET}  Installing the After Effects panel…\033[K\r"
    if install_ae_panel; then
        printf "\r\033[K"
        ok "After Effects panel installed"
    else
        printf "\r\033[K"
        info "AE panel install skipped — copy Lineup Panel.jsx manually if needed."
    fi
fi

# ── Done ────────────────────────────────────────────────────────
echo ""
echo "  ${GREEN}${BOLD}🎉  All set!${RESET}"
echo ""
echo "  ${DIM}What's next:${RESET}"
echo "    1. Open After Effects and load the template"
echo "    2. Double-click ${BOLD}START_MAC.command${RESET} to launch the app"
echo ""
read -p "  Press Enter to close…"

osascript -e 'tell application "Terminal" to close (every window whose tty contains "'$(tty | sed 's|/dev/||')'")' 2>/dev/null &
osascript -e 'tell application "iTerm" to close current window' 2>/dev/null &
exit 0
