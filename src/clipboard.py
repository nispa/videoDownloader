import ctypes
from ctypes import wintypes
import re

# Carica user32 e kernel32
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Definisci le funzioni Windows API per gli appunti
OpenClipboard = user32.OpenClipboard
OpenClipboard.argtypes = [wintypes.HWND]
OpenClipboard.restype = wintypes.BOOL

CloseClipboard = user32.CloseClipboard
CloseClipboard.restype = wintypes.BOOL

GetClipboardData = user32.GetClipboardData
GetClipboardData.argtypes = [wintypes.UINT]
GetClipboardData.restype = wintypes.HANDLE

GlobalLock = kernel32.GlobalLock
GlobalLock.argtypes = [wintypes.HANDLE]
GlobalLock.restype = ctypes.c_void_p

GlobalUnlock = kernel32.GlobalUnlock
GlobalUnlock.argtypes = [wintypes.HANDLE]
GlobalUnlock.restype = wintypes.BOOL

# Formato per il testo unicode
CF_UNICODETEXT = 13

# Regex semplice per validare URL generici
URL_REGEX = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)

def get_clipboard_text() -> str:
    """
    Legge il testo memorizzato negli appunti di Windows.
    Ritorna una stringa vuota se gli appunti non contengono testo o se si verifica un errore.
    """
    if not OpenClipboard(None):
        return ""
    
    try:
        handle = GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        
        ptr = GlobalLock(handle)
        if not ptr:
            return ""
            
        try:
            # Converte il puntatore in stringa Python (wchar_p per Unicode)
            text = ctypes.c_wchar_p(ptr).value
            return text if text else ""
        finally:
            GlobalUnlock(handle)
    except Exception:
        return ""
    finally:
        CloseClipboard()

def get_clipboard_url() -> str | None:
    """
    Verifica se negli appunti c'è un URL valido.
    Ritorna l'URL pulito (senza spazi bianchi) se valido, altrimenti None.
    """
    text = get_clipboard_text().strip()
    if not text:
        return None
    
    # Verifica se corrisponde a un URL
    if URL_REGEX.match(text):
        return text
    return None

if __name__ == "__main__":
    # Test veloce del modulo
    url = get_clipboard_url()
    if url:
        print(f"Trovato URL negli appunti: {url}")
    else:
        print("Nessun URL trovato negli appunti.")
