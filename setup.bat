@echo off
:: Hide individual commands to keep the output clean.
:: NOTE: keep this file pure ASCII (no accented letters!). With chcp 65001
:: active, multi-byte characters desync the cmd batch parser.
chcp 65001 >nul

:: Always work from the folder this script lives in. Launching it from a
:: shortcut, via "Run as administrator" (which starts in System32) or from
:: another drive would otherwise break every relative path below.
cd /d "%~dp0"

echo =======================================================
echo        Video ^& Audio Downloader - SETUP
echo =======================================================
echo.

:: 1. Find a usable Python.
::
:: "where python" is not enough: on Windows 11 it also matches the Microsoft
:: Store app execution alias, which exists even when Python is NOT installed
:: and merely opens the Store when run. The check would pass, then "python -m
:: venv" would silently create nothing and every later step would fail.
:: Actually running an interpreter and testing its exit code is the only
:: reliable probe. The py launcher is tried first: it is never the Store stub.
set "PYTHON_CMD="

py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if %errorlevel% equ 0 set "PYTHON_CMD=py -3"
if defined PYTHON_CMD goto python_found

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if %errorlevel% equ 0 set "PYTHON_CMD=python"
if defined PYTHON_CMD goto python_found

echo [ERROR] No usable Python 3.10 or later was found on this system.
echo.
echo If Python is not installed, download it from https://www.python.org
echo and tick "Add Python to PATH" during the installation.
echo.
echo If you believe Python IS installed, it may be too old. Reported version:
python --version 2>nul
py --version 2>nul
echo.
pause
exit /b 1

:python_found
for /f "tokens=*" %%v in ('%PYTHON_CMD% --version 2^>^&1') do echo [+] %%v detected.
echo.

:: 2. Create the .venv virtual environment if it does not exist
if not exist ".venv\Scripts\python.exe" (
    echo [+] Creating the virtual environment ^(.venv^)...
    %PYTHON_CMD% -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
    echo [+] Virtual environment created successfully.
) else (
    echo [+] Virtual environment ^(.venv^) already present.
)
echo.

:: 3. Upgrade pip and install the dependencies
echo [+] Upgrading pip and installing dependencies...
call .venv\Scripts\python -m pip install --upgrade pip
call .venv\Scripts\python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] An error occurred while installing the dependencies.
    echo.
    echo On a corporate network this is usually pip being unable to reach
    echo pypi.org through the proxy. Ask IT for the proxy address, then run:
    echo     set HTTPS_PROXY=http://proxy.example.com:8080
    echo and start this setup again.
    pause
    exit /b 1
)
echo [+] Dependencies installed successfully.
echo.

:: 4. Download/bootstrap the support tools (yt-dlp and ffmpeg)
echo [+] Downloading and updating the support tools ^(yt-dlp, FFmpeg^)...
call .venv\Scripts\python src/bootstrapper.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The support tools could not be initialized. The cause is
    echo printed above and recorded in logs\app.log.
    pause
    exit /b 1
)
echo [+] Tools configured successfully.
echo.

echo =======================================================
echo  Setup completed successfully! Everything is ready.
echo  You can start the application with 'run.bat'.
echo =======================================================
echo.
pause
