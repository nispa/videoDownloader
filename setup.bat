@echo off
:: Impedisce la visualizzazione dei singoli comandi nel terminale per mantenere l'output pulito
chcp 65001 >nul
:: Imposta la codifica UTF-8 per supportare le emoji nel terminale di Windows

echo =======================================================
echo        Video ^& Audio Downloader - SETUP
echo =======================================================
echo.

:: 1. Verifica la presenza di Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRORE] Python non è stato trovato nel sistema!
    echo Per favore, installa Python (versione 3.8 o superiore)
    echo e assicurati di spuntare l'opzione "Add Python to PATH" durante l'installazione.
    echo.
    pause
    exit /b 1
)

echo [+] Python rilevato nel sistema.
echo.

:: 2. Creazione dell'ambiente virtuale .venv se non esiste
if not exist ".venv" (
    echo [+] Creazione dell'ambiente virtuale (.venv) in corso...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERRORE] Impossibile creare l'ambiente virtuale.
        pause
        exit /b 1
    )
    echo [+] Ambiente virtuale creato con successo.
) else (
    echo [+] Ambiente virtuale (.venv) già presente.
)
echo.

:: 3. Aggiornamento pip e installazione delle dipendenze
echo [+] Aggiornamento di pip e installazione delle dipendenze in corso...
call .venv\Scripts\python -m pip install --upgrade pip
call .venv\Scripts\pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERRORE] Si è verificato un errore durante l'installazione delle dipendenze.
    pause
    exit /b 1
)
echo [+] Dipendenze installate con successo.
echo.

:: 4. Download/Bootstrap dei tool (yt-dlp e ffmpeg)
echo [+] Download e aggiornamento dei tool di supporto (yt-dlp, FFmpeg)...
call .venv\Scripts\python src/bootstrapper.py
if %errorlevel% neq 0 (
    echo [ERRORE] Si è verificato un errore durante l'inizializzazione dei tool di supporto.
    pause
    exit /b 1
)
echo [+] Configurazione dei tool completata.
echo.

echo =======================================================
echo  Setup completato con successo! Tutto è pronto all'uso.
echo  Puoi avviare l'applicazione usando 'run.bat'.
echo =======================================================
echo.
pause
