#!/usr/bin/env python3
"""
updater.py — Auto-updater for Flashscore Ratings
=================================================
Checks GitHub for a newer version and downloads updated files.

Usage (standalone):
    python updater.py

Used internally by launcher.py for startup check and one-click update.
"""

import sys
from pathlib import Path

BASE_DIR     = Path(__file__).parent
VERSION_FILE = BASE_DIR / "version.txt"

# ── GitHub config ─────────────────────────────────────────────────
# Set these to your actual GitHub username and repo name.
GITHUB_OWNER = "dsquash"
GITHUB_REPO  = "flashscore-ratings"
BRANCH       = "main"
# ─────────────────────────────────────────────────────────────────

RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{BRANCH}"

# Files that will be replaced on update (user data is never touched)
UPDATABLE_FILES = [
    "launcher.py",
    "run.py",
    "refresh_stats.py",
    "updater.py",
    "populate_lineup.jsx",
    "reset_lineup.jsx",
    "save_template_state.jsx",
    "Lineup Panel.jsx",
    "START HERE.bat",
    "version.txt",
]


# ── Version helpers ───────────────────────────────────────────────

def get_local_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def _fetch_url(url: str, timeout: int = 10) -> bytes:
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


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

def apply_update(progress_cb=None) -> list:
    """
    Downloads each file in UPDATABLE_FILES from GitHub and saves it locally.
    progress_cb(current, total, filename) called after each file.
    Returns list of successfully updated filenames.
    """
    updated = []
    failed  = []
    total   = len(UPDATABLE_FILES)

    for i, filename in enumerate(UPDATABLE_FILES):
        url  = f"{RAW_BASE}/{filename}"
        dest = BASE_DIR / filename
        try:
            data = _fetch_url(url, timeout=30)
            dest.write_bytes(data)
            updated.append(filename)
        except Exception as e:
            failed.append(f"{filename}: {e}")

        if progress_cb:
            progress_cb(i + 1, total, filename, filename not in [f.split(":")[0] for f in failed])

    return updated, failed


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
        # Print only the first section (latest release notes)
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

    updated, failed = apply_update(prog)

    print(f"\nUpdated {len(updated)} file(s).")
    if failed:
        print(f"Failed ({len(failed)}):")
        for f in failed:
            print(f"  {f}")

    print("\nRestart the app to apply changes.")
