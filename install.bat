@echo off
REM -------------------------------------------------------------------
REM Weekly Monitor — one-command installer (Windows)
REM
REM Usage: Double-click this file, or run from Command Prompt:
REM   install.bat
REM -------------------------------------------------------------------

echo.
echo   +===================================+
echo   ^|   Weekly Monitor — Installer      ^|
echo   +===================================+
echo.

SET INSTALL_DIR=%USERPROFILE%\weekly-monitor
SET REPO_URL=https://github.com/Orshikhbayar/weekly-report.git

REM ── Step 1: Check Python ────────────────────────────────────────
echo   [1/4] Checking for Python 3.11+...

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo         Python not found. Attempting to install via winget...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo   ERROR: Could not install Python automatically.
        echo   Please download Python 3.11+ from:
        echo     https://www.python.org/downloads/
        echo   Make sure to check "Add Python to PATH" during install.
        echo.
        pause
        exit /b 1
    )
    echo         Python installed. You may need to restart this terminal.
    echo         Restarting installer...
    echo.
    REM Refresh PATH
    SET "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
)

python --version
echo.

REM ── Step 2: Clone or update repo ────────────────────────────────
echo   [2/4] Getting source code...
if exist "%INSTALL_DIR%\.git" (
    echo         Updating existing installation...
    cd /d "%INSTALL_DIR%"
    git pull
) else (
    echo         Cloning repository...
    git clone --progress "%REPO_URL%" "%INSTALL_DIR%"
    cd /d "%INSTALL_DIR%"
)

REM ── Step 3: Create venv + install dependencies ──────────────────
echo   [3/4] Installing Python dependencies...
if not exist ".venv" (
    python -m venv .venv
)

.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install .

REM ── Step 4: Install Chromium ────────────────────────────────────
echo   [4/4] Installing Chromium browser for screenshots...
.venv\Scripts\python -m playwright install chromium

REM ── Done ────────────────────────────────────────────────────────
echo.
echo   +===================================+
echo   ^|   Installation complete!          ^|
echo   +===================================+
echo.
echo   Run the monitor:
echo.
echo     %INSTALL_DIR%\.venv\Scripts\weekly-monitor interactive
echo.
echo   Or add to your PATH:
echo     %INSTALL_DIR%\.venv\Scripts
echo.
pause
