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

# ── After Effects template (Google Drive) ─────────────────────────
GDRIVE_FOLDER_ID      = "1OwZoHfrUxtAZtS042g63Pqw0eSqP31Ti"
TEMPLATE_VERSION_FILE = BASE_DIR / ".template_version"   # local marker
TEMPLATE_AEP          = ROOT_DIR / "Match Ratings - Template.aep"
TEMPLATE_FOLDER       = ROOT_DIR / "Match Ratings - Template folder"

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
    # Cache-bust raw CDN (raw.githubusercontent.com caches aggressively ~5 min)
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}cb={int(__import__('time').time())}"
    req = urllib.request.Request(url, headers={
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "User-Agent": "flashscore-ratings-updater",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _fetch_file_via_api(filename: str, timeout: int = 30) -> bytes:
    """
    Descarca un fisier. Incearca intai GitHub API (mereu proaspat), iar daca
    da fail (ex: rate limit 60/ora pe IP) cade pe raw CDN cu cache-busting.
    """
    import urllib.request, json as _json, base64 as _b64
    from urllib.parse import quote
    # 1) GitHub API (proaspat, dar limitat la 60 cereri/ora neautentificat)
    try:
        api_url = (f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
                   f"/contents/{quote(filename)}?ref={BRANCH}")
        req = urllib.request.Request(api_url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "flashscore-ratings-updater",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            obj = _json.loads(r.read())
        if obj.get("content"):
            return _b64.b64decode(obj["content"])
        dl = obj.get("download_url")
        if dl:
            return _fetch_url(dl, timeout=timeout)
    except Exception:
        pass
    # 2) Fallback: raw CDN (fara rate limit), cache-busted
    return _fetch_url(f"{RAW_BASE}/{filename}", timeout=timeout)


def _verify_file(data: bytes, filename: str) -> bool:
    """Verifica integritatea unui fisier descarcat (marime minima + sintaxa Python)."""
    if len(data) < 2:
        return False
    if filename.endswith(".py"):
        import ast
        try:
            ast.parse(data.decode("utf-8", errors="replace"))
        except SyntaxError:
            return False
    return True


def get_remote_version() -> str:
    # GitHub API (fresh, no CDN cache), fallback to cache-busted raw CDN
    import json as _json, base64 as _b64, urllib.request as _ur
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/version.txt?ref={BRANCH}"
        req = _ur.Request(api_url, headers={"Accept": "application/vnd.github.v3+json",
                                            "User-Agent": "flashscore-ratings-updater"})
        with _ur.urlopen(req, timeout=10) as r:
            obj = _json.loads(r.read())
        return _b64.b64decode(obj["content"]).decode("utf-8").strip()
    except Exception:
        return _fetch_url(f"{RAW_BASE}/version.txt").decode("utf-8").strip()


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


# ── After Effects template version ────────────────────────────────

def get_local_template_version() -> str:
    try:
        return TEMPLATE_VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return "0"


def get_remote_template_version() -> str:
    # GitHub API (fresh) with cache-busted raw CDN fallback
    try:
        return _fetch_file_via_api("template_version.txt").decode("utf-8").strip()
    except Exception:
        return _fetch_url(f"{RAW_BASE}/template_version.txt").decode("utf-8").strip()


def check_template_update(timeout: int = 8) -> tuple:
    """
    Returns (update_available: bool, local: str, remote: str).
    Update available when the remote template marker differs from the local one.
    """
    local = get_local_template_version()
    try:
        remote = get_remote_template_version()
    except Exception:
        return False, local, "?"
    # Auto-heal: existing install has the template but no local marker yet.
    # Adopt the current remote version silently so we DON'T wipe the user's
    # working template on first run. Only a later bump triggers a real update.
    if local == "0" and (TEMPLATE_AEP.exists() or TEMPLATE_FOLDER.exists()):
        try:
            TEMPLATE_VERSION_FILE.write_text(remote, encoding="utf-8")
        except Exception:
            pass
        return False, remote, remote
    return (remote != local and remote not in ("", "?")), local, remote


def apply_template_update(progress_cb=None) -> tuple:
    """
    Downloads the AE template folder from Google Drive and replaces the local
    copy directly (no backup). Returns (ok: bool, message: str).
    """
    if progress_cb:
        progress_cb("Removing old template...")
    # Direct replace: delete existing template files first
    try:
        if TEMPLATE_AEP.exists():
            TEMPLATE_AEP.unlink()
        if TEMPLATE_FOLDER.exists():
            shutil.rmtree(str(TEMPLATE_FOLDER), ignore_errors=True)
    except Exception:
        pass

    if progress_cb:
        progress_cb("Downloading template from Google Drive...")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "gdown", "--folder", GDRIVE_FOLDER_ID,
             "-O", str(ROOT_DIR), "--quiet"],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode != 0:
            return False, f"gdown failed: {result.stderr.strip() or result.stdout.strip()}"
    except Exception as e:
        return False, f"Download error: {e}"

    if not TEMPLATE_AEP.exists() and not TEMPLATE_FOLDER.exists():
        return False, "Template not found after download."

    # Save the new local marker so we don't re-download next time
    try:
        remote = get_remote_template_version()
        TEMPLATE_VERSION_FILE.write_text(remote, encoding="utf-8")
    except Exception:
        pass
    return True, "Template updated."


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
            data = _fetch_file_via_api(filename, timeout=30)
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
