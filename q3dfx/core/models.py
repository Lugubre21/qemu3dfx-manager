"""Configurazione delle VM e libreria salvata su disco (JSON)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .presets import get_preset

CONFIG_NAME = "vm.json"


@dataclass
class VMConfig:
    name: str
    guest: str = "win98"
    ram_mb: int = 256
    cpus: int = 1
    vga: str = "std"
    sound: str = "sb16"
    nic: str = "pcnet"
    disk: str = "disk.qcow2"        # relativo alla cartella della VM
    cdrom: str = ""                 # percorso ISO montata all'avvio
    boot_from_cd: bool = False
    fullscreen: bool = False
    extra_args: str = ""            # argomenti QEMU aggiuntivi, liberi
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    folder: str = ""                # impostato dalla libreria, non salvato

    @classmethod
    def from_preset(cls, name: str, guest: str) -> "VMConfig":
        p = get_preset(guest)
        return cls(name=name, guest=p.key, ram_mb=p.ram_mb, cpus=p.cpus,
                   vga=p.vga, sound=p.sound, nic=p.nic)

    @property
    def folder_path(self) -> Path:
        return Path(self.folder)

    @property
    def disk_path(self) -> Path:
        d = Path(self.disk)
        return d if d.is_absolute() else self.folder_path / d

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("folder")
        return data

    @classmethod
    def from_dict(cls, data: dict, folder: str) -> "VMConfig":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known and k != "folder"}
        vm = cls(**clean)
        vm.folder = folder
        return vm


def safe_folder_name(name: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", name, flags=re.UNICODE).strip()
    return s or "VM"


class VMLibrary:
    """Ogni VM vive in una sua cartella: <root>/<nome>/vm.json + disco."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.vms: list[VMConfig] = []
        self.reload()

    def reload(self) -> None:
        self.vms = []
        for cfg in sorted(self.root.glob(f"*/{CONFIG_NAME}")):
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
                self.vms.append(VMConfig.from_dict(data, str(cfg.parent)))
            except (OSError, ValueError, TypeError):
                continue  # config corrotta: la ignoriamo invece di bloccare l'app

    def new_folder_for(self, name: str) -> Path:
        base = safe_folder_name(name)
        candidate = self.root / base
        n = 2
        while candidate.exists():
            candidate = self.root / f"{base} ({n})"
            n += 1
        return candidate

    def save(self, vm: VMConfig) -> None:
        if not vm.folder:
            vm.folder = str(self.new_folder_for(vm.name))
        vm.folder_path.mkdir(parents=True, exist_ok=True)
        tmp = vm.folder_path / (CONFIG_NAME + ".tmp")
        tmp.write_text(json.dumps(vm.to_dict(), indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(vm.folder_path / CONFIG_NAME)
        if vm not in self.vms:
            self.vms.append(vm)

    def remove(self, vm: VMConfig, delete_files: bool = False) -> None:
        if vm in self.vms:
            self.vms.remove(vm)
        if delete_files and vm.folder:
            import shutil
            shutil.rmtree(vm.folder_path, ignore_errors=True)
        elif vm.folder:
            # Senza vm.json la cartella non appare piu' nella libreria,
            # ma il disco resta dov'e'.
            cfg = vm.folder_path / CONFIG_NAME
            if cfg.exists():
                cfg.rename(vm.folder_path / (CONFIG_NAME + ".removed"))

    def get(self, vm_id: str) -> VMConfig | None:
        return next((v for v in self.vms if v.id == vm_id), None)
