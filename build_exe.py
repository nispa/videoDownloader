import os
import subprocess
import shutil
import sys

def main():
    print("=== Starting VideoDownloader build ===")

    # Find the pyinstaller executable inside the local venv
    venv_pyinstaller = os.path.join(".venv", "Scripts", "pyinstaller.exe")
    if not os.path.exists(venv_pyinstaller):
        print("pyinstaller not found in the venv. Falling back to the global command...")
        venv_pyinstaller = "pyinstaller"

    cmd = [
        venv_pyinstaller,
        "--noconsole",
        "--onefile",
        "--name=VideoDownloader",
        "--paths=src",
    ]

    # Bundle the logo so the single-file exe shows it without external files.
    # PyInstaller's --add-data separator is ';' on Windows.
    if os.path.isfile("logo.png"):
        cmd.append("--add-data=logo.png;.")

    cmd.append("src/gui.py")

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n=== Build completed successfully! ===")
        # Move the executable to the project root
        exe_src = os.path.join("dist", "VideoDownloader.exe")
        exe_dest = "VideoDownloader.exe"

        if os.path.exists(exe_src):
            if os.path.exists(exe_dest):
                try:
                    os.remove(exe_dest)
                except Exception as e:
                    print(f"Warning: could not remove the old executable (it may be running): {e}")
                    sys.exit(1)
            try:
                shutil.move(exe_src, exe_dest)
                print(f"Executable moved to the project root: {os.path.abspath(exe_dest)}")
            except Exception as e:
                print(f"Error while moving the executable: {e}")
                sys.exit(1)

            # Clean up temporary build files
            print("\nCleaning up temporary build files...")
            try:
                if os.path.exists("build"):
                    shutil.rmtree("build")
                if os.path.exists("dist"):
                    shutil.rmtree("dist")
                spec_file = "VideoDownloader.spec"
                if os.path.exists(spec_file):
                    os.remove(spec_file)
                print("Cleanup completed successfully!")
            except Exception as e:
                print(f"Warning: error while cleaning up temporary files: {e}")
        else:
            print("Error: could not find the generated executable in the 'dist/' folder.")
            sys.exit(1)
    else:
        print(f"\nError during the build. Exit code: {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
