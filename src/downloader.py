import os
import subprocess
import json
import re
import logging
import database

# Configura il logger specifico per i download, scrivendo in logs/download.log
logger = logging.getLogger("downloader")
logger.setLevel(logging.INFO)
logger.propagate = False  # Evita che i log vadano anche in app.log

logs_dir = os.path.join(database.BASE_DIR, "logs")
os.makedirs(logs_dir, exist_ok=True)
download_log_file = os.path.join(logs_dir, "download.log")

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# Handler per file
file_handler = logging.FileHandler(download_log_file, encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Handler per console (utile per la modalità CLI)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class VideoDownloader:
    def __init__(self):
        # Percorsi assoluti dei binari locali usando BASE_DIR centralizzato
        base_dir = database.BASE_DIR
        self.tools_dir = os.path.join(base_dir, "tools")
        self.yt_dlp_path = os.path.join(self.tools_dir, "yt-dlp.exe")
        
        # Carica il percorso di download dal DB o usa il default
        self.default_download_dir = database.get_setting("download_path")
        if not self.default_download_dir:
            self.default_download_dir = os.path.join(base_dir, "downloads")
        
        os.makedirs(self.default_download_dir, exist_ok=True)

    def is_url_supported(self, url: str) -> bool:
        """
        Verifica se l'URL appartiene a un dominio supportato da yt-dlp.
        Ritorna True se supportato (o se sembra un link diretto a file multimediale), False altrimenti.
        """
        from urllib.parse import urlparse
        
        # Pulisce l'URL
        url = url.strip()
        if not url:
            return False
            
        # 1. Se l'URL finisce con un'estensione video/audio comune, è supportato (tramite l'estrattore generico)
        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in [".mp4", ".m4a", ".mp3", ".webm", ".mkv", ".flv", ".avi", ".wav", ".ogg"]):
            return True
            
        # 2. Ottiene il dominio di base
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if ":" in netloc:
                netloc = netloc.split(":")[0]
            
            parts = netloc.split(".")
            if len(parts) >= 2:
                # Gestisce domini complessi come amazon.co.uk o simili
                if parts[-2] in ("com", "co", "net", "org", "gov", "edu") and len(parts) >= 3:
                    domain = parts[-3]
                else:
                    domain = parts[-2]
            elif len(parts) == 1:
                domain = parts[0]
            else:
                return False
        except Exception:
            return False
            
        if not domain:
            return False
            
        # Mappa alias comuni (es. youtu.be -> youtube, x.com -> twitter, ecc.)
        aliases = {
            "youtu": "youtube",
            "x": "twitter",
            "fb": "facebook",
            "instagr": "instagram"
        }
        domain = aliases.get(domain, domain)
        
        # Recupera la lista degli estrattori dal DB
        try:
            extractors = database.get_extractors()
            if not extractors:
                # Se il DB è vuoto per qualche motivo (es. primo avvio prima del bootstrap),
                # ritorna True per non bloccare preventivamente l'utente
                return True
                
            # Verifica se il dominio fa parte degli estrattori (es. "youtube", "tiktok", ecc.)
            for ext in extractors:
                if domain in ext or ext in domain:
                    return True
        except Exception:
            # Fallback in caso di errori nel DB
            return True
            
        return False

    def get_download_path(self) -> str:
        """Ritorna la cartella di download configurata correntemente."""
        path = database.get_setting("download_path")
        return path if path else self.default_download_dir

    def get_info(self, url: str) -> dict | None:
        """
        Estrae i metadati principali del video/audio senza avviarne il download.
        Ritorna un dizionario con i dettagli o None in caso di errore.
        """
        logger.info(f"Estrazione metadati per URL: {url}")
        
        # Esegue yt-dlp con l'opzione -J (dump JSON) e flat-playlist per evitare di caricare troppi dettagli in caso di playlist
        cmd = [
            self.yt_dlp_path,
            "-J",
            "--no-playlist",
            "--no-warnings",
            url
        ]
        
        try:
            # Nasconde la finestra su Windows per evitare popup spiacevoli
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                timeout=30
            )
            
            if process.returncode != 0:
                logger.error(f"Errore durante l'estrazione delle info (Codice {process.returncode}): {process.stderr}")
                return None
                
            data = json.loads(process.stdout)
            
            # Formatta la durata in formato leggibile MM:SS o HH:MM:SS
            duration_secs = data.get("duration")
            duration_str = "Sconosciuta"
            if duration_secs:
                hours, remainder = divmod(int(duration_secs), 3600)
                minutes, seconds = divmod(remainder, 60)
                if hours > 0:
                    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    duration_str = f"{minutes:02d}:{seconds:02d}"
            
            return {
                "title": data.get("title", "Titolo Sconosciuto"),
                "duration": duration_str,
                "uploader": data.get("uploader", "Autore Sconosciuto"),
                "thumbnail": data.get("thumbnail", ""),
                "description": data.get("description", "")[:150] + "..." if data.get("description") else "",
                "extractor": data.get("extractor_key", "Sconosciuto")
            }
            
        except Exception as e:
            logger.error(f"Eccezione durante l'estrazione delle info: {e}")
            return None

    def download(self, url: str, mode: str = "video", progress_callback=None) -> bool:
        """
        Scarica il video o l'audio da un URL.
        - mode: "video" (scarica video + audio alla miglior qualità mp4) o "audio" (estrae mp3).
        - progress_callback: funzione chiamata ad ogni aggiornamento di progresso con firma:
                             callback(percentage: float, speed: str, eta: str, status: str)
        """
        download_dir = self.get_download_path()
        os.makedirs(download_dir, exist_ok=True)
        
        # Template del nome del file
        output_template = os.path.join(download_dir, "%(title)s.%(ext)s")
        
        # Argomenti base
        cmd = [
            self.yt_dlp_path,
            "--ffmpeg-location", self.tools_dir,
            "--newline",
            "--no-playlist",
            "-o", output_template
        ]
        
        if mode == "audio":
            cmd.extend([
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0"  # Miglior qualità
            ])
        else:
            # Video: scarica la migliore qualità combinando video e audio e unendo in mp4/mkv
            cmd.extend([
                "-f", "bv*+ba/b",
                "--merge-output-format", "mp4"
            ])
            
        cmd.append(url)
        logger.info(f"Avvio comando di download: {' '.join(cmd)}")
        
        # Regex per fare il parsing del progresso emesso da yt-dlp
        # Esempio: [download]  12.3% of ~10.45MiB at  1.23MiB/s ETA 00:07
        progress_re = re.compile(
            r"\[download\]\s+(\d+\.\d+)%\s+of\s+([^\s]+)\s+at\s+([^\s]+)\s+ETA\s+([^\s]+)"
        )
        
        # Regex per la fase di post-processing (es. conversione o unione ffmpeg)
        ffmpeg_re = re.compile(r"\[(ExtractAudio|Merger|VideoConvertor)\]")

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo
            )
            
            last_status = "Inizializzazione"
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                
                line = line.strip()
                # logger.debug(f"yt-dlp: {line}") # Evitiamo di intasare il log principale
                
                # Parsing del progresso del download
                match = progress_re.search(line)
                if match:
                    percent = float(match.group(1))
                    total_size = match.group(2)
                    speed = match.group(3)
                    eta = match.group(4)
                    
                    status = f"Download ({total_size})"
                    last_status = status
                    if progress_callback:
                        progress_callback(percent, speed, eta, status)
                
                # Parsing del post-processing (FFmpeg)
                elif ffmpeg_re.search(line):
                    status = "Post-Processing (FFmpeg)..."
                    if status != last_status:
                        last_status = status
                        if progress_callback:
                            progress_callback(100.0, "---", "00:00", status)
                            
            process.wait()
            
            if process.returncode == 0:
                logger.info("Download completato con successo!")
                if progress_callback:
                    progress_callback(100.0, "0.0B/s", "00:00", "Completato")
                return True
            else:
                logger.error(f"Errore durante il download. Codice di uscita: {process.returncode}")
                if progress_callback:
                    progress_callback(0.0, "---", "--:--", f"Errore (Codice {process.returncode})")
                return False
                
        except Exception as e:
            logger.error(f"Eccezione durante il download: {e}")
            if progress_callback:
                progress_callback(0.0, "---", "--:--", "Errore Eccezione")
            return False
