"""
Minimal i18n support for the GUI.

UI strings live in JSON files inside <project root>/lang/, one file per
language (it.json, en.json, ...). Users can add a new language by copying an
existing file, renaming it (e.g. fr.json) and translating the values; it will
show up automatically in the language dropdown.

The built-in Italian and English dictionaries below are written to disk on
first run (or whenever the files are missing), so the standalone exe is
self-healing.
"""
import os
import json
import logging
import database

logger = logging.getLogger("i18n")

LANG_DIR = os.path.join(database.BASE_DIR, "lang")

# Built-in languages, used to (re)create the JSON files and as a fallback
# for keys missing from user-edited files. "_name" is the display name shown
# in the language dropdown.
BUILTIN_LANGUAGES = {
    "it": {
        "_name": "Italiano",
        "subtitle": "Scarica video e musica da YouTube ed altre piattaforme",
        "url_label": "Inserisci il link del video:",
        "url_placeholder": "https://www.youtube.com/watch?...",
        "paste": "Incolla",
        "info_ready": "Pronto per analizzare il link...",
        "info_analyzing": "Analisi del link in corso...",
        "info_unsupported": "⚠️ Questo sito o URL potrebbe non essere supportato da yt-dlp.",
        "info_error": "Impossibile estrarre informazioni dal link.",
        "info_author": "Canale/Autore: {uploader}",
        "info_duration": "Durata: {duration}  |  Piattaforma: {extractor}",
        "format_label": "Formato di download:",
        "path_label": "Cartella di salvataggio:",
        "browse": "Sfoglia",
        "cookie_browser_label": "Browser per cookie (Facebook/Instagram):",
        "cookie_none": "Nessuno",
        "cookie_file_label": "File cookies.txt (opzionale):",
        "cookie_file_dialog_title": "Seleziona il file cookies.txt",
        "cookie_file_dialog_text": "File di testo",
        "cookie_file_dialog_all": "Tutti i file",
        "download_now": "SCARICA ORA",
        "downloading": "DOWNLOAD IN CORSO...",
        "stats_init": "Inizializzazione download...",
        "stats_phase": "Fase: {status}",
        "stats_completed": "Completato!",
        "stats_error": "Errore: {status}",
        "stats_progress": "{percent:5.1f}% | Velocità: {speed} | ETA: {eta} | {status}",
        "done_label": "Download completato con successo!",
        "fail_label": "Errore durante il download.",
        "msg_warning_title": "Attenzione",
        "msg_no_clipboard": "Nessun testo trovato negli appunti.",
        "msg_no_url": "Inserisci un link valido prima di iniziare.",
        "msg_unsupported_title": "Sito non supportato",
        "msg_unsupported_body": "Questo sito o URL non sembra essere supportato ufficialmente da yt-dlp.\nVuoi comunque tentare il download usando l'estrattore generico?",
        "msg_success_title": "Successo",
        "msg_success_body": "Download e conversione completati con successo!",
        "msg_error_title": "Errore",
        "msg_error_body": "Si è verificato un errore durante il download o il post-processing. Controlla il log.",
        "boot_status": "Inizializzazione strumenti locali in corso...",
        "boot_error_status": "Errore: Impossibile scaricare o configurare gli strumenti di download.\nVerifica la connessione ad internet e riavvia il programma.",
        "boot_error_title": "Errore di Inizializzazione",
        "boot_error_body": "Impossibile configurare gli strumenti locali (yt-dlp/ffmpeg).\nVerifica la connessione a Internet e riprova."
    },
    "en": {
        "_name": "English",
        "subtitle": "Download videos and music from YouTube and other platforms",
        "url_label": "Enter the video link:",
        "url_placeholder": "https://www.youtube.com/watch?...",
        "paste": "Paste",
        "info_ready": "Ready to analyze the link...",
        "info_analyzing": "Analyzing the link...",
        "info_unsupported": "⚠️ This site or URL may not be supported by yt-dlp.",
        "info_error": "Could not extract information from the link.",
        "info_author": "Channel/Author: {uploader}",
        "info_duration": "Duration: {duration}  |  Platform: {extractor}",
        "format_label": "Download format:",
        "path_label": "Save folder:",
        "browse": "Browse",
        "cookie_browser_label": "Cookie browser (Facebook/Instagram):",
        "cookie_none": "None",
        "cookie_file_label": "cookies.txt file (optional):",
        "cookie_file_dialog_title": "Select the cookies.txt file",
        "cookie_file_dialog_text": "Text files",
        "cookie_file_dialog_all": "All files",
        "download_now": "DOWNLOAD NOW",
        "downloading": "DOWNLOADING...",
        "stats_init": "Initializing download...",
        "stats_phase": "Phase: {status}",
        "stats_completed": "Completed!",
        "stats_error": "Error: {status}",
        "stats_progress": "{percent:5.1f}% | Speed: {speed} | ETA: {eta} | {status}",
        "done_label": "Download completed successfully!",
        "fail_label": "Error during download.",
        "msg_warning_title": "Warning",
        "msg_no_clipboard": "No text found in the clipboard.",
        "msg_no_url": "Enter a valid link before starting.",
        "msg_unsupported_title": "Unsupported site",
        "msg_unsupported_body": "This site or URL does not seem to be officially supported by yt-dlp.\nDo you want to try the download anyway using the generic extractor?",
        "msg_success_title": "Success",
        "msg_success_body": "Download and conversion completed successfully!",
        "msg_error_title": "Error",
        "msg_error_body": "An error occurred during the download or post-processing. Check the log.",
        "boot_status": "Initializing local tools...",
        "boot_error_status": "Error: could not download or configure the download tools.\nCheck your internet connection and restart the program.",
        "boot_error_title": "Initialization Error",
        "boot_error_body": "Could not configure the local tools (yt-dlp/ffmpeg).\nCheck your internet connection and try again."
    }
}

DEFAULT_LANGUAGE = "it"

# Currently loaded strings (Italian fallback until load_language is called)
_strings: dict = dict(BUILTIN_LANGUAGES[DEFAULT_LANGUAGE])
_current_code: str = DEFAULT_LANGUAGE

def ensure_language_files():
    """
    Write the built-in language files to lang/ if they are missing.
    Never raises: if the directory or files cannot be created, the app
    still starts using the built-in dictionaries.
    """
    try:
        os.makedirs(LANG_DIR, exist_ok=True)
    except Exception as e:
        logger.error(f"Could not create language directory {LANG_DIR}: {e}")
        return
    for code, strings in BUILTIN_LANGUAGES.items():
        path = os.path.join(LANG_DIR, f"{code}.json")
        if not os.path.isfile(path):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(strings, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Could not write language file {path}: {e}")

def available_languages() -> dict[str, str]:
    """Return {code: display name} for every language file in lang/."""
    languages = {}
    try:
        for filename in sorted(os.listdir(LANG_DIR)):
            if not filename.lower().endswith(".json"):
                continue
            code = os.path.splitext(filename)[0]
            try:
                with open(os.path.join(LANG_DIR, filename), encoding="utf-8") as f:
                    data = json.load(f)
                languages[code] = data.get("_name", code)
            except Exception as e:
                logger.error(f"Invalid language file {filename}: {e}")
    except OSError:
        pass
    if not languages:
        # Fall back to the built-in languages if the directory is unusable
        languages = {code: strings["_name"] for code, strings in BUILTIN_LANGUAGES.items()}
    return languages

def load_language(code: str):
    """Load a language by code, falling back to built-in strings for missing keys."""
    global _strings, _current_code
    # Start from the built-in default so user files with missing keys still work
    strings = dict(BUILTIN_LANGUAGES[DEFAULT_LANGUAGE])
    strings.update(BUILTIN_LANGUAGES.get(code, {}))
    path = os.path.join(LANG_DIR, f"{code}.json")
    try:
        with open(path, encoding="utf-8") as f:
            strings.update(json.load(f))
    except Exception as e:
        logger.error(f"Could not load language file {path}: {e}")
    _strings = strings
    _current_code = code

def current_language() -> str:
    """Return the code of the currently loaded language."""
    return _current_code

def tr(key: str, **kwargs) -> str:
    """Return the translated string for a key, formatted with kwargs."""
    text = _strings.get(key)
    if text is None:
        return key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text

# Initialize on import: create missing files and load the saved language
ensure_language_files()
load_language(database.get_setting("language", DEFAULT_LANGUAGE))
