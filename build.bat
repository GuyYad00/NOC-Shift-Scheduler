@echo off
echo ============================================
echo   Building NOC Shift Scheduler EXE
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.10+ first.
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt
echo.

echo Detecting customtkinter path...
for /f "delims=" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i

if "%CTK_PATH%"=="" (
    echo ERROR: customtkinter not found.
    pause
    exit /b 1
)
echo Found customtkinter at: %CTK_PATH%
echo.

echo Building EXE...
pyinstaller --noconfirm --onefile --windowed ^
    --name "NOC_Scheduler" ^
    --add-data "%CTK_PATH%;customtkinter/" ^
    main.py

echo.
if exist "dist\NOC_Scheduler.exe" (
    echo ============================================
    echo   BUILD SUCCESS!
    echo   EXE located at: dist\NOC_Scheduler.exe
    echo ============================================
) else (
    echo BUILD FAILED. Check errors above.
)
pause
