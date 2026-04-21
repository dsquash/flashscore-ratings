@echo off
chcp 65001 >nul
title Flashscore Ratings — Setup

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║          FLASHSCORE RATINGS  —  First-time Setup            ║
echo  ║          Marian Grosu                                        ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
echo  This script will:
echo    1. Check Python is installed
echo    2. Install required Python packages
echo    3. Download Chromium (used for web scraping)
echo    4. Install the After Effects panel
echo.
pause

:: ═══════════════════════════════════════════════════════════════════
::  STEP 1 — Python
:: ═══════════════════════════════════════════════════════════════════
echo.
echo  ─────────────────────────────────────────────
echo  STEP 1 / 4   Checking Python...
echo  ─────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Python is not installed or not in PATH.
    echo.
    echo   Please download and install Python from:
    echo   https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: During installation, check the box:
    echo   "Add Python to PATH"
    echo.
    echo   After installing Python, run this script again.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   OK: %%v found.

:: ═══════════════════════════════════════════════════════════════════
::  STEP 2 — Python packages
:: ═══════════════════════════════════════════════════════════════════
echo.
echo  ─────────────────────────────────────────────
echo  STEP 2 / 4   Installing Python packages...
echo              (playwright, httpx, pillow)
echo  ─────────────────────────────────────────────
python -m pip install --upgrade pip --quiet
python -m pip install playwright httpx pillow --quiet
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Failed to install packages.
    echo   Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo   OK: playwright, httpx, pillow installed.

:: ═══════════════════════════════════════════════════════════════════
::  STEP 3 — Chromium for Playwright
:: ═══════════════════════════════════════════════════════════════════
echo.
echo  ─────────────────────────────────────────────
echo  STEP 3 / 4   Downloading Chromium browser...
echo              (this may take 1-2 minutes)
echo  ─────────────────────────────────────────────
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Failed to download Chromium.
    echo   Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo   OK: Chromium ready.

:: ═══════════════════════════════════════════════════════════════════
::  STEP 4 — After Effects Panel
:: ═══════════════════════════════════════════════════════════════════
echo.
echo  ─────────────────────────────────────────────
echo  STEP 4 / 4   Installing After Effects panel...
echo  ─────────────────────────────────────────────

set PANEL_FILE=%~dp0Lineup Panel.jsx
set AE_BASE=C:\Program Files\Adobe
set INSTALLED_COUNT=0

:: Cauta toate versiunile de After Effects instalate
for /d %%D in ("%AE_BASE%\Adobe After Effects*") do (
    set AE_PANEL_DIR=%%D\Support Files\Scripts\ScriptUI Panels
    if exist "%%D\Support Files\Scripts" (
        if not exist "%%D\Support Files\Scripts\ScriptUI Panels" (
            mkdir "%%D\Support Files\Scripts\ScriptUI Panels" >nul 2>&1
        )
        copy /Y "%PANEL_FILE%" "%%D\Support Files\Scripts\ScriptUI Panels\Lineup Panel.jsx" >nul 2>&1
        if !errorlevel! equ 0 (
            echo   OK: Panel installed in %%D
            set /a INSTALLED_COUNT+=1
        ) else (
            echo   WARNING: Could not copy to %%D
            echo            (try running this script as Administrator)
        )
    )
)

:: Daca nu s-a instalat automat, afiseaza instructiunile manuale
if %INSTALLED_COUNT% equ 0 (
    echo.
    echo   After Effects was not found in the default location,
    echo   or the copy failed (permissions).
    echo.
    echo   Please install the panel manually:
    echo.
    echo   1. Copy this file:
    echo      %PANEL_FILE%
    echo.
    echo   2. Paste it into:
    echo      C:\Program Files\Adobe\Adobe After Effects [version]\
    echo                     Support Files\Scripts\ScriptUI Panels\
    echo.
    echo   3. Restart After Effects.
    echo   4. Open it from: Window ^> Lineup Panel
) else (
    echo.
    echo   Panel installed in %INSTALLED_COUNT% After Effects version(s).
    echo   Restart After Effects, then open: Window ^> Lineup Panel
)

:: ═══════════════════════════════════════════════════════════════════
::  DONE
:: ═══════════════════════════════════════════════════════════════════
echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║                    Setup complete!                           ║
echo  ║                                                              ║
echo  ║   Now run  launcher.py  and you're ready to go.             ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
pause
