# Changelog

## v1.0.55
- Browser: headless=True — browserul nu mai apare vizibil

## v1.0.54
- Search: alias-uri echipe naționale pentru DDG & Startpage (ex: "Czech Republic" → "czechia") — îmbunătățește rezultatele pentru meciuri de naționale

## v1.0.53
- Photos: înlocuiește httpx cu urllib.request pentru fetch pagina SoFIFA — httpx primea 403 Cloudflare, urllib.request trece fără probleme

## v1.0.52
- Photos: înlocuiește navigarea Playwright cu fetch httpx direct pe pagina SoFIFA — evită blocarea Cloudflare pentru jucătorii cu versiuni FC26 (260xxx)
- Încearcă URL-ul original + /customized ca fallback; Playwright rămâne ultima opțiune

## v1.0.51
- Photos: încearcă URL-ul original de pe DDG/Startpage, dacă nu găsește foto revine automat la varianta /customized

## v1.0.50
- Photos: URL-urile de pe DDG/Startpage cu versiune numerică (ex: /260024) sunt acum convertite automat la /customized — rezolvă NOT FOUND pentru jucătorii brazilieni și alți jucători custom

## v1.0.49
- Updater: fixed URL encoding bug that caused "Lineup Panel.jsx" (and "START HERE.bat" on Windows) to fail during auto-update

## v1.0.48
- Search: restored Startpage/httpx as Step 5 fallback after DuckDuckGo (fixes rate-limiting issues with 12+ players)
- Error handling: ERR_NAME_NOT_RESOLVED and other network errors now show clear Romanian messages instead of raw Playwright errors
- DuckDuckGo remains Step 4 fallback after SoFIFA roster match

## v1.0.5
- macOS: switched to native light theme so Aqua renders tk.Label/tk.Entry correctly (no more invisible text)
- macOS: color remap applied automatically at widget creation, no code changes in body
- Windows/Linux: unchanged (dark theme preserved)

## v1.0.4
- macOS: installer now auto-downloads official Python 3.12 from python.org if needed (Tk 8.6, proper UI)
- macOS: fixed installer crash on `set -u` with unicode ellipsis
- macOS: installer and launcher made bash-safe across locales

## v1.0.3
- macOS: installer now uses stock system Python (no Homebrew required)
- macOS: fixed UI rendering on Tk 8.5 via ttk shim in launcher
- macOS: installer and launcher simplified - no .python_path pin

## v1.0.0
- Initial release
- Full run: scrape Flashscore + download player photos from SoFIFA + populate After Effects
- Refresh Stats: re-scrape scores and ratings without re-downloading images
- SoFIFA overrides: manually map player names to SoFIFA profile URLs
- After Effects panel: Populate / Reset / Save State / Refresh Stats / Render to AME
- Auto-updater: one-click updates from GitHub
