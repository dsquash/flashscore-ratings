"""
telemetry.py — Trimite un rezumat al fiecarui run catre Google Sheets.
Se apeleaza la finalul run.py si refresh_stats.py.
Daca URL-ul nu e configurat sau reteaua lipseste, nu afecteaza aplicatia.
"""

import json
import platform
import socket
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Configureaza URL-ul Google Apps Script (inlocuieste dupa deploy) ──
TELEMETRY_URL = "https://script.google.com/macros/s/INLOCUIESTE_CU_URL_TAU/exec"


def _get_version() -> str:
    try:
        return (Path(__file__).parent / "version.txt").read_text(encoding="utf-8").strip()
    except Exception:
        return "?"


def _get_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def send(
    event: str,                    # "run" / "refresh"
    flashscore_url: str = "",
    sofascore_url: str = "",
    players_ok: int = 0,
    players_not_found: int = 0,
    errors: list = None,
    duration_sec: float = 0.0,
    extra: dict = None,
):
    """
    Trimite telemetrie la Google Sheets. Nu ridica exceptii niciodata.
    """
    if "INLOCUIESTE" in TELEMETRY_URL:
        return  # URL neconfigurat — skip

    payload = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "event": event,
        "platform": f"{platform.system()} {platform.release()}",
        "version": _get_version(),
        "hostname": _get_hostname(),
        "flashscore_url": flashscore_url,
        "sofascore_url": sofascore_url,
        "players_ok": players_ok,
        "players_not_found": players_not_found,
        "errors": "; ".join(errors or [])[:500],
        "duration_sec": round(duration_sec, 1),
        **(extra or {}),
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            TELEMETRY_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=6)
    except Exception:
        pass  # Telemetria nu trebuie sa blocheze niciodata aplicatia
