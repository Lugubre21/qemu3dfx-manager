"""Client QMP minimale (socket TCP sincrono).

QMP e' il protocollo JSON di controllo di QEMU. Lo usiamo per pausa/ripresa,
spegnimento, snapshot a caldo e cambio del CD. Le chiamate sono bloccanti:
l'interfaccia le esegue in un thread separato.
"""

from __future__ import annotations

import json
import socket
import time


class QMPError(RuntimeError):
    pass


class QMPClient:
    def __init__(self, port: int, host: str = "127.0.0.1", timeout: float = 5.0):
        self.host, self.port, self.timeout = host, port, timeout
        self._sock: socket.socket | None = None
        self._buf = b""

    # -- connessione ------------------------------------------------------

    def connect(self, retries: int = 20, delay: float = 0.25) -> None:
        last = None
        for _ in range(retries):
            try:
                self._sock = socket.create_connection((self.host, self.port),
                                                      timeout=self.timeout)
                break
            except OSError as e:          # QEMU potrebbe non essere ancora pronto
                last = e
                time.sleep(delay)
        else:
            raise QMPError(f"Impossibile collegarsi a QMP: {last}")
        greeting = self._read_message()
        if "QMP" not in greeting:
            raise QMPError("Risposta QMP inattesa")
        self.execute("qmp_capabilities")

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self) -> "QMPClient":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- protocollo -------------------------------------------------------

    def _read_message(self, timeout: float | None = None) -> dict:
        assert self._sock is not None
        self._sock.settimeout(timeout or self.timeout)
        while b"\n" not in self._buf:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise QMPError("Connessione QMP chiusa")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return json.loads(line.decode("utf-8", errors="replace"))

    def execute(self, command: str, arguments: dict | None = None,
                timeout: float | None = None):
        if not self._sock:
            raise QMPError("Non connesso")
        msg = {"execute": command}
        if arguments:
            msg["arguments"] = arguments
        self._sock.sendall((json.dumps(msg) + "\n").encode())
        while True:
            reply = self._read_message(timeout)
            if "event" in reply:            # gli eventi asincroni si ignorano
                continue
            if "error" in reply:
                err = reply["error"]
                raise QMPError(f"{err.get('class')}: {err.get('desc')}")
            return reply.get("return")

    def hmp(self, command_line: str, timeout: float = 120.0) -> str:
        """Esegue un comando del monitor testuale (savevm, loadvm, change...).

        Molti comandi HMP segnalano gli errori solo come testo in uscita,
        quindi un output non vuoto viene trattato come errore dove serve.
        """
        out = self.execute("human-monitor-command",
                           {"command-line": command_line}, timeout=timeout)
        return out or ""

    # -- operazioni di alto livello ---------------------------------------

    def status(self) -> str:
        return (self.execute("query-status") or {}).get("status", "unknown")

    def pause(self) -> None:
        self.execute("stop")

    def resume(self) -> None:
        self.execute("cont")

    def powerdown(self) -> None:
        self.execute("system_powerdown")

    def reset(self) -> None:
        self.execute("system_reset")

    def quit(self) -> None:
        try:
            self.execute("quit")
        except QMPError:
            pass  # QEMU chiude la connessione prima di rispondere

    def _hmp_checked(self, line: str, timeout: float = 600.0) -> None:
        out = self.hmp(line, timeout=timeout).strip()
        if out:
            raise QMPError(out)

    def savevm(self, name: str) -> None:
        self._hmp_checked(f"savevm {_quote(name)}")

    def loadvm(self, name: str) -> None:
        self._hmp_checked(f"loadvm {_quote(name)}")

    def delvm(self, name: str) -> None:
        self._hmp_checked(f"delvm {_quote(name)}")

    def change_cd(self, drive_id: str, iso_path: str) -> None:
        self._hmp_checked(f"change {drive_id} {_quote(iso_path)}", timeout=30)

    def eject_cd(self, drive_id: str) -> None:
        self._hmp_checked(f"eject -f {drive_id}", timeout=30)


def _quote(s: str) -> str:
    # Il monitor HMP accetta argomenti tra virgolette doppie.
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
