# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller per QEMU-3dfx Manager.
# Uso (dalla radice del progetto):  pyinstaller --noconfirm packaging/q3dfx.spec
# Risultato: dist/QEMU-3dfx Manager/ (Windows/Linux) o dist/QEMU-3dfx Manager.app (macOS)

import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)
from q3dfx import APP_NAME, __version__  # noqa: E402

ICONS = os.path.join(SPECPATH, "icons")
icon = {
    "win32": os.path.join(ICONS, "app.ico"),
    "darwin": os.path.join(ICONS, "app.icns"),
}.get(sys.platform)

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "q3dfx", "resources"), os.path.join("q3dfx", "resources"))],
    # Moduli Qt non usati: esclusi per ridurre le dimensioni.
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml",
              "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtPdf",
              "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,          # app grafica: nessuna finestra di terminale
    icon=icon,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon,
        bundle_identifier="io.github.qemu3dfx-manager",
        version=__version__,
        info_plist={
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "QEMU-3dfx Manager",
        },
    )
