@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM   Flashscore Ratings -- Installer
REM   Downloads the app from GitHub + AE template from Drive
REM ============================================================

set GITHUB_ZIP=https://github.com/dsquash/flashscore-ratings/archive/refs/heads/main.zip
set GDRIVE_FOLDER_ID=1OwZoHfrUxtAZtS042g63Pqw0eSqP31Ti
set GDRIVE_URL=https://drive.google.com/drive/folders/1OwZoHfrUxtAZtS042g63Pqw0eSqP31Ti

set INSTALL_DIR=%~dp0
set SCRIPTS_DIR=%INSTALL_DIR%_DO NOT TOUCH_
set TEMP_ZIP=%TEMP%\flashscore_code.zip

echo.
echo  ============================================================
echo    Flashscore Ratings -- Installer
echo  ============================================================
echo.

REM -- Check / Install Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Python not found. Attempting automatic install...
    echo.

    winget --version >nul 2>&1
    if not errorlevel 1 (
        echo  Installing Python via winget...
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
    )

    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  [INFO] Downloading Python installer...
        powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe' -UseBasicParsing"
        echo  Running Python installer -- check "Add Python to PATH" and click Install Now.
        "%TEMP%\python_installer.exe" /passive PrependPath=1 Include_pip=1
        del "%TEMP%\python_installer.exe" >nul 2>&1
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
    )

    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  [ERROR] Python still not found. Install manually from https://www.python.org/downloads/
        echo          Check "Add Python to PATH" during install, then re-run this installer.
        echo.
        pause
        exit /b 1
    )
)
echo  [OK] Python found.

REM -- Download code from GitHub
echo.
echo  [1/4] Downloading app from GitHub...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%GITHUB_ZIP%' -OutFile '%TEMP_ZIP%' -UseBasicParsing; Write-Host 'OK' } catch { Write-Host ('FAIL: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
    echo  [ERROR] Could not download from GitHub. Check your internet connection.
    pause
    exit /b 1
)

REM -- Extract and organize into _DO NOT TOUCH_ folder
echo  [2/4] Extracting app files...
powershell -NoProfile -Command "Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP%\flashscore_extract' -Force"

REM Create _DO NOT TOUCH_ folder
if not exist "%SCRIPTS_DIR%" mkdir "%SCRIPTS_DIR%"

REM Move script files into _DO NOT TOUCH_
set SCRIPT_FILES=launcher.py run.py refresh_stats.py updater.py version.txt CHANGELOG.md sofija_overrides.json
for %%F in (%SCRIPT_FILES%) do (
    if exist "%TEMP%\flashscore_extract\flashscore-ratings-main\%%F" (
        copy /Y "%TEMP%\flashscore_extract\flashscore-ratings-main\%%F" "%SCRIPTS_DIR%\%%F" >nul
    )
)

REM JSX files (with spaces in names need special handling)
copy /Y "%TEMP%\flashscore_extract\flashscore-ratings-main\populate_lineup.jsx" "%SCRIPTS_DIR%\populate_lineup.jsx" >nul 2>&1
copy /Y "%TEMP%\flashscore_extract\flashscore-ratings-main\reset_lineup.jsx" "%SCRIPTS_DIR%\reset_lineup.jsx" >nul 2>&1
copy /Y "%TEMP%\flashscore_extract\flashscore-ratings-main\refresh_comps.jsx" "%SCRIPTS_DIR%\refresh_comps.jsx" >nul 2>&1
copy /Y "%TEMP%\flashscore_extract\flashscore-ratings-main\save_template_state.jsx" "%SCRIPTS_DIR%\save_template_state.jsx" >nul 2>&1
copy /Y "%TEMP%\flashscore_extract\flashscore-ratings-main\Lineup Panel.jsx" "%SCRIPTS_DIR%\Lineup Panel.jsx" >nul 2>&1

REM Root files (installer + launcher shortcut)
copy /Y "%TEMP%\flashscore_extract\flashscore-ratings-main\INSTALL.bat" "%INSTALL_DIR%INSTALL.bat" >nul 2>&1
copy /Y "%TEMP%\flashscore_extract\flashscore-ratings-main\START HERE.bat" "%INSTALL_DIR%START HERE.bat" >nul 2>&1

rmdir /s /q "%TEMP%\flashscore_extract" >nul 2>&1
del "%TEMP_ZIP%" >nul 2>&1
echo  [OK] Files installed into _DO NOT TOUCH_ folder.

REM -- Install Python packages
echo.
echo  [3/4] Installing Python packages...
python -m pip install playwright httpx pillow gdown ttkbootstrap --quiet
python -m playwright install chromium
echo  [OK] Python packages installed.

REM -- Download AE template from Google Drive
echo.
echo  [4/4] Downloading After Effects template from Google Drive...
python -m gdown --folder "%GDRIVE_FOLDER_ID%" -O "%INSTALL_DIR%"
if errorlevel 1 (
    echo.
    echo  [WARNING] Automatic download failed.
    echo           Opening Google Drive in your browser -- download the folder manually.
    echo           Save the files here: %INSTALL_DIR%
    echo.
    start "" "%GDRIVE_URL%"
) else (
    echo  [OK] After Effects template downloaded.
)

REM -- Install AE panel
echo.
echo  Installing After Effects panel...
set PANEL_SRC=%SCRIPTS_DIR%\Lineup Panel.jsx
set AE_BASE=C:\Program Files\Adobe
set INSTALLED_COUNT=0

for /d %%D in ("%AE_BASE%\Adobe After Effects*") do (
    if exist "%%D\Support Files\Scripts" (
        if not exist "%%D\Support Files\Scripts\ScriptUI Panels" mkdir "%%D\Support Files\Scripts\ScriptUI Panels" >nul 2>&1
        copy /Y "%PANEL_SRC%" "%%D\Support Files\Scripts\ScriptUI Panels\Lineup Panel.jsx" >nul 2>&1
        if not errorlevel 1 (
            echo  [OK] Panel installed in: %%D
            set /a INSTALLED_COUNT+=1
        ) else (
            echo  [WARNING] Could not copy panel to %%D - try running as Administrator.
        )
    )
)

if %INSTALLED_COUNT% equ 0 (
    echo  [INFO] After Effects not found automatically.
    echo         Copy "Lineup Panel.jsx" from "_DO NOT TOUCH_" folder manually into:
    echo         C:\Program Files\Adobe\Adobe After Effects [version]\Support Files\Scripts\ScriptUI Panels\
)

REM -- Done
echo.
echo  ============================================================
echo    DONE! Everything is installed.
echo.
echo    To get started:
echo      Double-click "START HERE.bat" to launch the app.
echo.
echo    For help, reach out to Marian Grosu.
echo  ============================================================
echo.
pause
