@echo off
:: Hide individual commands to keep the output clean.
:: NOTE: keep this file pure ASCII (no accented letters!). With chcp 65001
:: active, multi-byte characters desync the cmd batch parser.
chcp 65001 >nul

echo =======================================================
echo        Video ^& Audio Downloader - SETUP
echo =======================================================
echo.

:: 1. Check that Python is available
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found on this system!
    echo Please install Python ^(version 3.8 or later^)
    echo and make sure to check "Add Python to PATH" during the installation.
    echo.
    pause
    exit /b 1
)

echo [+] Python detected.
echo.

:: 2. Create the .venv virtual environment if it does not exist
if not exist ".venv" (
    echo [+] Creating the virtual environment ^(.venv^)...
    python -m venv .venv
    if %errorlevel% neq 0 (
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
call .venv\Scripts\pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] An error occurred while installing the dependencies.
    pause
    exit /b 1
)
echo [+] Dependencies installed successfully.
echo.

:: 4. Download/bootstrap the support tools (yt-dlp and ffmpeg)
echo [+] Downloading and updating the support tools ^(yt-dlp, FFmpeg^)...
call .venv\Scripts\python src/bootstrapper.py
if %errorlevel% neq 0 (
    echo [ERROR] An error occurred while initializing the support tools.
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
