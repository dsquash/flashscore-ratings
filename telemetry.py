"""
telemetry.py — Trimite notificari Pushover dupa fiecare run/refresh.
Nu blocheaza niciodata aplicatia daca reteaua lipseste.
"""

import json
import platform
import socket
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

_PUSHOVER_API = "https://api.pushover.net/1/messages.json"
_TOKEN = "afswgjonby544etrs33u55zhk9wp5w"
_USER  = "uevms5jfh4h8y5txjgey3rzzy5gsoo"


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
    event: str,
    flashscore_url: str = "",
    sofascore_url: str = "",
    players_ok: int = 0,
    players_not_found: int = 0,
    errors: list = None,
    duration_sec: float = 0.0,
    extra: dict = None,
):
    """
    Trimite notificare Pushover. Nu ridica exceptii niciodata.
    """
    try:
        _host = _get_hostname()
        _ver  = _get_version()
        _os   = platform.system()

        _match    = (extra or {}).get("match", "")
        _form     = (extra or {}).get("formations", "")

        if event == "run":
            _title = f"✅ {_match or 'Full Run'} — {_host}"
            if players_not_found > 0:
                _title = f"⚠️ {_match or 'Full Run'} — {players_not_found} negasiti — {_host}"
            _lines = [
                f"v{_ver} | {_os} | {int(duration_sec)}s",
            ]
            if _form:
                _lines.append(_form)
            _lines.append(f"Poze: {players_ok} OK / {players_not_found} negasite")
            if errors:
                _lines.append(f"Negasite: {', '.join(errors[:8])}")
                if len(errors) > 8:
                    _lines.append(f"  ... +{len(errors)-8} altii")
        elif event == "refresh":
            _title = f"🔄 Refresh Stats — {_host}"
            _lines = [
                f"v{_ver} | {_os}",
                f"Jucatori: {players_ok} OK / {players_not_found} negasiti",
            ]
        else:
            _title = f"Flashscore — {event} — {_host}"
            _lines = [f"v{_ver} | {_os}"]

        _msg = "\n".join(_lines)

        _data = urllib.parse.urlencode({
            "token":   _TOKEN,
            "user":    _USER,
            "title":   _title,
            "message": _msg,
            "priority": 0,
        }).encode()

        _req = urllib.request.Request(_PUSHOVER_API, data=_data)
        urllib.request.urlopen(_req, timeout=8)
    except Exception:
        pass
