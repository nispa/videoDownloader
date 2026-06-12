import os
import zipfile
import logging
import requests
import subprocess
from tqdm import tqdm
import database

# Main directories, based on BASE_DIR imported from database
BASE_DIR = database.BASE_DIR
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(TOOLS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Logging to file and console
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

# Standard headers for HTTP requests
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def download_file(url: str, dest_path: str, description: str):
    """Download a file from a URL showing a tqdm progress bar."""
    logger.info(f"Starting download of {description} from: {url}")
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
    logger.info(f"Download of {description} completed successfully.")

def bootstrap_yt_dlp() -> bool:
    """Check the local yt-dlp version and download the latest one if needed."""
    yt_dlp_path = os.path.join(TOOLS_DIR, "yt-dlp.exe")

    # 1. Fetch the latest available version via the GitHub API
    api_url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
    try:
        logger.info("Checking for the latest yt-dlp version...")
        r = requests.get(api_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        latest_version = data["tag_name"]

        # Look for the Windows executable among the release assets
        download_url = None
        for asset in data.get("assets", []):
            if asset["name"] == "yt-dlp.exe":
                download_url = asset["browser_download_url"]
                break

        if not download_url:
            logger.error("Could not find yt-dlp.exe among the GitHub release assets.")
            return False

    except Exception as e:
        logger.error(f"Error while fetching yt-dlp metadata from GitHub: {e}")
        # If the executable already exists locally, keep going anyway
        if os.path.exists(yt_dlp_path):
            logger.warning("Using the existing local version due to network problems.")
            return True
        return False

    # 2. Check the local version recorded in the DB
    local_version = database.get_tool_version("yt-dlp")
    file_exists = os.path.exists(yt_dlp_path)

    if not file_exists or local_version != latest_version:
        if not file_exists:
            logger.info("yt-dlp.exe not found locally. Starting download...")
        else:
            logger.info(f"New update found for yt-dlp: local={local_version}, latest={latest_version}")

        try:
            download_file(download_url, yt_dlp_path, "yt-dlp.exe")
            database.update_tool_version("yt-dlp", latest_version)
            logger.info(f"yt-dlp updated to version {latest_version}.")
            # Refresh the list of supported extractors
            update_extractors_list(yt_dlp_path)
        except Exception as e:
            logger.error(f"Error while downloading or saving yt-dlp.exe: {e}")
            if file_exists:
                logger.warning("The download failed, but the local yt-dlp.exe is still present. Continuing with it.")
                return True
            return False
    else:
        logger.info(f"yt-dlp is already up to date: {local_version}")

    return True

def bootstrap_ffmpeg() -> bool:
    """Check and download the local ffmpeg/ffprobe binaries if outdated or missing."""
    ffmpeg_path = os.path.join(TOOLS_DIR, "ffmpeg.exe")
    ffprobe_path = os.path.join(TOOLS_DIR, "ffprobe.exe")

    # 1. Fetch the latest ffmpeg version from gyan.dev
    version_url = "https://www.gyan.dev/ffmpeg/builds/release-version"
    try:
        logger.info("Checking for the latest FFmpeg version...")
        r = requests.get(version_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        latest_version = r.text.strip()
    except Exception as e:
        logger.error(f"Error while fetching the FFmpeg version from gyan.dev: {e}")
        if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
            logger.warning("Using the existing local FFmpeg binaries due to network problems.")
            return True
        return False

    # 2. Check the local version recorded in the DB and that the files actually exist
    local_version = database.get_tool_version("ffmpeg")
    files_exist = os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path)

    if not files_exist or local_version != latest_version:
        if not files_exist:
            logger.info("FFmpeg binaries missing. Starting download...")
        else:
            logger.info(f"New update found for FFmpeg: local={local_version}, latest={latest_version}")

        zip_temp_path = os.path.join(TOOLS_DIR, "ffmpeg_temp.zip")
        # Static essentials zip release from gyan.dev
        download_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

        try:
            download_file(download_url, zip_temp_path, "FFmpeg (Zip)")

            logger.info("Extracting ffmpeg.exe and ffprobe.exe from the zip...")
            extracted_count = 0
            with zipfile.ZipFile(zip_temp_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    filename = os.path.basename(member)
                    if filename in ("ffmpeg.exe", "ffprobe.exe"):
                        # Read the file data and extract it directly into TOOLS_DIR
                        with zip_ref.open(member) as source:
                            target_path = os.path.join(TOOLS_DIR, filename)
                            with open(target_path, "wb") as target:
                                target.write(source.read())
                        extracted_count += 1
                        logger.info(f"Extracted: {filename}")

            # Remove the temporary zip file
            if os.path.exists(zip_temp_path):
                os.remove(zip_temp_path)

            if extracted_count == 2:
                database.update_tool_version("ffmpeg", latest_version)
                logger.info(f"FFmpeg updated to version {latest_version}.")
            else:
                logger.error("Error: could not find both ffmpeg.exe and ffprobe.exe in the downloaded package.")
                if not files_exist:
                    return False
        except Exception as e:
            logger.error(f"Error while installing FFmpeg: {e}")
            if os.path.exists(zip_temp_path):
                try:
                    os.remove(zip_temp_path)
                except Exception:
                    pass
            if files_exist:
                logger.warning("The installation failed, but the existing local files are still available.")
                return True
            return False
    else:
        logger.info(f"FFmpeg is already up to date: {local_version}")

    return True

def update_extractors_list(yt_dlp_path: str):
    """Run yt-dlp --list-extractors and refresh the extractors table in the DB."""
    logger.info("Generating and updating the list of supported extractors...")
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
                logger.info(f"Saved {len(extractors)} extractors to the database.")
            else:
                logger.error("No extractors found in the yt-dlp output.")
        else:
            logger.error(f"Error while running yt-dlp --list-extractors (code {result.returncode})")
    except Exception as e:
        logger.error(f"Exception while updating the extractors list: {e}")

def run_bootstrap() -> bool:
    """Run the full bootstrap of yt-dlp and ffmpeg. Returns True if everything is ready."""
    logger.info("=== Starting Local Tools Bootstrapper ===")
    yt_ok = bootstrap_yt_dlp()
    ffmpeg_ok = bootstrap_ffmpeg()

    if yt_ok and ffmpeg_ok:
        logger.info("=== Bootstrapper Completed: All tools are ready! ===")
        # If the extractors table is empty, populate it now
        try:
            current_exts = database.get_extractors()
            if not current_exts:
                yt_dlp_path = os.path.join(TOOLS_DIR, "yt-dlp.exe")
                update_extractors_list(yt_dlp_path)
        except Exception as e:
            logger.error(f"Error during the initial extractors check/population: {e}")
        return True
    else:
        logger.error("=== Bootstrapper Failed: Some dependencies could not be satisfied. ===")
        return False

if __name__ == "__main__":
    run_bootstrap()
