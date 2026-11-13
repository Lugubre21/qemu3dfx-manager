"""Gestione snapshot: a caldo via QMP (con RAM) o a VM spenta via qemu-img."""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QInputDialog, QLabel,
                               QMessageBox, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout)

from ..core import qemu
from ..core.settings import AppSettings
from .runner import VMRunner
from .worker import run_async


class SnapshotDialog(QDialog):
    def __init__(self, runner: VMRunner, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.runner, self.settings = runner, settings
        self.vm = runner.vm
        self.setWindowTitle(f"Snapshot - {self.vm.name}")
        self.resize(600, 380)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Nome", "Data", "Tipo"])
        self.tree.setRootIsDecorated(False)
        self.tree.itemSelectionChanged.connect(self._update_buttons)

        self.info = QLabel()
        self.info.setWordWrap(True)

        self.b_create = QPushButton("Crea snapshot...")
        self.b_apply = QPushButton("Ripristina")
        self.b_delete = QPushButton("Elimina")
        self.b_refresh = QPushButton("Aggiorna")
        self.b_create.clicked.connect(self._create)
        self.b_apply.clicked.connect(self._apply)
        self.b_delete.clicked.connect(self._delete)
        self.b_refresh.clicked.connect(self.refresh)

        btns = QHBoxLayout()
        for b in (self.b_create, self.b_apply, self.b_delete):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(self.b_refresh)

        lay = QVBoxLayout(self)
        lay.addWidget(self.tree, 1)
        lay.addWidget(self.info)
        lay.addLayout(btns)

        runner.state_changed.connect(lambda *_: self._update_info())
        self._update_info()
        self.refresh()

    # -- stato ------------------------------------------------------------

    def _update_info(self) -> None:
        if self.runner.running:
            self.info.setText("VM accesa: lo snapshot salva anche la RAM, e il "
                              "ripristino riporta la VM esattamente a quel momento.")
        else:
            self.info.setText("VM spenta: lo snapshot salva solo il disco. Al "
                              "ripristino la VM ripartira' da quello stato del disco.")
        self._update_buttons()

    def _busy(self, on: bool) -> None:
        for b in (self.b_create, self.b_apply, self.b_delete, self.b_refresh):
            b.setEnabled(not on)
        if on:
            self.setCursor(Qt.CursorShape.WaitCursor)
        else:
            self.unsetCursor()
            self._update_buttons()

    def _update_buttons(self) -> None:
        sel = self._selected() is not None
        self.b_apply.setEnabled(sel)
        self.b_delete.setEnabled(sel)

    def _selected(self) -> str | None:
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    # -- operazioni -------------------------------------------------------

    def refresh(self) -> None:
        disk = self.vm.disk_path
        self._busy(True)
        run_async(lambda: qemu.list_snapshots(self.settings, disk),
                  self._fill, self._error)

    def _fill(self, snaps) -> None:
        self.tree.clear()
        for s in snaps:
            when = dt.datetime.fromtimestamp(s.date_sec).strftime("%d/%m/%Y %H:%M")
            kind = "Completo (RAM + disco)" if s.has_ram_state else "Solo disco"
            it = QTreeWidgetItem([s.name, when, kind])
            it.setData(0, Qt.ItemDataRole.UserRole, s.name)
            self.tree.addTopLevelItem(it)
        for c in range(3):
            self.tree.resizeColumnToContents(c)
        self._busy(False)

    def _error(self, msg: str) -> None:
        self._busy(False)
        QMessageBox.warning(self, "Snapshot", msg)

    def _run(self, op: str, name: str) -> None:
        self._busy(True)
        if self.runner.running:
            fn = {"create": lambda q: q.savevm(name),
                  "apply": lambda q: q.loadvm(name),
                  "delete": lambda q: q.delvm(name)}[op]
            self.runner.qmp_call(fn, lambda _: self.refresh(), self._error)
        else:
            disk = self.vm.disk_path
            run_async(lambda: qemu.offline_snapshot(self.settings, disk, op, name),
                      lambda _: self.refresh(), self._error)

    def _create(self) -> None:
        default = dt.datetime.now().strftime("Snapshot %d-%m-%Y %H.%M")
        name, ok = QInputDialog.getText(self, "Nuovo snapshot", "Nome:", text=default)
        if ok and name.strip():
            self._run("create", name.strip())

    def _apply(self) -> None:
        name = self._selected()
        if name and QMessageBox.question(
                self, "Ripristina",
                f"Ripristinare \"{name}\"? Lo stato attuale non salvato andra' perso."
        ) == QMessageBox.StandardButton.Yes:
            self._run("apply", name)

    def _delete(self) -> None:
        name = self._selected()
        if name and QMessageBox.question(
                self, "Elimina", f"Eliminare lo snapshot \"{name}\"?"
        ) == QMessageBox.StandardButton.Yes:
            self._run("delete", name)
