import sqlite3
import os
import sys

# Dynamic BASE_DIR detection to handle script vs frozen exe
if getattr(sys, 'frozen', False):
    # Running as a compiled EXE (located in the project root)
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # Running as a Python script (located inside src/)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_DIR = os.path.abspath(os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DB_DIR, "downloader.db")
DEFAULT_DOWNLOAD_DIR = os.path.abspath(os.path.join(BASE_DIR, "downloads"))

def init_db():
    """Initialize the SQLite database, creating tables and inserting default values."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
        os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
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

    conn.close()

def get_tool_version(tool_name: str) -> str | None:
    """Return the installed version of the tool, or None if not registered."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT installed_version FROM system_tools WHERE tool_name = ?", (tool_name,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def update_tool_version(tool_name: str, version: str):
    """Insert or update the tool version with the current timestamp."""
    import datetime
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO system_tools (tool_name, installed_version, last_checked)
        VALUES (?, ?, ?)
        ON CONFLICT(tool_name) DO UPDATE SET
            installed_version = excluded.installed_version,
            last_checked = excluded.last_checked
    """, (tool_name, version, now))
    conn.commit()
    conn.close()

def get_setting(key: str, default_value: str = None) -> str | None:
    """Return the value of a setting, or the default value."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default_value

def set_setting(key: str, value: str):
    """Save or update a setting."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

def save_extractors(extractor_names: list[str]):
    """Save the list of extractors supported by yt-dlp, clearing the old ones."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM extractors")
    cursor.executemany(
        "INSERT INTO extractors (extractor_name) VALUES (?)",
        [(name,) for name in extractor_names]
    )
    conn.commit()
    conn.close()

def get_extractors() -> set[str]:
    """Return the set of extractors stored in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT extractor_name FROM extractors")
    rows = cursor.fetchall()
    conn.close()
    return {row[0] for row in rows}

# Automatically initialize the DB when the module is loaded
init_db()
