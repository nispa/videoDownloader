import os
import sys
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk

# Aggiunge la directory superiore a sys.path per gli import se eseguito come script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import database
import bootstrapper
from clipboard import get_clipboard_url
from downloader import VideoDownloader

# Configura l'estetica generale di CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Finestra principale
        self.title("Video & Audio Downloader")
        self.geometry("640x550")
        self.minsize(640, 550)
        self.resizable(False, False)
        
        # Centra la finestra sullo schermo
        self.center_window()
        
        # Inizializza i moduli di backend
        self.downloader = VideoDownloader()
        
        # Variabili di stato
        self.downloading = False
        self.download_mode = "video"  # "video" o "audio"
        self.analyzing = False
        
        # Costruisce la UI
        self.create_widgets()
        
        # Avvia il bootstrapper in background per non bloccare l'interfaccia all'avvio
        self.run_bootstrapper_async()

    def center_window(self):
        self.update_idletasks()
        width = 640
        height = 550
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        # Frame Principale con padding
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 1. Header Frame (Titolo e Descrizione)
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="VIDEO & AUDIO DOWNLOADER", 
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#00ADB5"
        )
        self.title_label.pack(anchor="w")
        
        self.subtitle_label = ctk.CTkLabel(
            self.header_frame, 
            text="Scarica video e musica da YouTube ed altre piattaforme", 
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#EEEEEE"
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))
        
        # Dividitore
        self.divider = ctk.CTkFrame(self.main_frame, height=2, fg_color="#393E46")
        self.divider.pack(fill="x", padx=20, pady=5)
        
        # 2. Input Frame (URL Entry e Incolla)
        self.input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=20, pady=10)
        
        self.url_label = ctk.CTkLabel(
            self.input_frame, 
            text="Inserisci il link del video:", 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        )
        self.url_label.pack(anchor="w", pady=(0, 5))
        
        self.url_entry_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.url_entry_frame.pack(fill="x")
        
        self.url_entry = ctk.CTkEntry(
            self.url_entry_frame, 
            placeholder_text="https://www.youtube.com/watch?...",
            height=35,
            font=ctk.CTkFont(size=12)
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.url_entry.bind("<KeyRelease>", self.on_url_modified)
        
        self.paste_button = ctk.CTkButton(
            self.url_entry_frame, 
            text="Incolla", 
            width=80, 
            height=35,
            font=ctk.CTkFont(weight="bold"),
            fg_color="#393E46",
            hover_color="#00ADB5",
            command=self.paste_from_clipboard
        )
        self.paste_button.pack(side="right")
        
        # 3. Video Info Frame (Mostrato dopo l'analisi)
        self.info_frame = ctk.CTkFrame(self.main_frame, fg_color="#222831", corner_radius=10, height=100)
        self.info_frame.pack(fill="x", padx=20, pady=10)
        self.info_frame.pack_propagate(False)
        
        self.info_status_label = ctk.CTkLabel(
            self.info_frame, 
            text="Pronto per analizzare il link...", 
            font=ctk.CTkFont(slant="italic"),
            text_color="#888888"
        )
        self.info_status_label.pack(expand=True)
        
        # Widget delle informazioni (nascosti inizialmente)
        self.video_title_label = ctk.CTkLabel(
            self.info_frame, 
            text="", 
            font=ctk.CTkFont(weight="bold", size=13),
            anchor="w",
            text_color="#00ADB5"
        )
        self.video_author_label = ctk.CTkLabel(
            self.info_frame, 
            text="", 
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.video_duration_label = ctk.CTkLabel(
            self.info_frame, 
            text="", 
            font=ctk.CTkFont(size=11),
            anchor="w",
            text_color="#888888"
        )
        
        # 4. Formato e Cartella Frame
        self.settings_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.settings_frame.pack(fill="x", padx=20, pady=10)
        
        # Colonna Formato
        self.format_subframe = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.format_subframe.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.format_label = ctk.CTkLabel(
            self.format_subframe, 
            text="Formato di download:", 
            font=ctk.CTkFont(weight="bold", size=13)
        )
        self.format_label.pack(anchor="w", pady=(0, 5))
        
        self.format_selector = ctk.CTkSegmentedButton(
            self.format_subframe, 
            values=["Video (MP4)", "Audio (MP3)"],
            command=self.change_format
        )
        self.format_selector.set("Video (MP4)")
        self.format_selector.pack(fill="x", pady=2)
        
        # Colonna Cartella di Destinazione
        self.path_subframe = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.path_subframe.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        self.path_label = ctk.CTkLabel(
            self.path_subframe, 
            text="Cartella di salvataggio:", 
            font=ctk.CTkFont(weight="bold", size=13)
        )
        self.path_label.pack(anchor="w", pady=(0, 5))
        
        self.path_selection_frame = ctk.CTkFrame(self.path_subframe, fg_color="transparent")
        self.path_selection_frame.pack(fill="x")
        
        self.path_entry = ctk.CTkEntry(
            self.path_selection_frame, 
            height=30,
            state="disabled",
            font=ctk.CTkFont(size=11)
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.update_path_display()
        
        self.browse_button = ctk.CTkButton(
            self.path_selection_frame, 
            text="Sfoglia", 
            width=60, 
            height=30,
            fg_color="#393E46",
            hover_color="#00ADB5",
            command=self.browse_directory
        )
        self.browse_button.pack(side="right")
        
        # 5. Download e Progresso Frame (In basso)
        self.progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        self.download_button = ctk.CTkButton(
            self.progress_frame, 
            text="SCARICA ORA", 
            height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#00ADB5",
            hover_color="#393E46",
            command=self.start_download
        )
        self.download_button.pack(fill="x", pady=(0, 10))
        
        # Barra e statistiche progresso
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=10)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.pack_forget() # Nascosta fino all'avvio del download
        
        self.stats_label = ctk.CTkLabel(
            self.progress_frame, 
            text="", 
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#00ADB5"
        )
        self.stats_label.pack(fill="x")
        
        # Overlay per lo stato di Bootstrapping iniziale
        self.boot_overlay = ctk.CTkFrame(self, fg_color="#222831")
        self.boot_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        self.boot_title = ctk.CTkLabel(
            self.boot_overlay, 
            text="Video & Audio Downloader", 
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#00ADB5"
        )
        self.boot_title.pack(expand=True, pady=(150, 0))
        
        self.boot_status = ctk.CTkLabel(
            self.boot_overlay, 
            text="Inizializzazione strumenti locali in corso...", 
            font=ctk.CTkFont(size=14)
        )
        self.boot_status.pack(expand=True, pady=(0, 100))
        
        self.boot_progress = ctk.CTkProgressBar(self.boot_overlay, width=300, height=8)
        self.boot_progress.pack(expand=True, pady=(0, 150))
        self.boot_progress.configure(mode="indeterminate")
        self.boot_progress.start()

    # --- Gestione del Bootstrapping ---
    
    def run_bootstrapper_async(self):
        """Esegue il bootstrapper in un thread separato per evitare blocchi."""
        def boot_task():
            # Esegue il bootstrap dei binari
            success = bootstrapper.run_bootstrap()
            self.after(0, self.on_boot_complete, success)
            
        threading.Thread(target=boot_task, daemon=True).start()

    def on_boot_complete(self, success: bool):
        """Callback eseguita sul thread principale quando il bootstrap è terminato."""
        self.boot_progress.stop()
        if success:
            # Nasconde l'overlay
            self.boot_overlay.place_forget()
            # Controlla gli appunti per rilevare link
            self.check_clipboard_on_start()
        else:
            self.boot_status.configure(
                text="Errore: Impossibile scaricare o configurare gli strumenti di download.\nVerifica la connessione ad internet e riavvia il programma.",
                text_color="red"
            )
            messagebox.showerror(
                "Errore di Inizializzazione", 
                "Impossibile configurare gli strumenti locali (yt-dlp/ffmpeg).\nVerifica la connessione a Internet e riprova."
            )

    # --- Clipboard e Input ---
    
    def check_clipboard_on_start(self):
        """All'avvio, se rileva un URL valido negli appunti, lo inserisce automaticamente."""
        url = get_clipboard_url()
        if url:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
            self.analyze_url_async(url)

    def paste_from_clipboard(self):
        """Legge gli appunti e incolla il testo nell'input URL."""
        url = get_clipboard_url()
        if url:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
            self.analyze_url_async(url)
        else:
            # Tenta di incollare qualunque testo se non è un URL perfetto
            try:
                text = self.clipboard_get()
                if text:
                    self.url_entry.delete(0, "end")
                    self.url_entry.insert(0, text.strip())
                    self.analyze_url_async(text.strip())
            except Exception:
                messagebox.showwarning("Attenzione", "Nessun testo trovato negli appunti.")

    def on_url_modified(self, event):
        """Rileva quando l'utente incolla o modifica l'URL manualmente."""
        url = self.url_entry.get().strip()
        # Se assomiglia a un URL, lo analizza dopo una breve pausa o se cambia
        if url.startswith("http://") or url.startswith("https://"):
            # Per evitare troppe chiamate ravvicinate, avviamo l'analisi
            self.analyze_url_async(url)

    # --- Analisi del Link in Background ---
    
    def analyze_url_async(self, url: str):
        """Avvia il thread per estrarre le info sul video."""
        if self.analyzing or self.downloading:
            return
            
        # Pulisce i widget delle info precedenti e mostra lo stato
        self.info_status_label.pack(expand=True)
        self.info_status_label.configure(text="Analisi del link in corso...", text_color="#00ADB5")
        self.video_title_label.pack_forget()
        self.video_author_label.pack_forget()
        self.video_duration_label.pack_forget()
        
        # Verifica se l'URL è supportato prima di avviare il processo di analisi
        if not self.downloader.is_url_supported(url):
            self.info_status_label.configure(
                text="⚠️ Questo sito o URL potrebbe non essere supportato da yt-dlp.", 
                text_color="#FF9F1C"
            )
            return
            
        self.analyzing = True
        
        def analyze_task():
            info = self.downloader.get_info(url)
            self.after(0, self.on_analysis_complete, info)
            
        threading.Thread(target=analyze_task, daemon=True).start()

    def on_analysis_complete(self, info: dict | None):
        self.analyzing = False
        if info:
            # Nasconde la label di stato e mostra i widget con i dettagli del video
            self.info_status_label.pack_forget()
            
            # Titolo del video (troncato se troppo lungo)
            title = info["title"]
            if len(title) > 65:
                title = title[:62] + "..."
            self.video_title_label.configure(text=title)
            self.video_title_label.pack(anchor="w", padx=15, pady=(15, 2))
            
            self.video_author_label.configure(text=f"Canale/Autore: {info['uploader']}")
            self.video_author_label.pack(anchor="w", padx=15, pady=2)
            
            self.video_duration_label.configure(text=f"Durata: {info['duration']}  |  Piattaforma: {info['extractor']}")
            self.video_duration_label.pack(anchor="w", padx=15, pady=(2, 15))
        else:
            self.info_status_label.configure(text="Impossibile estrarre informazioni dal link.", text_color="red")

    # --- Gestione Impostazioni ---
    
    def change_format(self, value):
        if value == "Video (MP4)":
            self.download_mode = "video"
        else:
            self.download_mode = "audio"

    def update_path_display(self):
        """Aggiorna il percorso visualizzato nella entry di destinazione."""
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, self.downloader.get_download_path())
        self.path_entry.configure(state="disabled")

    def browse_directory(self):
        """Apre il selettore di cartella e salva la scelta nel DB."""
        directory = filedialog.askdirectory(initialdir=self.downloader.get_download_path())
        if directory:
            database.set_setting("download_path", os.path.abspath(directory))
            self.update_path_display()

    # --- Processo di Download ---
    
    def start_download(self):
        """Avvia il thread di download."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Attenzione", "Inserisci un link valido prima di iniziare.")
            return
            
        if self.downloading:
            return
            
        # Verifica se l'URL è supportato
        if not self.downloader.is_url_supported(url):
            proceed = messagebox.askyesno(
                "Sito non supportato", 
                "Questo sito o URL non sembra essere supportato ufficialmente da yt-dlp.\nVuoi comunque tentare il download usando l'estrattore generico?"
            )
            if not proceed:
                return
            
        self.downloading = True
        self.set_ui_state("downloading")
        
        # Mostra la barra di progresso e inizializza le statistiche
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.set(0.0)
        self.stats_label.configure(text="Inizializzazione download...")
        
        def download_task():
            # Chiamata bloccante al downloader
            success = self.downloader.download(
                url, 
                mode=self.download_mode, 
                progress_callback=self.progress_callback_bridge
            )
            self.after(0, self.on_download_complete, success)
            
        threading.Thread(target=download_task, daemon=True).start()

    def progress_callback_bridge(self, percentage: float, speed: str, eta: str, status: str):
        """Invocato dal thread in background. Passa i dati in modo thread-safe al thread principale."""
        self.after(0, self.update_download_ui, percentage, speed, eta, status)

    def update_download_ui(self, percentage: float, speed: str, eta: str, status: str):
        """Aggiorna i widget della UI con lo stato di avanzamento del download."""
        self.progress_bar.set(percentage / 100.0)
        
        # Formatta le statistiche
        if "Post-Processing" in status:
            stats_text = f"Fase: {status}"
        elif "Completato" in status:
            stats_text = "Completato!"
        elif "Errore" in status:
            stats_text = f"Errore: {status}"
        else:
            stats_text = f"{percentage:5.1f}% | Velocità: {speed} | ETA: {eta} | {status}"
            
        self.stats_label.configure(text=stats_text)

    def on_download_complete(self, success: bool):
        """Callback sul thread principale al termine del download."""
        self.downloading = False
        self.set_ui_state("normal")
        
        if success:
            self.progress_bar.set(1.0)
            self.stats_label.configure(text="Download completato con successo!", text_color="green")
            messagebox.showinfo("Successo", "Download e conversione completati con successo!")
        else:
            self.progress_bar.set(0.0)
            self.stats_label.configure(text="Errore durante il download.", text_color="red")
            messagebox.showerror("Errore", "Si è verificato un errore durante il download o il post-processing. Controlla il log.")

    def set_ui_state(self, state: str):
        """Disabilita o abilita gli elementi della UI in base allo stato del download."""
        if state == "downloading":
            self.url_entry.configure(state="disabled")
            self.paste_button.configure(state="disabled")
            self.browse_button.configure(state="disabled")
            self.format_selector.configure(state="disabled")
            self.download_button.configure(state="disabled", text="DOWNLOAD IN CORSO...", fg_color="#393E46")
        else:
            self.url_entry.configure(state="normal")
            self.paste_button.configure(state="normal")
            self.browse_button.configure(state="normal")
            self.format_selector.configure(state="normal")
            self.download_button.configure(state="normal", text="SCARICA ORA", fg_color="#00ADB5")

if __name__ == "__main__":
    app = DownloaderApp()
    app.mainloop()
