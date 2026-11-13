"""Avvio di QEMU-3dfx Manager:  python main.py"""

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 non e' installato. Esegui:  pip install -r requirements.txt")
        return 1

    from q3dfx import APP_NAME
    from q3dfx.core.settings import AppSettings
    from q3dfx.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")       # aspetto uguale su Windows, Linux e macOS
    from pathlib import Path
    from PySide6.QtGui import QIcon
    import q3dfx
    # Funziona sia dai sorgenti sia nell'app pacchettizzata (PyInstaller).
    icon = Path(q3dfx.__file__).resolve().parent / "resources" / "app.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    win = MainWindow(AppSettings.load())
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
