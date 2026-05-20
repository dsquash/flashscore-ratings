#!/usr/bin/env python3
"""
refresh_stats.py — Actualizeaza datele (stats, ratings, scor, events)
=========================================================================
Rescraped Flashscore si salveaza data.json fara sa atinga imaginile existente.

Rulare:
    python refresh_stats.py
    python refresh_stats.py "https://www.flashscore.com/match/..."
    python refresh_stats.py --download-missing          # descarca si pozele lipsa
    python refresh_stats.py "URL" --download-missing

Daca nu dai URL, foloseste URL-ul din flashscore_output/last_url.txt
(salvat automat de run.py la prima rulare).

Dupa refresh: deschide AE si ruleaza populate_lineup.jsx.
"""

import sys
import json
import asyncio
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
OUTPUT_DIR      = BASE_DIR / "flashscore_output"
IMAGES_DIR      = OUTPUT_DIR / "images"
DATA_JSON       = OUTPUT_DIR / "data.json"
LAST_URL        = OUTPUT_DIR / "last_url.txt"
SUMMARY_TXT     = OUTPUT_DIR / "last_refresh_summary.txt"


def main():
    # ── Parseaza argumente ───────────────────────────────────────
    args = sys.argv[1:]
    download_missing = "--download-missing" in args
    url_args = [a for a in args if not a.startswith("--")]

    # ── 1. Determina URL-ul ───────────────────────────────────────
    if url_args:
        url = url_args[0]
    elif LAST_URL.exists():
        url = LAST_URL.read_text(encoding="utf-8").strip()
        print(f"  URL from last_url.txt: {url}")
    else:
        print("⚠ Nu a fost gasit niciun URL salvat.")
        print("  Fie pasati URL-ul ca argument:")
        print('  python refresh_stats.py "https://www.flashscore.com/match/..."')
        print("  Fie rulati mai intai Full Run din launcher pentru a salva URL-ul automat.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    if download_missing:
        print("  REFRESH STATS + POZE — refresh_stats.py")
    else:
        print("  REFRESH STATS — refresh_stats.py")
    print("=" * 55)

    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        import run as r
    except ImportError as e:
        print(f"⚠ Eroare la importul run.py: {e}")
        print("  Asigurati-va ca run.py exista in acelasi folder cu refresh_stats.py.")
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
        except json.JSONDecodeError as e:
            print(f"\n⚠ data.json este corupt si nu poate fi citit: {e}")
            print("  Continuam fara comparatie — datele vechi nu vor fi comparate.")
            print("  Daca problema persista, ruleaza Full Run pentru a regenera data.json.\n")
        except Exception as e:
            print(f"\n⚠ Eroare la citirea data.json: {e}\n")

    print("\n[2/2] Comparing and saving...")

    changes = []
    new_players = []
    if old_data:
        changes = _collect_diff(old_data, new_data)
        new_players = _find_new_players(old_data, new_data)
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

    # Build summary base
    if changes:
        summary = match_line + "\n\n" + "\n".join(changes)
    else:
        summary = match_line + "\n\nNo changes detected."

    # ── 3. Download poze lipsa (optional) ────────────────────────
    if download_missing:
        summary += _download_missing_photos(r, new_data, new_players)

    # Write summary file
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_TXT.write_text(summary, encoding="utf-8")

    print(f"""
{"=" * 55}
  DONE!
  {match_line}

  Next step:
    Open AE and run populate_lineup.jsx
{"=" * 55}
""")


def _find_new_players(old_data: dict, new_data: dict) -> list:
    """Returneaza lista de jucatori noi (nu existau in data.json anterior)."""
    old_names = set()
    for team in ["home", "away"]:
        for grp in ["players", "substitutes"]:
            for p in old_data.get(team, {}).get(grp, []):
                if p.get("name"):
                    old_names.add(p["name"])

    new_players = []
    for team in ["home", "away"]:
        for grp in ["players", "substitutes"]:
            for p in new_data.get(team, {}).get(grp, []):
                if p.get("name") and p["name"] not in old_names:
                    new_players.append(p["name"])
    return new_players


def _download_missing_photos(r, new_data: dict, new_players: list) -> str:
    """
    Descarca pozele lipsa pentru jucatorii fara imagine in images/.
    Returneaza un string de adaugat la summary.
    """
    print("\n[3/3] Checking for missing photos...")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    groups = [
        (new_data["home"]["players"],     "home_player"),
        (new_data["away"]["players"],     "away_player"),
        (new_data["home"]["substitutes"], "home_sub"),
        (new_data["away"]["substitutes"], "away_sub"),
    ]

    # Incarca placeholders.json (poze generate, nu reale)
    placeholders_path = OUTPUT_DIR / "placeholders.json"
    try:
        placeholders = json.loads(placeholders_path.read_text(encoding="utf-8")) if placeholders_path.exists() else {}
    except Exception:
        placeholders = {}

    missing_players = []
    for players, prefix in groups:
        for i, p in enumerate(players, 1):
            name = p.get("name", "")
            if not name:
                continue
            img = IMAGES_DIR / f"{prefix}_{i}.png"
            file_key = f"{prefix}_{i}"
            is_placeholder = file_key in placeholders
            # Descarca daca: nu exista poza SAU e placeholder SAU e jucator nou
            if not img.exists() or is_placeholder or name in new_players:
                missing_players.append((name, prefix, i))

    if not missing_players:
        print("  ✓ All players already have photos.")
        return "\n\nAll player photos already downloaded."

    names_list = [name for name, _, _ in missing_players]
    print(f"  {len(missing_players)} missing/new photo(s):")
    for name in names_list:
        marker = " (new)" if name in new_players else ""
        print(f"    → {name}{marker}")

    print("\n  Downloading from SoFIFA...")
    asyncio.run(r.download_all_images(new_data))

    # Reincarca placeholders dupa download (pot fi actualizate)
    try:
        placeholders = json.loads(placeholders_path.read_text(encoding="utf-8")) if placeholders_path.exists() else {}
    except Exception:
        placeholders = {}

    # Verifica ce s-a descarcat
    downloaded = []
    still_missing = []
    for name, prefix, i in missing_players:
        img = IMAGES_DIR / f"{prefix}_{i}.png"
        file_key = f"{prefix}_{i}"
        is_placeholder = file_key in placeholders
        if img.exists() and not is_placeholder:
            downloaded.append(name)
        else:
            still_missing.append(name)

    parts = []
    if downloaded:
        parts.append(f"New photos downloaded ({len(downloaded)}): {', '.join(downloaded)}")
    if still_missing:
        parts.append(f"Still missing ({len(still_missing)}): {', '.join(still_missing)}")
    if downloaded:
        parts.append("→ Run POPULATE in the AE panel to update the template.")

    return "\n\n" + "\n".join(parts) if parts else ""


def _restore_kit_numbers(old_data: dict, new_data: dict):
    """
    Copiaza kit numbers (numarul de tricou din SoFIFA) din data.json vechi
    in cel nou, pentru jucatorii cu acelasi nume.
    refresh_stats nu re-descarca de pe SoFIFA, deci pastram ce avem.
    """
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

    om, nm = old.get("match", {}), new.get("match", {})
    old_score = f"{om.get('home_score', '?')}-{om.get('away_score', '?')}"
    new_score = f"{nm.get('home_score', '?')}-{nm.get('away_score', '?')}"
    if old_score != new_score:
        changes.append(f"Score: {old_score} → {new_score}")

    for side in ["home", "away"]:
        key = f"{side}_avg_rating"
        if om.get(key) != nm.get(key):
            old_val = om.get(key, "?")
            new_val = nm.get(key, "?")
            changes.append(f"Avg rating {side}: {old_val} → {new_val}")

    for team in ["home", "away"]:
        for grp in ["players", "substitutes"]:
            old_players = {p["name"]: p for p in old.get(team, {}).get(grp, [])}
            for p in new.get(team, {}).get(grp, []):
                name = p.get("name", "")
                op = old_players.get(name)
                if op:
                    if op.get("rating") != p.get("rating"):
                        old_r = op.get("rating", "?")
                        new_r = p.get("rating", "?")
                        changes.append(f"{name}: {old_r} → {new_r}")
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
