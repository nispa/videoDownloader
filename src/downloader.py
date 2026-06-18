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

logs_dir = os.path.join(database.BASE_DIR, "logs")
os.makedirs(logs_dir, exist_ok=True)
download_log_file = os.path.join(logs_dir, "download.log")

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# File handler
file_handler = logging.FileHandler(download_log_file, encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

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

        # Load the download path from the DB or fall back to the default
        self.default_download_dir = database.get_setting("download_path")
        if not self.default_download_dir:
            self.default_download_dir = os.path.join(base_dir, "downloads")

        os.makedirs(self.default_download_dir, exist_ok=True)

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

        # 1. URLs ending with a common video/audio extension are supported (via the generic extractor)
        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in [".mp4", ".m4a", ".mp3", ".webm", ".mkv", ".flv", ".avi", ".wav", ".ogg"]):
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
        """Return the currently configured download directory."""
        path = database.get_setting("download_path")
        return path if path else self.default_download_dir

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

    def get_info(self, url: str) -> dict | None:
        """
        Extract the main video/audio metadata without starting the download.
        Returns a dictionary with the details, or None on error.
        """
        logger.info(f"Extracting metadata for URL: {url}")

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
            return None

    @staticmethod
    def _find_srt_paths(stdout: str) -> list[str]:
        """
        Extract the subtitle file paths from yt-dlp's output (lines like
        "Writing video subtitles to: PATH" or "Destination: PATH"), then resolve
        each to its final .srt sibling on disk. Returns existing .srt paths only.
        """
        found: list[str] = []
        path_re = re.compile(r"(?:subtitles to:|Destination:)\s*(.+\.(?:srt|vtt|srv\d|ttml|json3))\s*$")
        for line in stdout.splitlines():
            m = path_re.search(line.strip())
            if not m:
                continue
            candidate = m.group(1).strip().strip('"')
            srt = os.path.splitext(candidate)[0] + ".srt"
            if os.path.isfile(srt) and srt not in found:
                found.append(srt)
        return found

    @staticmethod
    def _srt_to_txt(srt_path: str) -> str | None:
        """
        Convert an .srt file into a clean .txt: drop the sequence numbers, the
        "00:00:00,000 --> ..." timestamp lines and inline tags, then collapse the
        consecutive duplicate lines that auto-generated captions produce.
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
            "--convert-subs", "srt",
            "--no-playlist",
            "--windows-filenames",
            # Mitigate YouTube rate-limiting (HTTP 429): pause between requests and retry.
            "--sleep-requests", "1",
            "--retries", "10",
            "--retry-sleep", "5",
            "-o", output_template,
        ]
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
        download_dir = self.get_download_path()
        os.makedirs(download_dir, exist_ok=True)

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

        if mode == "audio":
            cmd.extend([
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0"  # Best quality
            ])
        else:
            # Video: download the best quality combining video and audio, merging into mp4
            cmd.extend([
                "-f", "bv*+ba/b",
                "--merge-output-format", "mp4"
            ])

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

            while True:
                line = process.stdout.readline()
                if not line:
                    break

                line = line.strip()
                # logger.debug(f"yt-dlp: {line}") # Avoid flooding the main log

                # Log errors emitted by yt-dlp to make failures diagnosable
                if line.startswith("ERROR") or line.startswith("WARNING"):
                    logger.error(f"yt-dlp: {line}")

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
                if progress_callback:
                    progress_callback(0.0, "---", "--:--", f"Errore (Codice {process.returncode})")
                return False

        except Exception as e:
            logger.error(f"Exception during download: {e}")
            if progress_callback:
                progress_callback(0.0, "---", "--:--", "Errore Eccezione")
            return False
