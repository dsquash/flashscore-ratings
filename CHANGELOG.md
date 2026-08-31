# Changelog

## v1.0.128
- **Fix important — poze de jucători greșite.** Lineup-ul Sofascore eșua cu "Execution context was destroyed": navigarea către sofascore.com se termina înainte de redirectul JS, care distrugea contextul în timpul `page.evaluate()`. Fără lineup, potrivirea cădea pe căutare după nume, care returna primul fotbalist cu acel nume din toată baza Sofascore. Ex. Liverpool–Nottingham: "Cunha" #23 lua poza lui Matheus Cunha (Man Utd) în loc de Jair (Forest) — și era raportat ca OK.
- Photos: sursa e acum **exclusiv** lineup-ul Sofascore din `--sofascore-url`, potrivit după numărul de tricou. Fără lineup nu se mai ghicește: jucătorii negăsiți primesc placeholder, vizibil, în loc de o poză greșită tăcută.
- Photos: fallback-ul pe poza Flashscore trece pe comutatorul `ALLOW_FLASHSCORE_PHOTO_FALLBACK` (implicit dezactivat)
- Scos complet sistemul SoFIFA și de overrides: `sofifa_overrides.json`, `get_sofifa_team_roster` (295 linii, nu era apelată niciodată), plus ferestrele SoFIFA din launcher (cod orfan, fără buton care să ducă la ele). ~760 de linii eliminate.
- AE panel: **Render exportă acum la 1080x1920** (FHD vertical) în loc de 2160x3840. Se face printr-un comp-înveliș temporar scalat la `RENDER_SCALE` (0.5), șters imediat după trimiterea în Media Encoder. Presetul din AME trebuie să fie "Match Source – Adaptive High Bitrate".

## v1.0.56
- Photos: ia cea mai mare varianta din srcset (in loc de prima/cea mai mica)
- Photos: upscale automat la 240x240 cu LANCZOS daca poza e sub 200px (ex: thumbnailuri Flashscore)

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

## v1.0.64
- Photos: srcset ia cea mai mare variantă disponibilă (rezoluție maximă)
- Photos: upscale automat la 240x240 dacă poza e sub 200px
- Browser: headless (fără fereastră vizibilă)
- Search: alias-uri echipe naționale (Czech Republic→czechia, Republic of Ireland→ireland etc.)
- Search: urllib.request în loc de httpx pentru fetch pagina SoFIFA (httpx blocat de Cloudflare)
- Search: încearcă URL original + /customized ca fallback
- Updater: fix URL encoding pentru fișiere cu spații în nume (Lineup Panel.jsx, START HERE.bat)
- Erori rețea: mesaje clare în română (ERR_NAME_NOT_RESOLVED, timeout etc.)
