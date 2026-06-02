import sqlite3
import os
import sys

# Rilevamento dinamico di BASE_DIR per gestire script vs exe
if getattr(sys, 'frozen', False):
    # Eseguito come EXE compilato (nella radice del progetto)
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # Eseguito come script Python (all'interno di src/)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_DIR = os.path.abspath(os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DB_DIR, "downloader.db")
DEFAULT_DOWNLOAD_DIR = os.path.abspath(os.path.join(BASE_DIR, "downloads"))

def init_db():
    """Inizializza il database SQLite creando le tabelle e inserendo i valori predefiniti."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabella per tracciare le versioni degli strumenti di terze parti
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_tools (
            tool_name TEXT PRIMARY KEY,
            installed_version TEXT,
            last_checked TEXT
        )
    """)
    
    # Tabella per tracciare le impostazioni dell'applicazione (es. percorso di download)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Tabella per memorizzare gli estrattori supportati da yt-dlp
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS extractors (
            extractor_name TEXT PRIMARY KEY
        )
    """)
    
    conn.commit()
    
    # Imposta il percorso di download predefinito se non è già presente
    cursor.execute("SELECT value FROM settings WHERE key = 'download_path'")
    if not cursor.fetchone():
        os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
        cursor.execute(
            "INSERT INTO settings (key, value) VALUES ('download_path', ?)",
            (DEFAULT_DOWNLOAD_DIR,)
        )
        conn.commit()
        
    conn.close()

def get_tool_version(tool_name: str) -> str | None:
    """Restituisce la versione installata del tool, o None se non è registrato."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT installed_version FROM system_tools WHERE tool_name = ?", (tool_name,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def update_tool_version(tool_name: str, version: str):
    """Aggiorna o inserisce la versione del tool con il timestamp corrente."""
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
    """Restituisce il valore di un'impostazione, o il valore di default."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default_value

def set_setting(key: str, value: str):
    """Salva o aggiorna un'impostazione."""
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
    """Salva la lista di estrattori supportati da yt-dlp nel DB, pulendo quelli vecchi."""
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
    """Restituisce il set degli estrattori salvati nel database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT extractor_name FROM extractors")
    rows = cursor.fetchall()
    conn.close()
    return {row[0] for row in rows}

# Inizializza automaticamente il DB al caricamento del modulo
init_db()
