"""
Provisioning of the local third-party binaries (yt-dlp, ffmpeg, ffprobe).

Design rules, all of them learned from failures that only show up on a machine
other than the developer's one:

* Never let a cosmetic detail break the download. Inside a PyInstaller
  ``--noconsole`` build ``sys.stderr`` is None, so a progress bar that writes to
  it raises AttributeError and the whole bootstrap is reported as "no internet".
* Never trust a file just because it exists. Downloads are written to a
  ``.part`` file and promoted only after the binary has been executed
  successfully, and binaries already on disk are probed at every startup.
* Never depend on a single host. Both yt-dlp and ffmpeg have a second source,
  because the GitHub API rate-limits per IP (60/h) and gyan.dev is routinely
  blocked by corporate proxies.
* Never report "check your internet connection" for a TLS interception, a proxy
  refusal, a rate limit or a permission problem. The caller gets the real cause.
"""
import os
import re
import sys
import time
import shutil
import zipfile
import logging
import subprocess
import contextlib
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

import database
import netconfig

# TLS verification must be routed through the Windows trust store before the
# first HTTPS request, otherwise a corporate root CA is not recognised.
netconfig.enable_os_trust_store()

# Main directories, based on BASE_DIR imported from database
BASE_DIR = database.BASE_DIR
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
LOGS_DIR = database.LOGS_DIR

# Recorded instead of raised: the GUI needs to be able to show this.
TOOLS_DIR_ERROR: str | None = None
try:
    os.makedirs(TOOLS_DIR, exist_ok=True)
except OSError as e:
    TOOLS_DIR_ERROR = f"Impossibile creare la cartella degli strumenti '{TOOLS_DIR}': {e}"

# Logging is configured centrally by the database module on import.
logger = logging.getLogger("bootstrapper")

# Standard headers for HTTP requests
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# --- Sources -----------------------------------------------------------------

# The API gives the exact version but is rate limited to 60 requests/hour per IP
# (shared office NAT exhausts it); the direct URL always works but tells us
# nothing about the version, so it is only a fallback.
YT_DLP_API_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
YT_DLP_DIRECT_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

FFMPEG_VERSION_URL = "https://www.gyan.dev/ffmpeg/builds/release-version"
FFMPEG_MIRRORS = [
    ("gyan.dev", "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"),
    ("BtbN/FFmpeg-Builds",
     "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"),
]

# Sanity floors used to reject a truncated download before it is promoted.
MIN_YT_DLP_BYTES = 4 * 1024 * 1024
MIN_FFMPEG_ZIP_BYTES = 10 * 1024 * 1024

CHUNK_SIZE = 1024 * 64


# --- Result type -------------------------------------------------------------

@dataclass
class BootstrapResult:
    """
    Outcome of a bootstrap run. Truthy when the application can work at all,
    i.e. when yt-dlp is available: without ffmpeg the app still downloads, it
    just cannot merge streams or convert to mp3.
    """
    yt_dlp_ok: bool = False
    ffmpeg_ok: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.yt_dlp_ok

    @property
    def complete(self) -> bool:
        return self.yt_dlp_ok and self.ffmpeg_ok

    @property
    def degraded(self) -> bool:
        return self.yt_dlp_ok and not self.ffmpeg_ok

    def __bool__(self) -> bool:
        return self.usable

    def message(self) -> str:
        """Human-readable summary of everything that went wrong."""
        return "\n\n".join(self.errors)


# --- Error reporting ---------------------------------------------------------

def describe_http_error(response, host: str) -> str:
    """Turn an HTTP failure into a sentence that names the actual problem."""
    code = response.status_code

    if code in (403, 429) and response.headers.get("X-RateLimit-Remaining") == "0":
        return (
            f"Limite di richieste dell'API di {host} raggiunto (60 richieste/ora per "
            f"indirizzo IP pubblico). Succede tipicamente su reti aziendali o condivise. "
            f"Non e' un problema di connessione: riprova piu' tardi oppure usa una rete diversa."
        )
    if code == 407:
        return f"Il proxy di rete richiede autenticazione per raggiungere {host} (HTTP 407)."
    if code in (401, 403):
        return (
            f"Accesso negato da {host} (HTTP {code}). Possibile blocco di un proxy, "
            f"di un firewall aziendale o di un filtro dei contenuti."
        )
    if code == 404:
        return f"Risorsa non trovata su {host} (HTTP 404): l'indirizzo di download non e' piu' valido."
    if code >= 500:
        return f"{host} e' temporaneamente non disponibile (HTTP {code}). Riprova piu' tardi."
    return f"Risposta HTTP {code} da {host}."


def describe_network_error(exc: Exception, url: str) -> str:
    """
    Turn an exception raised while fetching `url` into a specific diagnosis.
    Ordering matters: SSLError and ProxyError are subclasses of ConnectionError.
    """
    host = urlparse(url).netloc or url

    if isinstance(exc, requests.exceptions.SSLError):
        message = (
            f"Verifica del certificato TLS fallita verso {host}. Causa tipica: un proxy "
            f"aziendale o un antivirus che intercetta le connessioni HTTPS con un "
            f"certificato proprio. Non e' un'assenza di connessione."
        )
        if not netconfig.TRUST_STORE_ACTIVE:
            message += (
                "\n\nL'archivio certificati di Windows non e' in uso: installa il pacchetto "
                "'truststore' (eseguendo setup.bat) perche' il certificato aziendale venga "
                "riconosciuto come lo riconosce il browser."
            )
        return message
    if isinstance(exc, requests.exceptions.ProxyError):
        return f"Il proxy configurato ha rifiutato o non ha gestito la connessione verso {host}."
    if isinstance(exc, requests.exceptions.Timeout):
        return f"{host} non ha risposto entro il tempo massimo: rete molto lenta oppure filtrata."
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return describe_http_error(exc.response, host)
    if isinstance(exc, requests.exceptions.ConnectionError):
        message = (
            f"Impossibile contattare {host}: nessuna connessione, DNS non risolto "
            f"oppure traffico bloccato da un firewall."
        )
        hint = netconfig.proxy_hint()
        return f"{message}\n\n{hint}" if hint else message
    if isinstance(exc, PermissionError):
        return (
            f"Permesso negato durante la scrittura in '{TOOLS_DIR}'. La cartella e' "
            f"protetta oppure il file e' bloccato dall'antivirus."
        )
    if isinstance(exc, OSError):
        return f"Errore di sistema durante il download da {host}: {exc}"
    return f"Errore imprevisto durante il download da {host}: {type(exc).__name__}: {exc}"


def _missing_binary_hint(path: str, name: str) -> str:
    """Explain why a freshly installed binary is not runnable."""
    if not os.path.exists(path):
        return (
            f"{name} e' stato scaricato correttamente ma e' poi sparito dal disco: "
            f"quasi certamente messo in quarantena dall'antivirus ({name} e' un falso "
            f"positivo noto). Aggiungi un'esclusione per la cartella '{TOOLS_DIR}' e riprova."
        )
    return (
        f"{name} e' presente in '{TOOLS_DIR}' ma non e' eseguibile: file danneggiato "
        f"oppure bloccato dalle policy di sicurezza del sistema."
    )


# --- Download primitives -----------------------------------------------------

class _LogProgress:
    """
    Progress reporter used when there is no console to draw on (the exe is built
    with --noconsole, so sys.stderr is None). Writes one log line every 25%.
    """

    def __init__(self, total: int, description: str):
        self.total = total
        self.description = description
        self.done = 0
        self.next_mark = 25

    def update(self, size: int):
        self.done += size
        if not self.total:
            return
        percent = self.done * 100 // self.total
        if percent >= self.next_mark:
            logger.info(f"{self.description}: {percent}% ({self.done // 1024} KB)")
            self.next_mark = percent - percent % 25 + 25


@contextlib.contextmanager
def _progress(total: int, description: str):
    """Yield a progress reporter suitable for the current runtime."""
    stream = getattr(sys, "stderr", None)
    if stream is not None and hasattr(stream, "write"):
        from tqdm import tqdm
        with tqdm(total=total, unit="iB", unit_scale=True, desc=description, colour="cyan") as bar:
            yield bar
    else:
        yield _LogProgress(total, description)


def _startupinfo():
    """Hide the console window when spawning a child process on Windows."""
    if os.name != 'nt':
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info


def _promote(part_path: str, dest_path: str):
    """
    Atomically move the completed .part file over its destination. Retries a few
    times because an antivirus scan can briefly hold a lock on a new executable.
    """
    last_error = None
    for _ in range(4):
        try:
            os.replace(part_path, dest_path)
            return
        except PermissionError as e:
            last_error = e
            time.sleep(0.5)
    raise PermissionError(
        f"Impossibile sostituire '{dest_path}': il file e' in uso o bloccato "
        f"(antivirus o un'altra istanza dell'applicazione). {last_error}"
    )


def download_file(url: str, dest_path: str, description: str, min_bytes: int = 0):
    """
    Download a file to `dest_path`, writing to `<dest_path>.part` first and
    promoting it only once the transfer is verifiably complete. Raises on any
    failure; a partial transfer never overwrites a working file.
    """
    logger.info(f"Starting download of {description} from: {url}")
    part_path = dest_path + ".part"

    response = requests.get(url, stream=True, headers=HEADERS, timeout=30)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    written = 0

    try:
        with open(part_path, "wb") as f, _progress(total_size, description) as bar:
            for data in response.iter_content(chunk_size=CHUNK_SIZE):
                size = f.write(data)
                written += size
                bar.update(size)

        if total_size and written < total_size:
            raise IOError(
                f"Download interrotto: ricevuti {written} byte su {total_size} attesi."
            )
        if written < min_bytes:
            raise IOError(
                f"Il file scaricato e' troppo piccolo ({written} byte): la risposta non "
                f"e' il file atteso (possibile pagina di errore o portale captive)."
            )

        _promote(part_path, dest_path)
    finally:
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                pass

    logger.info(f"Download of {description} completed successfully ({written} bytes).")


def _discard(path: str):
    """Remove a file that proved to be unusable, ignoring failures."""
    try:
        os.remove(path)
    except OSError as e:
        logger.warning(f"Could not remove the unusable file '{path}': {e}")


# --- Binary validation -------------------------------------------------------

def _probe_binary(path: str, args: list[str]) -> str | None:
    """
    Run the binary and return the first line of its output, or None if it cannot
    be executed. This is what catches a truncated download: a half-written exe
    fails with [WinError 193] "not a valid Win32 application".
    """
    if not os.path.isfile(path):
        return None
    try:
        result = subprocess.run(
            [path, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=_startupinfo(),
            timeout=25,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"'{os.path.basename(path)}' non e' eseguibile: {e}")
        return None

    if result.returncode != 0:
        logger.warning(
            f"'{os.path.basename(path)}' ha restituito il codice {result.returncode}: "
            f"{(result.stderr or '').strip()[:200]}"
        )
        return None

    output = (result.stdout or result.stderr or "").strip().splitlines()
    return output[0].strip() if output else None


def _ffmpeg_version(version_line: str | None) -> str | None:
    """Extract "8.1.1-essentials_build-www.gyan.dev" from the ffmpeg -version banner."""
    if not version_line:
        return None
    match = re.search(r"ffmpeg version (\S+)", version_line)
    return match.group(1) if match else version_line


def _ffmpeg_is_current(local: str, latest: str) -> bool:
    """
    Compare the version reported by the binary with the one published upstream.
    They are not literally equal: gyan.dev publishes "8.1.2" while the binary
    built from it reports "8.1.2-essentials_build-www.gyan.dev". Without this
    normalization the whole 110 MB archive would be re-downloaded at every start.
    """
    return local == latest or local.startswith(f"{latest}-")


# --- yt-dlp ------------------------------------------------------------------

def _latest_yt_dlp_release() -> tuple[str | None, str | None, str | None]:
    """
    Query the GitHub API for the latest yt-dlp release.
    Returns (version, asset_url, error_description); the error is None on success.
    """
    try:
        logger.info("Checking for the latest yt-dlp version...")
        r = requests.get(YT_DLP_API_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        return None, None, f"Verifica della versione di yt-dlp non riuscita. {describe_network_error(e, YT_DLP_API_URL)}"
    except ValueError as e:
        return None, None, f"Risposta non valida dall'API di GitHub: {e}"

    version = data.get("tag_name")
    asset_url = None
    for asset in data.get("assets", []):
        if asset.get("name") == "yt-dlp.exe":
            asset_url = asset.get("browser_download_url")
            break
    return version, asset_url, None


def bootstrap_yt_dlp(errors: list[str]) -> bool:
    """Make sure a working yt-dlp.exe is available. Returns True if usable."""
    yt_dlp_path = os.path.join(TOOLS_DIR, "yt-dlp.exe")

    # 1. What do we actually have on disk? Ask the binary, not the database:
    #    a corrupted file whose version matches the DB would never be replaced.
    local_version = _probe_binary(yt_dlp_path, ["--version"])
    if local_version is None and os.path.exists(yt_dlp_path):
        logger.warning("yt-dlp.exe presente ma non eseguibile: verra' riscaricato.")
        _discard(yt_dlp_path)

    # 2. What is the latest release?
    latest_version, asset_url, lookup_error = _latest_yt_dlp_release()
    if lookup_error:
        logger.warning(lookup_error)

    # 3. Nothing to do when the local copy works and is current (or cannot be checked).
    if local_version and (latest_version is None or local_version == latest_version):
        if latest_version is None:
            logger.info(f"Aggiornamenti non verificabili: uso yt-dlp {local_version} gia' presente.")
        else:
            logger.info(f"yt-dlp is already up to date: {local_version}")
        database.update_tool_version("yt-dlp", local_version)
        return True

    if local_version:
        logger.info(f"New update found for yt-dlp: local={local_version}, latest={latest_version}")
    else:
        logger.info("yt-dlp.exe non disponibile localmente. Avvio del download...")

    # 4. Download, trying the API asset first and the version-less direct URL after.
    candidates = [u for u in (asset_url, YT_DLP_DIRECT_URL) if u]
    candidates = list(dict.fromkeys(candidates))
    last_error = lookup_error

    for url in candidates:
        try:
            download_file(url, yt_dlp_path, "yt-dlp.exe", min_bytes=MIN_YT_DLP_BYTES)
            break
        except Exception as e:
            last_error = describe_network_error(e, url)
            logger.warning(f"Download di yt-dlp da {urlparse(url).netloc} non riuscito: {last_error}")
    else:
        if local_version:
            logger.warning("Aggiornamento non riuscito: continuo con la versione locale di yt-dlp.")
            return True
        errors.append(f"Impossibile scaricare yt-dlp.exe.\n{last_error}")
        return False

    # 5. Trust the new file only after it has actually run.
    installed_version = _probe_binary(yt_dlp_path, ["--version"])
    if installed_version is None:
        errors.append(_missing_binary_hint(yt_dlp_path, "yt-dlp.exe"))
        return False

    database.update_tool_version("yt-dlp", installed_version)
    logger.info(f"yt-dlp updated to version {installed_version}.")
    update_extractors_list(yt_dlp_path)
    return True


# --- ffmpeg ------------------------------------------------------------------

def _latest_ffmpeg_version() -> tuple[str | None, str | None]:
    """Return (version, error_description) for the latest ffmpeg release."""
    try:
        logger.info("Checking for the latest FFmpeg version...")
        r = requests.get(FFMPEG_VERSION_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.text.strip(), None
    except requests.RequestException as e:
        return None, f"Verifica della versione di FFmpeg non riuscita. {describe_network_error(e, FFMPEG_VERSION_URL)}"


def _extract_ffmpeg(zip_path: str) -> list[str]:
    """
    Extract ffmpeg.exe and ffprobe.exe from `zip_path` into TOOLS_DIR, whatever
    their position inside the archive (gyan.dev and BtbN use different layouts).
    Each file is written as .part and promoted, so a locked binary cannot leave
    a half-written executable behind. Returns the names actually extracted.
    """
    wanted = ("ffmpeg.exe", "ffprobe.exe")
    extracted: list[str] = []

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        for member in zip_ref.namelist():
            filename = os.path.basename(member)
            if filename not in wanted or filename in extracted:
                continue
            target_path = os.path.join(TOOLS_DIR, filename)
            part_path = target_path + ".part"
            with zip_ref.open(member) as source, open(part_path, "wb") as target:
                shutil.copyfileobj(source, target)
            _promote(part_path, target_path)
            extracted.append(filename)
            logger.info(f"Extracted: {filename}")

    return extracted


def bootstrap_ffmpeg(errors: list[str]) -> bool:
    """Make sure working ffmpeg.exe and ffprobe.exe are available."""
    ffmpeg_path = os.path.join(TOOLS_DIR, "ffmpeg.exe")
    ffprobe_path = os.path.join(TOOLS_DIR, "ffprobe.exe")

    # 1. Probe what is on disk and drop anything that does not run.
    local_version = _ffmpeg_version(_probe_binary(ffmpeg_path, ["-version"]))
    ffprobe_ok = _probe_binary(ffprobe_path, ["-version"]) is not None
    if not (local_version and ffprobe_ok):
        for path in (ffmpeg_path, ffprobe_path):
            if os.path.exists(path):
                logger.warning(f"'{os.path.basename(path)}' non utilizzabile: verra' riscaricato.")
                _discard(path)
        local_version = None

    # 2. Latest published version.
    latest_version, lookup_error = _latest_ffmpeg_version()
    if lookup_error:
        logger.warning(lookup_error)

    if local_version and (latest_version is None or _ffmpeg_is_current(local_version, latest_version)):
        if latest_version is None:
            logger.info(f"Aggiornamenti non verificabili: uso FFmpeg {local_version} gia' presente.")
        else:
            logger.info(f"FFmpeg is already up to date: {local_version}")
        database.update_tool_version("ffmpeg", local_version)
        return True

    if local_version:
        logger.info(f"New update found for FFmpeg: local={local_version}, latest={latest_version}")
    else:
        logger.info("FFmpeg binaries missing. Starting download...")

    # 3. Download and extract, falling back to the second mirror when needed.
    zip_temp_path = os.path.join(TOOLS_DIR, "ffmpeg_temp.zip")
    last_error = lookup_error
    extracted: list[str] = []

    for source_name, url in FFMPEG_MIRRORS:
        try:
            download_file(url, zip_temp_path, f"FFmpeg ({source_name})",
                          min_bytes=MIN_FFMPEG_ZIP_BYTES)
            logger.info("Extracting ffmpeg.exe and ffprobe.exe from the zip...")
            extracted = _extract_ffmpeg(zip_temp_path)
            if len(extracted) == 2:
                break
            last_error = (
                f"L'archivio scaricato da {source_name} non contiene ffmpeg.exe e ffprobe.exe."
            )
            logger.warning(last_error)
        except zipfile.BadZipFile:
            last_error = f"L'archivio scaricato da {source_name} e' danneggiato o incompleto."
            logger.warning(last_error)
        except Exception as e:
            last_error = describe_network_error(e, url)
            logger.warning(f"Download di FFmpeg da {source_name} non riuscito: {last_error}")
        finally:
            if os.path.exists(zip_temp_path):
                try:
                    os.remove(zip_temp_path)
                except OSError:
                    pass
    else:
        if local_version:
            logger.warning("Aggiornamento non riuscito: continuo con la versione locale di FFmpeg.")
            return True
        errors.append(f"Impossibile installare FFmpeg.\n{last_error}")
        return False

    # 4. Validate before recording anything.
    installed_version = _ffmpeg_version(_probe_binary(ffmpeg_path, ["-version"]))
    if installed_version is None or _probe_binary(ffprobe_path, ["-version"]) is None:
        errors.append(_missing_binary_hint(ffmpeg_path, "ffmpeg.exe"))
        return False

    database.update_tool_version("ffmpeg", installed_version)
    logger.info(f"FFmpeg updated to version {installed_version}.")
    return True


# --- Extractors --------------------------------------------------------------

def update_extractors_list(yt_dlp_path: str):
    """Run yt-dlp --list-extractors and refresh the extractors table in the DB."""
    logger.info("Generating and updating the list of supported extractors...")
    try:
        result = subprocess.run(
            [yt_dlp_path, "--list-extractors"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            startupinfo=_startupinfo(),
            timeout=60
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


# --- Entry point -------------------------------------------------------------

def run_bootstrap() -> BootstrapResult:
    """
    Run the full bootstrap of yt-dlp and ffmpeg.

    The result is truthy when the application can run. ffmpeg missing is a
    degraded mode, not a failure: downloads still work, merging and mp3
    conversion do not.
    """
    logger.info("=== Starting Local Tools Bootstrapper ===")
    logger.info(netconfig.describe_environment())
    result = BootstrapResult()

    # A read-only install folder must be reported explicitly: it used to kill the
    # --noconsole exe before any window appeared.
    if TOOLS_DIR_ERROR:
        result.errors.append(TOOLS_DIR_ERROR)
        logger.error(TOOLS_DIR_ERROR)
        return result
    if database.INIT_ERROR:
        result.errors.append(database.INIT_ERROR)
    if database.BASE_DIR_FALLBACK_REASON:
        logger.info(f"Cartella dati alternativa in uso: '{BASE_DIR}'.")

    result.yt_dlp_ok = bootstrap_yt_dlp(result.errors)
    result.ffmpeg_ok = bootstrap_ffmpeg(result.errors)

    if result.complete:
        logger.info("=== Bootstrapper Completed: All tools are ready! ===")
    elif result.degraded:
        logger.warning("=== Bootstrapper Completed in modalita' ridotta: FFmpeg non disponibile ===")
    else:
        logger.error("=== Bootstrapper Failed: yt-dlp non disponibile ===")

    # Populate the extractors table if it is still empty (e.g. yt-dlp was already
    # installed and up to date on the very first run).
    if result.yt_dlp_ok:
        try:
            if not database.get_extractors():
                update_extractors_list(os.path.join(TOOLS_DIR, "yt-dlp.exe"))
        except Exception as e:
            logger.error(f"Error during the initial extractors check/population: {e}")

    return result


if __name__ == "__main__":
    outcome = run_bootstrap()
    if not outcome.usable:
        print(outcome.message())
        sys.exit(1)
    if outcome.degraded:
        print(outcome.message())
