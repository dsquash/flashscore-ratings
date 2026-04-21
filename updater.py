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

BASE_DIR     = Path(__file__).parent
VERSION_FILE = BASE_DIR / "version.txt"

# ── GitHub config ─────────────────────────────────────────────────
GITHUB_OWNER = "dsquash"
GITHUB_REPO  = "flashscore-ratings"
BRANCH       = "main"
# ─────────────────────────────────────────────────────────────────

RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{BRANCH}"

# Files downloaded from GitHub on every update
UPDATABLE_FILES = [
    "launcher.py",
    "run.py",
    "refresh_stats.py",
    "updater.py",
    "populate_lineup.jsx",
    "reset_lineup.jsx",
    "refresh_comps.jsx",
    "save_template_state.jsx",
    "Lineup Panel.jsx",
    "START HERE.bat",
    "version.txt",
]

AE_PANEL_FILE = "Lineup Panel.jsx"


# ── Version helpers ───────────────────────────────────────────────

def get_local_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def _fetch_url(url: str, timeout: int = 10) -> bytes:
    import urllib.request
    from urllib.parse import quote
    # Encode only the path portion to handle spaces and special chars in filenames
    if "raw.githubusercontent.com" in url:
        parts = url.split("/", 7)  # split up to the filename part
        if len(parts) == 8:
            parts[7] = quote(parts[7], safe="/")
            url = "/".join(parts)
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


# ── AE extension installer ────────────────────────────────────────

def find_ae_script_folders() -> list:
    """
    Returns all After Effects ScriptUI Panels folders found on this machine.
    Searches standard Program Files paths for any AE version.
    """
    import os
    folders = []
    base = Path("C:/Program Files/Adobe")
    if base.exists():
        for ae_dir in base.glob("Adobe After Effects*"):
            panel_dir = ae_dir / "Support Files" / "Scripts" / "ScriptUI Panels"
            if panel_dir.exists():
                folders.append(panel_dir)
    return folders


def install_ae_extension(panel_src: Path) -> list:
    """
    Copies Lineup Panel.jsx to all detected AE ScriptUI Panels folders.
    On permission errors, retries via PowerShell (elevated copy).
    Returns list of (path, success, error_msg) tuples.
    """
    import subprocess
    results = []
    ae_folders = find_ae_script_folders()
    for folder in ae_folders:
        dest = folder / AE_PANEL_FILE
        ok = False
        err_msg = ""
        # First try direct copy
        try:
            shutil.copy2(str(panel_src), str(dest))
            ok = True
        except PermissionError:
            # Retry via PowerShell with elevated privileges (UAC prompt)
            try:
                ps_cmd = (
                    f'Copy-Item -Path "{panel_src}" -Destination "{dest}" -Force'
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f'Start-Process powershell -ArgumentList \'-NoProfile -Command "{ps_cmd}"\''
                     ' -Verb RunAs -Wait'],
                    capture_output=True, timeout=30
                )
                # Verify the copy succeeded
                if dest.exists():
                    ok = True
                else:
                    err_msg = "Copy via UAC failed — try running the app as Administrator."
            except Exception as e2:
                err_msg = f"Permission denied. Run as Administrator to install AE extension. ({e2})"
        except Exception as e:
            err_msg = str(e)
        results.append((str(folder), ok, err_msg))
    return results


# ── Apply update ──────────────────────────────────────────────────

def apply_update(progress_cb=None) -> tuple:
    """
    Downloads each file in UPDATABLE_FILES from GitHub and saves it locally.
    Then installs the AE extension to all detected AE folders.

    progress_cb(current, total, label, ok) called after each step.
    Returns (updated: list, failed: list, ae_results: list).
    """
    updated = []
    failed  = []
    total   = len(UPDATABLE_FILES)

    for i, filename in enumerate(UPDATABLE_FILES):
        url  = f"{RAW_BASE}/{filename}"
        dest = BASE_DIR / filename
        ok   = False
        try:
            data = _fetch_url(url, timeout=30)
            dest.write_bytes(data)
            updated.append(filename)
            ok = True
        except Exception as e:
            failed.append(f"{filename}: {e}")

        if progress_cb:
            progress_cb(i + 1, total, filename, ok)

    # Install AE extension
    ae_results = []
    panel_src = BASE_DIR / AE_PANEL_FILE
    if panel_src.exists():
        ae_results = install_ae_extension(panel_src)

    return updated, failed, ae_results


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

    updated, failed, ae_results = apply_update(prog)

    print(f"\nUpdated {len(updated)} file(s).")

    if ae_results:
        print("\nAfter Effects extension:")
        for path, ok, err in ae_results:
            if ok:
                print(f"  ✓ Installed → {path}")
            else:
                print(f"  ✗ Failed ({path}): {err}")
    elif not ae_results:
        print("\nAfter Effects: no AE installation found (copy Lineup Panel.jsx manually).")

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for f in failed:
            print(f"  {f}")

    print("\nRestart the app to apply changes.")
