"""Piccoli widget riutilizzati nelle finestre di dialogo."""

from __future__ import annotations

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLineEdit, QPushButton,
                               QWidget)


class PathPicker(QWidget):
    """Campo di testo + pulsante Sfoglia, per file o cartelle."""

    def __init__(self, mode: str = "dir", file_filter: str = "",
                 placeholder: str = "", parent=None):
        super().__init__(parent)
        self.mode, self.file_filter = mode, file_filter
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        btn = QPushButton("Sfoglia...")
        btn.clicked.connect(self._browse)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit, 1)
        lay.addWidget(btn)

    def _browse(self) -> None:
        start = self.edit.text()
        if self.mode == "dir":
            path = QFileDialog.getExistingDirectory(self, "Scegli cartella", start)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Scegli file", start,
                                                  self.file_filter)
        if path:
            self.edit.setText(path)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, value: str) -> None:
        self.edit.setText(value)


ISO_FILTER = "Immagini CD (*.iso *.img *.cue *.bin);;Tutti i file (*)"
