"""Creazione guidata di una nuova VM, in stile VMware."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QLabel,
                               QLineEdit, QSpinBox, QVBoxLayout, QWizard,
                               QWizardPage)

from ..core.models import VMConfig
from ..core.presets import (NIC_CHOICES, PRESETS, SOUND_CHOICES, VGA_CHOICES,
                            get_preset)
from .widgets import ISO_FILTER, PathPicker


class _GuestPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Sistema operativo")
        self.setSubTitle("Scegli il sistema da installare: i valori hardware "
                         "verranno impostati di conseguenza.")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Es. Windows 98 Giochi")
        self.guest = QComboBox()
        for p in PRESETS.values():
            self.guest.addItem(p.label, p.key)
        self.notes = QLabel()
        self.notes.setWordWrap(True)
        self.guest.currentIndexChanged.connect(self._update_notes)
        self._update_notes()

        form = QFormLayout(self)
        form.addRow("Nome:", self.name)
        form.addRow("Sistema:", self.guest)
        form.addRow("", self.notes)
        self.registerField("name*", self.name)

    def _update_notes(self) -> None:
        self.notes.setText(get_preset(self.guest.currentData()).notes)

    def guest_key(self) -> str:
        return self.guest.currentData()


class _HardwarePage(QWizardPage):
    def __init__(self, guest_page: _GuestPage):
        super().__init__()
        self.guest_page = guest_page
        self.setTitle("Hardware virtuale")
        self.setSubTitle("I valori proposti vanno bene nella maggior parte dei casi.")
        self.ram = QSpinBox(); self.ram.setRange(16, 4096); self.ram.setSuffix(" MB")
        self.ram.setSingleStep(32)
        self.cpus = QSpinBox(); self.cpus.setRange(1, 4)
        self.disk = QSpinBox(); self.disk.setRange(1, 128); self.disk.setSuffix(" GB")
        self.vga = QComboBox(); self.vga.addItems(VGA_CHOICES)
        self.sound = QComboBox(); self.sound.addItems(SOUND_CHOICES)
        self.nic = QComboBox(); self.nic.addItems(NIC_CHOICES)
        form = QFormLayout(self)
        form.addRow("Memoria:", self.ram)
        form.addRow("Processori:", self.cpus)
        form.addRow("Disco (qcow2, cresce col contenuto):", self.disk)
        form.addRow("Scheda video:", self.vga)
        form.addRow("Audio:", self.sound)
        form.addRow("Rete:", self.nic)

    def initializePage(self) -> None:
        p = get_preset(self.guest_page.guest_key())
        self.ram.setValue(p.ram_mb)
        self.cpus.setValue(p.cpus)
        self.disk.setValue(p.disk_gb)
        self.vga.setCurrentText(p.vga)
        self.sound.setCurrentText(p.sound)
        self.nic.setCurrentText(p.nic)


class _InstallPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installazione")
        self.setSubTitle("Indica l'immagine del CD d'installazione. Puoi anche "
                         "lasciarla vuota e montarla in seguito.")
        self.iso = PathPicker("file", ISO_FILTER, "Immagine ISO del sistema")
        self.boot_cd = QCheckBox("Avvia dal CD (per l'installazione)")
        self.boot_cd.setChecked(True)
        tip = QLabel("Dopo l'installazione usa \"Inserisci 3dfx Tools\" per "
                     "installare i wrapper Glide e OpenGL nel guest.")
        tip.setWordWrap(True)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("CD d'installazione:", self.iso)
        lay.addLayout(form)
        lay.addWidget(self.boot_cd)
        lay.addStretch(1)
        lay.addWidget(tip)


class NewVMWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuova macchina virtuale")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(560, 420)
        self.p_guest = _GuestPage()
        self.p_hw = _HardwarePage(self.p_guest)
        self.p_inst = _InstallPage()
        for p in (self.p_guest, self.p_hw, self.p_inst):
            self.addPage(p)
        self.setButtonText(QWizard.WizardButton.FinishButton, "Crea")
        self.setButtonText(QWizard.WizardButton.NextButton, "Avanti >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Indietro")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Annulla")

    def result_vm(self) -> tuple[VMConfig, int]:
        vm = VMConfig(
            name=self.p_guest.name.text().strip(),
            guest=self.p_guest.guest_key(),
            ram_mb=self.p_hw.ram.value(),
            cpus=self.p_hw.cpus.value(),
            vga=self.p_hw.vga.currentText(),
            sound=self.p_hw.sound.currentText(),
            nic=self.p_hw.nic.currentText(),
            cdrom=self.p_inst.iso.text(),
            boot_from_cd=self.p_inst.boot_cd.isChecked() and bool(self.p_inst.iso.text()),
        )
        return vm, self.p_hw.disk.value()
