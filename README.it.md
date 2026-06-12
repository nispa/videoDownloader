# Video & Audio Downloader (yt-dlp & FFmpeg)

🇬🇧 [Read the documentation in English](README.md)

Un'applicazione Windows moderna, leggera e standalone per scaricare video o estrarre tracce audio (in formato MP3 ad alta qualità) da YouTube e da oltre 1.400 altre piattaforme supportate. 

Il programma gestisce autonomamente il download e l'aggiornamento dei componenti di terze parti (`yt-dlp` e `ffmpeg`), archivia le impostazioni in un database locale SQLite, separa accuratamente i file di log e integra una verifica preventiva degli URL.

---

## ⚡ Setup Rapido e Gestione (Windows Batch)

Per semplificare l'installazione e l'uso, il progetto include due script batch pronti all'uso nella root:

*   **`setup.bat`**: Configura automaticamente l'ambiente virtuale Python (`.venv`), aggiorna `pip`, installa tutte le dipendenze da `requirements.txt` ed effettua il primo download dei binari di supporto (`yt-dlp.exe`, `ffmpeg.exe` e `ffprobe.exe`).
*   **`run.bat`**: Un comodo menu interattivo da cui puoi fare tutto:
    1. Avviare l'Interfaccia Grafica (GUI).
    2. Avviare l'Interfaccia a Riga di Comando (CLI).
    3. Compilare l'app in un eseguibile standalone (`VideoDownloader.exe`).
    4. Eseguire o aggiornare l'intero setup.
    5. Uscire.

> [!NOTE]
> Se avvii `run.bat` e non hai ancora eseguito il setup, lo script rileverà automaticamente l'assenza della cartella `.venv` ed eseguirà `setup.bat` prima di avviare l'opzione desiderata.

---


## Struttura del Progetto

```
c:\lavori\video-downloader\
├── tools/                  # Eseguibili di supporto (yt-dlp.exe, ffmpeg.exe, ffprobe.exe)
├── data/                   # Database SQLite (downloader.db)
├── logs/                   # Cartella dei log (app.log e download.log)
├── downloads/              # Cartella di download predefinita
├── lang/                   # Traduzioni della UI (it.json, en.json, lingue aggiunte dall'utente)
├── src/                    # Codice sorgente Python
│   ├── gui.py              # Interfaccia Grafica (GUI CustomTkinter)
│   ├── main.py             # Interfaccia a riga di comando (CLI)
│   ├── downloader.py       # Gestione del download ed estrazione metadati
│   ├── bootstrapper.py     # Download e auto-aggiornamento dei tool
│   ├── database.py         # Configurazione DB SQLite e percorsi dinamici
│   ├── i18n.py             # Localizzazione della UI (carica le label da lang/*.json)
│   └── clipboard.py        # Integrazione delle API per gli appunti di Windows
├── VideoDownloader.exe     # Applicazione compilata standalone (root)
├── build_exe.py            # Script di compilazione con PyInstaller
└── requirements.txt        # Dipendenze Python
```

---

## 1. Utilizzo tramite Interfaccia Grafica (GUI) - Consigliato

L'interfaccia grafica moderna è costruita con `customtkinter` in modalità scura automatica e supporta l'esecuzione asincrona (multi-thread) per evitare blocchi dell'interfaccia.

### Come avviarlo:
- **Eseguibile standalone (Dalla root)**: Fai doppio clic su **`VideoDownloader.exe`**.
- **Da sorgente (Sviluppo)**: Esegui nel terminale:
  ```powershell
  .venv\Scripts\python src/gui.py
  ```

### Funzionalità principali della GUI:
*   **Incolla Rapido (Clipboard Auto-detect)**: All'avvio l'applicazione rileva se c'è un link negli appunti e lo inserisce automaticamente. Puoi usare anche il pulsante *Incolla* per caricare il contenuto degli appunti in qualsiasi momento.
*   **Analisi in Background**: Non appena inserisci un link valido, l'app avvia un'estrazione metadati mostrando Titolo, Canale autore e Durata.
*   **Verifica Preventiva degli URL**: Se inserisci un link non supportato, l'app ti avvisa istantaneamente a schermo prima ancora di provare a scaricarlo, interrogando la lista interna di oltre 1.480 estrattori caricata nel database.
*   **Sfoglia Destinazione**: Puoi cambiare la cartella di salvataggio predefinita con un comodo selettore grafico. La scelta viene salvata nel database e mantenuta per i successivi avvii.
*   **Autenticazione tramite Cookie (Facebook/Instagram)**: Molte piattaforme social richiedono il login per accedere ai video, Reel inclusi. Seleziona dal menu *Browser per cookie* il browser in cui sei già loggato, oppure scegli un file `cookies.txt` esportato (che ha priorità sul browser).
*   **Interfaccia Multilingua**: Cambia lingua dal menu a tendina in alto a destra (italiano e inglese inclusi). La scelta viene salvata e ripristinata all'avvio successivo.

### Note sui download da Facebook / Instagram

yt-dlp legge i cookie direttamente dal profilo del browser su disco:

*   **Firefox** funziona subito, anche con il browser aperto.
*   **Chrome/Edge**: il database dei cookie è bloccato mentre il browser è in esecuzione, quindi chiudilo completamente prima di scaricare. Le versioni recenti di Chrome (127+) cifrano i cookie con la App-Bound Encryption e potrebbero non funzionare affatto; in tal caso esporta un file `cookies.txt` con un'estensione del browser (es. *Get cookies.txt LOCALLY*) e selezionalo nella GUI.

### Aggiungere una nuova lingua

Le label della UI sono in file JSON nella cartella `lang/` (ricreata automaticamente se mancante). Per aggiungere una lingua, copia `en.json`, rinominalo (es. `fr.json`), traduci i valori e imposta il campo `_name`: comparirà automaticamente nel menu delle lingue.

---

## 2. Utilizzo tramite Riga di Comando (CLI)

Se preferisci un'interfaccia minimalista e rapida da tastiera, puoi utilizzare lo script CLI interattivo ed elegante con supporto per i colori nel terminale.

### Come avviarlo:
Esegui nel terminale:
```powershell
.venv\Scripts\python src/main.py
```

### Funzionalità della CLI:
*   **Rilevamento Appunti**: All'avvio, se rileva un link negli appunti ti chiederà se vuoi scaricare direttamente quello premendo semplicemente **INVIO**.
*   **Menu Interattivo**:
    1. *Scarica Video / Audio da Link*: Ti guida nella scelta del link e del formato (Video MP4 o Audio MP3).
    2. *Configura cartella di download*: Consente di digitare o incollare un nuovo percorso assoluto di salvataggio.
    3. *Esci*: Chiude l'applicazione.
*   **Barra di Avanzamento Testuale**: Mostra graficamente la percentuale scaricata, la velocità di download e il tempo stimato (ETA) in tempo reale.

---

## 3. Gestione dei Log (Separati)

Per facilitare il debug e l'ispezione, i log dell'applicazione sono divisi in due file all'interno della cartella `logs/`:
1.  **`app.log`**: Traccia le attività di sistema all'avvio, il bootstrap dei componenti, il controllo delle versioni online e l'aggiornamento dei moduli.
2.  **`download.log`**: Registra i dettagli del motore di download, inclusi gli URL inseriti, i comandi passati a `yt-dlp.exe` in subprocess, gli esiti delle conversioni FFmpeg e gli eventuali errori di download.

---

## 4. Come Ricompilare l'Eseguibile

Se apporti modifiche al codice sorgente in `src/` e desideri generare una nuova versione di `VideoDownloader.exe` nella radice del progetto, assicurati di chiudere il programma se è aperto ed esegui:

```powershell
.venv\Scripts\python build_exe.py
```

Lo script compilerà automaticamente l'interfaccia grafica in modalità `--noconsole` (senza terminale), sposterà l'EXE finale nella root e ripulirà tutti i file temporanei di compilazione.

---

## 5. Licenza

Il codice sorgente di questo progetto è rilasciato sotto la [Licenza MIT](LICENSE).

Le informazioni e le attribuzioni relative ai componenti software di terze parti utilizzati (`yt-dlp` e `FFmpeg`) sono disponibili nel file [LICENSE-3RD-PARTY.md](LICENSE-3RD-PARTY.md).
