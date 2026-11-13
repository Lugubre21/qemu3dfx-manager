"""Finestra principale: libreria VM a sinistra, dettagli e controlli a destra."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QDesktopServices, QFont, QGuiApplication,
                           QTextCursor)
from PySide6.QtWidgets import (QFileDialog, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter, QStyle,
                               QToolBar, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..core import qemu
from ..core.models import VMConfig, VMLibrary
from ..core.presets import get_preset
from ..core.settings import AppSettings, app_data_dir
from ..core.tools_iso import write_tools_iso
from .runner import VMRunner, VMState
from .settings_dialog import SettingsDialog
from .snapshots import SnapshotDialog
from .vm_dialog import VMDialog
from .widgets import ISO_FILTER
from .install_dialog import InstallDialog
from .wizard import NewVMWizard
from .worker import run_async

MAX_LOG_CHARS = 200_000

_STATE_COLORS = {
    VMState.STOPPED.value: "#888888",
    VMState.STARTING.value: "#d79b00",
    VMState.RUNNING.value: "#2e9e44",
    VMState.PAUSED.value: "#d79b00",
}


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings
        self.library = VMLibrary(settings.vm_root)
        self.runners: dict[str, VMRunner] = {}
        self.logs: dict[str, str] = {}

        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1000, 680)
        self._build_toolbar()
        self._build_body()
        self.reload_list()

        if not qemu.find_binary("qemu-system-i386", settings.qemu_dir):
            # Dopo che la finestra e' visibile, proponiamo l'installazione.
            QTimer.singleShot(300, self._offer_install)

    # ------------------------------------------------------------------ UI

    def _icon(self, sp: QStyle.StandardPixmap):
        return self.style().standardIcon(sp)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Principale")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        SP = QStyle.StandardPixmap

        def act(text, icon, slot):
            a = QAction(self._icon(icon), text, self)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        act("Nuova VM", SP.SP_FileDialogNewFolder, self.new_vm)
        tb.addSeparator()
        act("Crea ISO 3dfx Tools...", SP.SP_DriveCDIcon, self.export_tools_iso)
        act("Installa/aggiorna QEMU-3dfx", SP.SP_ArrowDown, self.open_installer)
        act("Impostazioni", SP.SP_FileDialogDetailedView, self.open_settings)

    def _build_body(self) -> None:
        SP = QStyle.StandardPixmap
        self.list = QListWidget()
        self.list.setIconSize(QSize(32, 32))
        self.list.setMinimumWidth(220)
        self.list.currentItemChanged.connect(lambda *_: self.refresh_details())
        self.list.itemDoubleClicked.connect(lambda *_: self.start_vm())

        # Intestazione
        self.title = QLabel()
        f = QFont(); f.setPointSize(f.pointSize() + 6); f.setBold(True)
        self.title.setFont(f)
        self.state_lbl = QLabel()

        # Riepilogo hardware
        self.summary = QFormLayout()
        self.summary.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        summary_box = QFrame()
        summary_box.setFrameShape(QFrame.Shape.StyledPanel)
        summary_box.setLayout(self.summary)

        # Pulsanti
        def btn(text, icon, slot):
            b = QPushButton(self._icon(icon), text)
            b.clicked.connect(slot)
            return b

        self.b_start = btn("Avvia", SP.SP_MediaPlay, self.start_vm)
        self.b_pause = btn("Pausa", SP.SP_MediaPause, self.toggle_pause)
        self.b_power = btn("Spegni", SP.SP_MediaStop, self.powerdown_vm)
        self.b_kill = btn("Forza spegnimento", SP.SP_BrowserStop, self.force_stop_vm)
        self.b_reset = btn("Riavvia", SP.SP_BrowserReload, self.reset_vm)
        self.b_snap = btn("Snapshot...", SP.SP_DialogSaveButton, self.open_snapshots)
        self.b_tools = btn("Inserisci 3dfx Tools", SP.SP_DriveCDIcon, self.insert_tools)
        self.b_cd = btn("Cambia CD...", SP.SP_DriveCDIcon, self.change_cd)
        self.b_eject = btn("Espelli CD", SP.SP_ArrowUp, self.eject_cd)
        self.b_edit = btn("Impostazioni VM...", SP.SP_FileDialogDetailedView, self.edit_vm)
        self.b_folder = btn("Apri cartella", SP.SP_DirOpenIcon, self.open_folder)
        self.b_copy = btn("Copia comando", SP.SP_FileIcon, self.copy_command)
        self.b_delete = btn("Rimuovi...", SP.SP_TrashIcon, self.delete_vm)

        grid = QGridLayout()
        layout_btns = [
            [self.b_start, self.b_pause, self.b_power, self.b_kill, self.b_reset],
            [self.b_snap, self.b_tools, self.b_cd, self.b_eject],
            [self.b_edit, self.b_folder, self.b_copy, self.b_delete],
        ]
        for r, row in enumerate(layout_btns):
            for c, b in enumerate(row):
                grid.addWidget(b, r, c)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Uscita di QEMU")
        mono = QFont("Monospace"); mono.setStyleHint(QFont.StyleHint.TypeWriter)
        self.log.setFont(mono)

        top = QWidget()
        tl = QVBoxLayout(top)
        head = QHBoxLayout()
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(self.state_lbl)
        tl.addLayout(head)
        tl.addWidget(summary_box)
        tl.addLayout(grid)
        tl.addStretch(1)

        self.placeholder = QLabel("Nessuna macchina virtuale.\n\n"
                                  "Premi \"Nuova VM\" per crearne una.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.addWidget(top)
        right_split.addWidget(self.log)
        right_split.setStretchFactor(0, 3)
        right_split.setStretchFactor(1, 2)
        self.detail = right_split

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.placeholder)
        rl.addWidget(self.detail)

        split = QSplitter()
        split.addWidget(self.list)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([240, 760])
        self.setCentralWidget(split)

    # ------------------------------------------------------------ libreria

    def current_vm(self) -> VMConfig | None:
        it = self.list.currentItem()
        return self.library.get(it.data(Qt.ItemDataRole.UserRole)) if it else None

    def runner_for(self, vm: VMConfig) -> VMRunner:
        r = self.runners.get(vm.id)
        if r is None:
            r = VMRunner(vm, self)
            r.state_changed.connect(self._on_state)
            r.output.connect(self._on_output)
            self.runners[vm.id] = r
        r.vm = vm
        return r

    def reload_list(self, select_id: str | None = None) -> None:
        select_id = select_id or (self.current_vm().id if self.current_vm() else None)
        self.list.blockSignals(True)
        self.list.clear()
        for vm in sorted(self.library.vms, key=lambda v: v.name.lower()):
            it = QListWidgetItem(self._icon(QStyle.StandardPixmap.SP_ComputerIcon), "")
            it.setData(Qt.ItemDataRole.UserRole, vm.id)
            self._decorate_item(it, vm)
            self.list.addItem(it)
            if vm.id == select_id:
                self.list.setCurrentItem(it)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self.refresh_details()

    def _decorate_item(self, it: QListWidgetItem, vm: VMConfig) -> None:
        r = self.runners.get(vm.id)
        state = r.state.value if r else VMState.STOPPED.value
        it.setText(f"{vm.name}\n{get_preset(vm.guest).label} - {state}")

    def refresh_details(self) -> None:
        vm = self.current_vm()
        has = vm is not None
        self.placeholder.setVisible(not has)
        self.detail.setVisible(has)
        if not has:
            return
        r = self.runner_for(vm)
        running = r.running
        paused = r.state == VMState.PAUSED

        self.title.setText(vm.name)
        color = _STATE_COLORS.get(r.state.value, "#888")
        self.state_lbl.setText(f"<span style='color:{color}'>&#9679;</span> {r.state.value}")

        while self.summary.rowCount():
            self.summary.removeRow(0)
        p = get_preset(vm.guest)
        rows = [
            ("Sistema", p.label),
            ("Memoria", f"{vm.ram_mb} MB"),
            ("Processori", str(vm.cpus)),
            ("Video", vm.vga),
            ("Audio", vm.sound),
            ("Rete", vm.nic),
            ("Disco", str(vm.disk_path)),
            ("CD", vm.cdrom or "vuoto"),
            ("Avvio da", "CD" if vm.boot_from_cd else "disco"),
        ]
        if vm.extra_args:
            rows.append(("Extra", vm.extra_args))
        for k, v in rows:
            lbl = QLabel(v)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lbl.setWordWrap(True)
            self.summary.addRow(f"{k}:", lbl)

        self.b_start.setEnabled(not running)
        self.b_pause.setEnabled(r.state in (VMState.RUNNING, VMState.PAUSED))
        self.b_pause.setText("Riprendi" if paused else "Pausa")
        for b in (self.b_power, self.b_kill, self.b_reset):
            b.setEnabled(running)
        self.b_eject.setEnabled(running or bool(vm.cdrom))
        self.b_delete.setEnabled(not running)

        self.log.setPlainText(self.logs.get(vm.id, ""))
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _on_state(self, vm_id: str, _state: str) -> None:
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == vm_id:
                vm = self.library.get(vm_id)
                if vm:
                    self._decorate_item(it, vm)
        cur = self.current_vm()
        if cur and cur.id == vm_id:
            self.refresh_details()

    def _on_output(self, vm_id: str, text: str) -> None:
        log = self.logs.get(vm_id, "") + text
        self.logs[vm_id] = log[-MAX_LOG_CHARS:]
        cur = self.current_vm()
        if cur and cur.id == vm_id:
            self.log.moveCursor(QTextCursor.MoveOperation.End)
            self.log.insertPlainText(text)

    def _error(self, msg: str) -> None:
        QMessageBox.warning(self, APP_NAME, msg)

    # ------------------------------------------------------------- azioni

    def new_vm(self) -> None:
        wiz = NewVMWizard(self)
        if not wiz.exec():
            return
        vm, disk_gb = wiz.result_vm()
        vm.folder = str(self.library.new_folder_for(vm.name))
        try:
            qemu.create_disk(self.settings, vm.disk_path, disk_gb)
        except qemu.QemuError as e:
            self._error(f"Impossibile creare il disco:\n{e}")
            return
        self.library.save(vm)
        self.reload_list(vm.id)
        self.statusBar().showMessage(f"Creata \"{vm.name}\". Premi Avvia per installare il sistema.", 8000)

    def start_vm(self) -> None:
        vm = self.current_vm()
        if not vm:
            return
        if not vm.disk_path.exists():
            self._error(f"Il disco della VM non esiste:\n{vm.disk_path}")
            return
        try:
            plan = qemu.build_command(vm, self.settings)
        except qemu.QemuError as e:
            self._error(str(e))
            return
        self.runner_for(vm).start(plan)

    def toggle_pause(self) -> None:
        vm = self.current_vm()
        if not vm:
            return
        r = self.runner_for(vm)
        if r.state == VMState.PAUSED:
            r.resume(self._error)
        else:
            r.pause(self._error)

    def powerdown_vm(self) -> None:
        vm = self.current_vm()
        if vm:
            self.runner_for(vm).powerdown(self._error)
            self.statusBar().showMessage(
                "Richiesta di spegnimento inviata. Windows 9x a volte la ignora: "
                "in quel caso spegni dal menu Start o usa Forza spegnimento.", 8000)

    def force_stop_vm(self) -> None:
        vm = self.current_vm()
        if vm and QMessageBox.question(
                self, "Forza spegnimento",
                "Equivale a staccare la corrente: i dati non salvati nel guest "
                "andranno persi. Continuare?") == QMessageBox.StandardButton.Yes:
            self.runner_for(vm).force_stop()

    def reset_vm(self) -> None:
        vm = self.current_vm()
        if vm and QMessageBox.question(
                self, "Riavvia", "Riavviare la VM come con il tasto Reset?"
        ) == QMessageBox.StandardButton.Yes:
            self.runner_for(vm).reset(self._error)

    def open_snapshots(self) -> None:
        vm = self.current_vm()
        if vm:
            SnapshotDialog(self.runner_for(vm), self.settings, self).exec()

    def edit_vm(self) -> None:
        vm = self.current_vm()
        if not vm:
            return
        if VMDialog(vm, self.runner_for(vm).running, self).exec():
            self.library.save(vm)
            self.reload_list(vm.id)

    def delete_vm(self) -> None:
        vm = self.current_vm()
        if not vm:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Rimuovi VM")
        box.setText(f"Rimuovere \"{vm.name}\" dalla libreria?")
        keep = box.addButton("Rimuovi, tieni i file", QMessageBox.ButtonRole.AcceptRole)
        wipe = box.addButton("Elimina anche il disco", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is wipe:
            if QMessageBox.question(
                    self, "Conferma",
                    f"Il disco e gli snapshot in\n{vm.folder}\nverranno eliminati "
                    "definitivamente. Continuare?") != QMessageBox.StandardButton.Yes:
                return
            self.library.remove(vm, delete_files=True)
        elif clicked is keep:
            self.library.remove(vm, delete_files=False)
        else:
            return
        self.runners.pop(vm.id, None)
        self.logs.pop(vm.id, None)
        self.reload_list()

    def open_folder(self) -> None:
        vm = self.current_vm()
        if vm:
            QDesktopServices.openUrl(QUrl.fromLocalFile(vm.folder))

    def copy_command(self) -> None:
        vm = self.current_vm()
        if not vm:
            return
        try:
            plan = qemu.build_command(vm, self.settings, qmp_port=4444)
        except qemu.QemuError as e:
            self._error(str(e))
            return
        QGuiApplication.clipboard().setText(qemu.format_command(plan.argv))
        self.statusBar().showMessage("Comando QEMU copiato negli appunti.", 4000)

    # ---------------------------------------------------------------- CD

    def _set_cd(self, vm: VMConfig, iso: str) -> None:
        """Monta un'ISO: a caldo se la VM e' accesa, altrimenti al prossimo avvio."""
        r = self.runner_for(vm)
        if r.running:
            r.qmp_call(lambda q: q.change_cd(qemu.CD_DRIVE_ID, iso),
                       lambda _: self.statusBar().showMessage(
                           f"CD inserito: {Path(iso).name}", 5000),
                       self._error)
        else:
            vm.cdrom = iso
            self.library.save(vm)
            self.refresh_details()
            self.statusBar().showMessage(
                "CD impostato: sara' inserito al prossimo avvio.", 5000)

    def change_cd(self) -> None:
        vm = self.current_vm()
        if not vm:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Scegli immagine CD",
                                              str(Path(vm.cdrom).parent) if vm.cdrom else "",
                                              ISO_FILTER)
        if path:
            self._set_cd(vm, path)

    def eject_cd(self) -> None:
        vm = self.current_vm()
        if not vm:
            return
        r = self.runner_for(vm)
        if r.running:
            r.qmp_call(lambda q: q.eject_cd(qemu.CD_DRIVE_ID), None, self._error)
        else:
            vm.cdrom = ""
            vm.boot_from_cd = False
            self.library.save(vm)
            self.refresh_details()

    def _tools_iso_path(self) -> Path:
        return app_data_dir() / "q3dfx-tools.iso"

    def _build_tools(self, out: Path, on_done) -> None:
        wrappers = self.settings.effective_wrappers_dir
        if not wrappers:
            self._error("Nessun wrapper disponibile: installa QEMU-3dfx dal "
                        "pulsante in alto oppure indica la cartella dei "
                        "wrapper nelle Impostazioni.")
            return
        src = Path(wrappers)
        self.statusBar().showMessage("Creazione ISO 3dfx Tools...")
        run_async(lambda: write_tools_iso(src, out), on_done,
                  lambda msg: (self.statusBar().clearMessage(),
                               self._error(f"ISO non creata:\n{msg}")))

    def insert_tools(self) -> None:
        vm = self.current_vm()
        if not vm:
            return
        iso = self._tools_iso_path()

        def done(scan):
            self.statusBar().clearMessage()
            if scan.warnings:
                QMessageBox.information(self, "3dfx Tools", scan.summary())
            self._set_cd(vm, str(iso))
            if vm.boot_from_cd:
                vm.boot_from_cd = False      # non vogliamo avviare dal CD dei Tools
                self.library.save(vm)
                self.refresh_details()

        # Ricreata ogni volta: costa poco e segue gli aggiornamenti dei wrapper.
        self._build_tools(iso, done)

    def export_tools_iso(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Salva ISO 3dfx Tools",
                                              str(Path.home() / "q3dfx-tools.iso"),
                                              "Immagine ISO (*.iso)")
        if path:
            self._build_tools(Path(path), lambda scan: (
                self.statusBar().clearMessage(),
                QMessageBox.information(self, "3dfx Tools",
                                        f"ISO creata:\n{path}\n\n{scan.summary()}")))

    # ------------------------------------------------------------ varie

    def _offer_install(self) -> None:
        if QMessageBox.question(
                self, "QEMU-3dfx non trovato",
                "QEMU-3dfx non e' installato su questo computer.\n\n"
                "Vuoi scaricarlo e installarlo adesso? Servono circa 50-150 MB."
        ) == QMessageBox.StandardButton.Yes:
            self.open_installer()
        else:
            self.statusBar().showMessage(
                "QEMU-3dfx non installato: usa \"Installa/aggiorna QEMU-3dfx\" "
                "oppure indica una cartella nelle Impostazioni.")

    def open_installer(self) -> None:
        if any(r.running for r in self.runners.values()):
            self._error("Spegni le VM in esecuzione prima di installare o "
                        "aggiornare QEMU-3dfx.")
            return
        if InstallDialog(self.settings, self).exec():
            self.statusBar().showMessage("QEMU-3dfx pronto.", 5000)

    def open_settings(self) -> None:
        old_root = self.settings.vm_root
        if SettingsDialog(self.settings, self).exec():
            if self.settings.vm_root != old_root:
                if any(r.running for r in self.runners.values()):
                    self._error("La nuova cartella delle VM verra' usata dopo "
                                "aver spento le VM in esecuzione e riavviato l'app.")
                else:
                    self.library = VMLibrary(self.settings.vm_root)
                    self.runners.clear()
                    self.reload_list()
            self.statusBar().clearMessage()

    def closeEvent(self, event) -> None:
        running = [r for r in self.runners.values() if r.running]
        if running:
            names = "\n".join(f"- {r.vm.name}" for r in running)
            if QMessageBox.question(
                    self, "VM in esecuzione",
                    f"Queste VM sono ancora accese:\n{names}\n\nChiudendo verranno "
                    "spente di colpo. Uscire comunque?") != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for r in running:
                r.kill_now()
        event.accept()
