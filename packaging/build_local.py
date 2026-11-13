"""Costruisce l'installer dell'app sul computer in uso.

Uso (dalla radice del progetto, in un virtualenv con requirements-build.txt):
    python packaging/build_local.py

Produce in dist/:
  - Windows: QEMU-3dfx-Manager-<versione>-Setup.exe  (serve Inno Setup 6)
  - macOS:   QEMU-3dfx-Manager-<versione>-macos-<arch>.dmg
  - Linux:   QEMU-3dfx-Manager-<versione>-x86_64.AppImage

PyInstaller non compila per altri sistemi: per avere tutte le piattaforme
usa il workflow GitHub "Build app".
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from q3dfx import __version__  # noqa: E402


def run(*cmd: str) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    os.chdir(ROOT)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "packaging/q3dfx.spec")
    system = platform.system()
    if system == "Windows":
        iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
        if not Path(iscc).exists():
            sys.exit("Inno Setup 6 non trovato: installalo da jrsoftware.org "
                     "(la cartella dist\\QEMU-3dfx Manager\\ e' comunque pronta).")
        run(iscc, f"/DAppVersion={__version__}", r"packaging\windows\installer.iss")
    elif system == "Darwin":
        arch = "arm64" if platform.machine() == "arm64" else "x64"
        run("bash", "packaging/macos/make_dmg.sh", __version__, arch)
    else:
        run("bash", "packaging/linux/make_appimage.sh", __version__)
    print("\nFatto: guarda nella cartella dist/")


if __name__ == "__main__":
    main()
