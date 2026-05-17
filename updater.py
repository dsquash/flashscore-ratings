#!/usr/bin/env python3
"""
updater.py — Auto-updater for Flashscore Ratings
=================================================
Checks GitHub for a newer version and downloads updated files.
Also reinstalls the After Effects extension (Lineup Panel.jsx) automatically.

Usage (standalone):
    python updater.py

Used internally by launcher.py for startup check and one-click update.
"""

import sys
import shutil
from pathlib import Path

BASE_DIR     = Path(__file__).parent        # _DO NOT TOUCH_/
ROOT_DIR     = BASE_DIR.parent              # app root (where .command / .bat files live)
VERSION_FILE = BASE_DIR / "version.txt"

# Files that live at ROOT_DIR level (not inside _DO NOT TOUCH_/)
_ROOT_ONLY_FILES = {
    "INSTALL_MAC.command", "START_MAC.command", "RUN_TERMINAL.command",
    "INSTALL.bat", "START HERE.bat",
}

# sofifa_overrides.json is user data — never overwrite if it already exists
_PRESERVE_IF_EXISTS = {"sofifa_overrides.json"}

# ── GitHub config ─────────────────────────────────────────────────
GITHUB_OWNER = "dsquash"
GITHUB_REPO  = "flashscore-ratings"
BRANCH       = "main"
# ─────────────────────────────────────────────────────────────────

RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{BRANCH}"

# Files common to all platforms
_COMMON_FILES = [
    "launcher.py",
    "run.py",
    "refresh_stats.py",
    "updater.py",
    "populate_lineup.jsx",
    "reset_lineup.jsx",
    "refresh_comps.jsx",
    "save_template_state.jsx",
    "Lineup Panel.jsx",
    "sofifa_overrides.json",
    "version.txt",
]

# Platform-specific installer/launcher scripts
_WINDOWS_FILES = [
    "INSTALL.bat",
    "START HERE.bat",
]

_MAC_FILES = [
    "INSTALL_MAC.command",
    "START_MAC.command",
]

# Pick the set for the OS running the updater — Mac never pulls .bat, Windows never pulls .command
if sys.platform.startswith("win"):
    UPDATABLE_FILES = _COMMON_FILES + _WINDOWS_FILES
elif sys.platform == "darwin":
    UPDATABLE_FILES = _COMMON_FILES + _MAC_FILES
else:
    UPDATABLE_FILES = list(_COMMON_FILES)

AE_PANEL_FILE = "Lineup Panel.jsx"  # kept for reference only


# ── Version helpers ───────────────────────────────────────────────

def get_local_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def _fetch_url(url: str, timeout: int = 10) -> bytes:
    import urllib.request
    from urllib.parse import quote
    # Encode the last path component to handle spaces and special chars in filenames
    if "raw.githubusercontent.com" in url:
        parts = url.split("/")
        parts[-1] = quote(parts[-1], safe="/")
        url = "/".join(parts)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _verify_file(data: bytes, filename: str) -> bool:
    """Verifica integritatea unui fisier descarcat (marime minima + sintaxa Python)."""
    if len(data) < 50:
        return False
    if filename.endswith(".py"):
        import ast
        try:
            ast.parse(data.decode("utf-8", errors="replace"))
        except SyntaxError:
            return False
    return True


def get_remote_version() -> str:
    data = _fetch_url(f"{RAW_BASE}/version.txt")
    return data.decode("utf-8").strip()


def _version_gt(a: str, b: str) -> bool:
    """Returns True if version string a is newer than b."""
    def parts(v):
        try:
            return [int(x) for x in v.strip().split(".")]
        except Exception:
            return [0]
    return parts(a) > parts(b)


def check_for_update(timeout: int = 8) -> tuple:
    """
    Returns (update_available: bool, local: str, remote: str).
    On network error returns (False, local, "?").
    """
    local = get_local_version()
    try:
        remote = get_remote_version()
        return _version_gt(remote, local), local, remote
    except Exception:
        return False, local, "?"


# ── Apply update ──────────────────────────────────────────────────

def apply_update(progress_cb=None) -> tuple:
    """
    Downloads each file in UPDATABLE_FILES from GitHub and saves it locally.

    progress_cb(current, total, label, ok) called after each step.
    Returns (updated: list, failed: list, ae_results: list).
    """
    updated = []
    failed  = []
    total   = len(UPDATABLE_FILES)

    for i, filename in enumerate(UPDATABLE_FILES):
        url  = f"{RAW_BASE}/{filename}"
        # .command / .bat files go to ROOT_DIR; everything else to BASE_DIR
        dest = ROOT_DIR / filename if filename in _ROOT_ONLY_FILES else BASE_DIR / filename
        ok   = False

        # Never overwrite user data files that already exist
        if filename in _PRESERVE_IF_EXISTS and dest.exists():
            updated.append(filename)
            if progress_cb:
                progress_cb(i + 1, total, f"{filename} (preserved)", True)
            continue

        try:
            data = _fetch_url(url, timeout=30)
            if not _verify_file(data, filename):
                failed.append(f"{filename}: integritate esuata (fisier corupt sau prea mic)")
            else:
                dest.write_bytes(data)
                updated.append(filename)
                ok = True
        except Exception as e:
            failed.append(f"{filename}: {e}")

        if progress_cb:
            progress_cb(i + 1, total, filename, ok)

    return updated, failed, []


def get_changelog() -> str:
    try:
        data = _fetch_url(f"{RAW_BASE}/CHANGELOG.md")
        return data.decode("utf-8")
    except Exception:
        return ""


# ── CLI entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("Checking for updates...")
    available, local, remote = check_for_update()

    if not available:
        if remote == "?":
            print("Could not reach GitHub. Check your internet connection.")
        else:
            print(f"Already up to date (v{local}).")
        sys.exit(0)

    print(f"\nUpdate available: v{local}  →  v{remote}\n")

    changelog = get_changelog()
    if changelog:
        lines = changelog.splitlines()
        for line in lines[1:]:
            if line.startswith("## ") and not line.startswith(f"## v{remote}"):
                break
            print(line)
        print()

    resp = input("Apply update? [y/N]: ").strip().lower()
    if resp != "y":
        print("Update cancelled.")
        sys.exit(0)

    print()

    def prog(current, total, name, ok):
        status = "✓" if ok else "✗"
        print(f"  [{current}/{total}] {status}  {name}")

    updated, failed, _ = apply_update(prog)

    print(f"\nUpdated {len(updated)} file(s).")

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for f in failed:
            print(f"  {f}")

    print("\nRestart the app to apply changes.")
