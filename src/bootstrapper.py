import os
import zipfile
import logging
import requests
import subprocess
from tqdm import tqdm
import database

# Configura le directory principali importando BASE_DIR da database
BASE_DIR = database.BASE_DIR
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(TOOLS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Configura il logging su file e su console
log_file = os.path.join(LOGS_DIR, "app.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("bootstrapper")

# Header standard per le richieste HTTP
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def download_file(url: str, dest_path: str, description: str):
    """Scarica un file da un URL mostrando una barra di avanzamento tqdm."""
    logger.info(f"Inizio download di {description} da: {url}")
    response = requests.get(url, stream=True, headers=HEADERS, timeout=30)
    response.raise_for_status()
    
    total_size = int(response.headers.get("content-length", 0))
    chunk_size = 1024 * 16  # 16 KB chunks
    
    with open(dest_path, "wb") as f, tqdm(
        total=total_size,
        unit="iB",
        unit_scale=True,
        desc=description,
        colour="cyan"
    ) as bar:
        for data in response.iter_content(chunk_size=chunk_size):
            size = f.write(data)
            bar.update(size)
    logger.info(f"Download di {description} completato con successo.")

def bootstrap_yt_dlp() -> bool:
    """Verifica la versione locale di yt-dlp e scarica l'ultima disponibile se necessario."""
    yt_dlp_path = os.path.join(TOOLS_DIR, "yt-dlp.exe")
    
    # 1. Recupera l'ultima versione disponibile tramite GitHub API
    api_url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
    try:
        logger.info("Verifica ultima versione di yt-dlp in corso...")
        r = requests.get(api_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        latest_version = data["tag_name"]
        
        # Cerca l'eseguibile di Windows tra gli asset
        download_url = None
        for asset in data.get("assets", []):
            if asset["name"] == "yt-dlp.exe":
                download_url = asset["browser_download_url"]
                break
                
        if not download_url:
            logger.error("Non è stato possibile trovare yt-dlp.exe negli asset del rilascio di GitHub.")
            return False
            
    except Exception as e:
        logger.error(f"Errore durante il recupero dei metadati di yt-dlp da GitHub: {e}")
        # Se l'eseguibile esiste già localmente, procediamo comunque
        if os.path.exists(yt_dlp_path):
            logger.warning("Uso della versione locale esistente a causa di problemi di rete.")
            return True
        return False

    # 2. Controlla la versione locale registrata nel DB
    local_version = database.get_tool_version("yt-dlp")
    file_exists = os.path.exists(yt_dlp_path)
    
    if not file_exists or local_version != latest_version:
        if not file_exists:
            logger.info("yt-dlp.exe non trovato localmente. Avvio download...")
        else:
            logger.info(f"Nuovo aggiornamento trovato per yt-dlp: locale={local_version}, ultimo={latest_version}")
            
        try:
            download_file(download_url, yt_dlp_path, "yt-dlp.exe")
            database.update_tool_version("yt-dlp", latest_version)
            logger.info(f"yt-dlp aggiornato alla versione {latest_version}.")
            # Aggiorna la lista degli estrattori supportati
            update_extractors_list(yt_dlp_path)
        except Exception as e:
            logger.error(f"Errore durante il download o salvataggio di yt-dlp.exe: {e}")
            if file_exists:
                logger.warning("Il download è fallito, ma yt-dlp.exe locale è ancora presente. Si continua con quello.")
                return True
            return False
    else:
        logger.info(f"yt-dlp è già aggiornato all'ultima versione: {local_version}")
        
    return True

def bootstrap_ffmpeg() -> bool:
    """Verifica e scarica ffmpeg/ffprobe locali se obsoleti o mancanti."""
    ffmpeg_path = os.path.join(TOOLS_DIR, "ffmpeg.exe")
    ffprobe_path = os.path.join(TOOLS_DIR, "ffprobe.exe")
    
    # 1. Recupera l'ultima versione di ffmpeg da gyan.dev
    version_url = "https://www.gyan.dev/ffmpeg/builds/release-version"
    try:
        logger.info("Verifica ultima versione di FFmpeg in corso...")
        r = requests.get(version_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        latest_version = r.text.strip()
    except Exception as e:
        logger.error(f"Errore durante il recupero della versione di FFmpeg da gyan.dev: {e}")
        if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
            logger.warning("Uso dei binari FFmpeg locali esistenti a causa di problemi di rete.")
            return True
        return False

    # 2. Controlla la versione locale registrata nel DB e l'esistenza fisica dei file
    local_version = database.get_tool_version("ffmpeg")
    files_exist = os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path)
    
    if not files_exist or local_version != latest_version:
        if not files_exist:
            logger.info("Binari FFmpeg mancanti. Avvio download...")
        else:
            logger.info(f"Nuovo aggiornamento trovato per FFmpeg: locale={local_version}, ultimo={latest_version}")
            
        zip_temp_path = os.path.join(TOOLS_DIR, "ffmpeg_temp.zip")
        # Rilascio statico zip essentials da gyan.dev
        download_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        
        try:
            download_file(download_url, zip_temp_path, "FFmpeg (Zip)")
            
            logger.info("Estrazione dei binari ffmpeg.exe e ffprobe.exe dallo zip...")
            extracted_count = 0
            with zipfile.ZipFile(zip_temp_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    filename = os.path.basename(member)
                    if filename in ("ffmpeg.exe", "ffprobe.exe"):
                        # Leggi i dati del file ed estrai direttamente in TOOLS_DIR usando with
                        with zip_ref.open(member) as source:
                            target_path = os.path.join(TOOLS_DIR, filename)
                            with open(target_path, "wb") as target:
                                target.write(source.read())
                        extracted_count += 1
                        logger.info(f"Estratto: {filename}")
                        
            # Rimuove il file zip temporaneo
            if os.path.exists(zip_temp_path):
                os.remove(zip_temp_path)
                
            if extracted_count == 2:
                database.update_tool_version("ffmpeg", latest_version)
                logger.info(f"FFmpeg aggiornato alla versione {latest_version}.")
            else:
                logger.error("Errore: impossibile trovare sia ffmpeg.exe che ffprobe.exe nel pacchetto scaricato.")
                if not files_exist:
                    return False
        except Exception as e:
            logger.error(f"Errore durante l'installazione di FFmpeg: {e}")
            if os.path.exists(zip_temp_path):
                try:
                    os.remove(zip_temp_path)
                except Exception:
                    pass
            if files_exist:
                logger.warning("L'installazione è fallita, ma i file locali esistenti sono ancora disponibili.")
                return True
            return False
    else:
        logger.info(f"FFmpeg è già aggiornato all'ultima versione: {local_version}")
        
    return True

def update_extractors_list(yt_dlp_path: str):
    """Esegue yt-dlp --list-extractors e aggiorna la tabella degli estrattori nel DB."""
    logger.info("Generazione ed aggiornamento lista degli estrattori supportati...")
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        result = subprocess.run(
            [yt_dlp_path, "--list-extractors"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            startupinfo=startupinfo,
            timeout=20
        )
        if result.returncode == 0:
            extractors = []
            for line in result.stdout.splitlines():
                line = line.strip().lower()
                if line:
                    base_name = line.split(":")[0]
                    base_name = base_name.split(" ")[0]
                    if base_name and base_name not in extractors:
                        extractors.append(base_name)
            if extractors:
                database.save_extractors(extractors)
                logger.info(f"Salvati {len(extractors)} estrattori nel database.")
            else:
                logger.error("Nessun estrattore trovato nell'output di yt-dlp.")
        else:
            logger.error(f"Errore durante l'esecuzione di yt-dlp --list-extractors (Codice {result.returncode})")
    except Exception as e:
        logger.error(f"Eccezione durante l'aggiornamento della lista estrattori: {e}")

def run_bootstrap() -> bool:
    """Esegue il bootstrap completo di yt-dlp e ffmpeg. Ritorna True se tutto è pronto."""
    logger.info("=== Avvio Bootstrapper Strumenti Locali ===")
    yt_ok = bootstrap_yt_dlp()
    ffmpeg_ok = bootstrap_ffmpeg()
    
    if yt_ok and ffmpeg_ok:
        logger.info("=== Bootstrapper Completato: Tutti gli strumenti sono pronti! ===")
        # Se la tabella degli estrattori è vuota, popolala ora
        try:
            current_exts = database.get_extractors()
            if not current_exts:
                yt_dlp_path = os.path.join(TOOLS_DIR, "yt-dlp.exe")
                update_extractors_list(yt_dlp_path)
        except Exception as e:
            logger.error(f"Errore nel controllo/popolamento iniziale degli estrattori: {e}")
        return True
    else:
        logger.error("=== Bootstrapper Fallito: Alcune dipendenze non sono state soddisfatte. ===")
        return False

if __name__ == "__main__":
    run_bootstrap()
