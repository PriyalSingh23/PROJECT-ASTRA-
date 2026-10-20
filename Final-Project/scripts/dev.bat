@echo off
setlocal enabledelayedexpansion
title SHADOWCOMM / ASTRA - Distributed Multi-Daemon Cluster Launcher (Windows)

echo ========================================================================
echo   SHADOWCOMM / ASTRA -- Distributed Tactical Cluster Launcher (Windows)
echo ========================================================================
echo.

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
cd /d "%PROJECT_ROOT%"

REM Detect Python executable (radioconda or system python)
set PYTHON_BIN=python
if exist "%USERPROFILE%\radioconda\python.exe" (
    set "PYTHON_BIN=%USERPROFILE%\radioconda\python.exe"
    echo [INFO] Using Radioconda Python: !PYTHON_BIN!
) else (
    echo [INFO] Using System Python: %PYTHON_BIN%
)

REM Verify Python is accessible
"%PYTHON_BIN%" --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ or Radioconda and add to PATH.
    pause
    exit /b 1
)

REM Ensure data directory exists
if not exist "data" mkdir data

REM Set PYTHONPATH
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

echo.
echo [1/3] Launching Station Alpha Daemon on http://127.0.0.1:5051 (data\alpha.db)...
start "ASTRA - Station Alpha (5051)" cmd /k ""%PYTHON_BIN%" -m messaging.server --host 127.0.0.1 --port 5051 --db data/alpha.db --station-id endpoint-a --station-name "Station Alpha" --peer-url http://127.0.0.1:5052/api/v1 --with-worker"

echo [2/3] Launching Station Bravo Daemon on http://127.0.0.1:5052 (data\bravo.db)...
start "ASTRA - Station Bravo (5052)" cmd /k ""%PYTHON_BIN%" -m messaging.server --host 127.0.0.1 --port 5052 --db data/bravo.db --station-id endpoint-b --station-name "Station Bravo" --peer-url http://127.0.0.1:5051/api/v1 --with-worker"

echo [3/3] Launching Unified Web Console Gateway on http://127.0.0.1:5050...
start "ASTRA - Unified Web Console (5050)" cmd /k ""%PYTHON_BIN%" -m messaging.server --host 127.0.0.1 --port 5050 --no-worker"

echo.
echo ========================================================================
echo   ASTRA Tactical Cluster Online!
echo ========================================================================
echo   - Unified Console:  http://127.0.0.1:5050/
echo   - Station Alpha:    http://127.0.0.1:5051/
echo   - Station Bravo:    http://127.0.0.1:5052/
echo.
echo   Default Demo Credentials:
echo     Operator: operator / OperatorPass@2026!
echo     Admin:    admin / AdminPass@2026!
echo ========================================================================
echo.
echo Close the individual window prompts or terminate to shutdown servers.
pause
