# Changelog

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
