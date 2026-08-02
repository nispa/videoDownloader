# Video & Audio Downloader (yt-dlp & FFmpeg)

🇬🇧 [Read the documentation in English](README.md)

Un'applicazione Windows moderna, leggera e standalone per scaricare video o estrarre tracce audio (in formato MP3 ad alta qualità) da YouTube e da oltre 1.400 altre piattaforme supportate. 

Il programma gestisce autonomamente il download e l'aggiornamento dei componenti di terze parti (`yt-dlp` e `ffmpeg`), archivia le impostazioni in un database locale SQLite, separa accuratamente i file di log e integra una verifica preventiva degli URL.

L'installazione è progettata per essere **portabile**: l'eseguibile può essere copiato su un altro computer e si configura da solo al primo avvio, con download verificati, sorgenti alternative in caso di irraggiungibilità e messaggi che indicano la causa reale di un eventuale problema anziché un generico errore di connessione.

---

## ⬇️ Download (consigliato)

Il modo più semplice per usare l'app — **niente Python, niente setup**:

1. Scarica **`VideoDownloader.exe`** dalla [pagina Releases](https://github.com/nispa/videoDownloader/releases).
2. Mettilo in una cartella a tua scelta e fai doppio clic. Fine.

Al primo avvio l'app scarica automaticamente gli strumenti di supporto (`yt-dlp` e `FFmpeg`) e crea le sue cartelle di lavoro accanto all'eseguibile.

L'unico requisito è **Windows 10/11**.

---

## 🛠️ Esecuzione da Sorgente / Compilazione in Proprio (opzionale)

Se preferisci eseguire direttamente il codice Python, o compilare `VideoDownloader.exe` per conto tuo, ti serviranno:

*   **Windows 10/11**
*   **Python 3.10 o superiore**, con *"Add Python to PATH"* spuntato durante l'installazione

### ⚡ Setup Rapido e Gestione (Windows Batch)

Per semplificare l'installazione e l'uso, il progetto include due script batch pronti all'uso nella root:

*   **`setup.bat`**: Configura automaticamente l'ambiente virtuale Python (`.venv`), aggiorna `pip`, installa tutte le dipendenze da `requirements.txt` ed effettua il primo download dei binari di supporto (`yt-dlp.exe`, `ffmpeg.exe` e `ffprobe.exe`).
*   **`run.bat`**: Un comodo menu interattivo da cui puoi fare tutto:
    1. Avviare l'Interfaccia Grafica (GUI).
    2. Avviare l'Interfaccia a Riga di Comando (CLI).
    3. Compilare l'app in un eseguibile standalone (`VideoDownloader.exe`).
    4. Eseguire o aggiornare l'intero setup.
    5. Uscire.

> [!NOTE]
> Se avvii `run.bat` e non hai ancora eseguito il setup, lo script rileverà l'assenza di un ambiente virtuale funzionante ed eseguirà `setup.bat` prima di avviare l'opzione desiderata.

Entrambi gli script si riportano automaticamente nella propria cartella, quindi funzionano anche se lanciati da un collegamento, da un'altra unità o con *Esegui come amministratore*. Il controllo di Python esegue davvero l'interprete anziché limitarsi a cercarlo nel `PATH`: su Windows 11 un alias del Microsoft Store è presente anche quando Python **non** è installato, e ingannerebbe una verifica superficiale.

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
│   ├── netconfig.py        # Certificati di sistema e diagnostica proxy (reti aziendali)
│   ├── i18n.py             # Localizzazione della UI (carica le label da lang/*.json)
│   └── clipboard.py        # Integrazione delle API per gli appunti di Windows
├── logo.png                # Logo dell'app (icona finestra/taskbar e header)
├── VideoDownloader.exe     # Applicazione compilata standalone (root)
├── build_exe.py            # Script di compilazione con PyInstaller
└── requirements.txt        # Dipendenze Python
```

---

## 1. Utilizzo tramite Interfaccia Grafica (GUI) - Consigliato

L'interfaccia grafica moderna è costruita con `customtkinter` in modalità scura automatica e supporta l'esecuzione asincrona (multi-thread) per evitare blocchi dell'interfaccia.

### Come avviarlo:
- **Dal menu del launcher (più semplice)**: Avvia **`run.bat`** e scegli l'opzione **1**.
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
*   **Download Sottotitoli / Trascrizione (YouTube e altri)**: Spunta *Scarica anche i sottotitoli* per salvare, insieme al video o all'audio, i sottotitoli (sia quelli manuali sia quelli auto-generati) in formato `.srt`. Scegli **una lingua per volta** (Italiano o English) dal menu a fianco. Con l'opzione aggiuntiva *Anche come .txt (senza timestamp)* viene generata anche una trascrizione in testo semplice, ripulita dai codici temporali e dalle righe duplicate. Il download dei sottotitoli è **non bloccante**: se YouTube limita le richieste (errore `HTTP 429`), il video viene comunque salvato e l'app segnala *Completato (sottotitoli non riusciti)*. Per ridurre i 429, imposta i cookie del browser e scarica una lingua alla volta.
*   **Autenticazione tramite Cookie (Facebook/Instagram)**: Molte piattaforme social richiedono il login per accedere ai video, Reel inclusi. Seleziona dal menu *Browser per cookie* il browser in cui sei già loggato, oppure scegli un file `cookies.txt` esportato (che ha priorità sul browser).
*   **Importazione dei Cookie con un clic**: Il pulsante *Importa*, accanto al menu del browser, genera un file `cookies.txt` a partire dal browser selezionato e lo imposta automaticamente. Serve soprattutto per la **portabilità**: i cookie letti direttamente dal browser sono cifrati con DPAPI e leggibili solo dall'utente Windows che li ha creati, mentre il file esportato funziona anche su un altro computer o profilo. L'esportazione non effettua alcuna richiesta di rete.

    > [!WARNING]
    > Il file generato contiene le sessioni di **tutti** i siti a cui sei connesso con quel browser, non solo quello che stai scaricando. Trattalo come una password e non condividerlo. Viene salvato in `data/`, cartella già esclusa da Git.

*   **Formati diretti**: Oltre alle pagine dei siti supportati puoi incollare direttamente l'indirizzo di un file multimediale o di un manifest di streaming (`.mp4`, `.m3u8`, `.mpd`, `.ts`, `.mov`, `.aac`, `.opus` e altri), inclusi gli URL firmati con token di scadenza. Utile per le piattaforme che costruiscono la pagina in JavaScript, dove l'indirizzo del flusso va recuperato dal pannello *Rete* degli strumenti di sviluppo del browser.
*   **Interfaccia Multilingua**: Cambia lingua dal menu a tendina in alto a destra (italiano e inglese inclusi). La scelta viene salvata e ripristinata all'avvio successivo.

### Note sui download da Facebook / Instagram

yt-dlp legge i cookie direttamente dal profilo del browser su disco:

*   **Firefox** funziona subito, anche con il browser aperto.
*   **Chrome/Edge**: il database dei cookie è bloccato mentre il browser è in esecuzione, quindi chiudilo completamente prima di scaricare. Le versioni recenti di Chrome (127+) cifrano i cookie con la App-Bound Encryption e potrebbero non funzionare affatto; in tal caso esporta un file `cookies.txt` con un'estensione del browser (es. *Get cookies.txt LOCALLY*) e selezionalo nella GUI.

Se l'importazione con il pulsante *Importa* non riesce, il messaggio indica la causa precisa e il rimedio:

| Messaggio | Rimedio |
|---|---|
| Il database dei cookie è bloccato | Chiudi completamente il browser, controllando anche l'area di notifica accanto all'orologio |
| Non è stato trovato alcun profilo | Il browser non è installato, oppure usa un profilo diverso da quello predefinito |
| Cookie protetti da DPAPI | Esegui l'esportazione con lo stesso account Windows con cui usi il browser |

### Aggiungere una nuova lingua

Le label della UI sono in file JSON nella cartella `lang/` (ricreata automaticamente se mancante). Per aggiungere una lingua, copia `en.json`, rinominalo (es. `fr.json`), traduci i valori e imposta il campo `_name`: comparirà automaticamente nel menu delle lingue.

---

## 2. Utilizzo tramite Riga di Comando (CLI)

Se preferisci un'interfaccia minimalista e rapida da tastiera, puoi utilizzare lo script CLI interattivo ed elegante con supporto per i colori nel terminale.

### Come avviarlo:
- **Dal menu del launcher (più semplice)**: Avvia **`run.bat`** e scegli l'opzione **2**.
- **Manualmente**: Esegui nel terminale:
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

Se apporti modifiche al codice sorgente in `src/` e desideri generare una nuova versione di `VideoDownloader.exe` nella radice del progetto, assicurati di chiudere il programma se è aperto, poi avvia **`run.bat`** e scegli l'opzione **3** — oppure esegui manualmente:

```powershell
.venv\Scripts\python build_exe.py
```

Lo script compilerà automaticamente l'interfaccia grafica in modalità `--noconsole` (senza terminale), sposterà l'EXE finale nella root e ripulirà tutti i file temporanei di compilazione.

---

## 5. Portabilità, reti aziendali e risoluzione dei problemi

### Copiare l'app su un altro computer

L'eseguibile è autosufficiente: al primo avvio scarica `yt-dlp` e `FFmpeg` e ricrea le proprie cartelle. Alcuni accorgimenti rendono il processo affidabile anche su macchine gestite:

*   **Download verificati**: i file vengono scritti in `.part` e sostituiscono l'originale solo dopo essere stati eseguiti con successo. Un trasferimento interrotto non lascia mai un binario danneggiato, e una copia già corrotta viene rilevata e riscaricata invece di essere riutilizzata.
*   **Sorgenti alternative**: se l'API di GitHub è irraggiungibile o ha esaurito il limite di richieste (60 all'ora per indirizzo IP, facile da saturare su una rete condivisa), `yt-dlp` viene scaricato da un indirizzo diretto. Per FFmpeg è previsto un mirror alternativo a gyan.dev.
*   **Cartella dati garantita**: se la cartella dell'applicazione non è scrivibile — per esempio in `C:\Program Files`, su un Desktop gestito o su una chiavetta in sola lettura — dati, log e strumenti vengono creati in `%LOCALAPPDATA%\VideoDownloader` anziché far fallire l'avvio.
*   **Modalità ridotta**: se FFmpeg non è disponibile l'app si avvia comunque e lo segnala. I download continuano a funzionare scaricando un flusso già combinato; non sono possibili l'unione di video e audio separati né la conversione in MP3.

### Antivirus

`yt-dlp.exe` è un falso positivo storico di molti antivirus. Se dopo il download il file sparisce dal disco, l'app lo rileva e suggerisce di aggiungere un'esclusione per la cartella `tools/`.

### Reti aziendali con proxy

*   **Certificati**: se la tua organizzazione usa un proxy che ispeziona il traffico HTTPS, la verifica TLS viene agganciata all'**archivio certificati di Windows** tramite il pacchetto `truststore`, così la root CA aziendale è riconosciuta esattamente come nel browser. Senza questo pacchetto l'app funziona ugualmente, ma su una rete di questo tipo fallirebbe con un errore di certificato.
*   **Proxy**: un proxy configurato nelle impostazioni di Windows viene già usato automaticamente. Se invece la rete usa un file di configurazione automatica (**PAC**), l'app lo rileva e lo segnala: chiedi all'assistenza informatica indirizzo e porta del proxy, poi impostali nelle variabili d'ambiente `HTTP_PROXY` e `HTTPS_PROXY`.

### Se qualcosa non funziona

I messaggi di errore indicano la causa concreta — certificato TLS, proxy, limite di richieste, timeout, permessi negati, quarantena antivirus — insieme al percorso del file di log da consultare. Il dettaglio completo è sempre in `logs/app.log` (avvio e strumenti) e `logs/download.log` (download).

---

## 6. Licenza

Il codice sorgente di questo progetto è rilasciato sotto la [Licenza MIT](LICENSE).

Le informazioni e le attribuzioni relative ai componenti software di terze parti utilizzati (`yt-dlp` e `FFmpeg`) sono disponibili nel file [LICENSE-3RD-PARTY.md](LICENSE-3RD-PARTY.md).
