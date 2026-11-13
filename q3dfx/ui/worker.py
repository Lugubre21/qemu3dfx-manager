"""Esecuzione di operazioni lente (QMP, qemu-img, ISO) fuori dal thread UI."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as e:  # noqa: BLE001 - l'errore va mostrato all'utente
            self.signals.failed.emit(str(e) or e.__class__.__name__)
        else:
            self.signals.done.emit(result)


# Teniamo un riferimento ai task attivi: senza, Python potrebbe distruggere
# l'oggetto dei segnali prima che arrivino al thread dell'interfaccia.
_active: set[_Task] = set()


def run_async(fn: Callable[[], Any],
              on_done: Callable[[Any], None] | None = None,
              on_error: Callable[[str], None] | None = None) -> None:
    task = _Task(fn)
    task.setAutoDelete(False)
    _active.add(task)

    def finish_ok(result):
        _active.discard(task)
        if on_done:
            on_done(result)

    def finish_err(msg):
        _active.discard(task)
        if on_error:
            on_error(msg)

    task.signals.done.connect(finish_ok)
    task.signals.failed.connect(finish_err)
    QThreadPool.globalInstance().start(task)
