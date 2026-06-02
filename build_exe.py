import os
import subprocess
import shutil
import sys

def main():
    print("=== Avvio Compilazione VideoDownloader ===")
    
    # Trova il percorso dell'eseguibile pyinstaller nel venv locale
    venv_pyinstaller = os.path.join(".venv", "Scripts", "pyinstaller.exe")
    if not os.path.exists(venv_pyinstaller):
        print("Rilevamento pyinstaller nel venv fallito. Provo con il comando globale...")
        venv_pyinstaller = "pyinstaller"
        
    cmd = [
        venv_pyinstaller,
        "--noconsole",
        "--onefile",
        "--name=VideoDownloader",
        "--paths=src",
        "src/gui.py"
    ]
    
    print(f"Esecuzione comando: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n=== Compilazione completata con successo! ===")
        # Sposta l'eseguibile nella root del progetto
        exe_src = os.path.join("dist", "VideoDownloader.exe")
        exe_dest = "VideoDownloader.exe"
        
        if os.path.exists(exe_src):
            if os.path.exists(exe_dest):
                try:
                    os.remove(exe_dest)
                except Exception as e:
                    print(f"Attenzione: Impossibile rimuovere il vecchio eseguibile (potrebbe essere in esecuzione): {e}")
                    sys.exit(1)
            try:
                shutil.move(exe_src, exe_dest)
                print(f"Eseguibile spostato nella root del progetto: {os.path.abspath(exe_dest)}")
            except Exception as e:
                print(f"Errore durante lo spostamento del file eseguibile: {e}")
                sys.exit(1)
            
            # Pulizia file temporanei di build
            print("\nPulizia dei file temporanei di build in corso...")
            try:
                if os.path.exists("build"):
                    shutil.rmtree("build")
                if os.path.exists("dist"):
                    shutil.rmtree("dist")
                spec_file = "VideoDownloader.spec"
                if os.path.exists(spec_file):
                    os.remove(spec_file)
                print("Pulizia completata con successo!")
            except Exception as e:
                print(f"Attenzione: Errore durante la pulizia dei file temporanei: {e}")
        else:
            print("Errore: Impossibile trovare l'eseguibile generato nella cartella 'dist/'.")
            sys.exit(1)
    else:
        print(f"\nErrore durante la compilazione. Codice di uscita: {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
