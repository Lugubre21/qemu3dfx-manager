"""Gestione di una VM in esecuzione: processo QEMU + canale QMP."""

from __future__ import annotations

from enum import Enum
from typing import Callable

from PySide6.QtCore import (QObject, QProcess, QProcessEnvironment, QTimer,
                            Signal)

from ..core.models import VMConfig
from ..core.qemu import LaunchPlan, format_command
from ..core.qmp import QMPClient
from .worker import run_async


class VMState(str, Enum):
    STOPPED = "Spenta"
    STARTING = "Avvio..."
    RUNNING = "In esecuzione"
    PAUSED = "In pausa"


class VMRunner(QObject):
    state_changed = Signal(str, str)     # vm_id, stato
    output = Signal(str, str)            # vm_id, testo

    def __init__(self, vm: VMConfig, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.state = VMState.STOPPED
        self.qmp_port = 0
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read_output)
        self.proc.started.connect(self._on_started)
        self.proc.finished.connect(self._on_finished)
        self.proc.errorOccurred.connect(self._on_error)

    # -- ciclo di vita ----------------------------------------------------

    @property
    def running(self) -> bool:
        return self.state in (VMState.STARTING, VMState.RUNNING, VMState.PAUSED)

    def start(self, plan: LaunchPlan) -> None:
        if self.running:
            return
        self.qmp_port = plan.qmp_port
        self.output.emit(self.vm.id, "$ " + format_command(plan.argv) + "\n")
        self._set_state(VMState.STARTING)
        env = QProcessEnvironment.systemEnvironment()
        for k, v in (plan.env or {}).items():
            env.insert(k, v)
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(self.vm.folder)
        self.proc.start(plan.argv[0], plan.argv[1:])

    def _on_started(self) -> None:
        # QEMU apre la porta QMP dopo qualche istante.
        QTimer.singleShot(500, lambda: self._set_state(VMState.RUNNING)
                          if self.state == VMState.STARTING else None)

    def _on_finished(self, code: int, _status) -> None:
        self.output.emit(self.vm.id, f"\n[QEMU terminato, codice {code}]\n")
        self._set_state(VMState.STOPPED)

    def _on_error(self, err) -> None:
        if err == QProcess.ProcessError.FailedToStart:
            self.output.emit(self.vm.id,
                             "\n[Impossibile avviare QEMU: controlla il "
                             "percorso nelle Impostazioni]\n")
            self._set_state(VMState.STOPPED)

    def _read_output(self) -> None:
        data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        if data:
            self.output.emit(self.vm.id, data)

    def _set_state(self, st: VMState) -> None:
        self.state = st
        self.state_changed.emit(self.vm.id, st.value)

    # -- comandi via QMP --------------------------------------------------

    def qmp_call(self, fn: Callable[[QMPClient], object],
                 on_done: Callable[[object], None] | None = None,
                 on_error: Callable[[str], None] | None = None) -> None:
        """Apre una connessione QMP breve, esegue fn e la chiude.

        Una connessione per operazione e' piu' robusta di una persistente:
        se QEMU si riavvia o la connessione cade, non c'e' stato da ripulire.
        """
        port = self.qmp_port

        def job():
            with QMPClient(port) as q:
                return fn(q)

        run_async(job, on_done, on_error)

    def pause(self, on_error=None) -> None:
        self.qmp_call(lambda q: q.pause(),
                      lambda _: self._set_state(VMState.PAUSED), on_error)

    def resume(self, on_error=None) -> None:
        self.qmp_call(lambda q: q.resume(),
                      lambda _: self._set_state(VMState.RUNNING), on_error)

    def powerdown(self, on_error=None) -> None:
        self.qmp_call(lambda q: q.powerdown(), None, on_error)

    def reset(self, on_error=None) -> None:
        self.qmp_call(lambda q: q.reset(), None, on_error)

    def force_stop(self) -> None:
        if not self.running:
            return
        # Prima chiediamo a QEMU di uscire; se non risponde, kill.
        self.qmp_call(lambda q: q.quit(), None, lambda _msg: self.proc.kill())
        QTimer.singleShot(3000, lambda: self.proc.kill()
                          if self.proc.state() != QProcess.ProcessState.NotRunning
                          else None)

    def kill_now(self) -> None:
        if self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(3000)
