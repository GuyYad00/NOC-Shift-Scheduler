@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"

".venv\Scripts\python.exe" run_build.py > build_log.txt 2>&1

if exist "dist\NOC_Scheduler_V2.exe" (
    echo BUILD SUCCESS > build_status.txt
) else (
    echo BUILD FAILED > build_status.txt
)
