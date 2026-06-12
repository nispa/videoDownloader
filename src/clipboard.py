import ctypes
from ctypes import wintypes
import re

# Load user32 and kernel32
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Define the Windows API functions for the clipboard
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

# Clipboard format for unicode text
CF_UNICODETEXT = 13

# Simple regex to validate generic URLs
URL_REGEX = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)

def get_clipboard_text() -> str:
    """
    Read the text stored in the Windows clipboard.
    Returns an empty string if the clipboard has no text or an error occurs.
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
            # Convert the pointer to a Python string (wchar_p for Unicode)
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
    Check whether the clipboard contains a valid URL.
    Returns the cleaned URL (no surrounding whitespace) if valid, None otherwise.
    """
    text = get_clipboard_text().strip()
    if not text:
        return None

    # Check whether it matches a URL
    if URL_REGEX.match(text):
        return text
    return None

if __name__ == "__main__":
    # Quick module test
    url = get_clipboard_url()
    if url:
        print(f"Found URL in clipboard: {url}")
    else:
        print("No URL found in clipboard.")
