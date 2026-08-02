"""
Persistence layer and application-wide paths.

This module is imported first by every entry point, so it is also the place
where BASE_DIR is decided and logging is configured. Both steps are written to
never raise at import time: on a locked-down machine (exe placed in
C:\\Program Files, a managed Desktop, a OneDrive folder with Controlled Folder
Access, a read-only USB stick) the application must still start and be able to
explain what is wrong, instead of dying silently behind --noconsole.
"""
import sqlite3
import os
import sys
import logging
import tempfile

APP_NAME = "VideoDownloader"


def _app_dir() -> str:
    """Directory the application lives in: next to the exe, or the project root."""
    if getattr(sys, 'frozen', False):
        # Running as a compiled EXE (located in the project root)
        return os.path.dirname(os.path.abspath(sys.executable))
    # Running as a Python script (located inside src/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_writable(path: str) -> bool:
    """True if `path` exists (or can be created) and a file can be written into it."""
    try:
        os.makedirs(path, exist_ok=True)
        fd, probe = tempfile.mkstemp(prefix=".write_test_", dir=path)
        os.close(fd)
        os.remove(probe)
        return True
    except OSError:
        return False


def _resolve_base_dir() -> tuple[str, str | None]:
    """
    Pick a writable BASE_DIR. Returns (base_dir, fallback_reason); the reason is
    None when the application directory itself is usable.

    The app directory is preferred so the install stays portable (USB stick,
    shared folder). When it is not writable we fall back to %LOCALAPPDATA% and,
    as a last resort, to the system temp directory.
    """
    app_dir = _app_dir()
    if _is_writable(app_dir):
        return app_dir, None

    reason = f"'{app_dir}' non e' scrivibile"
    local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    candidate = os.path.join(local_appdata, APP_NAME)
    if _is_writable(candidate):
        return candidate, reason

    return os.path.join(tempfile.gettempdir(), APP_NAME), reason


APP_DIR = _app_dir()
BASE_DIR, BASE_DIR_FALLBACK_REASON = _resolve_base_dir()

DB_DIR = os.path.abspath(os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DB_DIR, "downloader.db")
DEFAULT_DOWNLOAD_DIR = os.path.abspath(os.path.join(BASE_DIR, "downloads"))
LOGS_DIR = os.path.abspath(os.path.join(BASE_DIR, "logs"))

# Set when init_db() could not prepare the database; the GUI surfaces it instead
# of failing with an unexplained crash.
INIT_ERROR: str | None = None


def _configure_logging():
    """
    Configure the root logger once, as early as possible, so that messages
    emitted while the paths are being resolved are not lost. Falls back to
    console-only logging when the logs directory cannot be created.
    """
    root = logging.getLogger()
    if root.handlers:  # already configured by another entry point
        return

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    root.setLevel(logging.INFO)

    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(LOGS_DIR, "app.log"), encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        pass  # console-only logging is better than no application at all

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)


_configure_logging()
logger = logging.getLogger("database")

if BASE_DIR_FALLBACK_REASON:
    logger.warning(
        f"{BASE_DIR_FALLBACK_REASON}. Dati e strumenti verranno salvati in '{BASE_DIR}'."
    )


def _connect() -> sqlite3.Connection:
    """Open a connection to the database. Raises sqlite3.Error if unusable."""
    return sqlite3.connect(DB_PATH)


def init_db() -> bool:
    """
    Initialize the SQLite database, creating tables and inserting default values.
    Returns True on success; on failure it records the cause in INIT_ERROR and
    returns False rather than raising, so the caller can still show a window.
    """
    global INIT_ERROR
    try:
        os.makedirs(DB_DIR, exist_ok=True)
        conn = _connect()
    except (OSError, sqlite3.Error) as e:
        INIT_ERROR = f"Impossibile aprire il database in '{DB_PATH}': {e}"
        logger.error(INIT_ERROR)
        return False

    try:
        cursor = conn.cursor()

        # Table tracking the versions of third-party tools
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_tools (
                tool_name TEXT PRIMARY KEY,
                installed_version TEXT,
                last_checked TEXT
            )
        """)

        # Table tracking application settings (e.g. download path)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Table storing the extractors supported by yt-dlp
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extractors (
                extractor_name TEXT PRIMARY KEY
            )
        """)

        conn.commit()

        # Set the default download path if not already present
        cursor.execute("SELECT value FROM settings WHERE key = 'download_path'")
        if not cursor.fetchone():
            try:
                os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
            except OSError as e:
                logger.warning(f"Could not create the default download folder: {e}")
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES ('download_path', ?)",
                (DEFAULT_DOWNLOAD_DIR,)
            )
            conn.commit()

        # Set the default cookie browser (none) if not already present
        cursor.execute("SELECT value FROM settings WHERE key = 'cookie_browser'")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES ('cookie_browser', 'none')"
            )
            conn.commit()
    except sqlite3.Error as e:
        INIT_ERROR = f"Database non utilizzabile ('{DB_PATH}'): {e}"
        logger.error(INIT_ERROR)
        return False
    finally:
        conn.close()

    INIT_ERROR = None
    return True


def get_tool_version(tool_name: str) -> str | None:
    """Return the installed version of the tool, or None if not registered."""
    try:
        conn = _connect()
    except sqlite3.Error as e:
        logger.error(f"get_tool_version({tool_name}) failed: {e}")
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT installed_version FROM system_tools WHERE tool_name = ?", (tool_name,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"get_tool_version({tool_name}) failed: {e}")
        return None
    finally:
        conn.close()


def update_tool_version(tool_name: str, version: str) -> bool:
    """Insert or update the tool version with the current timestamp."""
    import datetime
    now = datetime.datetime.now().isoformat()
    try:
        conn = _connect()
    except sqlite3.Error as e:
        logger.error(f"update_tool_version({tool_name}) failed: {e}")
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_tools (tool_name, installed_version, last_checked)
            VALUES (?, ?, ?)
            ON CONFLICT(tool_name) DO UPDATE SET
                installed_version = excluded.installed_version,
                last_checked = excluded.last_checked
        """, (tool_name, version, now))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"update_tool_version({tool_name}) failed: {e}")
        return False
    finally:
        conn.close()


def get_setting(key: str, default_value: str = None) -> str | None:
    """Return the value of a setting, or the default value."""
    try:
        conn = _connect()
    except sqlite3.Error as e:
        logger.error(f"get_setting({key}) failed: {e}")
        return default_value
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default_value
    except sqlite3.Error as e:
        logger.error(f"get_setting({key}) failed: {e}")
        return default_value
    finally:
        conn.close()


def set_setting(key: str, value: str) -> bool:
    """Save or update a setting."""
    try:
        conn = _connect()
    except sqlite3.Error as e:
        logger.error(f"set_setting({key}) failed: {e}")
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"set_setting({key}) failed: {e}")
        return False
    finally:
        conn.close()


def save_extractors(extractor_names: list[str]) -> bool:
    """Save the list of extractors supported by yt-dlp, clearing the old ones."""
    try:
        conn = _connect()
    except sqlite3.Error as e:
        logger.error(f"save_extractors failed: {e}")
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM extractors")
        cursor.executemany(
            "INSERT INTO extractors (extractor_name) VALUES (?)",
            [(name,) for name in extractor_names]
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"save_extractors failed: {e}")
        return False
    finally:
        conn.close()


def get_extractors() -> set[str]:
    """Return the set of extractors stored in the database."""
    try:
        conn = _connect()
    except sqlite3.Error as e:
        logger.error(f"get_extractors failed: {e}")
        return set()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT extractor_name FROM extractors")
        return {row[0] for row in cursor.fetchall()}
    except sqlite3.Error as e:
        logger.error(f"get_extractors failed: {e}")
        return set()
    finally:
        conn.close()


# Automatically initialize the DB when the module is loaded
init_db()
