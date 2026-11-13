"""Finestra di installazione/aggiornamento di QEMU-3dfx."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QVBoxLayout)

from ..core import installer
from ..core.settings import AppSettings
from .worker import run_async


class _Bridge(QObject):
    # Creato nel thread dell'interfaccia: i segnali emessi dal thread di
    # download arrivano qui in coda, senza toccare i widget da altri thread.
    progress = Signal(int, int)
    status = Signal(str)


class InstallDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.result_install: installer.InstalledQemu | None = None
        self._cancel = threading.Event()
        self.setWindowTitle("Installa QEMU-3dfx")
        self.setMinimumWidth(480)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        cur = installer.current_install()
        self.info = QLabel(
            ("Installato: " + cur.describe()) if cur else
            "QEMU-3dfx non e' installato. Verra' scaricato il pacchetto gia' "
            "compilato per questo sistema dal repository " + settings.repo + ".")
        self.info.setWordWrap(True)
        self.status = QLabel("")
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.hide()

        self.b_go = QPushButton("Aggiorna" if cur else "Installa")
        self.b_go.setDefault(True)
        self.b_close = QPushButton("Chiudi")
        self.b_go.clicked.connect(self.start)
        self.b_close.clicked.connect(self._close_or_cancel)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.b_close)
        btns.addWidget(self.b_go)

        lay = QVBoxLayout(self)
        lay.addWidget(self.info)
        lay.addWidget(self.status)
        lay.addWidget(self.bar)
        lay.addLayout(btns)

        self.bridge = _Bridge()
        self.bridge.progress.connect(self._on_progress)
        self.bridge.status.connect(self.status.setText)
        self._running = False

    def start(self) -> None:
        self._running = True
        self._cancel.clear()
        self.b_go.setEnabled(False)
        self.b_close.setText("Annulla")
        self.bar.show()
        self.bar.setRange(0, 0)
        repo = self.settings.repo
        bridge, cancel = self.bridge, self._cancel

        def job():
            return installer.install_latest(
                repo,
                progress=lambda d, t: bridge.progress.emit(d, t),
                cancelled=cancel.is_set,
                status=lambda m: bridge.status.emit(m),
            )

        run_async(job, self._done, self._failed)

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            # QProgressBar usa int a 32 bit: lavoriamo in KB.
            self.bar.setRange(0, max(1, total // 1024))
            self.bar.setValue(done // 1024)
            self.status.setText(f"Download: {done / 1048576:.1f} di "
                                f"{total / 1048576:.1f} MB")

    def _done(self, inst) -> None:
        self._running = False
        self.result_install = inst
        # Da qui in poi l'app usa la versione installata in automatico.
        self.settings.qemu_dir = ""
        self.settings.wrappers_dir = ""
        self.settings.save()
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.status.setText("Installazione completata: " + inst.describe())
        self.b_close.setText("Chiudi")
        self.b_go.hide()

    def _failed(self, msg: str) -> None:
        self._running = False
        self.bar.hide()
        self.status.setText(msg)
        self.status.setWordWrap(True)
        self.b_go.setEnabled(True)
        self.b_go.setText("Riprova")
        self.b_close.setText("Chiudi")

    def _close_or_cancel(self) -> None:
        if self._running:
            self._cancel.set()
            self.status.setText("Annullamento...")
        else:
            self.accept() if self.result_install else self.reject()

    def closeEvent(self, event) -> None:
        if self._running:
            self._cancel.set()
            event.ignore()
        else:
            event.accept()
