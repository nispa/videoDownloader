# Video & Audio Downloader (yt-dlp & FFmpeg)

🇮🇹 [Leggi la documentazione in Italiano](README.it.md)

A modern, lightweight, standalone Windows application to download videos or extract high-quality audio (MP3) from YouTube and over 1,400 other supported platforms.

The program automatically handles the downloading and updating of third-party dependencies (`yt-dlp` and `ffmpeg`), stores settings in a local SQLite database, separates logs, and features instant local URL validation.

---

## ⚡ Quick Setup & Launcher (Windows Batch)

To make installation and usage extremely simple, the project contains two ready-to-use batch scripts in the root folder:

*   **`setup.bat`**: Automatically configures the Python virtual environment (`.venv`), upgrades `pip`, installs all dependencies from `requirements.txt`, and runs the initial download of support binaries (`yt-dlp.exe`, `ffmpeg.exe`, and `ffprobe.exe`).
*   **`run.bat`**: A convenient interactive menu script from which you can do everything:
    1. Start the Graphical User Interface (GUI).
    2. Start the Command Line Interface (CLI).
    3. Compile the app into a standalone executable (`VideoDownloader.exe`).
    4. Run or update the complete setup.
    5. Exit.

> [!NOTE]
> If you run `run.bat` before setting up, the script will automatically detect that the `.venv` folder is missing and run `setup.bat` first.

---


## Project Structure

```
c:\lavori\video-downloader\
├── tools/                  # Support binaries (yt-dlp.exe, ffmpeg.exe, ffprobe.exe)
├── data/                   # SQLite database (downloader.db)
├── logs/                   # Log folder (app.log and download.log)
├── downloads/              # Default downloads directory
├── src/                    # Python source code
│   ├── gui.py              # Graphical User Interface (GUI using CustomTkinter)
│   ├── main.py             # Command Line Interface (CLI)
│   ├── downloader.py       # Download engine and metadata extraction
│   ├── bootstrapper.py     # Tool manager and auto-updater
│   ├── database.py         # SQLite DB config and dynamic path helper
│   └── clipboard.py        # Windows Clipboard API integration
├── VideoDownloader.exe     # Compiled standalone application (root)
├── build_exe.py            # Compilation script using PyInstaller
└── requirements.txt        # Python dependencies
```

---

## 1. Desktop GUI (Recommended)

The desktop graphical interface is built with `customtkinter` with an elegant, responsive dark theme. It handles processes asynchronously (multi-threading) to prevent the window from freezing during downloads.

### How to run it:
- **Standalone executable**: Double-click **`VideoDownloader.exe`** in the project root.
- **From source (Development)**: Run the following command in your terminal:
  ```powershell
  .venv\Scripts\python src/gui.py
  ```

### Main GUI Features:
*   **Clipboard Auto-detect**: On startup, the application detects if there is a valid URL in your clipboard and automatically pastes it. You can also click the *Paste* button to read from the clipboard at any time.
*   **Background Metadata Extraction**: When you input a supported URL, the app extracts metadata in a background thread to show the Title, Uploader, and Duration before you start the download.
*   **Instant URL Validation**: If you input an unsupported URL, the app alerts you immediately without launching background subprocesses, checking against a local SQLite table containing over 1,480 supported extractors.
*   **Custom Downloads Folder**: Change your downloads directory using a native file explorer. Your choice is saved in the SQLite database and remembered across sessions.

---

## 2. Command Line Interface (CLI)

If you prefer a keyboard-driven, minimal interface, you can run the interactive CLI script, which features colored terminal output.

### How to run it:
Run the following command in your terminal:
```powershell
.venv\Scripts\python src/main.py
```

### CLI Features:
*   **Clipboard Integration**: If a link is detected in the clipboard, you can press **ENTER** to select it immediately.
*   **Interactive Menu**:
    1. *Download Video / Audio from Link*: Download as high-quality Video (MP4) or Audio (MP3).
    2. *Configure download folder*: Manually enter or paste a new target directory.
    3. *Exit*: Close the app.
*   **Live Text Progress Bar**: Displays progress percentage, download speed, and estimated time of arrival (ETA) in real time.

---

## 3. Dedicated Logs

Logs are separated into two distinct files inside the `logs/` folder to make inspection easier:
1.  **`app.log`**: Tracks system activities on startup, bootstrapper actions, online version checks, and updates.
2.  **`download.log`**: Records download engine events, URLs processed, raw commands sent to `yt-dlp.exe`, FFmpeg conversions, and errors.

---

## 4. How to Compile the App to EXE

To bundle the Python scripts in `src/` into a single standalone `VideoDownloader.exe` in the root folder, make sure the application is closed and run:

```powershell
.venv\Scripts\python build_exe.py
```

The script will package the GUI in `--noconsole` mode (no black command window on startup), move the final EXE to the root directory, and clean up all temporary build files.

---

## 5. License

The source code of this project is licensed under the [MIT License](LICENSE).

Third-party software assets (`yt-dlp` and `FFmpeg`) are subject to their respective licenses. Details and attributions can be found in the [LICENSE-3RD-PARTY.md](LICENSE-3RD-PARTY.md) file.
