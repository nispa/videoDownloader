import os
import sys
import time
from colorama import init, Fore, Style

# Local modules
import database
import bootstrapper
from clipboard import get_clipboard_url
from downloader import VideoDownloader

# Initialize colorama for Windows
init(autoreset=True)

def print_banner():
    """Print a colorful banner for the application."""
    os.system('cls' if os.name == 'nt' else 'clear')
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}=======================================================
{Fore.YELLOW}{Style.BRIGHT}         VIDEO & AUDIO DOWNLOADER (yt-dlp)
{Fore.CYAN}{Style.BRIGHT}=======================================================
{Fore.GREEN}Strumenti Locali: {Fore.WHITE}Gestiti in ./tools/
{Fore.GREEN}Database:         {Fore.WHITE}data/downloader.db
{Fore.GREEN}Cartella Download:{Fore.WHITE} {database.get_setting("download_path")}
{Fore.CYAN}=======================================================
"""
    print(banner)

def get_progress_callback():
    """Return a callback function that renders a command-line progress bar."""
    last_percent = -1

    def callback(percentage: float, speed: str, eta: str, status: str):
        nonlocal last_percent
        # Skip updates when the value barely changes, except during post-processing
        if percentage == last_percent and "Post-Processing" not in status and percentage < 100:
            return
        last_percent = percentage

        width = 30
        filled = int(width * percentage / 100)

        # Render the bar
        if percentage >= 100:
            bar_color = Fore.GREEN
            bar_str = "=" * width
        else:
            bar_color = Fore.YELLOW
            # Avoid empty strings or misplacing the '>' character
            if filled > 0:
                bar_str = "=" * (filled - 1) + ">" + " " * (width - filled)
            else:
                bar_str = ">" + " " * (width - 1)

        # Clear the current line and write
        sys.stdout.write(f"\r\033[K{bar_color}[{bar_str}] {Fore.CYAN}{percentage:5.1f}% {Fore.WHITE}| {Fore.YELLOW}{speed:<10s} {Fore.WHITE}| ETA: {Fore.GREEN}{eta:<6s} {Fore.WHITE}| {Fore.MAGENTA}{status}")
        sys.stdout.flush()

        if percentage >= 100 and (status == "Completato" or "Errore" in status):
            sys.stdout.write("\n")
            sys.stdout.flush()

    return callback

def download_menu(downloader: VideoDownloader):
    """Handle the download flow for a single video."""
    print_banner()
    print(f"{Fore.CYAN}[Menu Download]")

    # 1. Detect a link in the clipboard
    clipboard_url = get_clipboard_url()
    url = None

    if clipboard_url:
        print(f"\n{Fore.GREEN}⚡ Rilevato link negli appunti:{Fore.WHITE} {clipboard_url}")
        choice = input(f"{Fore.YELLOW}Premi INVIO per usare questo link, oppure scrivi/incolla un altro link:\n{Fore.CYAN}> {Style.RESET_ALL}").strip()
        if choice == "":
            url = clipboard_url
        else:
            url = choice
    else:
        url = input(f"\n{Fore.YELLOW}Incolla il link del video da scaricare:\n{Fore.CYAN}> {Style.RESET_ALL}").strip()

    if not url:
        print(f"\n{Fore.RED}Errore: Nessun link fornito. Ritorno al menu principale...")
        time.sleep(2)
        return

    # 2. Extract the video info
    print(f"\n{Fore.CYAN}Recupero informazioni sul video in corso...")
    info = downloader.get_info(url)

    if not info:
        print(f"\n{Fore.RED}Errore: Impossibile estrarre informazioni dal link. Verifica la connessione o il link.")
        input(f"\n{Fore.WHITE}Premi Invio per continuare...")
        return

    print(f"\n{Fore.GREEN}Dettagli Trovati:")
    print(f" {Fore.YELLOW}Titolo:     {Fore.WHITE}{info['title']}")
    print(f" {Fore.YELLOW}Autore:     {Fore.WHITE}{info['uploader']}")
    print(f" {Fore.YELLOW}Durata:     {Fore.WHITE}{info['duration']}")
    print(f" {Fore.YELLOW}Piattaforma:{Fore.WHITE}{info['extractor']}")

    # 3. Format choice
    print(f"\n{Fore.CYAN}Scegli formato di download:")
    print(f" {Fore.WHITE}1) {Fore.GREEN}Video {Fore.WHITE}(Migliore risoluzione mp4)")
    print(f" {Fore.WHITE}2) {Fore.GREEN}Audio {Fore.WHITE}(Estrazione MP3 alta qualità)")
    print(f" {Fore.WHITE}3) Annulla")

    format_choice = input(f"\n{Fore.YELLOW}Seleziona un'opzione [1-3]: {Fore.CYAN}").strip()

    if format_choice == "1":
        mode = "video"
    elif format_choice == "2":
        mode = "audio"
    else:
        print(f"\n{Fore.YELLOW}Operazione annullata.")
        time.sleep(1)
        return

    # 4. Run the download
    print(f"\n{Fore.CYAN}Avvio download in corso... (Salvataggio in: {downloader.get_download_path()})")

    progress_cb = get_progress_callback()

    success = downloader.download(url, mode=mode, progress_callback=progress_cb)

    if success:
        print(f"\n{Fore.GREEN}🎉 File scaricato correttamente!")
    else:
        print(f"\n{Fore.RED}❌ Download fallito. Controlla logs/app.log per maggiori informazioni.")

    input(f"\n{Fore.WHITE}Premi Invio per tornare al menu...")

def settings_menu(downloader: VideoDownloader):
    """Handle the settings menu (download directory)."""
    print_banner()
    print(f"{Fore.CYAN}[Menu Impostazioni]")
    current_path = downloader.get_download_path()
    print(f"\nCartella di download attuale: {Fore.YELLOW}{current_path}")

    new_path = input(f"\n{Fore.WHITE}Inserisci il nuovo percorso assoluto per i download (oppure premi Invio per annullare):\n{Fore.CYAN}> {Style.RESET_ALL}").strip()

    if new_path:
        # Strip quotes that may be added when dragging a folder into the terminal
        new_path = new_path.strip('"').strip("'")
        try:
            os.makedirs(new_path, exist_ok=True)
            database.set_setting("download_path", os.path.abspath(new_path))
            print(f"\n{Fore.GREEN}✔ Cartella di download aggiornata con successo!")
        except Exception as e:
            print(f"\n{Fore.RED}Errore: Impossibile creare o accedere alla cartella inserita: {e}")
    else:
        print(f"\n{Fore.YELLOW}Operazione annullata.")

    time.sleep(2)

def main():
    # 1. Run the bootstrapper to make sure yt-dlp and ffmpeg are available
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Fore.CYAN}=== Avvio in corso ===")
    print(f"{Fore.WHITE}Verifica dipendenze in corso (yt-dlp, ffmpeg)...")

    if not bootstrapper.run_bootstrap():
        print(f"\n{Fore.RED}Errore critico: Impossibile configurare gli strumenti di download.")
        print("Verifica la connessione ad internet e riprova.")
        input("\nPremi Invio per uscire...")
        sys.exit(1)

    # Initialize the downloader
    downloader = VideoDownloader()

    # 2. Main application loop
    while True:
        print_banner()
        print(f" {Fore.WHITE}1) {Fore.GREEN}Scarica Video / Audio da Link")
        print(f" {Fore.WHITE}2) {Fore.GREEN}Configura cartella di download")
        print(f" {Fore.WHITE}3) {Fore.RED}Esci")

        choice = input(f"\n{Fore.YELLOW}Seleziona un'opzione [1-3]: {Fore.CYAN}").strip()

        if choice == "1":
            download_menu(downloader)
        elif choice == "2":
            settings_menu(downloader)
        elif choice == "3":
            print(f"\n{Fore.YELLOW}Grazie per aver usato Video & Audio Downloader. Alla prossima!")
            break
        else:
            print(f"\n{Fore.RED}Opzione non valida. Riprova.")
            time.sleep(1.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Programma interrotto dall'utente. Uscita...")
        sys.exit(0)
