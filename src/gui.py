import os
import sys
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk

# Add the parent directory to sys.path for imports when run as a script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import database
import bootstrapper
import i18n
from i18n import tr
from clipboard import get_clipboard_url
from downloader import VideoDownloader

# Global CustomTkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Main window
        self.title("Video & Audio Downloader")
        self.geometry("640x620")
        self.minsize(640, 620)
        self.resizable(False, False)

        # Center the window on screen
        self.center_window()

        # Initialize the backend modules
        self.downloader = VideoDownloader()

        # State variables
        self.downloading = False
        self.download_mode = "video"  # "video" or "audio"
        self.analyzing = False
        self.info_state = "ready"  # ready | analyzing | unsupported | error | shown

        # Available languages: {code: display name} and the reverse map
        self.languages = i18n.available_languages()
        self.lang_by_name = {name: code for code, name in self.languages.items()}

        # Build the UI
        self.create_widgets()

        # Run the bootstrapper in the background to avoid blocking the UI at startup
        self.run_bootstrapper_async()

    def center_window(self):
        self.update_idletasks()
        width = 640
        height = 620
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        # Main frame with padding
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # 1. Header frame (title, subtitle and language selector)
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(15, 10))

        self.header_text_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.header_text_frame.pack(side="left", fill="x", expand=True)

        self.title_label = ctk.CTkLabel(
            self.header_text_frame,
            text="VIDEO & AUDIO DOWNLOADER",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#00ADB5"
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            self.header_text_frame,
            text=tr("subtitle"),
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#EEEEEE"
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))

        # Language selector (top right). Languages come from the JSON files in lang/
        self.lang_selector = ctk.CTkOptionMenu(
            self.header_frame,
            values=list(self.languages.values()),
            command=self.change_language,
            width=110,
            height=28,
            fg_color="#393E46",
            button_color="#00ADB5",
            button_hover_color="#393E46",
            font=ctk.CTkFont(size=12)
        )
        self.lang_selector.pack(side="right", anchor="n")
        current_name = self.languages.get(i18n.current_language())
        if current_name:
            self.lang_selector.set(current_name)

        # Divider
        self.divider = ctk.CTkFrame(self.main_frame, height=2, fg_color="#393E46")
        self.divider.pack(fill="x", padx=20, pady=5)

        # 2. Input frame (URL entry and paste button)
        self.input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=20, pady=10)

        self.url_label = ctk.CTkLabel(
            self.input_frame,
            text=tr("url_label"),
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        )
        self.url_label.pack(anchor="w", pady=(0, 5))

        self.url_entry_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.url_entry_frame.pack(fill="x")

        self.url_entry = ctk.CTkEntry(
            self.url_entry_frame,
            placeholder_text=tr("url_placeholder"),
            height=35,
            font=ctk.CTkFont(size=12)
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.url_entry.bind("<KeyRelease>", self.on_url_modified)

        self.paste_button = ctk.CTkButton(
            self.url_entry_frame,
            text=tr("paste"),
            width=80,
            height=35,
            font=ctk.CTkFont(weight="bold"),
            fg_color="#393E46",
            hover_color="#00ADB5",
            command=self.paste_from_clipboard
        )
        self.paste_button.pack(side="right")

        # 3. Video info frame (shown after analysis)
        self.info_frame = ctk.CTkFrame(self.main_frame, fg_color="#222831", corner_radius=10, height=100)
        self.info_frame.pack(fill="x", padx=20, pady=10)
        self.info_frame.pack_propagate(False)

        self.info_status_label = ctk.CTkLabel(
            self.info_frame,
            text=tr("info_ready"),
            font=ctk.CTkFont(slant="italic"),
            text_color="#888888"
        )
        self.info_status_label.pack(expand=True)

        # Info widgets (initially hidden)
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

        # 4. Format and destination folder frame
        self.settings_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.settings_frame.pack(fill="x", padx=20, pady=10)

        # Format column
        self.format_subframe = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.format_subframe.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.format_label = ctk.CTkLabel(
            self.format_subframe,
            text=tr("format_label"),
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

        # Destination folder column
        self.path_subframe = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.path_subframe.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.path_label = ctk.CTkLabel(
            self.path_subframe,
            text=tr("path_label"),
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
            text=tr("browse"),
            width=60,
            height=30,
            fg_color="#393E46",
            hover_color="#00ADB5",
            command=self.browse_directory
        )
        self.browse_button.pack(side="right")

        # 4b. Cookie / authentication frame (for Facebook, Instagram, etc.)
        self.cookie_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.cookie_frame.pack(fill="x", padx=20, pady=(0, 5))

        # Cookie browser column
        self.cookie_browser_subframe = ctk.CTkFrame(self.cookie_frame, fg_color="transparent")
        self.cookie_browser_subframe.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.cookie_label = ctk.CTkLabel(
            self.cookie_browser_subframe,
            text=tr("cookie_browser_label"),
            font=ctk.CTkFont(weight="bold", size=13)
        )
        self.cookie_label.pack(anchor="w", pady=(0, 5))

        self.cookie_selector = ctk.CTkOptionMenu(
            self.cookie_browser_subframe,
            values=[tr("cookie_none"), "Edge", "Chrome", "Firefox", "Opera", "Brave"],
            command=self.change_cookie_browser,
            fg_color="#393E46",
            button_color="#00ADB5",
            button_hover_color="#393E46",
            font=ctk.CTkFont(size=12)
        )
        self.cookie_selector.pack(fill="x", pady=2)
        self.update_cookie_selector_display()

        # cookies.txt file column (alternative to the browser, takes priority)
        self.cookie_file_subframe = ctk.CTkFrame(self.cookie_frame, fg_color="transparent")
        self.cookie_file_subframe.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.cookie_file_label = ctk.CTkLabel(
            self.cookie_file_subframe,
            text=tr("cookie_file_label"),
            font=ctk.CTkFont(weight="bold", size=13)
        )
        self.cookie_file_label.pack(anchor="w", pady=(0, 5))

        self.cookie_file_selection_frame = ctk.CTkFrame(self.cookie_file_subframe, fg_color="transparent")
        self.cookie_file_selection_frame.pack(fill="x")

        self.cookie_file_entry = ctk.CTkEntry(
            self.cookie_file_selection_frame,
            height=30,
            state="disabled",
            font=ctk.CTkFont(size=11)
        )
        self.cookie_file_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.update_cookie_file_display()

        self.cookie_browse_button = ctk.CTkButton(
            self.cookie_file_selection_frame,
            text=tr("browse"),
            width=60,
            height=30,
            fg_color="#393E46",
            hover_color="#00ADB5",
            command=self.browse_cookie_file
        )
        self.cookie_browse_button.pack(side="left", padx=(0, 5))

        self.cookie_clear_button = ctk.CTkButton(
            self.cookie_file_selection_frame,
            text="✕",
            width=30,
            height=30,
            fg_color="#393E46",
            hover_color="#B00020",
            command=self.clear_cookie_file
        )
        self.cookie_clear_button.pack(side="right")

        # 5. Download and progress frame (bottom)
        self.progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=20, pady=(15, 10))

        self.download_button = ctk.CTkButton(
            self.progress_frame,
            text=tr("download_now"),
            height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#00ADB5",
            hover_color="#393E46",
            command=self.start_download
        )
        self.download_button.pack(fill="x", pady=(0, 10))

        # Progress bar and stats
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=10)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.pack_forget()  # Hidden until a download starts

        self.stats_label = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#00ADB5"
        )
        self.stats_label.pack(fill="x")

        # Overlay shown while the initial bootstrap is running
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
            text=tr("boot_status"),
            font=ctk.CTkFont(size=14)
        )
        self.boot_status.pack(expand=True, pady=(0, 100))

        self.boot_progress = ctk.CTkProgressBar(self.boot_overlay, width=300, height=8)
        self.boot_progress.pack(expand=True, pady=(0, 150))
        self.boot_progress.configure(mode="indeterminate")
        self.boot_progress.start()

    # --- Language handling ---

    def change_language(self, display_name: str):
        """Switch the UI language and persist the choice."""
        code = self.lang_by_name.get(display_name)
        if not code:
            return
        database.set_setting("language", code)
        i18n.load_language(code)
        self.apply_language()

    def apply_language(self):
        """Refresh every static label with the current language strings."""
        self.subtitle_label.configure(text=tr("subtitle"))
        self.url_label.configure(text=tr("url_label"))
        self.url_entry.configure(placeholder_text=tr("url_placeholder"))
        self.paste_button.configure(text=tr("paste"))
        self.format_label.configure(text=tr("format_label"))
        self.path_label.configure(text=tr("path_label"))
        self.browse_button.configure(text=tr("browse"))
        self.cookie_label.configure(text=tr("cookie_browser_label"))
        self.cookie_file_label.configure(text=tr("cookie_file_label"))
        self.cookie_browse_button.configure(text=tr("browse"))
        self.boot_status.configure(text=tr("boot_status"))
        if not self.downloading:
            self.download_button.configure(text=tr("download_now"))

        # Rebuild the cookie browser selector so the "none" entry is translated
        self.cookie_selector.configure(
            values=[tr("cookie_none"), "Edge", "Chrome", "Firefox", "Opera", "Brave"]
        )
        self.update_cookie_selector_display()

        # Refresh the info status text only when it shows a static message
        if self.info_state in ("ready", "analyzing", "unsupported", "error"):
            colors = {
                "ready": "#888888",
                "analyzing": "#00ADB5",
                "unsupported": "#FF9F1C",
                "error": "red"
            }
            self.info_status_label.configure(
                text=tr(f"info_{self.info_state}"),
                text_color=colors[self.info_state]
            )

    # --- Bootstrap handling ---

    def run_bootstrapper_async(self):
        """Run the bootstrapper in a separate thread to avoid blocking the UI."""
        def boot_task():
            # Bootstrap the local binaries
            success = bootstrapper.run_bootstrap()
            self.after(0, self.on_boot_complete, success)

        threading.Thread(target=boot_task, daemon=True).start()

    def on_boot_complete(self, success: bool):
        """Called on the main thread when the bootstrap finishes."""
        self.boot_progress.stop()
        if success:
            # Hide the overlay
            self.boot_overlay.place_forget()
            # Check the clipboard for a link
            self.check_clipboard_on_start()
        else:
            self.boot_status.configure(text=tr("boot_error_status"), text_color="red")
            messagebox.showerror(tr("boot_error_title"), tr("boot_error_body"))

    # --- Clipboard and input ---

    def check_clipboard_on_start(self):
        """At startup, if a valid URL is in the clipboard, fill it in automatically."""
        url = get_clipboard_url()
        if url:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
            self.analyze_url_async(url)

    def paste_from_clipboard(self):
        """Read the clipboard and paste the text into the URL entry."""
        url = get_clipboard_url()
        if url:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
            self.analyze_url_async(url)
        else:
            # Try pasting any text even if it is not a perfect URL
            try:
                text = self.clipboard_get()
                if text:
                    self.url_entry.delete(0, "end")
                    self.url_entry.insert(0, text.strip())
                    self.analyze_url_async(text.strip())
            except Exception:
                messagebox.showwarning(tr("msg_warning_title"), tr("msg_no_clipboard"))

    def on_url_modified(self, event):
        """Detect when the user pastes or edits the URL manually."""
        url = self.url_entry.get().strip()
        # If it looks like a URL, analyze it
        if url.startswith("http://") or url.startswith("https://"):
            self.analyze_url_async(url)

    # --- Background link analysis ---

    def analyze_url_async(self, url: str):
        """Start the thread that extracts the video info."""
        if self.analyzing or self.downloading:
            return

        # Clear the previous info widgets and show the status
        self.info_status_label.pack(expand=True)
        self.info_state = "analyzing"
        self.info_status_label.configure(text=tr("info_analyzing"), text_color="#00ADB5")
        self.video_title_label.pack_forget()
        self.video_author_label.pack_forget()
        self.video_duration_label.pack_forget()

        # Check whether the URL is supported before starting the analysis
        if not self.downloader.is_url_supported(url):
            self.info_state = "unsupported"
            self.info_status_label.configure(text=tr("info_unsupported"), text_color="#FF9F1C")
            return

        self.analyzing = True

        def analyze_task():
            info = self.downloader.get_info(url)
            self.after(0, self.on_analysis_complete, info)

        threading.Thread(target=analyze_task, daemon=True).start()

    def on_analysis_complete(self, info: dict | None):
        self.analyzing = False
        if info:
            # Hide the status label and show the widgets with the video details
            self.info_state = "shown"
            self.info_status_label.pack_forget()

            # Video title (truncated if too long)
            title = info["title"]
            if len(title) > 65:
                title = title[:62] + "..."
            self.video_title_label.configure(text=title)
            self.video_title_label.pack(anchor="w", padx=15, pady=(15, 2))

            self.video_author_label.configure(text=tr("info_author", uploader=info["uploader"]))
            self.video_author_label.pack(anchor="w", padx=15, pady=2)

            self.video_duration_label.configure(
                text=tr("info_duration", duration=info["duration"], extractor=info["extractor"])
            )
            self.video_duration_label.pack(anchor="w", padx=15, pady=(2, 15))
        else:
            self.info_state = "error"
            self.info_status_label.configure(text=tr("info_error"), text_color="red")

    # --- Settings handling ---

    def change_format(self, value):
        if value == "Video (MP4)":
            self.download_mode = "video"
        else:
            self.download_mode = "audio"

    def change_cookie_browser(self, value: str):
        """Save the chosen cookie browser to the DB."""
        db_value = "none" if value == tr("cookie_none") else value.lower()
        database.set_setting("cookie_browser", db_value)

    def update_cookie_selector_display(self):
        """Show the saved cookie browser in the selector."""
        saved_browser = database.get_setting("cookie_browser", "none")
        if saved_browser and saved_browser != "none":
            self.cookie_selector.set(saved_browser.capitalize())
        else:
            self.cookie_selector.set(tr("cookie_none"))

    def update_cookie_file_display(self):
        """Show the configured cookies file path in the entry."""
        path = database.get_setting("cookie_file", "")
        self.cookie_file_entry.configure(state="normal")
        self.cookie_file_entry.delete(0, "end")
        if path:
            self.cookie_file_entry.insert(0, path)
        self.cookie_file_entry.configure(state="disabled")

    def browse_cookie_file(self):
        """Open the file picker for the cookies.txt file and save the choice to the DB."""
        file_path = filedialog.askopenfilename(
            title=tr("cookie_file_dialog_title"),
            filetypes=[(tr("cookie_file_dialog_text"), "*.txt"), (tr("cookie_file_dialog_all"), "*.*")]
        )
        if file_path:
            database.set_setting("cookie_file", os.path.abspath(file_path))
            self.update_cookie_file_display()

    def clear_cookie_file(self):
        """Remove the configured cookies file (falls back to browser cookies)."""
        database.set_setting("cookie_file", "")
        self.update_cookie_file_display()

    def update_path_display(self):
        """Show the current download directory in the destination entry."""
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, self.downloader.get_download_path())
        self.path_entry.configure(state="disabled")

    def browse_directory(self):
        """Open the folder picker and save the choice to the DB."""
        directory = filedialog.askdirectory(initialdir=self.downloader.get_download_path())
        if directory:
            database.set_setting("download_path", os.path.abspath(directory))
            self.update_path_display()

    # --- Download process ---

    def start_download(self):
        """Start the download thread."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(tr("msg_warning_title"), tr("msg_no_url"))
            return

        if self.downloading:
            return

        # Check whether the URL is supported
        if not self.downloader.is_url_supported(url):
            proceed = messagebox.askyesno(tr("msg_unsupported_title"), tr("msg_unsupported_body"))
            if not proceed:
                return

        self.downloading = True
        self.set_ui_state("downloading")

        # Show the progress bar and initialize the stats
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.set(0.0)
        self.stats_label.configure(text=tr("stats_init"))

        def download_task():
            # Blocking call to the downloader
            success = self.downloader.download(
                url,
                mode=self.download_mode,
                progress_callback=self.progress_callback_bridge
            )
            self.after(0, self.on_download_complete, success)

        threading.Thread(target=download_task, daemon=True).start()

    def progress_callback_bridge(self, percentage: float, speed: str, eta: str, status: str):
        """Invoked from the background thread. Forward the data thread-safely to the main thread."""
        self.after(0, self.update_download_ui, percentage, speed, eta, status)

    def update_download_ui(self, percentage: float, speed: str, eta: str, status: str):
        """Update the UI widgets with the download progress."""
        self.progress_bar.set(percentage / 100.0)

        # Format the stats. The status tokens ("Post-Processing", "Completato",
        # "Errore") are fixed internal codes emitted by the downloader.
        if "Post-Processing" in status:
            stats_text = tr("stats_phase", status=status)
        elif "Completato" in status:
            stats_text = tr("stats_completed")
        elif "Errore" in status:
            stats_text = tr("stats_error", status=status)
        else:
            stats_text = tr("stats_progress", percent=percentage, speed=speed, eta=eta, status=status)

        self.stats_label.configure(text=stats_text)

    def on_download_complete(self, success: bool):
        """Called on the main thread when the download finishes."""
        self.downloading = False
        self.set_ui_state("normal")

        if success:
            self.progress_bar.set(1.0)
            self.stats_label.configure(text=tr("done_label"), text_color="green")
            messagebox.showinfo(tr("msg_success_title"), tr("msg_success_body"))
        else:
            self.progress_bar.set(0.0)
            self.stats_label.configure(text=tr("fail_label"), text_color="red")
            messagebox.showerror(tr("msg_error_title"), tr("msg_error_body"))

    def set_ui_state(self, state: str):
        """Enable or disable the UI elements based on the download state."""
        if state == "downloading":
            self.url_entry.configure(state="disabled")
            self.paste_button.configure(state="disabled")
            self.browse_button.configure(state="disabled")
            self.format_selector.configure(state="disabled")
            self.cookie_selector.configure(state="disabled")
            self.cookie_browse_button.configure(state="disabled")
            self.cookie_clear_button.configure(state="disabled")
            self.lang_selector.configure(state="disabled")
            self.download_button.configure(state="disabled", text=tr("downloading"), fg_color="#393E46")
        else:
            self.url_entry.configure(state="normal")
            self.paste_button.configure(state="normal")
            self.browse_button.configure(state="normal")
            self.format_selector.configure(state="normal")
            self.cookie_selector.configure(state="normal")
            self.cookie_browse_button.configure(state="normal")
            self.cookie_clear_button.configure(state="normal")
            self.lang_selector.configure(state="normal")
            self.download_button.configure(state="normal", text=tr("download_now"), fg_color="#00ADB5")

if __name__ == "__main__":
    app = DownloaderApp()
    app.mainloop()
