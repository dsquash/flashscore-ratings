#!/usr/bin/env python3
"""
run.py — FlashScore Ratings Automation
=======================================
Setup (o singura data):
    pip install playwright httpx pillow
    playwright install chromium

Rulare:
    python run.py "https://www.flashscore.com/match/football/..."

Ce face:
    1. Scrapeaza lineup + ratings + events de pe Flashscore
    2. Descarca pozele jucatorilor DIRECT de pe Flashscore
    3. Salveaza flashscore_output/data.json
    4. Salveaza flashscore_output/images/home_player_1.png etc.

Next step:
    Deschide proiectul AE si ruleaza populate_lineup.jsx
"""

import sys
import re
import json
import asyncio
import io
import traceback
import unicodedata
from pathlib import Path

# Forteaza UTF-8 pe stdout (fix pentru Windows cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import httpx

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

# ── Paths ─────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "flashscore_output"
IMAGES_DIR = OUTPUT_DIR / "images"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

# ── Tipul meciului ─────────────────────────────────────────────
# "club"     = meci de club (Premier League, Champions League etc.)
# "national" = meci de nationala (Nations League, CM, CE etc.)
MATCH_TYPE = "club"




# ══════════════════════════════════════════════════════════════
#  STEP 1 — SCRAPE FLASHSCORE
# ══════════════════════════════════════════════════════════════

def ensure_lineups_url(url):
    """
    Normalizeaza URL-ul la pagina de lineups, PASTRAND domeniul original.
    Astfel livesport.cz → ramane livesport.cz (nume cu diacritice),
    flashscore.com → ramane flashscore.com etc.

    Domenii si caile lor de lineup:
      flashscore.*         /match/football/{s1}/{s2}/summary/lineups/
      livesport.cz         /zapas/fotbal/{s1}/{s2}/prehled/sestavy/
      (orice alt domeniu)  /match/football/{s1}/{s2}/summary/lineups/
    """
    # Separa query params (?mid= e esential)
    if "?" in url:
        base, query = url.split("?", 1)
    else:
        base, query = url, ""

    # Elimina fragment (#/...) daca exista
    if "#" in base:
        base = base.split("#")[0]

    base = base.rstrip("/")

    # Extrage domeniul
    domain_m = re.match(r'(https?://[^/]+)', base)
    domain = domain_m.group(1) if domain_m else "https://www.flashscore.com"

    # Extrage slug-urile celor 2 echipe (ID-urile sunt universale cross-domain)
    slug_m = re.search(
        r'/([^/]+-[A-Za-z0-9]{6,10})/([^/]+-[A-Za-z0-9]{6,10})',
        base
    )
    if slug_m:
        slug1, slug2 = slug_m.group(1), slug_m.group(2)

        # Construieste calea corecta pentru domeniu
        if "livesport.cz" in domain:
            path = f"/zapas/fotbal/{slug1}/{slug2}/prehled/sestavy/"
        else:
            path = f"/match/football/{slug1}/{slug2}/summary/lineups/"

        return domain + path + ("?" + query if query else "")

    # Fallback: ajusteaza calea daca nu s-au gasit slug-urile
    lineup_markers = ["/lineups", "/sestavy"]
    if not any(m in base for m in lineup_markers):
        if "livesport.cz" in domain and "/prehled" in base:
            base = re.sub(r"/prehled.*$", "/prehled/sestavy/", base)
        elif "/summary" in base:
            base = re.sub(r"/summary.*$", "/summary/lineups/", base)
        else:
            base = base + "/summary/lineups/"

    return base + ("?" + query if query else "")


def scrape_flashscore(url: str) -> dict:
    from playwright.sync_api import sync_playwright
    import time

    lineups_url = ensure_lineups_url(url)
    print(f"\n[1/3] Scraping Flashscore...")
    print(f"      {lineups_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=UA,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        try:
            page.goto(lineups_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as _nav_err:
            _nav_msg = str(_nav_err)
            if "ERR_NAME_NOT_RESOLVED" in _nav_msg or "ERR_INTERNET_DISCONNECTED" in _nav_msg or "ERR_NETWORK_CHANGED" in _nav_msg:
                print("\n\n  ⚠ EROARE INTERNET: Nu se poate conecta la Flashscore.")
                print("  Verificati conexiunea la internet si incercati din nou.\n")
            elif "ERR_CONNECTION_TIMED_OUT" in _nav_msg or "Timeout" in _nav_msg:
                print("\n\n  ⚠ TIMEOUT: Flashscore nu raspunde. Incercati din nou.\n")
            else:
                print(f"\n\n  ⚠ Eroare navigare: {_nav_msg[:120]}\n")
            browser.close()
            raise SystemExit(1)

        # Cookie banner
        try:
            page.wait_for_selector("#onetrust-accept-btn-handler", timeout=5000)
            page.click("#onetrust-accept-btn-handler")
        except Exception:
            pass

        # Asteapta formationul
        try:
            page.wait_for_selector(".lf__formation", timeout=15000)
            print("      Lineup OK")
        except Exception:
            print("      ⚠ Lineup not loaded — check debug.png")

        # Scroll pana jos ca sa se incarce lazy-loaded substitutions
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        # Asteapta sa apara mai mult de 2 elemente substituedPlayer
        for _ in range(10):
            count = page.evaluate(
                "document.querySelectorAll('.lf__participantNew--substituedPlayer').length"
            )
            if count >= 4:
                break
            time.sleep(0.5)

        page.screenshot(path=str(OUTPUT_DIR / "debug.png"), full_page=True)

        data = page.evaluate("""() => {
            const result = {
                match: {
                    home_team:"", away_team:"", home_score:"", away_score:"",
                    status:"", home_formation:"", away_formation:"",
                    home_logo_url:"", away_logo_url:""
                },
                home: { players:[], substitutes:[] },
                away: { players:[], substitutes:[] }
            };

            // ── Echipe ────────────────────────────────────────────
            const homeEl = document.querySelector(
                ".duelParticipant__home .participant__participantName, " +
                ".duelParticipant__home [class*='participantName']"
            );
            const awayEl = document.querySelector(
                ".duelParticipant__away .participant__participantName, " +
                ".duelParticipant__away [class*='participantName']"
            );
            if (homeEl) result.match.home_team = homeEl.innerText.trim();
            if (awayEl) result.match.away_team = awayEl.innerText.trim();

            // ── Logo-uri echipe (direct de pe Flashscore) ─────────
            function extractLogo(sectionSel) {
                const section = document.querySelector(sectionSel);
                if (!section) return "";
                // Selector specific pentru logo echipa (img din link-ul de echipa)
                const teamLinkImg = section.querySelector(
                    '[class*="participantLink--team"] img, [class*="participantLogo"] img'
                );
                if (teamLinkImg) {
                    const src = teamLinkImg.src || teamLinkImg.getAttribute("src") || "";
                    if (src) return src;
                }
                // Fallback: orice img cu src /image/data/ (format Flashscore CDN)
                for (const img of section.querySelectorAll("img")) {
                    const src = img.src || img.getAttribute("src") || "";
                    if (src && src.includes("/image/data/")) return src;
                }
                return "";
            }
            result.match.home_logo_url = extractLogo(".duelParticipant__home");
            result.match.away_logo_url = extractLogo(".duelParticipant__away");

            // ── Scor ──────────────────────────────────────────────
            // Incearca mai multi selectori in ordine de prioritate
            const scoreSelectors = [
                ".detailScore__wrapper",
                ".duelScore__scoreWrapper",
                "[class*='score__wrapper']",
                "[class*='Score__wrapper']",
                "[class*='scoreWrapper']",
                "[class*='detailScore']"
            ];
            for (const sel of scoreSelectors) {
                const el = document.querySelector(sel);
                if (!el) continue;
                const spans = el.querySelectorAll("span");
                // Cauta doua span-uri cu numere (scoruri)
                const nums = [];
                spans.forEach(s => {
                    const t = s.innerText.trim();
                    if (/^\\d+$/.test(t)) nums.push(t);
                });
                if (nums.length >= 2) {
                    result.match.home_score = nums[0];
                    result.match.away_score = nums[1];
                    break;
                }
                // Fallback: text complet cu pattern "X - Y" sau "X-Y"
                const full = el.innerText.replace(/\\s/g,"");
                const m = full.match(/^(\\d+)[:\\-](\\d+)$/);
                if (m) {
                    result.match.home_score = m[1];
                    result.match.away_score = m[2];
                    break;
                }
            }
            // Fallback global: cauta orice element cu pattern scor "X - Y"
            if (!result.match.home_score) {
                document.querySelectorAll("*").forEach(el => {
                    if (result.match.home_score) return;
                    if (el.children.length > 3) return;
                    const t = (el.innerText || "").trim();
                    const m = t.match(/^(\\d{1,3})\\s*[-:]\\s*(\\d{1,3})$/);
                    if (m && parseInt(m[1]) < 20 && parseInt(m[2]) < 20) {
                        result.match.home_score = m[1];
                        result.match.away_score = m[2];
                    }
                });
            }

            // ── Average ratings (Ø 7.2 / Ø 6.5 in colturile terenului) ──
            result.match.home_avg_rating = "";
            result.match.away_avg_rating = "";
            const avgFound = [];

            // Metoda 1: scaneaza body.innerText pentru "Ø X.X" — ordinea in text = home first, away second
            {
                const bodyText = (document.body.innerText || '');
                const re = /[\u00d8\u00f8\u00d8Ø]\\s*(\\d\\.\\d)/g;
                let m;
                while ((m = re.exec(bodyText)) !== null && avgFound.length < 2) {
                    const v = parseFloat(m[1]);
                    if (v >= 4.0 && v <= 9.9) avgFound.push(String(v));
                }
            }

            // Metoda 2: fallback — CSS selectors pentru clase Flashscore
            if (avgFound.length < 2) {
                const avgSelectors = [
                    '[class*="lf__average"]', '[class*="lfAverage"]',
                    '[class*="lineupAverage"]', '[class*="teamRating"]',
                    '[class*="average" i]'
                ];
                for (const sel of avgSelectors) {
                    if (avgFound.length >= 2) break;
                    document.querySelectorAll(sel).forEach(el => {
                        if (avgFound.length >= 2) return;
                        const t = (el.innerText || '').trim();
                        const m = t.match(/(\\d\\.\\d)/);
                        if (m) {
                            const v = parseFloat(m[1]);
                            if (v >= 4.0 && v <= 9.9) avgFound.push(m[1]);
                        }
                    });
                }
            }

            if (avgFound[0]) result.match.home_avg_rating = avgFound[0];
            if (avgFound[1]) result.match.away_avg_rating = avgFound[1];

            // ── Status ────────────────────────────────────────────
            const statusEl = document.querySelector(
                ".fixedHeaderDuel__detailStatus, .detailScore__status, [class*='detailStatus']"
            );
            if (statusEl) result.match.status = statusEl.innerText.trim();

            // ── Formatii — cauta "4-2-3-1" sau "4 - 2 - 3 - 1" oriunde ──
            const fFound = [];
            document.querySelectorAll("*").forEach(el => {
                if (el.children.length === 0 && fFound.length < 2) {
                    const raw = (el.innerText || "").trim();
                    const normalized = raw.replace(/\\s/g, "");
                    if (/^\\d(-\\d+){2,4}$/.test(normalized) && !fFound.includes(normalized))
                        fFound.push(normalized);
                }
            });
            result.match.home_formation = fFound[0] || "";
            result.match.away_formation = fFound[1] || "";

            // ── Helper: extrage events dintr-un element player ────
            function getEvents(el) {
                const e = [];

                // ── Goluri ─────────────────────────────────────────
                // Gol simplu
                el.querySelectorAll(
                    '[data-testid="wcl-icon-incidents-goal-soccer"], ' +
                    '[data-testid*="goal-soccer"]:not([data-testid*="brace"]):not([data-testid*="hat"])'
                ).forEach(() => e.push("goal"));

                // Brace / double goal (2 goluri) — icon distinct pe Flashscore
                el.querySelectorAll(
                    '[data-testid*="brace"], [data-testid*="Brace"], ' +
                    '[data-testid*="goal-soccer-double"], [data-testid*="double-goal"], ' +
                    '[data-testid*="goal-soccer-brace"]'
                ).forEach(() => { e.push("goal"); e.push("goal"); });

                // Hat-trick (3 goluri)
                el.querySelectorAll(
                    '[data-testid*="hat-trick"], [data-testid*="hatTrick"], ' +
                    '[data-testid*="hat_trick"], [data-testid*="HatTrick"], ' +
                    '[data-testid*="goal-soccer-hat"]'
                ).forEach(() => { e.push("goal"); e.push("goal"); e.push("goal"); });

                // Fallback: badge numeric (ex. "2" sau "3") langa orice icon de incident
                if (e.filter(x => x === "goal").length === 0) {
                    el.querySelectorAll('[data-testid*="incidents"]').forEach(icon => {
                        const p = icon.parentElement;
                        if (!p) return;
                        p.querySelectorAll('span, div, small, b').forEach(node => {
                            if (node.children.length > 0) return;
                            const txt = (node.innerText || '').trim();
                            if (txt === '2') { e.push("goal"); e.push("goal"); }
                            else if (txt === '3') { e.push("goal"); e.push("goal"); e.push("goal"); }
                        });
                    });
                }

                // Own goal
                if (el.querySelector('[data-testid*="own-goal"]')) e.push("own_goal");
                // Yellow card
                if (el.querySelector(
                    '[data-testid="wcl-icon-incidents-yellow-card"], ' +
                    '[data-testid*="yellow"]'
                )) e.push("yellow_card");
                // Red card
                if (el.querySelector(
                    '[data-testid*="red-card"], [data-testid*="redCard"]'
                )) e.push("red_card");
                // Substituted out
                if (el.querySelector(
                    '[data-testid="wcl-icon-incidents-substitution"], ' +
                    '[data-testid*="substitution"]'
                )) e.push("substituted_out");
                // Star player (cel mai bun jucator) — badge cu clasa/atribut "star"
                const ratingEl = el.querySelector(
                    '[data-testid="wcl-badgeRating"], [data-testid*="badgeRating"]'
                );
                if (ratingEl) {
                    const rClass = ratingEl.className || "";
                    const rParent = ratingEl.parentElement;
                    const pClass = rParent ? (rParent.className || "") : "";
                    if (rClass.toLowerCase().includes("star") ||
                        pClass.toLowerCase().includes("star") ||
                        el.querySelector('[class*="star" i], [data-testid*="star" i]')) {
                        e.push("star");
                    }
                }
                return e;
            }

            // ── Helper: curata numele (scoate prefix numar) ──────
            function cleanName(raw) {
                return raw.replace(/^\\d+[\\n\\r\\s]+/, "").trim();
            }

            // ── Helper: extrage datele unui player din .lf__player ─
            function extractPlayer(playerEl, posLeft, posTop) {
                // Nume — incearca data-testid, fallback la img[alt]
                const nameEl = playerEl.querySelector(
                    '[data-testid="wcl-lineupsParticipantName"], ' +
                    '[data-testid*="ParticipantName"]'
                );
                let name = nameEl ? cleanName(nameEl.innerText) : "";
                if (!name) {
                    const imgAlt = playerEl.querySelector("img[alt]");
                    if (imgAlt) name = imgAlt.alt.trim();
                }
                if (!name) return null;

                // Poza — src sau primul srcset entry
                const imgEl = playerEl.querySelector("img[alt]");
                let imgSrc = "";
                if (imgEl) {
                    imgSrc = imgEl.src || "";
                    if (!imgSrc && imgEl.getAttribute("srcset")) {
                        const srcsetParts = imgEl.getAttribute("srcset").split(",");
                        imgSrc = srcsetParts[srcsetParts.length - 1].trim().split(" ")[0];
                    }
                }

                // Rating
                const ratingEl = playerEl.querySelector(
                    '[data-testid="wcl-badgeRating"], [data-testid*="badgeRating"]'
                );
                const rating = ratingEl ? ratingEl.innerText.trim() : "";

                // Numar tricou — cauta element cu text pur numeric
                let number = "";
                playerEl.querySelectorAll("span, div").forEach(el => {
                    if (!number && /^\\d{1,2}$/.test((el.innerText || "").trim()) &&
                        el.children.length === 0) {
                        number = el.innerText.trim();
                    }
                });

                return {
                    name, number, rating,
                    position_left: Math.round(posLeft),
                    position_top:  Math.round(posTop),
                    img_src: imgSrc,
                    events: getEvents(playerEl),
                    flashscore_url: getPlayerUrl(playerEl)
                };
            }

            // ── Calculeaza pozitii din linii ───────────────────────
            // Liniile in DOM sunt ordonate GK→atacanti (linie 0 = GK)
            // position_top: GK=88, atacanti=18
            // position_left: distribuit uniform pe latime (15%..85%)
            function parseFormationLines(formationEl) {
                const players = [];
                // Doar copiii DIRECTI cu clasa lf__line — evita linii nested din alte sectiuni
                const lines = Array.from(formationEl.children)
                    .filter(c => c.classList.contains("lf__line"));
                const nLines = lines.length;

                lines.forEach((line, lineIdx) => {
                    const playerEls = line.querySelectorAll(".lf__player");
                    const count = playerEls.length;
                    const posTop = nLines > 1
                        ? 88 - (lineIdx / (nLines - 1)) * 70
                        : 88;

                    playerEls.forEach((pEl, pIdx) => {
                        // 2 jucatori intr-o linie (ex. 2 MF centrali) → range mai strans
                        // Altfel 15-85 ar pune MF-ii pe margini ca fundasii extremi
                        const posLeft = count === 1 ? 50
                            : count === 2 ? 30 + pIdx * 40   // 30, 70 — MF centrali mai aproape de centru
                            : 15 + (pIdx / (count - 1)) * 70;
                        const p = extractPlayer(pEl, posLeft, posTop);
                        if (p) {
                            p.index = players.length;
                            players.push(p);
                        }
                    });
                });
                return players;
            }

                        // ── Helper: extrage URL profil jucator Flashscore ────
            function getPlayerUrl(playerEl) {
                // 1. Link direct in interiorul elementului
                const a = playerEl.querySelector('a[href*="/player/"]');
                if (a) return a.href;
                // 2. Elementul e infasurat intr-un <a> (traverseaza DOAR spre radacina,
                //    fara a cauta in descendenti — altfel prinde URL-uri ale altor jucatori)
                let par = playerEl.parentElement;
                while (par && par !== document.body) {
                    if (par.tagName === 'A' && par.href && par.href.includes('/player/'))
                        return par.href;
                    // Nu face querySelector pe par (ar gasi primul /player/ link din sectiune,
                    // care poate fi al unui alt jucator)
                    par = par.parentElement;
                }
                return '';
            }

            // ── Titulari ──────────────────────────────────────────
            const homeForm = document.querySelector(".lf__formation");
            const awayForm = document.querySelector(".lf__formationAway");

            if (homeForm) result.home.players = parseFormationLines(homeForm);
            if (awayForm) result.away.players = parseFormationLines(awayForm);

            // ── Rezerve — toti lf__participantNew--substituedPlayer ─
            // Fiecare are clasa lf__isReversed daca e away
            document.querySelectorAll(".lf__participantNew--substituedPlayer").forEach(el => {
                const isAway = el.getAttribute("class").includes("lf__isReversed");

                // Nume din img[alt] (cel mai sigur)
                const imgEl = el.querySelector("img[alt]");
                const name  = imgEl ? imgEl.alt.trim() : "";
                if (!name) return;

                let imgSrc = imgEl ? (imgEl.src || "") : "";
                if (!imgSrc && imgEl && imgEl.getAttribute("srcset"))
                    imgSrc = imgEl.getAttribute("srcset").split(",")[0].trim().split(" ")[0];

                const ratingEl = el.querySelector(
                    '[data-testid="wcl-badgeRating"], [data-testid*="badgeRating"]'
                );
                const rating = ratingEl ? ratingEl.innerText.trim() : "";

                // Minut — cauta in elementul parinte/frate
                let minute = "";
                const parent = el.parentElement;
                if (parent) {
                    const minEl = parent.querySelector(
                        '[class*="minute"],[class*="Minute"],[class*="time"],[class*="Time"]'
                    );
                    if (minEl) minute = minEl.innerText.replace(/\\D/g, "");
                }

                const team = isAway ? "away" : "home";
                result[team].substitutes.push({
                    name, number: "", rating, minute, img_src: imgSrc,
                    events: getEvents(el),
                    flashscore_url: getPlayerUrl(el)
                });
            });

            return result;
        }""")

        # ── Kit numbers din Flashscore (wcl-participant_ — starters + subs) ──
        try:
            _kit_map = page.evaluate("""() => {
                var res = {home: {}, away: {}};
                document.querySelectorAll('[class*="wcl-participant_"]').forEach(function(el) {
                    var numEl = el.querySelector('[class*="wcl-number_"]');
                    if (!numEl) return;
                    var number = numEl.innerText.trim();
                    if (!number || !/^\\d{1,3}$/.test(number)) return;
                    var name = "";
                    el.querySelectorAll('[class*="wcl-bold_"]').forEach(function(span) {
                        var t = span.innerText.trim();
                        if (!name && t && !/^\\d+\\.?\\d*$/.test(t) && t.length > 2) name = t;
                    });
                    if (!name) {
                        var ot = el.querySelector('[class*="wcl-overflowText_"]');
                        if (ot) name = ot.innerText.trim();
                    }
                    if (!name || name.length < 2) return;
                    var isAway = el.className.indexOf("rtl") >= 0;
                    var team = isAway ? "away" : "home";
                    res[team][name] = number;
                });
                return res;
            }""")
            # Aplica numerele pe subs (unde e hardcodat "")
            for _team in ["home", "away"]:
                _kmap = _kit_map.get(_team, {})
                for _p in data[_team]["substitutes"]:
                    if not _p.get("number"):
                        _p["number"] = _kmap.get(_p["name"], "")
                # Suplimenteaza starters daca lipseste numarul
                for _p in data[_team]["players"]:
                    if not _p.get("number"):
                        _p["number"] = _kmap.get(_p["name"], "")
            _total_kits = sum(1 for _t in ["home","away"]
                              for _p in data[_t]["players"] + data[_t]["substitutes"]
                              if _p.get("number"))
            _total_all = sum(len(data[_t]["players"]) + len(data[_t]["substitutes"])
                             for _t in ["home","away"])
            print(f"      Kit numbers (Flashscore): {_total_kits}/{_total_all} jucatori")
        except Exception as _kit_exc:
            print(f"      [kit numbers exc]: {_kit_exc}")

        # Debug: colecteaza toate data-testid-urile din elementele de player
        # (ajuta la identificarea iconului de brace/hat-trick)
        try:
            testids = page.evaluate("""() => {
                const ids = new Set();
                document.querySelectorAll('.lf__player [data-testid], .lf__participantNew [data-testid]')
                    .forEach(el => { if (el.dataset.testid) ids.add(el.dataset.testid); });
                return Array.from(ids).sort();
            }""")
            if testids:
                testid_path = str(OUTPUT_DIR / "debug_testids.txt")
                with open(testid_path, "w", encoding="utf-8") as tf:
                    tf.write("\n".join(testids))
                print(f"      Debug testids saved: {testid_path}")
        except Exception:
            pass

        browser.close()

    m = data["match"]
    print(f"      {m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']}")
    print(f"      {m['home_formation']} vs {m['away_formation']}")
    if m.get('home_avg_rating'):
        print(f"      Avg ratings: Ø{m['home_avg_rating']} vs Ø{m['away_avg_rating']}")
    print(f"      Home: {len(data['home']['players'])} starters, {len(data['home']['substitutes'])} subs")
    print(f"      Away: {len(data['away']['players'])} starters, {len(data['away']['substitutes'])} subs")

    # Lista jucatori pentru verificare
    print(f"\n      HOME starters: {[p['name'] for p in data['home']['players']]}")
    print(f"      HOME subs:  {[p['name'] for p in data['home']['substitutes']]}")
    print(f"      AWAY starters: {[p['name'] for p in data['away']['players']]}")
    print(f"      AWAY subs:  {[p['name'] for p in data['away']['substitutes']]}")

    # Debug goluri — arata toti jucatorii cu events ca sa verificam golurile multiple
    all_players = (data['home']['players'] + data['home']['substitutes'] +
                   data['away']['players'] + data['away']['substitutes'])
    goal_players = [p for p in all_players if 'goal' in p.get('events', [])]
    if goal_players:
        print(f"\n      GOALS DETECTED:")
        for p in goal_players:
            n_goals = p['events'].count('goal')
            print(f"        {p['name']}: {n_goals} goal(s) | events={p['events']}")

    return data


# ══════════════════════════════════════════════════════════════
#  STEP 2 — DOWNLOAD IMAGINI DE PE SOFASCORE
# ══════════════════════════════════════════════════════════════

# Sursa pozelor e exclusiv lineup-ul Sofascore din --sofascore-url.
# True = jucatorii care lipsesc din acel lineup iau poza de pe Flashscore
# in loc de placeholder.
ALLOW_FLASHSCORE_PHOTO_FALLBACK = False

# ── Helpers pentru potrivire nume ─────────────────────────────

def _norm(name: str) -> str:
    """Lowercase, fara diacritice, fara punctuatie."""
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = re.sub(r"[^a-z0-9\s]", "", n.lower())
    return n.strip()

















def _ss_norm(name: str) -> str:
    """Normalizeaza un nume pentru comparare cu lineup Sofascore (lowercase, fara diacritice)."""
    nfd = unicodedata.normalize('NFD', name or '')
    no_diac = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', no_diac.lower().strip())


def _parse_sofascore_event_id(url: str) -> str:
    """Extrage event ID din URL Sofascore (ex: #id:12345678 sau /event/12345678)."""
    if not url:
        return ""
    # Format 1: https://www.sofascore.com/slug#id:12345678
    m = re.search(r'#id:?(\d+)', url)
    if m:
        return m.group(1)
    # Format 2: /event/12345678
    m = re.search(r'/event/(\d+)', url)
    if m:
        return m.group(1)
    return ""


async def _fetch_sofascore_lineup(page, event_id: str) -> tuple:
    """
    Descarca lineup-ul unui meci Sofascore.
    Navigheaza pe www.sofascore.com intai (trece JS challenge/cookies),
    apoi face fetch() din contextul paginii catre API (mosteneste cookies/sesiune).
    Returneaza (home_map, away_map) unde fiecare map e {normalized_name: player_id}.
    """
    if not event_id:
        return {}, {}
    try:
        import json as _json_ll
        _api_url = f"https://api.sofascore.com/api/v1/event/{event_id}/lineups"
        # Viziteaza site-ul mai intai ca sa treaca verificarile Cloudflare/JS
        try:
            await page.goto("https://www.sofascore.com/", wait_until="domcontentloaded", timeout=20000)
            # Asteapta ca redirectarile/challenge-ul JS sa se aseze. Fara asta,
            # o navigare tardiva distruge contextul JS in timpul evaluarii de mai jos
            # ("Execution context was destroyed, most likely because of a navigation").
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                await page.wait_for_timeout(1500)
        except Exception:
            pass

        _txt = ""

        # 1) APIRequestContext — partajeaza cookies cu browser-ul, dar NU depinde
        #    de contextul JS al paginii, deci o navigare nu-l poate distruge.
        try:
            _r_ll = await page.context.request.get(_api_url, headers={
                "Accept": "application/json, text/plain, */*",
                "x-requested-with": "XMLHttpRequest",
                "Referer": "https://www.sofascore.com/",
            })
            if _r_ll.ok:
                _txt = await _r_ll.text()
            else:
                # 403 de la Cloudflare e normal aici: APIRequestContext nu are
                # amprenta completa de browser. Cadem pe fetch-ul din pagina.
                _txt = ""
        except Exception:
            _txt = ""

        # 2) Fallback: fetch din contextul paginii, cu reincercare daca o navigare
        #    distruge contextul JS intre timp.
        if not _txt:
            _js = """async () => {
                try {
                    const r = await fetch("__API_URL__", {
                        method: "GET",
                        headers: {
                            "Accept": "application/json, text/plain, */*",
                            "x-requested-with": "XMLHttpRequest",
                            "Referer": "https://www.sofascore.com/"
                        }
                    });
                    if (!r.ok) return JSON.stringify({_error: r.status});
                    return await r.text();
                } catch(e) {
                    return JSON.stringify({_error: String(e)});
                }
            }""".replace("__API_URL__", _api_url)
            for _attempt in range(3):
                try:
                    _txt = await page.evaluate(_js)
                    break
                except Exception as _ev_e:
                    if "context was destroyed" in str(_ev_e).lower() and _attempt < 2:
                        await page.wait_for_timeout(2000)
                        continue
                    raise

        _data_check = _json_ll.loads(_txt)
        if isinstance(_data_check, dict) and "_error" in _data_check:
            print(f"  ⚠ Sofascore lineup: HTTP {_data_check['_error']}")
            return {}, {}
        _data = _data_check
        
        def _build_map(side_data):
            # Returneaza {"names": {nume_norm: pid}, "nums": {numar: pid},
            #             "surn": {nume_familie: [(pid, initiala_prenume), ...]}}
            _names = {}
            _nums  = {}
            _surn  = {}
            for _entry in side_data.get("players", []):
                _p = _entry.get("player", {})
                _pid = _p.get("id")
                if not _pid:
                    continue
                # Numar de tricou — potrivire neambigua
                _jersey = _entry.get("shirtNumber") or _entry.get("jerseyNumber") or _p.get("jerseyNumber")
                if _jersey is not None and str(_jersey).strip():
                    _nums[str(_jersey).strip()] = _pid
                # Nume de familie + initiala prenume (din numele complet de pe Sofascore)
                _full = _p.get("name", "") or _p.get("shortName", "")
                _fp = _full.split()
                if len(_fp) >= 2:
                    _surname = _ss_norm(_fp[-1])
                    _initial = _ss_norm(_fp[0])[:1]   # prima litera a prenumelui
                    if _surname:
                        _surn.setdefault(_surname, []).append((_pid, _initial))
                for _fname in ["name", "shortName"]:
                    _n = _p.get(_fname, "")
                    if _n:
                        _names[_ss_norm(_n)] = _pid
                        _parts = _n.split()
                        if len(_parts) > 1:
                            _names[_ss_norm(_parts[-1])] = _pid
                            _names[_ss_norm(' '.join(_parts[:2]))] = _pid
            return {"names": _names, "nums": _nums, "surn": _surn}
        
        home_map = _build_map(_data.get("home", {}))
        away_map = _build_map(_data.get("away", {}))
        _hn = len(set(home_map["names"].values()))
        _an = len(set(away_map["names"].values()))
        print(f"  ✓ Sofascore lineup: {_hn} home + {_an} away players "
              f"({len(home_map['nums'])}+{len(away_map['nums'])} with jersey #)")
        return home_map, away_map
    except Exception as _e:
        print(f"  ⚠ Sofascore lineup error: {_e}")
        return {}, {}


async def fetch_player_photo(name: str, page,
                             client: httpx.AsyncClient, is_sub: bool = False,
                             flashscore_url: str = "", team_name: str = "",
                             img_src: str = "", ss_ctx=None,
                             ss_lineup_map: dict = None,
                             ss_player_number: str = ""):
    """
    Descarca poza jucatorului EXCLUSIV din lineup-ul Sofascore dat prin
    --sofascore-url. Potrivirea se face dupa numarul de tricou, apoi dupa nume.
    Returneaza (photo_bytes, kit_number, source_label).
    """
    clean = re.sub(r'^\d+[\n\r\s]+', '', name).strip()
    clean = re.sub(r'\.$', '', clean).strip()
    # Varianta fara initiala: "Martinelli G." → "Martinelli"
    clean_no_init = re.sub(r'(\s+[A-Z][a-z]{0,2}\.?)+$', '', clean).strip()

    # ── 1. Photo service — sursa primara, acoperire universala ──────
    if ss_ctx:
        try:
            import io as _io_ss
            from PIL import Image as _PILss
            from collections import deque as _dq_ss

            # ── 1a. Lineup map exact match (cand e data URL Sofascore) ──
            _ss_pid = None
            if ss_lineup_map:
                _names_map = ss_lineup_map.get("names", {}) if isinstance(ss_lineup_map, dict) else {}
                _nums_map  = ss_lineup_map.get("nums", {})  if isinstance(ss_lineup_map, dict) else {}
                _surn_map  = ss_lineup_map.get("surn", {})  if isinstance(ss_lineup_map, dict) else {}

                # 1a-i. Potrivire dupa NUMARUL DE TRICOU (neambigua) — prioritar
                _kit = str(ss_player_number).strip() if ss_player_number else ""
                if _kit and _kit in _nums_map:
                    _ss_pid = _nums_map[_kit]

                # 1a-ii. Potrivire dupa nume complet exact
                if not _ss_pid:
                    for _try_name in [clean_no_init, clean]:
                        if not _try_name:
                            continue
                        _k = _ss_norm(_try_name)
                        if _k in _names_map:
                            _ss_pid = _names_map[_k]
                            break

                # 1a-iii. Potrivire dupa NUME DE FAMILIE + INITIALA prenumelui
                #   ex: Flashscore "Magalhães G." -> familie "magalhaes", initiala "g"
                #   cauta pe Sofascore jucatorul cu acelasi nume de familie a carui
                #   prenume incepe cu acea initiala (dezambiguizeaza Silva B. vs Silva T.)
                if not _ss_pid:
                    # Extrage numele de familie si initiala din numele Flashscore
                    _fs_tokens = clean.split()
                    _fs_initial = ""
                    _fs_surname_tokens = []
                    for _tok in _fs_tokens:
                        _tt = _tok.replace(".", "")
                        if len(_tt) == 1 and _tt.isalpha():
                            _fs_initial = _ss_norm(_tt)[:1]   # token de o litera = initiala
                        else:
                            _fs_surname_tokens.append(_tok)
                    # numele de familie = ultimul token "lung" (sau tot, daca nu separam)
                    _fs_surname = _ss_norm(_fs_surname_tokens[-1]) if _fs_surname_tokens else ""
                    if _fs_surname and _fs_surname in _surn_map:
                        _cands = _surn_map[_fs_surname]
                        if len(_cands) == 1:
                            _ss_pid = _cands[0][0]   # un singur jucator cu acel nume de familie
                        elif _fs_initial:
                            for _cpid, _cinit in _cands:
                                if _cinit == _fs_initial:
                                    _ss_pid = _cpid
                                    break

                # 1a-iv. Ultima incercare: doar nume de familie (last word) in names map
                if not _ss_pid:
                    for _try_name in [clean_no_init, clean]:
                        if not _try_name:
                            continue
                        _parts = _try_name.split()
                        if len(_parts) > 1:
                            _k2 = _ss_norm(_parts[-1])
                            if _k2 in _names_map:
                                _ss_pid = _names_map[_k2]
                                break

            # NB: nu exista fallback pe cautare dupa nume. Cautarea returna
            # primul fotbalist cu numele respectiv din toata baza Sofascore
            # (ex: "Cunha" -> Matheus Cunha / Man Utd in loc de Jair / Forest),
            # deci punea poze gresite fara sa avertizeze. Daca jucatorul nu e
            # in lineup-ul din URL-ul Sofascore, se genereaza placeholder.
            if _ss_pid is not None:
                _img_url = f"https://img.sofascore.com/api/v1/player/{_ss_pid}/image"
                _body = b""
                # Navigheaza direct la URL-ul imaginii (ca un om care deschide link-ul).
                # Dintr-un context curat asta returneaza imaginea full 150x150.
                try:
                    _nav_resp = await page.goto(_img_url, wait_until="load", timeout=15000)
                    if _nav_resp and _nav_resp.ok:
                        _body = await _nav_resp.body()
                except Exception:
                    _body = b""
                # 2) Fallback: ctx.request daca navigarea a esuat
                if len(_body) <= 500:
                    try:
                        _img_r = await ss_ctx.request.get(_img_url, headers={
                            "Referer": "https://www.sofascore.com/",
                            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        })
                        _body = await _img_r.body()
                    except Exception:
                        _body = b""
                if len(_body) > 500:
                    try:
                        _pil  = _PILss.open(_io_ss.BytesIO(_body)).convert("RGBA")
                        _w, _h = _pil.size
                        _px   = _pil.load()
                        _q    = _dq_ss([(0,0),(_w-1,0),(0,_h-1),(_w-1,_h-1)])
                        _seen = set()
                        while _q:
                            _x, _y = _q.popleft()
                            if (_x,_y) in _seen or not (0<=_x<_w and 0<=_y<_h):
                                continue
                            _seen.add((_x,_y))
                            _r2,_g2,_b2,_a2 = _px[_x,_y]
                            if _r2>230 and _g2>230 and _b2>230 and _a2>100:
                                _px[_x,_y] = (255,255,255,0)
                                for _dx,_dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]:
                                    _q.append((_x+_dx,_y+_dy))
                        _buf = _io_ss.BytesIO()
                        _pil.save(_buf, format="PNG")
                        _body = _buf.getvalue()
                    except Exception:
                        pass
                    try:
                        _dbg_w, _dbg_h = _PILss.open(_io_ss.BytesIO(_body)).size
                        print(f"[photo ✓ {_dbg_w}x{_dbg_h}]", end=" ", flush=True)
                    except Exception:
                        print(f"[photo ✓]", end=" ", flush=True)
                    return _body, "", "photo"
                else:
                    print(f"[no image]", end=" ", flush=True)
            else:
                print(f"[not found]", end=" ", flush=True)
        except Exception as _ss_exc:
            print(f"[exc: {_ss_exc}]", end=" ", flush=True)

    # ── 2. Flashscore photo — fallback final, DEZACTIVAT implicit ──
    # Sursa ceruta e exclusiv Sofascore. Pune True daca vrei ca jucatorii
    # lipsa din lineup-ul Sofascore sa ia totusi poza de pe Flashscore
    # in loc de placeholder.
    if ALLOW_FLASHSCORE_PHOTO_FALLBACK and img_src and img_src.startswith("http"):
        try:
            import urllib.request as _urlreq_fs, asyncio as _aio_fs
            _FS_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            def _fs_dl():
                _req = _urlreq_fs.Request(img_src, headers={
                    "User-Agent": _FS_UA,
                    "Referer": "https://www.flashscore.com/",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                })
                with _urlreq_fs.urlopen(_req, timeout=10) as _r:
                    return _r.read()
            _fs_bytes = await _aio_fs.to_thread(_fs_dl)
            if _fs_bytes and len(_fs_bytes) > 1000:
                print(f"[flashscore photo]", end=" ", flush=True)
                return _fs_bytes, "", "flashscore"
        except Exception as _fs_exc:
            print(f"[flashscore exc: {_fs_exc}]", end=" ", flush=True)

    return None, "", None

def generate_placeholder(name: str, dest: Path) -> bool:
    """
    Genereaza o poza placeholder 240x240 cu numele jucatorului.
    Folosita cand jucatorul nu e gasit in lineup-ul Sofascore.
    """
    if not _PIL:
        return False
    try:
        SIZE = 240

        # ── Fundal gradient inchis ──────────────────────────────
        img = Image.new("RGBA", (SIZE, SIZE), (30, 35, 45, 255))

        # Cerc silhouette (cap + umeri) in gri inchis
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)

        # Umeri / bust
        draw.ellipse([20, 130, 220, 310], fill=(55, 62, 78, 255))
        # Cap
        draw.ellipse([75, 55, 165, 145], fill=(70, 78, 95, 255))

        # ── Text cu numele ──────────────────────────────────────
        # Curata numele: scoate initiala (ex. "Soucek T." → "Soucek T.")
        display_name = name.strip()

        # Incearca font TrueType de sistem, fallback la default PIL
        font_small = None
        font_large = None
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        ]
        try:
            from PIL import ImageFont
            for fp in font_paths:
                if Path(fp).exists():
                    font_large = ImageFont.truetype(fp, 20)
                    font_small = ImageFont.truetype(fp, 15)
                    break
        except Exception:
            pass

        # Imparte numele in max 2 randuri daca e lung
        words = display_name.split()
        if len(words) <= 1:
            lines = [display_name]
        elif len(display_name) <= 14:
            lines = [display_name]
        else:
            mid = len(words) // 2
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]

        font_use = font_large if font_large else None
        y_start  = 170 if len(lines) == 1 else 162

        for i, line in enumerate(lines):
            if font_use:
                bbox = draw.textbbox((0, 0), line, font=font_use)
                tw = bbox[2] - bbox[0]
            else:
                tw = len(line) * 8  # estimare fara font
            x = (SIZE - tw) // 2
            y = y_start + i * 22
            # Umbra subtila
            draw.text((x + 1, y + 1), line, fill=(0, 0, 0, 180), font=font_use)
            draw.text((x, y), line, fill=(200, 210, 230, 255), font=font_use)

        # Linie subtire la baza ca separator
        draw.rectangle([30, 158, SIZE - 30, 160], fill=(80, 90, 110, 200))

        img.save(str(dest), format="PNG")
        return True
    except Exception as e:
        print(f"[placeholder err: {e}]", end=" ")
        return False


def save_image(raw: bytes, path: Path) -> bool:
    if not raw or len(raw) < 200:
        return False
    if _PIL:
        try:
            img = Image.open(io.BytesIO(raw)).convert("RGBA")
            if img.width < 10:
                return False
            img.save(str(path), format="PNG")
            return True
        except Exception:
            pass
    try:
        path.write_bytes(raw)
        return True
    except Exception:
        return False



async def download_all_images(data: dict, images_only: bool = False,
                              player_only: str = None, sofascore_url: str = ""):
    """
    player_only: daca e setat, descarca DOAR jucatorul cu acel nume (override rapid).
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("\n⚠ EROARE: Playwright nu este instalat.")
        print("  Rulati urmatoarele comenzi in terminal si reporniti aplicatia:")
        print("    pip install playwright")
        print("    playwright install chromium")
        return

    if player_only:
        print(f"\n[2/3] Downloading photo for: {player_only}...")
    else:
        print(f"\n[2/3] Downloading photos...")


    home_team = data.get("match", {}).get("home_team", "")
    away_team = data.get("match", {}).get("away_team", "")

    ok = 0; fail = 0; missing = []
    sources = {}          # {"photo": N, "flashscore": N, ...}
    ss_lineup_ok = False  # SofaScore lineup loaded?

    # Incarca lista placeholder-elor existente (prefix_i -> name)
    placeholders_path = OUTPUT_DIR / "placeholders.json"
    try:
        placeholders = json.loads(placeholders_path.read_text(encoding="utf-8")) if placeholders_path.exists() else {}
    except Exception:
        placeholders = {}

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(
                headless=True,    # page.goto merge si headless (testat: 150x150)
                args=[
                    "--window-position=9999,9999",
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--window-size=1280,800",
                ]
            )
        except Exception as _pw_err:
            _emsg = str(_pw_err)
            if "Executable doesn" in _emsg or "chromium" in _emsg.lower() or "playwright install" in _emsg.lower():
                print("\n⚠ EROARE: Chromium nu este instalat pentru Playwright.")
                print("  Rulati in terminal:")
                print("    playwright install chromium")
            else:
                print(f"\n⚠ EROARE la pornirea browserului: {_emsg}")
            return
        ctx = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        # Elimina flag-ul navigator.webdriver care detecteaza Playwright
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await ctx.new_page()

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:

            hdrs = {"User-Agent": UA, "Referer": "https://www.flashscore.com/"}

            # ── 0. Photo service: initializare context ──
            ss_ctx = ctx

            # ── 0.1 Lineup exact map (daca e data URL Sofascore) ────
            home_lineup_map: dict = {}
            away_lineup_map: dict = {}
            _ss_event_id = _parse_sofascore_event_id(sofascore_url)
            if _ss_event_id:
                print(f"  [Sofascore lineup] Event ID: {_ss_event_id}")
                home_lineup_map, away_lineup_map = await _fetch_sofascore_lineup(page, _ss_event_id)
                ss_lineup_ok = bool(home_lineup_map or away_lineup_map)

            # ── 1. Descarca logo-uri echipe din Flashscore ────────────────
            fs_home_logo = data.get("match", {}).get("home_logo_url", "")
            fs_away_logo = data.get("match", {}).get("away_logo_url", "")

            for logo_url, filename in [
                (fs_home_logo, "home_logo.png"),
                (fs_away_logo, "away_logo.png"),
            ]:
                if not logo_url:
                    print(f"  ⚠ Logo {filename}: not found")
                    continue
                try:
                    r = await client.get(logo_url, headers=hdrs, timeout=15,
                                         follow_redirects=True)
                    if r.status_code == 200 and len(r.content) > 100:
                        (IMAGES_DIR / filename).write_bytes(r.content)
                        print(f"  ✓ Logo: {filename}")
                    else:
                        print(f"  ⚠ Logo {filename}: not found")
                except Exception:
                    print(f"  ⚠ Logo {filename}: not found")

            # Kit numbers vin din Flashscore (scraped direct)
            groups = [
                (data["home"]["players"],     "home_player", home_team, home_lineup_map),
                (data["away"]["players"],     "away_player", away_team, away_lineup_map),
                (data["home"]["substitutes"], "home_sub",    home_team, home_lineup_map),
                (data["away"]["substitutes"], "away_sub",    away_team, away_lineup_map),
            ]

            # ── 3. Per jucator: descarca foto (paralel, max 3 simultan) ────
            # 3a. Pre-procesare sincrona: skip cached
            _dl_sem   = asyncio.Semaphore(3)
            _dl_tasks = []

            for players, prefix, _tname, _lineup_map in groups:
                is_sub = prefix.endswith("_sub")
                for i, p in enumerate(players, 1):
                    name = p.get("name", "").strip()
                    if not name:
                        continue

                    if player_only and _norm(name) != _norm(player_only):
                        continue

                    dest     = IMAGES_DIR / f"{prefix}_{i}.png"
                    file_key = f"{prefix}_{i}"
                    is_placeholder = file_key in placeholders

                    if player_only and dest.exists():
                        dest.unlink(missing_ok=True)
                        is_placeholder = False

                    # Cand e dat URL Sofascore, fortam re-download (sterge poza veche)
                    if sofascore_url and dest.exists():
                        dest.unlink(missing_ok=True)
                        is_placeholder = False
                    if dest.exists() and not is_placeholder:
                        print(f"  ✓ {name} (cached)")
                        ok += 1
                        continue

                    lbl = " (placeholder — retrying)" if is_placeholder else ""
                    print(f"  → {name}{lbl}", flush=True)
                    _dl_tasks.append({
                        "name": name, "p": p, "is_sub": is_sub,
                        "_tname": _tname,
                        "dest": dest, "file_key": file_key,
                        "ss_lineup_map": _lineup_map,
                    })

            # 3b. Descarca in paralel (max 3 simultan, fiecare task isi creeaza propria pagina)
            async def _fetch_one(_t):
                async with _dl_sem:
                    _pg = await ctx.new_page()
                    try:
                        return await fetch_player_photo(
                            _t["name"], _pg, client,
                            is_sub=_t["is_sub"],
                            flashscore_url=_t["p"].get("flashscore_url", ""),
                            team_name=_t["_tname"],
                            img_src=_t["p"].get("img_src", ""),
                            ss_ctx=ss_ctx,
                            ss_lineup_map=_t.get("ss_lineup_map"),
                            ss_player_number=_t["p"].get("number", ""),
                        )
                    except BaseException as _e:
                        print(f"\n      ⚠ Crash '{_t['name']}': {type(_e).__name__}: {_e}")
                        traceback.print_exc()
                        return None, None, None
                    finally:
                        try:
                            await _pg.close()
                        except Exception:
                            pass

            _results = await asyncio.gather(*[_fetch_one(_t) for _t in _dl_tasks])

            # 3c. Proceseaza rezultatele in ordinea initiala
            for _t, (raw, kit, src) in zip(_dl_tasks, _results):
                p        = _t["p"]
                dest     = _t["dest"]
                file_key = _t["file_key"]
                name     = _t["name"]
                is_sub   = _t["is_sub"]

                if kit:
                    if is_sub or not p.get("number") or MATCH_TYPE == "national":
                        p["number"] = kit
                num_label = f" #{p.get('number','')}" if p.get('number') else ""
                if raw and save_image(raw, dest):
                    print(f"  ✓ {name}: OK ({src}{num_label})")
                    ok += 1
                    sources[src] = sources.get(src, 0) + 1
                    placeholders.pop(file_key, None)
                else:
                    safe_name = re.sub(r'[^\w\s\-]', '', name).strip()
                    safe_name = re.sub(r'\s+', '_', safe_name)
                    if generate_placeholder(name, dest):
                        named_dest = IMAGES_DIR / f"{safe_name}_placeholder.png"
                        try:
                            import shutil
                            shutil.copy2(str(dest), str(named_dest))
                        except Exception:
                            pass
                        print(f"  ✗ {name}: NOT FOUND → placeholder ({safe_name}_placeholder.png)")
                    else:
                        print(f"  ✗ {name}: NOT FOUND")
                    placeholders[file_key] = name
                    missing.append(name)
                    fail += 1

        # Salveaza placeholders.json actualizat
        try:
            placeholders_path.write_text(
                json.dumps(placeholders, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

        await browser.close()

    print(f"\n      Downloaded: {ok}  |  Not found: {fail}")
    if missing:
        print(f"      Missing: {', '.join(missing)}")

    return ok, fail, missing, sources, ss_lineup_ok


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def _fetch_fifa_rankings(home_team: str, away_team: str) -> tuple:
    """
    Returneaza (home_rank, away_rank) ca string-uri — pozitia in FIFA World Ranking
    LIVE (api.fifa.com). "" pentru echipe negasite (ex: cluburi). Nu ridica exceptii.
    Endpoint-ul 'live' e mereu cel curent (pagina inside.fifa.com se actualizeaza
    periodic — acest API reflecta ranking-ul la zi).
    """
    if not home_team and not away_team:
        return "", ""
    try:
        import urllib.request as _ur, json as _json, unicodedata as _ud
        _UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        _api = ("https://api.fifa.com/api/v3/fifarankings/rankings/live"
                "?gender=1&sportType=0&language=en")
        _rq = _ur.Request(_api, headers={"User-Agent": _UA, "Accept": "application/json"})
        _res = _json.loads(_ur.urlopen(_rq, timeout=20).read()).get("Results", [])
        if not _res:
            return "", ""
        def _fn(_s):
            _s = _ud.normalize("NFD", _s or "")
            _s = "".join(_c for _c in _s if _ud.category(_c) != "Mn")
            return re.sub(r"[^a-z0-9 ]", "", _s.lower()).strip()
        _by, _by_cc = {}, {}
        for _it in _res:
            _tn = _it.get("TeamName") or []
            _nm = _tn[0].get("Description", "") if _tn else ""
            if _nm: _by[_fn(_nm)] = _it.get("Rank")
            if _it.get("IdCountry"): _by_cc[_it["IdCountry"].lower()] = _it.get("Rank")
        _aliases = {
            "south korea": "korea republic", "north korea": "dpr korea",
            "iran": "ir iran", "turkey": "turkiye", "czech republic": "czechia",
            "ivory coast": "cote divoire", "dr congo": "congo dr",
            "cape verde": "cabo verde", "united states": "usa", "china": "china pr",
            "bosnia and herzegovina": "bosnia and herzegovina",
            "bosnia herzegovina": "bosnia and herzegovina",
        }
        def _match(_team):
            if not _team: return ""
            _n = _fn(_team)
            if _n in _by: return str(_by[_n])
            if _n in _aliases and _aliases[_n] in _by: return str(_by[_aliases[_n]])
            if len(_n) == 3 and _n in _by_cc: return str(_by_cc[_n])
            for _fname, _rk in _by.items():
                if _n and (_n in _fname or _fname in _n): return str(_rk)
            _nt = set(_n.split()); _best = None; _bo = 0
            for _fname, _rk in _by.items():
                _ov = len(_nt & set(_fname.split()))
                if _ov > _bo: _bo = _ov; _best = _rk
            return str(_best) if _bo >= 1 else ""
        return _match(home_team), _match(away_team)
    except Exception as _e:
        print(f"  ⚠ FIFA ranking: {_e}")
        return "", ""

def main():
    # Suporta flag --images-only: sare peste scraping, foloseste data.json existent
    images_only = "--images-only" in sys.argv

    # Supports --player "Nume": descarca DOAR jucatorul respectiv (override rapid)
    player_only = None
    for i, a in enumerate(sys.argv):
        if a == "--player" and i + 1 < len(sys.argv):
            player_only = sys.argv[i + 1]
            break
    if player_only:
        images_only = True  # --player implica --images-only

    # Suporta flag --sofascore-url: URL-ul meciului pe Sofascore (pentru lineup exact)
    sofascore_url = ""
    for i, a in enumerate(sys.argv):
        if a == "--sofascore-url" and i + 1 < len(sys.argv):
            sofascore_url = sys.argv[i + 1]
            break

    args = [a for a in sys.argv[1:] if not a.startswith("--") and a != player_only and a != sofascore_url]

    if not args and not images_only:
        print("=" * 55)
        print("  FLASHSCORE RATINGS — run.py")
        print("=" * 55)
        print("\nUsage:")
        print('  python run.py "https://www.flashscore.com/match/..."')
        print('  python run.py --images-only   # re-download images')
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    _ver = ""
    try:
        _ver = (BASE_DIR / "version.txt").read_text(encoding="utf-8").strip()
    except Exception:
        pass
    print("=" * 55)
    print(f"  FLASHSCORE RATINGS — run.py  (v{_ver})")
    print("=" * 55)

    import time as _time_run
    _run_start = _time_run.time()

    if images_only:
        # Mod rapid: sare peste scraping, incarca data.json existent
        data_path = OUTPUT_DIR / "data.json"
        if not data_path.exists():
            print("\n⚠ Nu exista data.json. Ruleaza mai intai fara --images-only.")
            sys.exit(1)
        print("\n[--images-only] Using existing data.json, re-downloading images...")
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        url = args[0]
        # Salveaza URL-ul pentru refresh_stats.py
        (OUTPUT_DIR / "last_url.txt").write_text(url, encoding="utf-8")

        # 1. Scrape Flashscore
        data = scrape_flashscore(url)

        if not data["home"]["players"]:
            print("\n⚠ No players found. Check flashscore_output/debug.png")
            return

    # 2. Download imagini
    _dl_ok, _dl_fail, _dl_missing, _dl_sources, _dl_ss_ok = asyncio.run(
        download_all_images(data, images_only=images_only,
                            player_only=player_only,
                            sofascore_url=sofascore_url))

    # 3. Curata img_src din data.json final (nu e nevoie in AE)
    for group in [data["home"]["players"], data["away"]["players"],
                  data["home"]["substitutes"], data["away"]["substitutes"]]:
        for p in group:
            p.pop("img_src", None)

    # 3.5 FIFA World Ranking (echipe nationale)
    _fr_h, _fr_a = _fetch_fifa_rankings(data.get("match", {}).get("home_team", ""),
                                        data.get("match", {}).get("away_team", ""))
    data["match"]["home_fifa_rank"] = _fr_h
    data["match"]["away_fifa_rank"] = _fr_a
    if _fr_h or _fr_a:
        print(f"  FIFA ranking: {data['match'].get('home_team','?')}={_fr_h or '-'}  "
              f"{data['match'].get('away_team','?')}={_fr_a or '-'}")

    # 4. Salveaza data.json
    print(f"\n[3/3] Saving data.json...")
    data_path = OUTPUT_DIR / "data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"      Saved: {data_path}")

    m = data["match"]
    print(f"""
{"=" * 55}
  DONE!
  {m["home_team"]} {m["home_score"]} - {m["away_score"]} {m["away_team"]}
  {m["home_formation"]} vs {m["away_formation"]}

  Next step:
    Open .aep and run populate_lineup.jsx
{"=" * 55}
""")

    # ── Telemetrie ────────────────────────────────────────────────
    try:
        import telemetry as _tel
        _m = data.get("match", {})
        _tel.send(
            event="run",
            flashscore_url="" if images_only else (args[0] if args else ""),
            sofascore_url=sofascore_url,
            players_ok=_dl_ok,
            players_not_found=_dl_fail,
            errors=_dl_missing,
            duration_sec=_time_run.time() - _run_start,
            extra={
                "match": f"{_m.get('home_team','')} {_m.get('home_score','')} - {_m.get('away_score','')} {_m.get('away_team','')}",
                "formations": f"{_m.get('home_formation','')} vs {_m.get('away_formation','')}",
                "sources": _dl_sources,
                "ss_lineup_ok": _dl_ss_ok,
            },
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
