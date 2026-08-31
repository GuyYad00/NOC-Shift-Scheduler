@echo off
setlocal
cd /d "%~dp0"

set VENV_PATH=.venv
set PYTHON_EXE=%VENV_PATH%\Scripts\python.exe
set PIP_EXE=%VENV_PATH%\Scripts\pip.exe

echo ============================================
echo   Building Advanced NOC Shift Scheduler EXE
echo ============================================
echo.

if not exist %PYTHON_EXE% (
    echo ERROR: Virtual environment '.venv' not found in this directory.
    echo Create it first:  python -m venv .venv
    pause
    exit /b 1
)

echo [1/3] Updating dependencies in .venv...
%PIP_EXE% install --upgrade pip
%PIP_EXE% install -r requirements.txt
%PIP_EXE% install pyinstaller
echo.

echo [2/3] Cleaning old build folders...
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
echo.

echo [3/3] Starting PyInstaller via run_build.py...
%PYTHON_EXE% run_build.py

echo.
if exist "dist\NOC_Scheduler_V2.exe" (
    echo ============================================
    echo   BUILD SUCCESS!
    echo   dist\NOC_Scheduler_V2.exe
    echo ============================================
) else (
    echo ============================================
    echo   BUILD FAILED. Check the errors above.
    echo ============================================
)
pause
