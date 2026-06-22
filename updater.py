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

import os
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
GDRIVE_TEMPLATE_ZIP_ID = "1qNKeaZReMOWc4bU5qLVpBFlcYOnM3dOl"   # single template .zip on Drive
TEMPLATE_VERSION_FILE = BASE_DIR / ".template_version"   # local marker
TEMPLATE_AEP          = ROOT_DIR / "Match Ratings - Template.aep"
TEMPLATE_FOLDER       = ROOT_DIR / "Match Ratings - Template folder"

# Files common to all platforms
_COMMON_FILES = [
    "launcher.py",
    "run.py",
    "refresh_stats.py",
    "updater.py",
    "telemetry.py",
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
    Downloads the AE template from Google Drive into a temp dir, then swaps it
    in (replacing the local copy directly, no backup). Downloading to temp first
    means a failed/partial download never leaves you without a template.
    Returns (ok: bool, message: str).
    """
    import subprocess, tempfile

    if progress_cb:
        progress_cb("Downloading template from Google Drive...")

    if not GDRIVE_TEMPLATE_ZIP_ID:
        return False, "Template zip not configured yet."

    import zipfile
    _tmp = Path(tempfile.mkdtemp(prefix="fs_tpl_"))
    try:
        _zip_path = _tmp / "template.zip"
        # Direct HTTP download (proven reliable; gdown is flaky/throttled here).
        # &confirm=t bypasses Drive's virus-scan interstitial for larger files.
        _url = (f"https://drive.usercontent.google.com/download?id={GDRIVE_TEMPLATE_ZIP_ID}"
                f"&export=download&confirm=t")
        try:
            import urllib.request
            _req = urllib.request.Request(_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(_req, timeout=600) as _r, open(str(_zip_path), "wb") as _out:
                shutil.copyfileobj(_r, _out)
        except Exception as e:
            return False, f"Download error: {e}"

        if not _zip_path.exists() or _zip_path.stat().st_size < 1000:
            return False, "Zip download failed (empty file)."
        # Verify it's really a zip (PK header), not an HTML error/confirm page
        try:
            with open(str(_zip_path), "rb") as _hf:
                if _hf.read(2) != b"PK":
                    return False, "Downloaded file is not a zip (Drive returned a page)."
        except Exception:
            return False, "Could not read downloaded file."

        if progress_cb:
            progress_cb("Extracting template...")
        _extract = _tmp / "extracted"
        try:
            with zipfile.ZipFile(str(_zip_path)) as _z:
                _z.extractall(str(_extract))
        except Exception as e:
            return False, f"Zip extract failed: {e}"

        # Locate the downloaded .aep anywhere under the extracted dir
        _new_aep = None
        for _root, _dirs, _files in os.walk(str(_extract)):
            for _f in _files:
                if _f.lower().endswith(".aep"):
                    _new_aep = Path(_root) / _f
                    break
            if _new_aep:
                break
        if not _new_aep:
            return False, "Template (.aep) not found inside the zip."

        # The folder that actually contains the downloaded content
        _src_root = _new_aep.parent

        if progress_cb:
            progress_cb("Installing new template...")

        # Direct replace: remove old template, then move new files in
        try:
            if TEMPLATE_AEP.exists():
                TEMPLATE_AEP.unlink()
            if TEMPLATE_FOLDER.exists():
                shutil.rmtree(str(TEMPLATE_FOLDER), ignore_errors=True)
        except Exception:
            pass

        for _entry in os.listdir(str(_src_root)):
            if _entry == "__MACOSX" or _entry.startswith("._"):
                continue
            _src = _src_root / _entry
            _dst = ROOT_DIR / _entry
            try:
                if _dst.exists():
                    if _dst.is_dir():
                        shutil.rmtree(str(_dst), ignore_errors=True)
                    else:
                        _dst.unlink()
                shutil.move(str(_src), str(_dst))
            except Exception:
                pass

        if not TEMPLATE_AEP.exists():
            return False, "Template install failed (.aep missing after move)."

        # Save the new local marker so we don't re-download next time
        try:
            remote = get_remote_template_version()
            TEMPLATE_VERSION_FILE.write_text(remote, encoding="utf-8")
        except Exception:
            pass
        return True, "Template updated."
    finally:
        shutil.rmtree(str(_tmp), ignore_errors=True)


# ── Apply update ──────────────────────────────────────────────────

def _install_ae_panel():
    """
    Copiaza 'Lineup Panel.jsx' din _DO NOT TOUCH_ in folderul de panel-uri al
    fiecarei versiuni de After Effects gasite (Mac + Windows). Asa extensia se
    actualizeaza odata cu update-ul (necesita restart AE ca sa se incarce).
    Returneaza lista de cai unde s-a copiat.
    """
    import glob as _glob
    src = BASE_DIR / "Lineup Panel.jsx"
    if not src.exists():
        return []
    done = []
    _patterns = [
        "/Applications/Adobe After Effects */Scripts/ScriptUI Panels",
        "C:/Program Files/Adobe/Adobe After Effects */Support Files/Scripts/ScriptUI Panels",
        "C:/Program Files/Adobe/Adobe After Effects */Scripts/ScriptUI Panels",
    ]
    for _pat in _patterns:
        for _panels in _glob.glob(_pat):
            try:
                shutil.copy2(str(src), os.path.join(_panels, "Lineup Panel.jsx"))
                done.append(_panels)
            except Exception:
                pass
    return done


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

    # Copiaza panel-ul si in After Effects (altfel extensia ramane veche in AE)
    ae_done = []
    try:
        ae_done = _install_ae_panel()
        if ae_done and progress_cb:
            progress_cb(total, total, "Lineup Panel.jsx -> After Effects", True)
    except Exception:
        pass

    return updated, failed, ae_done


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
