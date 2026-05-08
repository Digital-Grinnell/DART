@echo off
REM FLAT - Flet Layout Application Template - Windows Launch Script
REM Sets up a Python virtual environment and launches the Flet app.
REM
REM Prerequisites (one-time, if not already installed):
REM   Python 3:  https://www.python.org/downloads/

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo === FLAT - Flet Layout Application Template ===
echo.

REM Verify Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH.
    echo Please install Python 3 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist ".venv\" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

REM Install / upgrade dependencies
echo Installing dependencies (this may take a few minutes on first run)...
python -m pip install --upgrade pip --quiet
python -m pip install -r python_requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

REM Launch the app
echo Launching FLAT...
echo.
python app.py

REM Keep window open if the app exits with an error
if errorlevel 1 (
    echo.
    echo FLAT exited with an error. See messages above.
    pause
)

endlocal
