#!/usr/bin/env python3
"""
refresh_stats.py — Actualizeaza doar datele (stats, ratings, scor, events)
============================================================================
Rescraped Flashscore si salveaza data.json fara sa atinga imaginile existente.

Rulare:
    python refresh_stats.py
    python refresh_stats.py "https://www.flashscore.com/match/..."

Daca nu dai URL, foloseste URL-ul din flashscore_output/last_url.txt
(salvat automat de run.py la prima rulare).

Dupa refresh: deschide AE si ruleaza populate_lineup.jsx.
"""

import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
OUTPUT_DIR      = BASE_DIR / "flashscore_output"
DATA_JSON       = OUTPUT_DIR / "data.json"
LAST_URL        = OUTPUT_DIR / "last_url.txt"
SUMMARY_TXT     = OUTPUT_DIR / "last_refresh_summary.txt"


def main():
    # ── 1. Determina URL-ul ───────────────────────────────────────
    if len(sys.argv) >= 2:
        url = sys.argv[1]
    elif LAST_URL.exists():
        url = LAST_URL.read_text(encoding="utf-8").strip()
        print(f"  URL from last_url.txt: {url}")
    else:
        print("ERROR: no URL found. Pass it as an argument or run run.py first.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("  REFRESH STATS — refresh_stats.py")
    print("=" * 55)

    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        import run as r
    except ImportError as e:
        print(f"ERROR: could not import run.py: {e}")
        sys.exit(1)

    print("\n[1/2] Re-scraping Flashscore...")
    new_data = r.scrape_flashscore(url)

    if not new_data["home"]["players"]:
        print("\n⚠ No players found. Check flashscore_output/debug.png")
        sys.exit(1)

    for group in [new_data["home"]["players"], new_data["away"]["players"],
                  new_data["home"]["substitutes"], new_data["away"]["substitutes"]]:
        for p in group:
            p.pop("img_src", None)

    old_data = None
    if DATA_JSON.exists():
        try:
            with open(DATA_JSON, "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            pass

    print("\n[2/2] Comparing and saving...")

    changes = []
    if old_data:
        changes = _collect_diff(old_data, new_data)
        if changes:
            print("\n  CHANGES DETECTED:")
            for c in changes:
                print(c)
        else:
            print("\n  No changes compared to previous data.json.")

    # Preserve kit numbers from SoFIFA (refresh doesn't re-download from SoFIFA)
    if old_data:
        _restore_kit_numbers(old_data, new_data)

    LAST_URL.write_text(url, encoding="utf-8")

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ data.json updated: {DATA_JSON}")

    m = new_data["match"]
    match_line = f"{m['home_team']} {m['home_score']} - {m['away_score']} {m['away_team']}"

    # Write summary for AE panel / launcher popup
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if changes:
        summary = match_line + "\n\n" + "\n".join(changes)
    else:
        summary = match_line + "\n\nNo changes detected."
    SUMMARY_TXT.write_text(summary, encoding="utf-8")

    print(f"""
{"=" * 55}
  DONE!
  {match_line}

  Next step:
    Open AE and run populate_lineup.jsx
{"=" * 55}
""")


def _restore_kit_numbers(old_data: dict, new_data: dict):
    """
    Copiaza kit numbers (numarul de tricou din SoFIFA) din data.json vechi
    in cel nou, pentru jucatorii cu acelasi nume.
    refresh_stats nu re-descarca de pe SoFIFA, deci pastram ce avem.
    """
    # Construieste index nume → numar din datele vechi
    old_numbers = {}
    for group_key in [("home", "players"), ("home", "substitutes"),
                       ("away", "players"), ("away", "substitutes")]:
        team, grp = group_key
        for p in old_data.get(team, {}).get(grp, []):
            if p.get("name") and p.get("number"):
                old_numbers[p["name"]] = p["number"]

    restored = 0
    for team in ["home", "away"]:
        for grp in ["players", "substitutes"]:
            for p in new_data.get(team, {}).get(grp, []):
                name = p.get("name", "")
                if name in old_numbers and not p.get("number"):
                    p["number"] = old_numbers[name]
                    restored += 1

    if restored:
        print(f"  ✓ Kit numbers preserved: {restored} player(s)")


def _collect_diff(old: dict, new: dict) -> list:
    """Returneaza lista de modificari fata de data.json anterior."""
    changes = []

    # Scor
    om, nm = old.get("match", {}), new.get("match", {})
    old_score = f"{om.get('home_score','?')}-{om.get('away_score','?')}"
    new_score = f"{nm.get('home_score','?')}-{nm.get('away_score','?')}"
    if old_score != new_score:
        changes.append(f"Score: {old_score} → {new_score}")

    # Avg ratings
    for side in ["home", "away"]:
        key = f"{side}_avg_rating"
        if om.get(key) != nm.get(key):
            changes.append(f"Avg rating {side}: {om.get(key,'?')} → {nm.get(key,'?')}")

    # Ratings + events per jucator
    for team in ["home", "away"]:
        for grp in ["players", "substitutes"]:
            old_players = {p["name"]: p for p in old.get(team, {}).get(grp, [])}
            for p in new.get(team, {}).get(grp, []):
                name = p.get("name", "")
                op = old_players.get(name)
                if op:
                    if op.get("rating") != p.get("rating"):
                        changes.append(
                            f"{name}: {op.get('rating','?')} → {p.get('rating','?')}"
                        )
                    old_ev = sorted(op.get("events", []))
                    new_ev = sorted(p.get("events", []))
                    if old_ev != new_ev:
                        added   = [e for e in new_ev if e not in old_ev]
                        removed = [e for e in old_ev if e not in new_ev]
                        parts = []
                        if added:   parts.append("+" + ", ".join(str(e) for e in added))
                        if removed: parts.append("-" + ", ".join(str(e) for e in removed))
                        changes.append(f"{name} events: {' | '.join(parts)}")
                else:
                    changes.append(f"New player: {name} ({team}/{grp})")

    return changes


if __name__ == "__main__":
    main()
