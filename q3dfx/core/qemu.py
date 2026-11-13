"""Costruzione della riga di comando QEMU e operazioni con qemu-img.

Tutto qui e' indipendente da Qt, cosi' si puo' testare senza interfaccia.
"""

from __future__ import annotations

import json
import os
import platform
import shlex
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import VMConfig
from .presets import get_preset
from .settings import AppSettings

SYSTEM = platform.system()          # "Windows" | "Linux" | "Darwin"
EXE = ".exe" if SYSTEM == "Windows" else ""

# Su Windows i processi figli non devono aprire una finestra console.
_NO_WINDOW = 0x08000000 if SYSTEM == "Windows" else 0


class QemuError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Ricerca dei binari
# --------------------------------------------------------------------------

def find_binary(name: str, qemu_dir: str = "") -> Path | None:
    """Ordine di ricerca: cartella scelta a mano, versione installata
    dall'app, PATH di sistema."""
    if qemu_dir:
        p = Path(qemu_dir) / f"{name}{EXE}"
        return p if p.is_file() else None
    from .installer import current_install
    inst = current_install()
    if inst:
        p = inst.bin_dir / f"{name}{EXE}"
        if p.is_file():
            return p
    found = shutil.which(name)
    return Path(found) if found else None


def launch_env(exe: Path) -> dict[str, str]:
    """Variabili d'ambiente per un QEMU pacchettizzato (bin/ + lib/).

    qemu-3dfx carica OpenGlide con dlopen("libglide2x.so"/".dylib") o
    LoadLibrary("glide2x.dll"), cioe' col solo nome: serve che lib/ (o bin/
    su Windows) sia nel percorso di ricerca del loader.
    """
    lib = exe.parent.parent / "lib"
    env: dict[str, str] = {}
    if SYSTEM == "Windows":
        env["PATH"] = str(exe.parent) + os.pathsep + os.environ.get("PATH", "")
    elif lib.is_dir():
        if SYSTEM == "Darwin":
            # Sostituisce il fallback di default: rimettiamo i percorsi standard.
            env["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join(
                [str(lib), "/usr/local/lib", "/usr/lib"])
        else:
            env["LD_LIBRARY_PATH"] = os.pathsep.join(
                p for p in (str(lib), os.environ.get("LD_LIBRARY_PATH", "")) if p)
    return env


def data_dir_for(exe: Path) -> Path | None:
    """Cartella dei firmware (BIOS, VGA BIOS, keymap) di un QEMU pacchettizzato."""
    share = exe.parent.parent / "share" / "qemu"
    return share if share.is_dir() else None


def qemu_system(settings: AppSettings) -> Path:
    p = find_binary("qemu-system-i386", settings.qemu_dir)
    if not p:
        raise QemuError(
            "qemu-system-i386 non trovato. Indica la cartella di QEMU-3dfx "
            "nelle Impostazioni.")
    return p


def qemu_img(settings: AppSettings) -> Path:
    p = find_binary("qemu-img", settings.qemu_dir)
    if not p:
        raise QemuError(
            "qemu-img non trovato. Indica la cartella di QEMU-3dfx nelle "
            "Impostazioni.")
    return p


# --------------------------------------------------------------------------
# Accelerazione e audio in base al sistema host
# --------------------------------------------------------------------------

def detect_accels(choice: str = "auto") -> list[str]:
    """Restituisce gli acceleratori in ordine di preferenza.

    QEMU prova i -accel nell'ordine dato e usa il primo disponibile, quindi
    'tcg' in coda fa da rete di sicurezza.
    """
    if choice and choice != "auto":
        accels = [choice]
    elif SYSTEM == "Windows":
        # kernel-irqchip=off evita blocchi noti di WHPX con i guest a 32 bit.
        accels = ["whpx,kernel-irqchip=off"]
    elif SYSTEM == "Linux":
        accels = ["kvm"] if os.access("/dev/kvm", os.R_OK | os.W_OK) else []
    elif SYSTEM == "Darwin":
        # HVF puo' accelerare guest x86 solo su Mac Intel.
        accels = ["hvf"] if platform.machine() == "x86_64" else []
    else:
        accels = []
    if "tcg" not in accels:
        accels.append("tcg")
    return accels


def audio_backend() -> str:
    return {"Windows": "dsound", "Darwin": "coreaudio"}.get(SYSTEM, "pa")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------------
# Riga di comando
# --------------------------------------------------------------------------

_SOUND_DEVICES = {"sb16": "sb16", "ac97": "AC97", "es1370": "ES1370"}

CD_DRIVE_ID = "cd0"


def _opt_path(p) -> str:
    # Nelle opzioni QEMU la virgola separa i parametri: va raddoppiata.
    return str(p).replace(",", ",,")


@dataclass
class LaunchPlan:
    argv: list[str]
    qmp_port: int
    env: dict[str, str] = None  # type: ignore[assignment]


def build_command(vm: VMConfig, settings: AppSettings,
                  qmp_port: int | None = None,
                  binary: Path | None = None) -> LaunchPlan:
    port = qmp_port or free_port()
    exe_path = Path(binary or qemu_system(settings))
    exe = str(exe_path)
    family = get_preset(vm.guest).family

    a: list[str] = [exe, "-name", vm.name, "-machine", "pc"]
    data = data_dir_for(exe_path)
    if data:
        a += ["-L", str(data)]
    for acc in detect_accels(settings.accel):
        a += ["-accel", acc]
    a += ["-m", str(vm.ram_mb), "-smp", str(max(1, vm.cpus))]
    a += ["-rtc", "base=localtime"]        # Windows si aspetta l'ora locale
    a += ["-vga", vm.vga]

    # Disco fisso (IDE primario) e lettore CD (IDE secondario, sempre presente
    # anche vuoto, cosi' si puo' inserire un'ISO a VM accesa).
    a += ["-drive", f"file={_opt_path(vm.disk_path)},format=qcow2,if=ide,"
                    "index=0,media=disk"]
    cd = f"if=ide,index=2,media=cdrom,id={CD_DRIVE_ID}"
    if vm.cdrom:
        cd = f"file={_opt_path(vm.cdrom)},{cd}"
    a += ["-drive", cd]
    a += ["-boot", "order=dc" if vm.boot_from_cd else "order=cd"]

    if vm.sound in _SOUND_DEVICES:
        a += ["-audiodev", f"{audio_backend()},id=snd0",
              "-device", f"{_SOUND_DEVICES[vm.sound]},audiodev=snd0"]

    a += ["-nic", "none" if vm.nic == "none" else f"user,model={vm.nic}"]

    # Su 2000/XP un tablet USB evita la cattura del mouse: il puntatore entra
    # ed esce dalla finestra liberamente, come con VMware Tools.
    if family == "nt":
        a += ["-usb", "-device", "usb-tablet"]

    display = settings.display or "sdl"
    if settings.gl and display in ("sdl", "gtk"):
        display += ",gl=on"
    a += ["-display", display]
    if vm.fullscreen:
        a.append("-full-screen")

    a += ["-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off"]

    if vm.extra_args.strip():
        a += shlex.split(vm.extra_args, posix=(SYSTEM != "Windows"))
    return LaunchPlan(argv=a, qmp_port=port, env=launch_env(exe_path))


def format_command(argv: list[str]) -> str:
    """Versione leggibile/copiabile del comando, per il pannello dettagli."""
    if SYSTEM == "Windows":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


# --------------------------------------------------------------------------
# qemu-img: dischi e snapshot a VM spenta
# --------------------------------------------------------------------------

def _run(argv: list[str], timeout: int = 120) -> str:
    env = {**os.environ, **launch_env(Path(argv[0]))}
    try:
        r = subprocess.run(argv, capture_output=True, text=True, env=env,
                           timeout=timeout, creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise QemuError(str(e)) from e
    if r.returncode != 0:
        raise QemuError((r.stderr or r.stdout).strip() or
                        f"{Path(argv[0]).name} ha restituito {r.returncode}")
    return r.stdout


def create_disk(settings: AppSettings, path: Path, size_gb: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise QemuError(f"Il disco {path} esiste gia'.")
    _run([str(qemu_img(settings)), "create", "-f", "qcow2", str(path),
          f"{int(size_gb)}G"])


@dataclass
class Snapshot:
    id: str
    name: str
    vm_state_size: int
    date_sec: int
    vm_clock_sec: int

    @property
    def has_ram_state(self) -> bool:
        return self.vm_state_size > 0


def parse_snapshots(info_json: str) -> list[Snapshot]:
    info = json.loads(info_json)
    out = []
    for s in info.get("snapshots", []) or []:
        out.append(Snapshot(
            id=str(s.get("id", "")),
            name=s.get("name", ""),
            vm_state_size=int(s.get("vm-state-size", 0) or 0),
            date_sec=int(s.get("date-sec", 0) or 0),
            vm_clock_sec=int(s.get("vm-clock-sec", 0) or 0),
        ))
    return out


def list_snapshots(settings: AppSettings, disk: Path) -> list[Snapshot]:
    # -U (force-share) permette di leggere il disco anche a VM accesa.
    out = _run([str(qemu_img(settings)), "info", "-U", "--output=json",
                str(disk)])
    return parse_snapshots(out)


def offline_snapshot(settings: AppSettings, disk: Path, op: str,
                     name: str) -> None:
    flag = {"create": "-c", "apply": "-a", "delete": "-d"}[op]
    _run([str(qemu_img(settings)), "snapshot", flag, name, str(disk)])
