"""Modifica delle impostazioni di una VM esistente."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QLineEdit, QSpinBox, QVBoxLayout)

from ..core.models import VMConfig
from ..core.presets import NIC_CHOICES, PRESETS, SOUND_CHOICES, VGA_CHOICES
from .widgets import ISO_FILTER, PathPicker


class VMDialog(QDialog):
    def __init__(self, vm: VMConfig, running: bool, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.setWindowTitle(f"Impostazioni - {vm.name}")
        self.setMinimumWidth(520)

        self.name = QLineEdit(vm.name)
        self.guest = QComboBox()
        for p in PRESETS.values():
            self.guest.addItem(p.label, p.key)
        self.guest.setCurrentIndex(max(0, self.guest.findData(vm.guest)))
        self.ram = QSpinBox(); self.ram.setRange(16, 4096); self.ram.setSuffix(" MB")
        self.ram.setSingleStep(32); self.ram.setValue(vm.ram_mb)
        self.cpus = QSpinBox(); self.cpus.setRange(1, 4); self.cpus.setValue(vm.cpus)
        self.vga = QComboBox(); self.vga.addItems(VGA_CHOICES); self.vga.setCurrentText(vm.vga)
        self.sound = QComboBox(); self.sound.addItems(SOUND_CHOICES); self.sound.setCurrentText(vm.sound)
        self.nic = QComboBox(); self.nic.addItems(NIC_CHOICES); self.nic.setCurrentText(vm.nic)
        self.cdrom = PathPicker("file", ISO_FILTER, "Nessun CD")
        self.cdrom.setText(vm.cdrom)
        self.boot_cd = QCheckBox("Avvia dal CD")
        self.boot_cd.setChecked(vm.boot_from_cd)
        self.fullscreen = QCheckBox("Avvia a schermo intero")
        self.fullscreen.setChecked(vm.fullscreen)
        self.extra = QLineEdit(vm.extra_args)
        self.extra.setPlaceholderText("Es. -cpu pentium3")

        form = QFormLayout()
        form.addRow("Nome:", self.name)
        form.addRow("Sistema:", self.guest)
        form.addRow("Memoria:", self.ram)
        form.addRow("Processori:", self.cpus)
        form.addRow("Scheda video:", self.vga)
        form.addRow("Audio:", self.sound)
        form.addRow("Rete:", self.nic)
        form.addRow("CD all'avvio:", self.cdrom)
        form.addRow("", self.boot_cd)
        form.addRow("", self.fullscreen)
        form.addRow("Argomenti QEMU extra:", self.extra)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        if running:
            from PySide6.QtWidgets import QLabel
            warn = QLabel("La VM e' accesa: le modifiche hardware avranno "
                          "effetto al prossimo avvio.")
            warn.setWordWrap(True)
            lay.addWidget(warn)
        lay.addWidget(buttons)

    def _save(self) -> None:
        vm = self.vm
        vm.name = self.name.text().strip() or vm.name
        vm.guest = self.guest.currentData()
        vm.ram_mb = self.ram.value()
        vm.cpus = self.cpus.value()
        vm.vga = self.vga.currentText()
        vm.sound = self.sound.currentText()
        vm.nic = self.nic.currentText()
        vm.cdrom = self.cdrom.text()
        vm.boot_from_cd = self.boot_cd.isChecked()
        vm.fullscreen = self.fullscreen.isChecked()
        vm.extra_args = self.extra.text().strip()
        self.accept()
