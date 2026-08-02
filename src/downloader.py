import os
import subprocess
import json
import re
import logging
import database

# Dedicated logger for downloads, writing to logs/download.log
logger = logging.getLogger("downloader")
logger.setLevel(logging.INFO)
logger.propagate = False  # Keep these logs out of app.log

logs_dir = database.LOGS_DIR
DOWNLOAD_LOG_FILE = os.path.join(logs_dir, "download.log")

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# File handler. The logs directory may be unavailable on a locked-down machine:
# losing the log file must not prevent downloading.
try:
    os.makedirs(logs_dir, exist_ok=True)
    file_handler = logging.FileHandler(DOWNLOAD_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
except OSError:
    pass

# Console handler (useful for CLI mode)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class VideoDownloader:
    def __init__(self):
        # Absolute paths of the local binaries, based on the centralized BASE_DIR
        base_dir = database.BASE_DIR
        self.tools_dir = os.path.join(base_dir, "tools")
        self.yt_dlp_path = os.path.join(self.tools_dir, "yt-dlp.exe")
        self.ffmpeg_path = os.path.join(self.tools_dir, "ffmpeg.exe")

        # Last human-readable failure, so the GUI can show the actual cause
        # instead of a generic "check the log".
        self.last_error: str | None = None

        # Fallback always living next to the app (same drive as the executable,
        # so it survives removable/unmounted drives -> portability).
        self.fallback_download_dir = os.path.join(base_dir, "downloads")

        # Load the download path from the DB or fall back to the default
        configured = database.get_setting("download_path") or self.fallback_download_dir
        self.default_download_dir = self._ensure_usable_dir(configured)

    @property
    def ffmpeg_available(self) -> bool:
        """
        True when ffmpeg is installed. Without it yt-dlp cannot merge separate
        video and audio streams nor convert to mp3, so the app runs in a reduced
        mode instead of failing.
        """
        return os.path.isfile(self.ffmpeg_path)

    def _check_yt_dlp(self) -> str | None:
        """Return an explanatory message when yt-dlp cannot be used, else None."""
        if not os.path.isfile(self.yt_dlp_path):
            return (
                f"yt-dlp.exe non è presente in '{self.tools_dir}'. "
                f"L'inizializzazione degli strumenti non è andata a buon fine: "
                f"riavvia l'applicazione o controlla il log."
            )
        return None

    @staticmethod
    def _explain_yt_dlp_error(output: str) -> str | None:
        """
        Translate a known yt-dlp failure into an actionable message. These cases
        are frequent when the app is moved to a different machine or user profile.
        """
        if not output:
            return None
        if "DPAPI" in output or ("cookie" in output.lower() and "could not copy" in output.lower()):
            return (
                "Non è stato possibile leggere i cookie dal browser: sono cifrati e legati "
                "all'utente Windows di origine, quindi non sono trasferibili su un altro PC "
                "o profilo. Imposta 'Nessuno' come browser per i cookie, oppure esporta un "
                "file cookies.txt e selezionalo nelle impostazioni."
            )
        if "HTTP Error 429" in output:
            return (
                "Il sito ha risposto 'Too Many Requests' (429): troppe richieste dallo stesso "
                "indirizzo IP. Attendi qualche minuto e riprova."
            )
        if "ffmpeg" in output.lower() and ("not found" in output.lower() or "not installed" in output.lower()):
            return (
                "FFmpeg non è disponibile: non è possibile unire video e audio né convertire "
                "in mp3. Riavvia l'applicazione per riprovare a installarlo."
            )
        if "Sign in to confirm" in output or "age" in output.lower() and "restricted" in output.lower():
            return (
                "Il sito richiede l'autenticazione per questo contenuto. Configura i cookie "
                "del browser oppure un file cookies.txt nelle impostazioni."
            )
        # Surface the raw yt-dlp error line: more useful than "check the log".
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("ERROR:"):
                return line
        return None

    def _ensure_usable_dir(self, path: str) -> str:
        """
        Make sure `path` exists, creating it if needed. If that fails (e.g. the
        drive is unmounted/removed), log a warning and fall back to the app-local
        downloads folder instead of crashing. Returns a usable path.
        """
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except OSError as e:
            logger.warning(
                f"Download folder '{path}' is not available ({e}). "
                f"Falling back to '{self.fallback_download_dir}'."
            )
            try:
                os.makedirs(self.fallback_download_dir, exist_ok=True)
            except OSError as e2:
                logger.error(f"Could not create the fallback download folder: {e2}")
            return self.fallback_download_dir

    def is_url_supported(self, url: str) -> bool:
        """
        Check whether the URL belongs to a domain supported by yt-dlp.
        Returns True if supported (or if it looks like a direct media file link), False otherwise.
        """
        from urllib.parse import urlparse

        # Clean up the URL
        url = url.strip()
        if not url:
            return False

        # 1. URLs ending with a common media extension are supported (via the generic
        #    extractor). .m3u8 (HLS) and .mpd (DASH) matter for platforms that build the
        #    page in JavaScript: the manifest URL copied from the browser's network panel
        #    is often the only thing yt-dlp can be pointed at.
        path = urlparse(url).path.lower()
        direct_media = (".mp4", ".m4a", ".mp3", ".webm", ".mkv", ".flv", ".avi",
                        ".wav", ".ogg", ".m3u8", ".mpd", ".ts", ".mov", ".aac", ".opus")
        if path.endswith(direct_media):
            return True

        # 2. Extract the base domain
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if ":" in netloc:
                netloc = netloc.split(":")[0]

            parts = netloc.split(".")
            if len(parts) >= 2:
                # Handle compound domains such as amazon.co.uk
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

        # Map common aliases (e.g. youtu.be -> youtube, x.com -> twitter, etc.)
        aliases = {
            "youtu": "youtube",
            "x": "twitter",
            "fb": "facebook",
            "instagr": "instagram"
        }
        domain = aliases.get(domain, domain)

        # Fetch the extractor list from the DB
        try:
            extractors = database.get_extractors()
            if not extractors:
                # If the DB is empty for some reason (e.g. first run before bootstrap),
                # return True to avoid preemptively blocking the user
                return True

            # Check whether the domain matches one of the extractors (e.g. "youtube", "tiktok", ...)
            for ext in extractors:
                if domain in ext or ext in domain:
                    return True
        except Exception:
            # Fallback in case of DB errors
            return True

        return False

    def get_download_path(self) -> str:
        """
        Return a usable download directory: the configured one if reachable,
        otherwise the app-local fallback. Never raises on a missing drive.
        """
        path = database.get_setting("download_path") or self.default_download_dir
        return self._ensure_usable_dir(path)

    def _get_cookie_args(self) -> list[str]:
        """
        Return the yt-dlp arguments for cookie-based authentication.
        A configured and existing cookies.txt file takes priority over the browser.
        """
        cookie_file = database.get_setting("cookie_file")
        if cookie_file and os.path.isfile(cookie_file):
            return ["--cookies", cookie_file]
        cookie_browser = database.get_setting("cookie_browser", "none")
        if cookie_browser and cookie_browser.lower() != "none":
            return ["--cookies-from-browser", cookie_browser.lower()]
        return []

    @staticmethod
    def _explain_cookie_error(browser: str, output: str) -> str:
        """Translate a failed cookie export into something the user can act on."""
        low = (output or "").lower()
        name = browser.capitalize()

        if "could not copy" in low and "cookie database" in low:
            return (
                f"Il database dei cookie di {name} è bloccato perché il browser è in "
                f"esecuzione. Chiudi completamente {name} (controlla anche l'area di "
                f"notifica accanto all'orologio) e riprova."
            )
        if "could not find" in low and "cookies database" in low:
            return (
                f"Non è stato trovato alcun profilo di {name} su questo computer: "
                f"il browser non è installato oppure usa un profilo diverso da quello predefinito."
            )
        if "dpapi" in low:
            return (
                f"Impossibile decifrare i cookie di {name}: sono protetti da DPAPI e "
                f"leggibili solo dall'utente Windows che li ha creati. Esegui "
                f"l'esportazione con lo stesso account Windows con cui usi il browser."
            )
        if "unsupported browser" in low:
            return f"{name} non è supportato da yt-dlp per la lettura dei cookie."
        if "permission" in low or "access is denied" in low:
            return (
                f"Permesso negato durante la lettura del profilo di {name}. "
                f"Chiudi il browser e verifica di avere accesso alla cartella del profilo."
            )

        for line in (output or "").splitlines():
            line = line.strip()
            if line.startswith("ERROR:"):
                return line
        return f"Esportazione dei cookie da {name} non riuscita, causa sconosciuta."

    @staticmethod
    def _count_cookies(path: str) -> int:
        """Count the actual cookie records in a Netscape cookies.txt file."""
        count = 0
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    # "#HttpOnly_<domain>" lines are records, not comments.
                    if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
                        continue
                    count += 1
        except OSError as e:
            logger.warning(f"Could not count the exported cookies: {e}")
        return count

    def export_browser_cookies(self, browser: str, dest_path: str) -> tuple[bool, str]:
        """
        Export the cookies of `browser` into `dest_path` in Netscape format.

        This is what makes an authenticated setup portable: browser cookies are
        encrypted per Windows user (DPAPI), so they cannot be read on another PC
        or profile, while a cookies.txt file can.

        yt-dlp is invoked without any URL: it still writes the cookie jar and
        performs no network request, but it exits with code 2 ("You must provide
        at least one URL"). Success is therefore decided by the produced file,
        never by the exit code.

        Returns (ok, message).
        """
        missing = self._check_yt_dlp()
        if missing:
            return False, missing

        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        except OSError as e:
            return False, f"Impossibile creare la cartella di destinazione: {e}"

        part_path = dest_path + ".part"
        cmd = [
            self.yt_dlp_path,
            "--cookies-from-browser", browser.lower(),
            "--cookies", part_path,
            "--skip-download",
            "--ignore-errors",
            "--no-warnings",
        ]
        logger.info(f"Exporting cookies from {browser} to {dest_path}")

        try:
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
                timeout=120
            )
        except Exception as e:
            logger.error(f"Exception while exporting cookies: {e}")
            return False, f"Impossibile eseguire yt-dlp: {e}"

        if not (os.path.isfile(part_path) and os.path.getsize(part_path) > 0):
            message = self._explain_cookie_error(browser, f"{process.stderr}\n{process.stdout}")
            logger.error(f"Cookie export failed: {message}")
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except OSError:
                    pass
            return False, message

        count = self._count_cookies(part_path)
        try:
            os.replace(part_path, dest_path)
        except OSError as e:
            logger.error(f"Could not write the cookie file: {e}")
            return False, f"Impossibile salvare '{dest_path}': {e}"

        logger.info(f"Exported {count} cookies from {browser}.")
        return True, str(count)

    def get_info(self, url: str) -> dict | None:
        """
        Extract the main video/audio metadata without starting the download.
        Returns a dictionary with the details, or None on error.
        """
        logger.info(f"Extracting metadata for URL: {url}")

        missing = self._check_yt_dlp()
        if missing:
            self.last_error = missing
            logger.error(missing)
            return None

        # Run yt-dlp with -J (dump JSON); --no-playlist avoids loading full playlist details
        cmd = [
            self.yt_dlp_path,
            "-J",
            "--no-playlist",
            "--no-warnings",
        ]
        cmd.extend(self._get_cookie_args())
        cmd.append(url)

        try:
            # Hide the console window on Windows to avoid popup flashes
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
                logger.error(f"Error while extracting info (code {process.returncode}): {process.stderr}")
                self.last_error = self._explain_yt_dlp_error(process.stderr)
                return None

            data = json.loads(process.stdout)

            # Format the duration as MM:SS or HH:MM:SS
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
            logger.error(f"Exception while extracting info: {e}")
            self.last_error = f"Impossibile eseguire yt-dlp: {e}"
            return None

    @staticmethod
    def _find_srt_paths(stdout: str) -> list[str]:
        """
        Extract the subtitle file paths from yt-dlp's output (lines like
        "Writing video subtitles to: PATH" or "Destination: PATH"), then resolve
        each to its final .srt sibling on disk. Falls back to the file yt-dlp
        actually wrote when the .srt conversion did not happen (no ffmpeg).
        """
        found: list[str] = []
        path_re = re.compile(r"(?:subtitles to:|Destination:)\s*(.+\.(?:srt|vtt|srv\d|ttml|json3))\s*$")
        for line in stdout.splitlines():
            m = path_re.search(line.strip())
            if not m:
                continue
            candidate = m.group(1).strip().strip('"')
            srt = os.path.splitext(candidate)[0] + ".srt"
            for path in (srt, candidate):
                if os.path.isfile(path) and path not in found:
                    found.append(path)
                    break
        return found

    @staticmethod
    def _srt_to_txt(srt_path: str) -> str | None:
        """
        Convert an .srt (or .vtt, when ffmpeg was unavailable) file into a clean
        .txt: drop the sequence numbers, the "00:00:00,000 --> ..." timestamp
        lines, the WebVTT header and inline tags, then collapse the consecutive
        duplicate lines that auto-generated captions produce.
        Returns the path of the written .txt, or None on error.
        """
        try:
            with open(srt_path, "r", encoding="utf-8", errors="replace") as f:
                raw_lines = f.read().splitlines()

            cleaned: list[str] = []
            for line in raw_lines:
                line = line.strip()
                if not line:
                    continue
                if "-->" in line:  # timestamp line
                    continue
                if line.isdigit():  # subtitle index
                    continue
                # WebVTT preamble, present when the captions were not converted
                if line.startswith("WEBVTT") or re.match(r"^(Kind|Language):", line):
                    continue
                # Strip inline tags like <c>, <00:00:00.000>, <i> ...
                line = re.sub(r"<[^>]+>", "", line).strip()
                if not line:
                    continue
                # Skip if identical to the previous kept line (rolling auto-subs)
                if cleaned and cleaned[-1] == line:
                    continue
                cleaned.append(line)

            txt_path = os.path.splitext(srt_path)[0] + ".txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(cleaned))
            logger.info(f"Wrote clean transcript: {txt_path}")
            return txt_path
        except Exception as e:
            logger.warning(f"Could not convert subtitles to txt ({srt_path}): {e}")
            return None

    def _download_subtitles(self, url: str, output_template: str, sub_langs: str,
                            subs_as_txt: bool = False) -> bool:
        """
        Download subtitles (manual + auto-generated) as .srt in a standalone yt-dlp
        run with --skip-download. Run AFTER the media download so a YouTube 429
        rate-limit on captions never fails the actual video/audio download.
        If subs_as_txt is True, also write a clean .txt next to each .srt.
        Returns True on success, False on any error (logged as a warning).
        """
        cmd = [
            self.yt_dlp_path,
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", sub_langs,
            "--no-playlist",
            "--windows-filenames",
            # Mitigate YouTube rate-limiting (HTTP 429): pause between requests and retry.
            "--sleep-requests", "1",
            "--retries", "10",
            "--retry-sleep", "5",
            "-o", output_template,
        ]

        # Converting the captions to .srt is an ffmpeg post-processing step: asking
        # for it without ffmpeg fails the whole run, so keep the native format.
        if self.ffmpeg_available:
            cmd.extend(["--ffmpeg-location", self.tools_dir, "--convert-subs", "srt"])
        else:
            logger.warning("FFmpeg non disponibile: i sottotitoli restano nel formato originale (.vtt).")

        cmd.extend(self._get_cookie_args())
        cmd.append(url)
        logger.info(f"Fetching subtitles ({sub_langs}): {' '.join(cmd)}")

        try:
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
                timeout=120
            )

            if process.returncode == 0:
                logger.info("Subtitles downloaded successfully.")
                if subs_as_txt:
                    for srt in self._find_srt_paths(process.stdout):
                        self._srt_to_txt(srt)
                return True

            logger.warning(f"Could not download subtitles (code {process.returncode}): {process.stderr.strip()}")
            return False
        except Exception as e:
            logger.warning(f"Exception while downloading subtitles: {e}")
            return False

    def download(self, url: str, mode: str = "video", progress_callback=None,
                 download_subs: bool = False, sub_langs: str = "it",
                 subs_as_txt: bool = False) -> bool:
        """
        Download the video or audio from a URL.
        - mode: "video" (best quality video + audio merged into mp4) or "audio" (extract mp3).
        - progress_callback: called on every progress update with signature:
                             callback(percentage: float, speed: str, eta: str, status: str)
        - download_subs: if True, also download subtitles (manual + auto-generated),
                         converted to .srt, alongside the media file.
        - sub_langs: comma-separated subtitle languages to fetch (e.g. "it,en").
        - subs_as_txt: if True, also write a clean .txt (no timestamps) next to each .srt.
        """
        self.last_error = None

        missing = self._check_yt_dlp()
        if missing:
            self.last_error = missing
            logger.error(missing)
            if progress_callback:
                progress_callback(0.0, "---", "--:--", "Errore")
            return False

        download_dir = self.get_download_path()

        # Output filename template. The title is truncated to 100 characters because
        # some sites (e.g. Facebook) use the whole post description as the title,
        # exceeding the 260-character Windows path limit.
        output_template = os.path.join(download_dir, "%(title).100s.%(ext)s")

        # Base arguments
        cmd = [
            self.yt_dlp_path,
            "--ffmpeg-location", self.tools_dir,
            "--newline",
            "--no-playlist",
            "--windows-filenames",
            "-o", output_template
        ]

        cmd.extend(self._get_cookie_args())

        has_ffmpeg = self.ffmpeg_available

        if mode == "audio":
            if not has_ffmpeg:
                # Extraction to mp3 is done by ffmpeg: there is no way around it.
                self.last_error = (
                    "FFmpeg non è installato, quindi la conversione in mp3 non è possibile. "
                    "Riavvia l'applicazione per riprovare l'installazione degli strumenti, "
                    "oppure scarica il video e converti l'audio in un secondo momento."
                )
                logger.error(self.last_error)
                if progress_callback:
                    progress_callback(0.0, "---", "--:--", "Errore")
                return False
            cmd.extend([
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0"  # Best quality
            ])
        elif has_ffmpeg:
            # Video: download the best quality combining video and audio, merging into mp4
            cmd.extend([
                "-f", "bv*+ba/b",
                "--merge-output-format", "mp4"
            ])
        else:
            # Reduced mode: without ffmpeg the separate video and audio streams
            # cannot be merged, so ask for a stream that already contains both.
            # Quality is capped by what the site offers pre-muxed (usually 720p).
            logger.warning(
                "FFmpeg non disponibile: scarico un flusso video+audio gia' combinato "
                "(qualita' massima limitata)."
            )
            cmd.extend(["-f", "b"])

        cmd.append(url)
        logger.info(f"Starting download command: {' '.join(cmd)}")

        # Regex to parse the progress lines emitted by yt-dlp.
        # Example: [download]  12.3% of ~10.45MiB at  1.23MiB/s ETA 00:07
        progress_re = re.compile(
            r"\[download\]\s+(\d+\.\d+)%\s+of\s+([^\s]+)\s+at\s+([^\s]+)\s+ETA\s+([^\s]+)"
        )

        # Regex for the post-processing phase (e.g. ffmpeg conversion or merge)
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
            error_lines: list[str] = []

            while True:
                line = process.stdout.readline()
                if not line:
                    break

                line = line.strip()
                # logger.debug(f"yt-dlp: {line}") # Avoid flooding the main log

                # Log errors emitted by yt-dlp to make failures diagnosable, and
                # keep them so the real cause can be shown in the UI.
                if line.startswith("ERROR") or line.startswith("WARNING"):
                    logger.error(f"yt-dlp: {line}")
                    if line.startswith("ERROR"):
                        error_lines.append(line)

                # Parse download progress
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

                # Parse post-processing (FFmpeg)
                elif ffmpeg_re.search(line):
                    status = "Post-Processing (FFmpeg)..."
                    if status != last_status:
                        last_status = status
                        if progress_callback:
                            progress_callback(100.0, "---", "00:00", status)

            process.wait()

            if process.returncode == 0:
                logger.info("Download completed successfully!")

                # Subtitles are fetched in a separate, non-fatal step: a YouTube 429
                # (rate-limit) on captions must not mark the whole download as failed.
                if download_subs:
                    if progress_callback:
                        progress_callback(100.0, "---", "00:00", "Sottotitoli...")
                    subs_ok = self._download_subtitles(url, output_template, sub_langs, subs_as_txt)
                    final_status = "Completato" if subs_ok else "Completato (sottotitoli non riusciti)"
                else:
                    final_status = "Completato"

                if progress_callback:
                    progress_callback(100.0, "0.0B/s", "00:00", final_status)
                return True
            else:
                logger.error(f"Error during download. Exit code: {process.returncode}")
                self.last_error = self._explain_yt_dlp_error("\n".join(error_lines))
                if progress_callback:
                    progress_callback(0.0, "---", "--:--", f"Errore (Codice {process.returncode})")
                return False

        except Exception as e:
            logger.error(f"Exception during download: {e}")
            self.last_error = f"Impossibile eseguire yt-dlp: {e}"
            if progress_callback:
                progress_callback(0.0, "---", "--:--", "Errore Eccezione")
            return False
