"""Impostazioni globali dell'applicazione (percorsi di QEMU, wrapper, VM)."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def app_data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "QEMU-3dfx Manager"


def default_vm_dir() -> Path:
    return Path.home() / "QEMU-3dfx VMs"


@dataclass
class AppSettings:
    qemu_dir: str = ""        # cartella con qemu-system-i386 e qemu-img (vuoto = PATH)
    wrappers_dir: str = ""    # cartella con i wrapper Glide/OpenGL compilati
    vm_dir: str = ""          # radice della libreria VM
    display: str = "sdl"      # sdl | gtk | cocoa
    gl: bool = True           # -display ...,gl=on (necessario per MESA pass-through)
    accel: str = "auto"       # auto | whpx | kvm | hvf | tcg
    github_repo: str = ""     # vuoto = q3dfx.config.GITHUB_REPO

    @property
    def vm_root(self) -> Path:
        return Path(self.vm_dir) if self.vm_dir else default_vm_dir()

    @property
    def repo(self) -> str:
        from ..config import GITHUB_REPO
        return self.github_repo.strip() or GITHUB_REPO

    @property
    def effective_wrappers_dir(self) -> str:
        """Cartella wrapper scelta a mano, altrimenti quella installata."""
        if self.wrappers_dir:
            return self.wrappers_dir
        from .installer import current_install
        inst = current_install()
        return str(inst.wrappers_dir) if inst and inst.wrappers_dir.is_dir() else ""

    @classmethod
    def load(cls) -> "AppSettings":
        path = app_data_dir() / "settings.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in known})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self) -> None:
        d = app_data_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / "settings.json").write_text(json.dumps(asdict(self), indent=2),
                                         encoding="utf-8")
