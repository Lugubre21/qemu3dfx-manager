"""Impostazioni globali: percorsi di QEMU-3dfx, wrapper, display."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QVBoxLayout)

from ..core import qemu
from ..core.settings import AppSettings, default_vm_dir
from .widgets import PathPicker


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Impostazioni")
        self.settings = settings
        self.setMinimumWidth(560)

        self.qemu_dir = PathPicker("dir", placeholder="Vuoto = versione installata dall'app, poi PATH")
        self.qemu_dir.setText(settings.qemu_dir)
        self.wrappers_dir = PathPicker("dir", placeholder="Vuoto = wrapper installati con QEMU-3dfx")
        self.wrappers_dir.setText(settings.wrappers_dir)
        self.vm_dir = PathPicker("dir", placeholder=str(default_vm_dir()))
        self.vm_dir.setText(settings.vm_dir)

        self.display = QComboBox()
        displays = ["sdl", "gtk"] + (["cocoa"] if qemu.SYSTEM == "Darwin" else [])
        self.display.addItems(displays)
        self.display.setCurrentText(settings.display if settings.display in displays else "sdl")
        self.gl = QCheckBox("OpenGL nella finestra (gl=on, serve al pass-through MESA)")
        self.gl.setChecked(settings.gl)

        self.repo = QLineEdit(settings.github_repo)
        from ..config import GITHUB_REPO
        self.repo.setPlaceholderText(GITHUB_REPO)
        from ..core.installer import current_install
        inst = current_install()
        self.installed = QLabel(inst.describe() if inst else "nessuna")
        self.installed.setWordWrap(True)

        self.accel = QComboBox()
        self.accel.addItems(["auto", "whpx", "kvm", "hvf", "tcg"])
        self.accel.setCurrentText(settings.accel)

        form = QFormLayout()
        form.addRow("Versione installata:", self.installed)
        form.addRow("Cartella QEMU-3dfx:", self.qemu_dir)
        form.addRow("Cartella wrapper:", self.wrappers_dir)
        form.addRow("Cartella delle VM:", self.vm_dir)
        form.addRow("Display:", self.display)
        form.addRow("", self.gl)
        form.addRow("Accelerazione:", self.accel)
        form.addRow("Repository GitHub:", self.repo)

        check = QPushButton("Verifica configurazione")
        check.clicked.connect(self._verify)

        hint = QLabel("Con \"auto\" viene usato WHPX su Windows, KVM su Linux, "
                      "HVF sui Mac Intel e l'emulazione software (TCG) come "
                      "ripiego. Sui Mac Apple Silicon i guest x86 girano sempre "
                      "in TCG, quindi piu' lentamente.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addWidget(check)
        lay.addWidget(buttons)

    def _collect(self) -> AppSettings:
        return AppSettings(
            qemu_dir=self.qemu_dir.text(),
            wrappers_dir=self.wrappers_dir.text(),
            vm_dir=self.vm_dir.text(),
            display=self.display.currentText(),
            gl=self.gl.isChecked(),
            accel=self.accel.currentText(),
            github_repo=self.repo.text().strip(),
        )

    def _verify(self) -> None:
        s = self._collect()
        lines = []
        for name in ("qemu-system-i386", "qemu-img"):
            p = qemu.find_binary(name, s.qemu_dir)
            lines.append(f"{name}: {p if p else 'NON TROVATO'}")
        lines.append("Acceleratori in ordine: " + ", ".join(qemu.detect_accels(s.accel)))
        if s.effective_wrappers_dir:
            from ..core.tools_iso import scan_wrappers
            from pathlib import Path
            lines.append("")
            lines.append(scan_wrappers(Path(s.effective_wrappers_dir)).summary())
        QMessageBox.information(self, "Verifica", "\n".join(lines))

    def _save(self) -> None:
        new = self._collect()
        for f in ("qemu_dir", "wrappers_dir", "vm_dir", "display", "gl", "accel",
                  "github_repo"):
            setattr(self.settings, f, getattr(new, f))
        self.settings.save()
        self.accept()
