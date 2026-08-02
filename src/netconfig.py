"""
Network configuration for locked-down and corporate machines.

Two things routinely break the downloader on a managed PC, and neither of them
is a missing internet connection:

* **Certificates.** ``requests`` validates TLS against certifi's own CA bundle,
  not the Windows certificate store. A root CA that the IT department installed
  in Windows — which is how every TLS-inspecting proxy works — is therefore
  invisible to it, and every HTTPS request fails with ``SSLError``. The
  ``truststore`` package makes Python use the operating system trust store, so
  the corporate CA is honoured exactly like in the browser.

* **Proxy auto-configuration.** ``urllib`` (and therefore ``requests`` and
  yt-dlp) already reads a proxy configured explicitly in the Windows registry,
  so that case works out of the box. What it ignores is ``AutoConfigURL``, the
  PAC file many organizations use to distribute proxy settings. Interpreting a
  PAC file means running JavaScript, which is out of scope, so the situation is
  detected and reported instead of failing with a misleading message.
"""
import os
import logging

logger = logging.getLogger("netconfig")

# Set by enable_os_trust_store(); reported in the startup log.
TRUST_STORE_ACTIVE = False


def enable_os_trust_store() -> bool:
    """
    Route TLS verification through the operating system trust store.

    Must run before the first HTTPS request. Returns True when the injection
    succeeded; a False here is not fatal, it just means requests keeps using
    certifi and a corporate CA will not be recognised.
    """
    global TRUST_STORE_ACTIVE
    try:
        import truststore
    except ImportError:
        logger.info(
            "truststore non disponibile: la verifica TLS usa il bundle di certifi. "
            "Su una rete con proxy che ispeziona HTTPS potrebbe fallire."
        )
        return False

    try:
        truststore.inject_into_ssl()
    except Exception as e:
        logger.warning(f"Impossibile attivare l'archivio certificati di sistema: {e}")
        return False

    TRUST_STORE_ACTIVE = True
    logger.info("Verifica TLS agganciata all'archivio certificati di Windows.")
    return True


def _registry_value(name: str) -> str | None:
    """Read a value from the Internet Settings key. Returns None when absent."""
    if os.name != 'nt':
        return None
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except (OSError, ImportError):
        return None


def system_proxies() -> dict:
    """Proxies urllib/requests will actually use (environment + Windows registry)."""
    import urllib.request
    try:
        return urllib.request.getproxies()
    except Exception:
        return {}


def pac_url() -> str | None:
    """
    The URL of the proxy auto-configuration script, when the machine uses one.
    Its presence explains failures that look like "no internet" but are really
    "the traffic should have gone through a proxy nobody told us about".
    """
    value = _registry_value("AutoConfigURL")
    return value.strip() if isinstance(value, str) and value.strip() else None


def proxy_hint() -> str | None:
    """
    An extra sentence to append to a network error, when the environment
    explains it. Returns None when there is nothing useful to add.
    """
    if system_proxies():
        return None  # a usable proxy is configured; it is not the missing piece

    pac = pac_url()
    if pac:
        return (
            f"Questo computer usa un file di configurazione automatica del proxy "
            f"(PAC: {pac}), che questa applicazione non è in grado di interpretare. "
            f"Chiedi all'assistenza informatica l'indirizzo e la porta del proxy, poi "
            f"impostali nelle variabili d'ambiente HTTP_PROXY e HTTPS_PROXY."
        )
    return None


def describe_environment() -> str:
    """One-line summary of the network configuration, for the startup log."""
    parts = []
    proxies = system_proxies()
    parts.append(f"proxy={proxies}" if proxies else "proxy=nessuno")
    pac = pac_url()
    if pac:
        parts.append(f"PAC={pac}")
    parts.append(f"trust store di sistema={'attivo' if TRUST_STORE_ACTIVE else 'non attivo'}")
    return "Configurazione di rete: " + ", ".join(parts)
