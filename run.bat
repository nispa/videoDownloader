@echo off
:: NOTE: keep this file pure ASCII (no accented letters!). With chcp 65001
:: active, multi-byte characters desync the cmd batch parser.
chcp 65001 >nul

:menu
cls
echo =======================================================
echo            Video ^& Audio Downloader Menu
echo =======================================================
echo.
echo  1. Start Graphical Interface (GUI) - Recommended
echo  2. Start Command Line Interface (CLI)
echo  3. Build Executable (VideoDownloader.exe)
echo  4. Run / Repair Full Setup
echo  5. Exit
echo.
echo =======================================================
set choice=
set /p choice="Select an option (1-5): "

if "%choice%"=="1" goto run_gui
if "%choice%"=="2" goto run_cli
if "%choice%"=="3" goto compile
if "%choice%"=="4" goto run_setup
if "%choice%"=="5" goto exit
goto menu

:run_gui
cls
echo [+] Starting the Graphical Interface...
if not exist ".venv" (
    echo [WARNING] Virtual environment not found. Running automatic setup...
    call setup.bat
)
call .venv\Scripts\python src/gui.py
pause
goto menu

:run_cli
cls
echo [+] Starting the Command Line Interface...
if not exist ".venv" (
    echo [WARNING] Virtual environment not found. Running automatic setup...
    call setup.bat
)
call .venv\Scripts\python src/main.py
pause
goto menu

:compile
cls
echo [+] Building the standalone application...
if not exist ".venv" (
    echo [WARNING] Virtual environment not found. Running automatic setup...
    call setup.bat
)
call .venv\Scripts\python build_exe.py
pause
goto menu

:run_setup
cls
echo [+] Running Setup...
call setup.bat
goto menu

:exit
cls
echo Thanks for using Video ^& Audio Downloader!
timeout /t 3 >nul
exit
