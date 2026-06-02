@echo off
chcp 65001 >nul

:menu
cls
echo =======================================================
echo            Video ^& Audio Downloader Menu
echo =======================================================
echo.
echo  1. Avvia Interfaccia Grafica (GUI) - Consigliato
echo  2. Avvia Riga di Comando (CLI)
echo  3. Compila in Eseguibile (VideoDownloader.exe)
echo  4. Esegui / Ripristina Setup Completo
echo  5. Esci
echo.
echo =======================================================
set choice=
set /p choice="Seleziona un'opzione (1-5): "

if "%choice%"=="1" goto run_gui
if "%choice%"=="2" goto run_cli
if "%choice%"=="3" goto compile
if "%choice%"=="4" goto run_setup
if "%choice%"=="5" goto exit
goto menu

:run_gui
cls
echo [+] Avvio dell'Interfaccia Grafica in corso...
if not exist ".venv" (
    echo [AVVISO] Ambiente virtuale non trovato. Avvio setup automatico...
    call setup.bat
)
call .venv\Scripts\python src/gui.py
pause
goto menu

:run_cli
cls
echo [+] Avvio dell'Interfaccia a Riga di Comando in corso...
if not exist ".venv" (
    echo [AVVISO] Ambiente virtuale non trovato. Avvio setup automatico...
    call setup.bat
)
call .venv\Scripts\python src/main.py
pause
goto menu

:compile
cls
echo [+] Compilazione dell'applicazione standalone in corso...
if not exist ".venv" (
    echo [AVVISO] Ambiente virtuale non trovato. Avvio setup automatico...
    call setup.bat
)
call .venv\Scripts\python build_exe.py
pause
goto menu

:run_setup
cls
echo [+] Esecuzione del Setup in corso...
call setup.bat
goto menu

:exit
cls
echo Grazie per aver utilizzato Video ^& Audio Downloader!
timeout /t 3 >nul
exit
