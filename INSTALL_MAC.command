#!/bin/bash
# Flashscore Ratings — macOS installer (clean UX)

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
        # left padding of `pos` spaces, then ⚽, then right padding
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
    # step "done label" -- command...
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

# ── Pick the best python3 ───────────────────────────────────────
# The stock /usr/bin/python3 (from Xcode CLT) ships Tcl/Tk 8.5 which
# renders Tkinter labels/entries incorrectly on macOS. We need Python
# with Tk 8.6+ — Homebrew's python@3.12 bundles it, python.org builds
# bundle it. We try to find a "good" one and install Homebrew's if not.
PY_BIN=""

check_tk_ok() {
    # Returns 0 if the given python has usable Tk (>= 8.6)
    local py="$1"
    [ -z "$py" ] && return 1
    "$py" -c "import tkinter; r=tkinter.Tk(); v=r.tk.call('info','patchlevel'); r.destroy(); import sys; sys.exit(0 if v.split('.')[0]=='8' and int(v.split('.')[1])>=6 else 1)" 2>/dev/null
}

# Prefer Homebrew pythons over system python3
for CANDIDATE in \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3 \
    python3.12 python3
do
    if command -v "$CANDIDATE" >/dev/null 2>&1 && check_tk_ok "$CANDIDATE"; then
        PY_BIN="$(command -v "$CANDIDATE")"
        break
    fi
done

if [ -z "$PY_BIN" ]; then
    info "First-time setup needs Python. Takes about 3–10 minutes."
    info "You'll be asked to press RETURN and to type your Mac password."
    echo ""
    if ! command -v brew >/dev/null 2>&1; then
        # Interactive install — Homebrew needs to prompt for sudo password
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        [ -x /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
        [ -x /usr/local/bin/brew ]    && eval "$(/usr/local/bin/brew shellenv)"
    fi
    if ! command -v brew >/dev/null 2>&1; then
        abort "Homebrew install didn't complete. Re-run when you're ready."
    fi
    echo ""
    echo "  ${DIM}Installing Python 3.12…${RESET}"
    brew install python@3.12
    echo ""

    for CANDIDATE in /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12; do
        if [ -x "$CANDIDATE" ] && check_tk_ok "$CANDIDATE"; then
            PY_BIN="$CANDIDATE"
            break
        fi
    done
    [ -z "$PY_BIN" ] && abort "Python installed but can't find a working one"
    clear 2>/dev/null || printf '\033[2J\033[H'
    banner
    ok "Python installed"
else
    ok "Python ready"
fi

# Pin the chosen Python for START_MAC.command so the app always uses the same one
echo "$PY_BIN" > "$INSTALL_DIR/.python_path"

# 2. Download files (one spinner, not 14)
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

# 3. Python packages (+ Chromium)
install_deps() {
    "$PY_BIN" -m pip install --quiet --break-system-packages playwright httpx pillow gdown 2>/dev/null \
      || "$PY_BIN" -m pip install --quiet playwright httpx pillow gdown
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

# Run AE install inline (may show admin dialog — don't hide under spinner)
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

# Auto-close the Terminal window
osascript -e 'tell application "Terminal" to close (every window whose tty contains "'$(tty | sed 's|/dev/||')'")' 2>/dev/null &
osascript -e 'tell application "iTerm" to close current window' 2>/dev/null &
exit 0
