@echo off
set VENV_PATH=.venv
set PYTHON_EXE=%VENV_PATH%\Scripts\python.exe
set PIP_EXE=%VENV_PATH%\Scripts\pip.exe
set PYINSTALLER_EXE=%VENV_PATH%\Scripts\pyinstaller.exe

echo ============================================
echo   Building Advanced NOC Shift Scheduler EXE
echo ============================================
echo.

if not exist %PYTHON_EXE% (
    echo ERROR: Virtual environment '.venv' not found.
    pause
    exit /b 1
)

echo [1/5] Updating dependencies...
%PIP_EXE% install --upgrade pip
%PIP_EXE% install -r requirements.txt
%PIP_EXE% install pyinstaller
echo.

echo [2/5] Detecting asset paths...
for /f "delims=" %%i in ('%PYTHON_EXE% -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i
for /f "delims=" %%i in ('%PYTHON_EXE% -c "import pulp, os; print(os.path.join(os.path.dirname(pulp.__file__), 'solverdir', 'cbc', 'win', 'i64', 'cbc.exe'))"') do set CBC_PATH=%%i

if "%CTK_PATH%"=="" (
    echo ERROR: customtkinter not found.
    pause
    exit /b 1
)
if not exist "%CBC_PATH%" (
    echo ERROR: PuLP CBC solver not found at %CBC_PATH%
    pause
    exit /b 1
)
echo   customtkinter: %CTK_PATH%
echo   CBC solver:    %CBC_PATH%
echo.

echo [3/5] Detecting Anaconda DLLs and Tcl/Tk...
set ANACONDA_BIN=C:\Users\guyys\anaconda3\Library\bin
set TCL_LIB=C:\Users\guyys\anaconda3\Library\lib\tcl8.6
set TK_LIB=C:\Users\guyys\anaconda3\Library\lib\tk8.6
echo.

echo [4/5] Cleaning old build...
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
echo.

echo [5/5] Building EXE...
%PYINSTALLER_EXE% --noconfirm --onefile --windowed ^
    --name "NOC_Scheduler_V2" ^
    --add-data "%CTK_PATH%;customtkinter/" ^
    --add-binary "%CBC_PATH%;." ^
    --add-binary "%ANACONDA_BIN%\tk86t.dll;." ^
    --add-binary "%ANACONDA_BIN%\tcl86t.dll;." ^
    --add-binary "%ANACONDA_BIN%\libssl-3-x64.dll;." ^
    --add-binary "%ANACONDA_BIN%\libcrypto-3-x64.dll;." ^
    --add-binary "%ANACONDA_BIN%\ffi.dll;." ^
    --add-binary "%ANACONDA_BIN%\libexpat.dll;." ^
    --add-binary "%ANACONDA_BIN%\liblzma.dll;." ^
    --add-binary "%ANACONDA_BIN%\libbz2.dll;." ^
    --add-data "%TCL_LIB%;tcl\tcl8.6" ^
    --add-data "%TK_LIB%;tcl\tk8.6" ^
    main.py

echo.
if exist "dist\NOC_Scheduler_V2.exe" (
    echo ============================================
    echo   BUILD SUCCESS!
    echo   dist\NOC_Scheduler_V2.exe
    echo ============================================
) else (
    echo BUILD FAILED. Check errors above.
)
pause
