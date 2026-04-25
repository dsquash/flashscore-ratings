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

Urmator pas:
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

# ── SoFIFA API ─────────────────────────────────────────────────
SOFIFA_API_BASE  = "https://api.sofifa.net"
SOFIFA_CDN_BASE  = "https://cdn.sofifa.net/players"
SOFIFA_API_TOKEN = "rWXBRm1CliEYGcZH8o"   # folosit DOAR ca path-param in /customizedPlayers/
# Endpoint-urile publice (/leagues /teams /team) NU necesita autentificare
SOFIFA_HEADERS   = {
    "User-Agent": UA,
    "Accept": "application/json",
    "Referer": "https://sofifa.com/",
    "Origin": "https://sofifa.com",
}


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
        page.goto(lineups_url, wait_until="domcontentloaded", timeout=30000)

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
            print("      ⚠ Lineup nu s-a incarcat — verifica debug.png")

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
                for (const img of section.querySelectorAll("img")) {
                    const src = img.src || img.getAttribute("src") || "";
                    if (src && src.includes("team_logo")) return src;
                }
                // Fallback: orice img cu src valid din sectiune
                for (const img of section.querySelectorAll("img")) {
                    const src = img.src || img.getAttribute("src") || "";
                    if (src && (src.startsWith("http") || src.startsWith("/"))) return src;
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
                const re = /[\u00d8\u00f8\u00d8Ø]\s*(\d\.\d)/g;
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
                        const m = t.match(/(\d\.\d)/);
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
                        imgSrc = imgEl.getAttribute("srcset").split(",")[0].trim().split(" ")[0];
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
                    events: getEvents(playerEl)
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
                    events: getEvents(el)
                });
            });

            return result;
        }""")

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
                print(f"      Debug testids salvate: {testid_path}")
        except Exception:
            pass

        browser.close()

    m = data["match"]
    print(f"      {m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']}")
    print(f"      {m['home_formation']} vs {m['away_formation']}")
    if m.get('home_avg_rating'):
        print(f"      Avg ratings: Ø{m['home_avg_rating']} vs Ø{m['away_avg_rating']}")
    print(f"      Home: {len(data['home']['players'])} titulari, {len(data['home']['substitutes'])} rezerve")
    print(f"      Away: {len(data['away']['players'])} titulari, {len(data['away']['substitutes'])} rezerve")

    # Lista jucatori pentru verificare
    print(f"\n      HOME titulari: {[p['name'] for p in data['home']['players']]}")
    print(f"      HOME rezerve:  {[p['name'] for p in data['home']['substitutes']]}")
    print(f"      AWAY titulari: {[p['name'] for p in data['away']['players']]}")
    print(f"      AWAY rezerve:  {[p['name'] for p in data['away']['substitutes']]}")

    # Debug goluri — arata toti jucatorii cu events ca sa verificam golurile multiple
    all_players = (data['home']['players'] + data['home']['substitutes'] +
                   data['away']['players'] + data['away']['substitutes'])
    goal_players = [p for p in all_players if 'goal' in p.get('events', [])]
    if goal_players:
        print(f"\n      GOLURI DETECTATE:")
        for p in goal_players:
            n_goals = p['events'].count('goal')
            print(f"        {p['name']}: {n_goals} gol(uri) | events={p['events']}")

    return data


# ══════════════════════════════════════════════════════════════
#  STEP 2 — DOWNLOAD IMAGINI + NUMERE DE PE SOFIFA
# ══════════════════════════════════════════════════════════════

# ── Helpers pentru potrivire nume ─────────────────────────────

def _norm(name: str) -> str:
    """Lowercase, fara diacritice, fara punctuatie."""
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = re.sub(r"[^a-z0-9\s]", "", n.lower())
    return n.strip()


def _name_match(search: str, found: str) -> float:
    """
    Scor 0-1: cat de bine potriveste 'found' (SoFIFA) cu 'search' (Flashscore).
    Ex: search='Martinelli G', found='Gabriel Martinelli' → 1.0 (token 'martinelli' gasit)
    """
    s = _norm(search)
    f = _norm(found)
    toks = [t for t in s.split() if len(t) >= 3]
    if not toks:
        return 0.0
    return sum(1 for t in toks if t in f) / len(toks)


def _search_keywords(name: str) -> list:
    """
    Genereaza variante de keyword pentru cautare SoFIFA din numele Flashscore.
    'Martinelli G'  → ['Martinelli G', 'Martinelli']
    'Madueke N.'    → ['Madueke N', 'Madueke']
    'Foden'         → ['Foden']
    """
    clean = re.sub(r'^\d+[\n\r\s]+', '', name).strip()
    clean = re.sub(r'\.$', '', clean).strip()
    kws = [clean]
    # Scoate initiala de la final: "Martinelli G" → "Martinelli"
    no_init = re.sub(r'\s+[A-Z]\.?$', '', clean).strip()
    if no_init and no_init != clean and len(no_init) >= 3:
        kws.append(no_init)
    # Daca mai mult de 2 tokeni, incearca si primul (nume de familie scurt)
    parts = clean.split()
    if len(parts) >= 2 and parts[0] not in kws:
        kws.append(parts[0])
    return kws


async def safe_goto(page, url: str, wait_until: str = "domcontentloaded",
                    timeout: int = 30000, retries: int = 2):
    """page.goto cu retry automat la timeout."""
    last_exc = None
    for attempt in range(retries):
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            return
        except Exception as e:
            last_exc = e
            if attempt < retries - 1:
                await page.wait_for_timeout(2500)
    raise last_exc


async def get_sofifa_team_roster(team_name: str, page) -> tuple:
    """
    1. Cauta echipa pe sofifa.com/teams
    2. Viziteaza pagina echipei
    3. Returneaza (team_id, [{name, kit, photo_url, player_url}])
    """
    try:
        # Genereaza variante de cautare: full name + fiecare cuvant cu >= 4 litere
        search_variants = [team_name]
        for word in team_name.split():
            if len(word) >= 4 and word not in search_variants:
                search_variants.append(word)

        JS_FIND_BEST = """(target) => {
                const rows = document.querySelectorAll('table tbody tr');
                let best = null, bestScore = -1;
                rows.forEach(row => {
                    const link = row.querySelector('td a[href*="/team/"]');
                    if (!link) return;
                    const nm = link.innerText.trim().toLowerCase()
                        .normalize('NFD').replace(/[\\u0300-\\u036f]/g,'')
                        .replace(/[^a-z0-9 ]/g,'');
                    const toks = target.split(' ').filter(t => t.length >= 3);
                    const score = toks.reduce(
                        (s,t) => s + (nm.includes(t) ? t.length : 0), 0);
                    if (score > bestScore) { bestScore = score; best = link.href; }
                });
                return best;
            }"""

        href = None
        used_variant = team_name
        for variant in search_variants:
            search_url = (f"https://sofifa.com/teams?keyword="
                          f"{variant.replace(' ', '+')}&hl=en-US")
            await safe_goto(page, search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(600)
            href = await page.evaluate(JS_FIND_BEST, _norm(variant))
            if not href:
                # Fallback: cauta orice link cu /team/ pe pagina, nu doar in table
                href = await page.evaluate("""(target) => {
                    const links = document.querySelectorAll('a[href*="/team/"]');
                    let best = null, bestScore = -1;
                    links.forEach(link => {
                        const nm = (link.innerText||'').trim().toLowerCase()
                            .normalize('NFD').replace(/[\\u0300-\\u036f]/g,'')
                            .replace(/[^a-z0-9 ]/g,'');
                        const toks = target.split(' ').filter(t => t.length >= 3);
                        const score = toks.reduce(
                            (s,t) => s + (nm.includes(t) ? t.length : 0), 0);
                        if (score > bestScore) { bestScore = score; best = link.href; }
                    });
                    return bestScore > 0 ? best : null;
                }""", _norm(variant))
            if href:
                used_variant = variant
                if variant != team_name:
                    print(f"      SoFIFA: '{team_name}' gasit cu varianta '{variant}'")
                break

        if not href:
            title = await page.title()
            print(f"      ⚠ '{team_name}' negasit pe sofifa.com/teams (page: '{title}')")
            return 0, [], ""

        m = re.search(r'/team/(\d+)', href)
        team_id = int(m.group(1)) if m else 0
        print(f"      SoFIFA team '{team_name}' → id={team_id}")

        # Viziteaza pagina echipei
        # Tabelul de jucatori se incarca din HTML initial — domcontentloaded e suficient
        # si evita timeout-uri de 30s cu networkidle (ex. Dortmund)
        await page.goto(href, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(600)
        # Scroll pentru lazy-loading imagini
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(400)
        await page.evaluate("window.scrollTo(0, 0)")

        # Logo echipa — SoFIFA: cdn.sofifa.net/teams/{size}/{id}.png
        logo_url = await page.evaluate("""() => {
            for (const img of document.querySelectorAll('img')) {
                // Incearca src live, data-src (lazy), si atributul src static
                const candidates = [
                    img.src || '',
                    img.getAttribute('data-src') || '',
                    img.getAttribute('src') || ''
                ];
                for (const src of candidates) {
                    if (!src) continue;
                    // Pattern SoFIFA logo: /teams/{numar}/{numar}.png
                    if (/\\/teams\\/\\d+\\/\\d+/.test(src) ||
                        (src.includes('/teams/') && src.includes('.png'))) {
                        return src.replace('_60.png','_240.png')
                                  .replace('_120.png','_240.png');
                    }
                }
            }
            return '';
        }""")

        roster = await page.evaluate("""() => {
            const result = [];
            const table = document.querySelector('table');
            if (!table) return result;

            // Gaseste indexul coloanei kit number din header
            let kitColIdx = -1;
            table.querySelectorAll('thead th, thead td').forEach((th, idx) => {
                const t = (th.innerText || th.getAttribute('title') || '').trim().toLowerCase();
                if (t === '#' || t === 'kit' || t === 'kit number' || t.includes('kit'))
                    kitColIdx = idx;
            });

            table.querySelectorAll('tbody tr').forEach(row => {
                const link = row.querySelector('td a[href*="/player/"]');
                if (!link) return;

                const name = link.innerText.trim();
                const playerUrl = link.href;

                // Photo thumbnail → upgrade la 240px
                const img = row.querySelector('img');
                let photoUrl = '';
                if (img) {
                    const srcs = [img.src||'', img.getAttribute('data-src')||'',
                                  img.getAttribute('src')||''];
                    for (const s of srcs) {
                        const m = s.match(/\\/players\\/(\\d+)\\/(\\d+)\\//);
                        if (m && parseInt(m[1]) > 0) {
                            photoUrl = s.replace('_60.png','_240.png')
                                        .replace('_120.png','_240.png');
                            break;
                        }
                    }
                }

                // Kit number — coloana identificata sau fallback primul numar mic
                let kit = '';
                const tds = row.querySelectorAll('td');
                if (kitColIdx >= 0 && tds[kitColIdx]) {
                    const txt = (tds[kitColIdx].innerText || '').trim();
                    if (/^\\d{1,3}$/.test(txt)) kit = txt;
                }
                if (!kit) {
                    // Fallback SIGUR: verifica DOAR prima celula (col 0)
                    // Pe SoFIFA, kit number este intotdeauna prima coloana
                    // (col 1 are img+link, col 2 este varsta — de aceea nu iterez)
                    if (tds[0] && !tds[0].querySelector('img, a')) {
                        const txt = (tds[0].innerText || '').trim();
                        if (/^\\d{1,2}$/.test(txt) && parseInt(txt) >= 1)
                            kit = txt;
                    }
                }

                result.push({ name, kit, photoUrl, playerUrl });
            });
            return result;
        }""")

        print(f"      Roster '{team_name}': {len(roster)} jucatori | logo={'DA' if logo_url else 'NU'}")
        return team_id, roster, logo_url

    except Exception as e:
        print(f"      ⚠ get_sofifa_team_roster '{team_name}': {e}")
        return 0, [], ""


def _load_overrides() -> dict:
    """
    Incarca sofifa_overrides.json — mapari manuale Flashscore name → SoFIFA URL.
    Ex: { "Inacio": "https://sofifa.com/player/262622/samuele-inacio-pia/" }
    """
    path = BASE_DIR / "sofifa_overrides.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


async def fetch_from_roster(name: str, roster: list, page,
                             client: httpx.AsyncClient, is_sub: bool = False,
                             overrides: dict = None, match_type: str = "club"):
    """
    Cauta jucatorul in roster-ul pre-incarcat al echipei.
    - is_sub=True: INTOTDEAUNA viziteaza pagina jucatorului pentru kit number
    - overrides: dict cu mapari manuale Flashscore name → SoFIFA URL
    - match_type: 'club' sau 'national' (pentru kit number preferat)
    Returneaza (photo_bytes, kit_number, source_label, sofifa_url) sau (None, '', None, '').
    """
    clean = re.sub(r'^\d+[\n\r\s]+', '', name).strip()
    clean = re.sub(r'\.$', '', clean).strip()
    # Varianta fara initiala: "Martinelli G" → "Martinelli"
    clean_no_init = re.sub(r'\s+[A-Z]\.?$', '', clean).strip()

    hdrs = {"User-Agent": UA, "Referer": "https://sofifa.com/"}

    # ── 0. Override manual — verifica sofifa_overrides.json ──────
    if overrides:
        override_url = None
        for fs_name, sofifa_url in overrides.items():
            if _norm(fs_name) == _norm(clean) or _norm(fs_name) == _norm(clean_no_init):
                override_url = sofifa_url
                break
        if override_url:
            print(f"[override] ", end=" ", flush=True)
            try:
                await safe_goto(page, override_url, timeout=35000)
                await page.wait_for_timeout(500)
                # Scroll complet ca sa triggeram lazy-loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(600)
                await page.evaluate("window.scrollTo(0, 0)")

                pg = await page.evaluate("""(matchType) => {
                    let photoUrl = '';
                    for (const img of document.querySelectorAll('img')) {
                        // Cauta in src, data-src si srcset (lazy loading SoFIFA)
                        const candidates = [
                            img.src || '',
                            img.getAttribute('data-src') || '',
                            img.getAttribute('src') || '',
                            (img.getAttribute('srcset') || '').split(',')[0].trim().split(' ')[0]
                        ];
                        for (const src of candidates) {
                            const m = src.match(/\\/players\\/(\\d+)\\/(\\d+)\\//);
                            if (m && parseInt(m[1]) > 0) {
                                photoUrl = src.replace('_120.png','_240.png')
                                              .replace('_60.png','_240.png');
                                break;
                            }
                        }
                        if (photoUrl) break;
                    }
                    let kit = '';
                    const body = document.body.innerText;
                    // SoFIFA scrie "Kit Number Club 17" sau "Kit Number (Club): 17"
                    const mClub = body.match(/Kit\\s*Number\\s*(?:\\(Club\\)|Club)[\\s:\\-\\t]*(\\d{1,3})/i);
                    const mNat  = body.match(/Kit\\s*Number\\s*(?:\\(National\\)|National)[\\s:\\-\\t]*(\\d{1,3})/i);
                    if (matchType === 'national') {
                        if (mNat) kit = mNat[1];
                        else if (mClub) kit = mClub[1];
                    } else {
                        if (mClub) kit = mClub[1];
                        else if (mNat) kit = mNat[1];
                    }
                    return { photoUrl, kit };
                }""", match_type) or {}

                kit = pg.get('kit', '')
                photo_url = pg.get('photoUrl', '')
                print(f"photo={'DA' if photo_url else 'NU'} kit={kit or '?'}", end=" ", flush=True)

                if photo_url:
                    # Incearca toate marimile disponibile pe CDN sofifa
                    base_url = re.sub(r'_\d+\.png$', '', photo_url)
                    for size in ["_240.png", "_120.png", "_60.png", ".png"]:
                        try_url = base_url + size
                        try:
                            r = await client.get(try_url, headers=hdrs,
                                                 timeout=15, follow_redirects=True)
                            if r.status_code == 200 and len(r.content) > 300:
                                return r.content, kit, "override", override_url
                        except Exception:
                            pass
                    print(f"[404 toate marimile]", end=" ")
                else:
                    print(f"[poza negasita pe pagina override]", end=" ")
            except Exception as e:
                print(f"[override err: {e}]", end=" ")

    # ── 1. Potrivire nume in roster ───────────────────────────
    best, best_score = None, 0.0
    for player in roster:
        score = max(
            _name_match(clean, player['name']),
            _name_match(clean_no_init, player['name']) if clean_no_init != clean else 0
        )
        if score > best_score:
            best_score, best = score, player

    # ── 2. Descarca foto din thumbnail (fara page visit) ─────
    kit        = ''
    photo_raw  = None
    photo_src  = None
    if best and best_score >= 0.3:
        kit = best.get('kit', '')
        if best.get('photoUrl'):
            try:
                r = await client.get(
                    best['photoUrl'], headers=hdrs, timeout=15, follow_redirects=True
                )
                if r.status_code == 200 and len(r.content) > 300:
                    photo_raw = r.content
                    photo_src = f"roster(score={best_score:.1f})"
            except Exception:
                pass

        # ── 3. Pagina jucatorului:
        #   - INTOTDEAUNA pt rezerve (kit sigur de pe player page)
        #   - Fallback pt titulari daca thumbnail invalid
        #   - INTOTDEAUNA pt national (kit national de pe player page)
        need_page = is_sub or photo_raw is None or match_type == "national"
        if need_page and best.get('playerUrl'):
            try:
                await safe_goto(page, best['playerUrl'], timeout=35000)
                await page.wait_for_timeout(600)
                # Scroll complet pentru lazy-loading (kit number + poze)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(500)
                await page.evaluate("window.scrollTo(0, 0)")
                pg = await page.evaluate("""(matchType) => {
                    let photoUrl = '';
                    for (const img of document.querySelectorAll('img')) {
                        const candidates = [
                            img.src || '',
                            img.getAttribute('data-src') || '',
                            img.getAttribute('src') || ''
                        ];
                        for (const src of candidates) {
                            const m = src.match(/\\/players\\/(\\d+)\\/(\\d+)\\//);
                            if (m && parseInt(m[1]) > 0) {
                                photoUrl = src.replace('_120.png','_240.png')
                                              .replace('_60.png','_240.png');
                                break;
                            }
                        }
                        if (photoUrl) break;
                    }
                    let kit = '';
                    const body = document.body.innerText;
                    // SoFIFA scrie "Kit Number Club 17" sau "Kit Number (Club): 17"
                    const mClub = body.match(/Kit\\s*Number\\s*(?:\\(Club\\)|Club)[\\s:\\-\\t]*(\\d{1,3})/i);
                    const mNat  = body.match(/Kit\\s*Number\\s*(?:\\(National\\)|National)[\\s:\\-\\t]*(\\d{1,3})/i);
                    if (matchType === 'national') {
                        if (mNat) kit = mNat[1];
                        else if (mClub) kit = mClub[1];
                    } else {
                        if (mClub) kit = mClub[1];
                        else if (mNat) kit = mNat[1];
                    }
                    return { photoUrl, kit };
                }""", match_type) or {}
                # Kit de pe player page are prioritate (mai sigur decat roster table)
                if pg.get('kit'):
                    kit = pg['kit']
                # Foto de pe player page — folosita doar daca thumbnail a esuat
                if photo_raw is None and pg.get('photoUrl'):
                    r = await client.get(
                        pg['photoUrl'], headers=hdrs, timeout=15, follow_redirects=True
                    )
                    if r.status_code == 200 and len(r.content) > 300:
                        photo_raw = r.content
                        photo_src = f"player_page(score={best_score:.1f})"
            except Exception as e:
                print(f"\n        [player page exc] {e}")

        if photo_raw is not None:
            return photo_raw, kit, photo_src, best.get('playerUrl', '')

    # ── 4. Fallback final: cautare directa SoFIFA dupa nume ──────
    # (folosit cand jucatorul nu e in roster: ex. imprumut, jucator nou)
    print(f"\n        [direct search] {clean}...", end=" ", flush=True)
    try:
        kw = _search_keywords(clean)[0].replace(" ", "+")
        search_url = f"https://sofifa.com/players?keyword={kw}&hl=en-US"
        await safe_goto(page, search_url, timeout=35000)
        await page.wait_for_timeout(300)
        pg2 = await page.evaluate("""(searchName) => {
            const rows = document.querySelectorAll('table tbody tr');
            let best = null, bestScore = -1;
            const norm = s => s.toLowerCase().normalize('NFD')
                .replace(/[\\u0300-\\u036f]/g,'').replace(/[^a-z0-9 ]/g,'');
            const toks = norm(searchName).split(' ').filter(t => t.length >= 3);
            rows.forEach(row => {
                const link = row.querySelector('td a[href*="/player/"]');
                if (!link) return;
                const nm   = norm(link.innerText);
                // Verifica si URL-ul (slug-ul contine numele complet, ex. kepa-arrizabalaga-revuelta)
                const slug = norm(link.href.replace(/-/g,' '));
                const scNm  = toks.reduce((s,t) => s + (nm.includes(t)   ? 1 : 0), 0) / toks.length;
                const scUrl = toks.reduce((s,t) => s + (slug.includes(t) ? 1 : 0), 0) / toks.length;
                const sc = Math.max(scNm, scUrl);
                if (sc > bestScore) { bestScore = sc; best = { url: link.href, score: sc }; }
            });
            if (!best || bestScore < 0.5) return null;
            return best;
        }""", clean)
        if pg2 and pg2.get('url'):
            direct_url = pg2['url']
            await safe_goto(page, direct_url, timeout=35000)
            await page.wait_for_timeout(600)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)
            await page.evaluate("window.scrollTo(0, 0)")
            pg3 = await page.evaluate("""(matchType) => {
                let photoUrl = '';
                for (const img of document.querySelectorAll('img')) {
                    const candidates = [
                        img.src || '',
                        img.getAttribute('data-src') || '',
                        img.getAttribute('src') || ''
                    ];
                    for (const src of candidates) {
                        const m = src.match(/\\/players\\/(\\d+)\\/(\\d+)\\//);
                        if (m && parseInt(m[1]) > 0) {
                            photoUrl = src.replace('_120.png','_240.png')
                                          .replace('_60.png','_240.png');
                            break;
                        }
                    }
                    if (photoUrl) break;
                }
                let kit = '';
                const body = document.body.innerText;
                // SoFIFA scrie "Kit Number Club 17" sau "Kit Number (Club): 17"
                const mClub = body.match(/Kit\\s*Number\\s*(?:\\(Club\\)|Club)[\\s:\\-\\t]*(\\d{1,3})/i);
                const mNat  = body.match(/Kit\\s*Number\\s*(?:\\(National\\)|National)[\\s:\\-\\t]*(\\d{1,3})/i);
                if (matchType === 'national') {
                    if (mNat) kit = mNat[1];
                    else if (mClub) kit = mClub[1];
                } else {
                    if (mClub) kit = mClub[1];
                    else if (mNat) kit = mNat[1];
                }
                return { photoUrl, kit };
            }""", match_type) or {}
            if pg3.get('kit'): kit = pg3['kit']
            if pg3.get('photoUrl'):
                r = await client.get(
                    pg3['photoUrl'], headers=hdrs, timeout=15, follow_redirects=True
                )
                if r.status_code == 200 and len(r.content) > 300:
                    return r.content, kit, "direct_search", direct_url
    except Exception as e:
        print(f"[search exc: {e}]", end=" ", flush=True)

    # Pastreaza kit-ul gasit (din roster / pagina jucatorului) chiar daca poza a esuat
    return None, kit, None, (best.get('playerUrl', '') if best else '')

def generate_placeholder(name: str, dest: Path) -> bool:
    """
    Genereaza o poza placeholder 240x240 cu numele jucatorului.
    Folosita cand poza reala nu se gaseste pe SoFIFA.
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
            if img.width < 200:
                img = img.resize((200, 200), Image.LANCZOS)
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
                              player_only: str = None):
    """
    player_only: daca e setat, descarca DOAR jucatorul cu acel nume (override rapid).
    """
    from playwright.async_api import async_playwright

    if player_only:
        print(f"\n[2/3] Descarcare poza pentru: {player_only}...")
    else:
        print(f"\n[2/3] Descarcare poze + numere (SoFIFA roster per echipa)...")

    # Incarca overrides manuale (sofifa_overrides.json)
    overrides = _load_overrides()
    if overrides:
        print(f"  Override-uri active: {list(overrides.keys())}")

    home_team = data.get("match", {}).get("home_team", "")
    away_team = data.get("match", {}).get("away_team", "")

    ok = 0; fail = 0; missing = []

    # Incarca lista placeholder-elor existente (prefix_i -> name)
    placeholders_path = OUTPUT_DIR / "placeholders.json"
    try:
        placeholders = json.loads(placeholders_path.read_text(encoding="utf-8")) if placeholders_path.exists() else {}
    except Exception:
        placeholders = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
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

            hdrs = {"User-Agent": UA, "Referer": "https://sofifa.com/"}

            # ── 1. Incarca roster complet — pagina proaspata per echipa ──
            print(f"\n  SoFIFA: {home_team}...")
            sf_page = await ctx.new_page()
            _home_tid, home_roster, home_logo_url = await get_sofifa_team_roster(home_team, sf_page)
            await sf_page.close()

            print(f"\n  SoFIFA: {away_team}...")
            sf_page = await ctx.new_page()
            _away_tid, away_roster, away_logo_url = await get_sofifa_team_roster(away_team, sf_page)
            await sf_page.close()

            # ── 2. Descarca logo-uri echipe ───────────────────────────────
            # Ordinea de prioritate: Flashscore logo → SoFIFA logo
            fs_home_logo = data.get("match", {}).get("home_logo_url", "")
            fs_away_logo = data.get("match", {}).get("away_logo_url", "")

            for logo_urls, filename in [
                ([fs_home_logo, home_logo_url], "home_logo.png"),
                ([fs_away_logo, away_logo_url], "away_logo.png"),
            ]:
                saved = False
                for logo_url in logo_urls:
                    if not logo_url or saved:
                        continue
                    try:
                        r = await client.get(logo_url, headers=hdrs, timeout=15,
                                             follow_redirects=True)
                        if r.status_code == 200 and len(r.content) > 100:
                            (IMAGES_DIR / filename).write_bytes(r.content)
                            print(f"  ✓ Logo: {filename}")
                            saved = True
                    except Exception:
                        pass
                if not saved:
                    print(f"  ⚠ Logo {filename}: negasit")

            groups = [
                (data["home"]["players"],     "home_player", home_roster),
                (data["away"]["players"],     "away_player", away_roster),
                (data["home"]["substitutes"], "home_sub",    home_roster),
                (data["away"]["substitutes"], "away_sub",    away_roster),
            ]

            # ── 3. Per jucator: match in roster → descarca foto ──────────
            for players, prefix, roster in groups:
                is_sub = prefix.endswith("_sub")
                for i, p in enumerate(players, 1):
                    name = p.get("name", "").strip()
                    if not name:
                        continue

                    dest = IMAGES_DIR / f"{prefix}_{i}.png"
                    file_key = f"{prefix}_{i}"

                    # Modul single-player: sare peste toti in afara de cel dorit
                    if player_only and _norm(name) != _norm(player_only):
                        # Pastreaza numerele existente pentru jucatorii sarite
                        continue

                    # Este placeholder daca a fost inregistrat in placeholders.json
                    is_placeholder = file_key in placeholders

                    # In modul --images-only sau --player, forteaza re-download pt overrides
                    clean_name_for_check = re.sub(r'^\d+[\n\r\s]+', '', name).strip()
                    clean_name_for_check = re.sub(r'\.$', '', clean_name_for_check).strip()
                    clean_no_init_check  = re.sub(r'\s+[A-Z]\.?$', '', clean_name_for_check).strip()
                    has_override = overrides and any(
                        _norm(fs) in (_norm(clean_name_for_check), _norm(clean_no_init_check))
                        for fs in overrides
                    )

                    # In modul --player: sterge poza cache indiferent (re-download fortat)
                    if player_only and dest.exists():
                        dest.unlink(missing_ok=True)
                        is_placeholder = False

                    # ── Kit din roster (merge si pt poze cached) ─────────────
                    # Rezervele nu au numar de pe Flashscore — updatam din roster
                    # chiar daca poza e deja in cache, ca sa nu piarda kit-ul.
                    if not p.get("number"):
                        _c  = clean_name_for_check
                        _ni = clean_no_init_check
                        _bk, _bs = '', 0.0
                        for _rp in roster:
                            _sc = max(
                                _name_match(_c,  _rp['name']),
                                _name_match(_ni, _rp['name']) if _ni != _c else 0
                            )
                            if _sc > _bs:
                                _bs, _bk = _sc, _rp.get('kit', '')
                        if _bk and _bs >= 0.3:
                            p["number"] = _bk

                    # Sare peste cache daca:
                    # - fisierul nu exista (normal)
                    # - este placeholder (va fi re-descarcat)
                    # - are override activ si rulam --images-only (re-descarcam cu noul URL)
                    if dest.exists() and not is_placeholder and not (images_only and has_override):
                        print(f"  ✓ {name} (cached)")
                        ok += 1
                        continue

                    if is_placeholder:
                        print(f"  → {name} (placeholder — re-incerc) ...", end=" ", flush=True)
                    else:
                        print(f"  → {name} ...", end=" ", flush=True)
                    raw = kit = src = sofifa_url = None

                    try:
                        raw, kit, src, sofifa_url = await fetch_from_roster(
                            name, roster, page, client, is_sub=is_sub,
                            overrides=overrides, match_type=MATCH_TYPE
                        )
                    except BaseException as e:
                        print(f"\n      ⚠ Crash '{name}': {type(e).__name__}: {e}")
                        traceback.print_exc()
                        try:
                            page = await ctx.new_page()
                        except BaseException:
                            pass

                    # Actualizeaza kit number:
                    # - intotdeauna la rezerve (nu au numar de pe Flashscore)
                    # - la meciuri nationale (kit national, nu cel de club)
                    # - la titulari fara numar
                    if kit:
                        if is_sub or not p.get("number") or MATCH_TYPE == "national":
                            p["number"] = kit

                    # Stocheaza URL-ul SoFIFA folosit (pentru override manual ulterior)
                    if sofifa_url:
                        p["sofifa_url"] = sofifa_url

                    if raw and save_image(raw, dest):
                        num_label = f" #{p.get('number','')}" if p.get('number') else ""
                        print(f"OK ({src}{num_label})")
                        ok += 1
                        # Poza reala descarcata — scoate din lista de placeholders
                        placeholders.pop(file_key, None)
                    else:
                        # Genereaza placeholder cu numele jucatorului
                        if generate_placeholder(name, dest):
                            safe_name = re.sub(r'[^\w\s\-]', '', name).strip()
                            safe_name = re.sub(r'\s+', '_', safe_name)
                            named_dest = IMAGES_DIR / f"{safe_name}_placeholder.png"
                            try:
                                import shutil
                                shutil.copy2(str(dest), str(named_dest))
                            except Exception:
                                pass
                            print(f"NOT FOUND → placeholder ({safe_name}_placeholder.png)")
                        else:
                            print("NOT FOUND")
                        # Inregistreaza ca placeholder ca sa fie re-incarcat data viitoare
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

    print(f"\n      Descarcate: {ok}  |  Negasite: {fail}")
    if missing:
        print(f"      Lipsa: {', '.join(missing)}")


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    # Suporta flag --images-only: sare peste scraping, foloseste data.json existent
    images_only = "--images-only" in sys.argv

    # Suporta --player "Nume": descarca DOAR jucatorul respectiv (override rapid)
    player_only = None
    for i, a in enumerate(sys.argv):
        if a == "--player" and i + 1 < len(sys.argv):
            player_only = sys.argv[i + 1]
            break
    if player_only:
        images_only = True  # --player implica --images-only

    args = [a for a in sys.argv[1:] if not a.startswith("--") and a != player_only]

    if not args and not images_only:
        print("=" * 55)
        print("  FLASHSCORE RATINGS — run.py")
        print("=" * 55)
        print("\nUsage:")
        print('  python run.py "https://www.flashscore.com/match/..."')
        print('  python run.py --images-only   # re-descarca imagini cu overrides')
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("  FLASHSCORE RATINGS — run.py")
    print("=" * 55)

    if images_only:
        # Mod rapid: sare peste scraping, incarca data.json existent
        data_path = OUTPUT_DIR / "data.json"
        if not data_path.exists():
            print("\n⚠ Nu exista data.json. Ruleaza mai intai fara --images-only.")
            sys.exit(1)
        print("\n[--images-only] Folosesc data.json existent, re-descarc imaginile...")
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        url = args[0]
        # Salveaza URL-ul pentru refresh_stats.py
        (OUTPUT_DIR / "last_url.txt").write_text(url, encoding="utf-8")

        # 1. Scrape Flashscore
        data = scrape_flashscore(url)

        if not data["home"]["players"]:
            print("\n⚠ Nu s-au gasit jucatori. Verifica flashscore_output/debug.png")
            return

    # 2. Download imagini de pe SoFIFA
    asyncio.run(download_all_images(data, images_only=images_only,
                                    player_only=player_only))

    # 3. Curata img_src din data.json final (nu e nevoie in AE)
    for group in [data["home"]["players"], data["away"]["players"],
                  data["home"]["substitutes"], data["away"]["substitutes"]]:
        for p in group:
            p.pop("img_src", None)

    # 4. Salveaza data.json
    print(f"\n[3/3] Salvare data.json...")
    data_path = OUTPUT_DIR / "data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"      Salvat: {data_path}")

    m = data["match"]
    print(f"""
{"=" * 55}
  GATA!
  {m["home_team"]} {m["home_score"]} - {m["away_score"]} {m["away_team"]}
  {m["home_formation"]} vs {m["away_formation"]}

  Urmator pas:
    Deschide .aep si ruleaza populate_lineup.jsx
{"=" * 55}
""")


if __name__ == "__main__":
    main()
