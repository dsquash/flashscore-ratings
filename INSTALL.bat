@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================
::   Flashscore Ratings — Installer
::   Downloads the app from GitHub + AE template from Drive
:: ============================================================

set GITHUB_ZIP=https://github.com/dsquash/flashscore-ratings/archive/refs/heads/main.zip

:: ── Google Drive folder with the AE template ────────────────
set GDRIVE_FOLDER_ID=1OwZoHfrUxtAZtS042g63Pqw0eSqP31Ti
:: ────────────────────────────────────────────────────────────

set INSTALL_DIR=%~dp0
set TEMP_ZIP=%TEMP%\flashscore_code.zip

echo.
echo  ============================================================
echo    Flashscore Ratings — Installer
echo  ============================================================
echo.

:: ── Check / Install Python ───────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Python not found. Attempting automatic install...
    echo.

    :: Try winget first (available on Windows 10/11)
    winget --version >nul 2>&1
    if not errorlevel 1 (
        echo  Installing Python via winget...
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        :: Refresh PATH so python is visible immediately
        call refreshenv >nul 2>&1
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
    )

    :: Check again after winget attempt
    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  [INFO] Winget install did not work. Downloading Python installer...
        set PY_INSTALLER=%TEMP%\python_installer.exe
        powershell -NoProfile -Command ^
          "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe' -UseBasicParsing"
        echo.
        echo  Running Python installer — check "Add Python to PATH" and click Install Now.
        "%TEMP%\python_installer.exe" /passive PrependPath=1 Include_pip=1
        del "%TEMP%\python_installer.exe" >nul 2>&1
        :: Refresh PATH
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
    )

    :: Final check
    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  [ERROR] Python still not found after install attempt.
        echo          Please install Python manually from https://www.python.org/downloads/
        echo          Make sure to check "Add Python to PATH" during install, then re-run this installer.
        echo.
        pause
        exit /b 1
    )
)
echo  [OK] Python found.

:: ── Download code from GitHub ─────────────────────────────────
echo.
echo  [1/4] Downloading app from GitHub...
powershell -NoProfile -Command ^
  "try { Invoke-WebRequest -Uri '%GITHUB_ZIP%' -OutFile '%TEMP_ZIP%' -UseBasicParsing; Write-Host 'OK' } catch { Write-Host ('FAIL: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
    echo  [ERROR] Could not download from GitHub. Check your internet connection.
    pause
    exit /b 1
)

:: ── Extract code ──────────────────────────────────────────────
echo  [2/4] Extracting app files...
powershell -NoProfile -Command ^
  "Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP%\flashscore_extract' -Force"

:: Move files from the extracted subfolder to install dir
xcopy /e /i /y "%TEMP%\flashscore_extract\flashscore-ratings-main\*" "%INSTALL_DIR%" >nul
rmdir /s /q "%TEMP%\flashscore_extract" >nul 2>&1
del "%TEMP_ZIP%" >nul 2>&1
echo  [OK] App files installed.

:: ── Download AE template from Google Drive (folder) ──────────
echo.
echo  [3/4] Downloading After Effects template from Google Drive...
python -m pip install gdown --quiet
python -m gdown --folder "%GDRIVE_FOLDER_ID%" -O "%INSTALL_DIR%" --quiet 2>nul

if errorlevel 1 (
    echo  [WARNING] Could not download AE template automatically.
    echo            Download it manually from:
    echo            https://drive.google.com/drive/folders/%GDRIVE_FOLDER_ID%
) else (
    echo  [OK] After Effects template downloaded.
)

:after_template

:: ── Install Python packages + Chromium ───────────────────────
echo.
echo  Installing Python packages...
python -m pip install playwright httpx pillow --quiet
python -m playwright install chromium

:: ── Install AE extension ──────────────────────────────────────
echo.
echo  Installing After Effects extension...
set AE_BASE=C:\Program Files\Adobe
set PANEL_SRC=%INSTALL_DIR%Lineup Panel.jsx
set INSTALLED_AE=0

if exist "%PANEL_SRC%" (
    for /d %%D in ("%AE_BASE%\Adobe After Effects*") do (
        set PANEL_DST=%%D\Support Files\Scripts\ScriptUI Panels
        if exist "!PANEL_DST!" (
            copy /y "%PANEL_SRC%" "!PANEL_DST!\" >nul 2>&1
            if !errorlevel! equ 0 (
                echo  [OK] Extension installed: %%D
                set INSTALLED_AE=1
            ) else (
                echo  [WARNING] Could not copy to %%D ^(try running as Administrator^)
            )
        )
    )
    if !INSTALLED_AE! equ 0 (
        echo  [INFO] After Effects not found in default location.
        echo         Copy "Lineup Panel.jsx" manually to:
        echo         AE folder\Support Files\Scripts\ScriptUI Panels\
    )
) else (
    echo  [INFO] Lineup Panel.jsx not found, skipping AE extension.
)

:: ── Done ──────────────────────────────────────────────────────
echo.
echo  ============================================================
echo    DONE! Everything is installed.
echo.
echo    To get started:
echo      1. Open After Effects and load the .aep template
echo      2. Run launcher.py to start the app
echo.
echo    For help, reach out to Marian Grosu.
echo  ============================================================
echo.
pause
