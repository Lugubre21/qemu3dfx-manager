"""Generazione dell'ISO "3dfx Tools", l'equivalente di VMware Tools.

Cerca i wrapper compilati di qemu-3dfx in una cartella (anche annidata), li
organizza in un CD con script di installazione per Windows 9x/ME e per
Windows 2000/XP, e scrive l'immagine ISO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .iso9660 import build_iso, to_83

# Dove finisce ciascun file nel guest (dal README di qemu-3dfx).
GLIDE_CORE = ["GLIDE.DLL", "GLIDE2X.DLL", "GLIDE3X.DLL"]
NINE_X_ONLY = ["FXMEMMAP.VXD"]           # -> %windir%\SYSTEM (solo 9x)
NT_ONLY = ["FXPTL.SYS", "INSTDRV.EXE"]   # driver e installer (solo 2000/XP)
OVL = ["GLIDE2X.OVL"]                    # -> %windir% (9x) e giochi DOS
OPENGL = ["OPENGL32.DLL"]                # -> cartella di ogni gioco
KNOWN = set(GLIDE_CORE + NINE_X_ONLY + NT_ONLY + OVL + OPENGL)

# Altre DLL utili (es. WineD3D modificate) vanno copiate nei giochi a mano.
EXTRA_SUFFIXES = {".DLL", ".DXE", ".EXE", ".VXD", ".SYS", ".OVL"}


@dataclass
class WrapperScan:
    found: dict[str, Path] = field(default_factory=dict)   # NOME.EXT -> file
    dxe: dict[str, Path] = field(default_factory=dict)     # wrapper DJGPP
    extras: dict[str, Path] = field(default_factory=dict)  # es. WineD3D
    warnings: list[str] = field(default_factory=list)

    @property
    def has_glide(self) -> bool:
        return any(n in self.found for n in GLIDE_CORE)

    def summary(self) -> str:
        lines = ["Wrapper trovati: " + (", ".join(sorted(self.found)) or "nessuno")]
        if self.dxe:
            lines.append("Wrapper DOS (DJGPP): " + ", ".join(sorted(self.dxe)))
        if self.extras:
            lines.append("Altri file: " + ", ".join(sorted(self.extras)))
        lines += self.warnings
        return "\n".join(lines)


def scan_wrappers(folder: Path) -> WrapperScan:
    scan = WrapperScan()
    folder = Path(folder)
    if not folder.is_dir():
        scan.warnings.append(f"La cartella {folder} non esiste.")
        return scan

    def rank(p: Path) -> tuple:
        # Con duplicati in piu' sottocartelle si preferiscono le build per
        # Windows a quelle per DOS/DJGPP/Linux.
        parts = [s.lower() for s in p.relative_to(folder).parts[:-1]]
        other = any(k in s for s in parts for k in ("djgpp", "dos", "linux"))
        return (other, len(parts), str(p).lower())

    files = sorted((p for p in folder.rglob("*") if p.is_file()), key=rank)
    for p in files:
        name = p.name.upper()
        suffix = p.suffix.upper()
        if name in KNOWN:
            bucket = scan.found
        elif suffix == ".DXE":
            bucket = scan.dxe
        elif suffix in EXTRA_SUFFIXES:
            bucket = scan.extras
        else:
            continue
        if to_83(name, is_dir=False) != name:
            # Un nome accorciato renderebbe la DLL inutilizzabile nel guest.
            scan.warnings.append(
                f"{p.name} non rispetta il formato 8.3: escluso dall'ISO")
            continue
        if name in bucket:
            scan.warnings.append(
                f"{name} presente piu' volte: uso {bucket[name]}, ignoro {p}")
            continue
        bucket[name] = p

    if not scan.has_glide:
        scan.warnings.append(
            "Nessuna GLIDE*.DLL trovata: controlla di aver indicato la "
            "cartella dei wrapper compilati.")
    return scan


def _crlf(text: str) -> bytes:
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("cp850", "replace")


def _setup_9x(scan: WrapperScan) -> str:
    lines = [
        "@ECHO OFF",
        "ECHO QEMU-3dfx Tools - installazione per Windows 95/98/ME",
        "ECHO.",
        "IF NOT EXIST SETUP9X.BAT GOTO NOCD",
    ]
    for n in NINE_X_ONLY + GLIDE_CORE:
        if n in scan.found:
            lines += [f"COPY /Y GLIDE\\{n} %windir%\\SYSTEM",
                      f"ATTRIB -R %windir%\\SYSTEM\\{n}"]
    for n in OVL:
        if n in scan.found:
            lines += [f"COPY /Y GLIDE\\{n} %windir%",
                      f"ATTRIB -R %windir%\\{n}"]
    lines += [
        "ECHO.",
        "ECHO Fatto. Riavvia Windows prima di avviare i giochi Glide.",
    ]
    if "OPENGL32.DLL" in scan.found:
        lines.append("ECHO Per OpenGL copia OPENGL\\OPENGL32.DLL nella cartella del gioco.")
    lines += [
        "GOTO END",
        ":NOCD",
        "ECHO Avvia questo file direttamente dal CD QEMU-3dfx Tools.",
        ":END",
        "PAUSE",
    ]
    return "\n".join(lines) + "\n"


def _setup_nt(scan: WrapperScan) -> str:
    lines = [
        "@echo off",
        "echo QEMU-3dfx Tools - installazione per Windows 2000/XP",
        "echo Serve un account amministratore.",
        "echo.",
        'cd /d "%~dp0"',
    ]
    if "FXPTL.SYS" in scan.found:
        lines += ['copy /y GLIDE\\FXPTL.SYS "%SystemRoot%\\system32\\drivers\\"',
                  'attrib -r "%SystemRoot%\\system32\\drivers\\FXPTL.SYS"']
    for n in GLIDE_CORE:
        if n in scan.found:
            lines += [f'copy /y GLIDE\\{n} "%SystemRoot%\\system32\\"',
                      f'attrib -r "%SystemRoot%\\system32\\{n}"']
    if "INSTDRV.EXE" in scan.found:
        lines += ["echo Registrazione del driver FXPTL...", "GLIDE\\INSTDRV.EXE"]
    lines += ["echo.", "echo Fatto. Riavvia Windows prima di avviare i giochi Glide."]
    if "OPENGL32.DLL" in scan.found:
        lines.append("echo Per OpenGL copia OPENGL\\OPENGL32.DLL nella cartella del gioco.")
    lines.append("pause")
    return "\n".join(lines) + "\n"


_README = """QEMU-3dfx Tools
===============

WINDOWS 95 / 98 / ME
  Esegui SETUP9X.BAT da questo CD, poi riavvia.

WINDOWS 2000 / XP
  Esegui SETUPNT.BAT da questo CD (come amministratore), poi riavvia.

OPENGL
  OPENGL32.DLL NON va installata nel sistema: copiala nella cartella di
  ciascun gioco OpenGL che vuoi accelerare.

DOS
  I giochi Glide per DOS usano GLIDE2X.OVL (cartella GLIDE) e, per i
  titoli DJGPP, i file .DXE nella cartella DOS: copiali nella cartella
  del gioco.

ALTRI FILE (cartella EXTRA)
  Ad esempio le librerie WineD3D modificate per DirectDraw/Direct3D:
  copiale nella cartella del gioco che le richiede.

Generato da QEMU-3dfx Manager.
"""


def build_tools_tree(scan: WrapperScan) -> dict:
    tree: dict = {
        "SETUP9X.BAT": _crlf(_setup_9x(scan)),
        "SETUPNT.BAT": _crlf(_setup_nt(scan)),
        "LEGGIMI.TXT": _crlf(_README),
    }
    glide = {n: p.read_bytes() for n, p in scan.found.items() if n not in OPENGL}
    if glide:
        tree["GLIDE"] = glide
    gl = {n: p.read_bytes() for n, p in scan.found.items() if n in OPENGL}
    if gl:
        tree["OPENGL"] = gl
    if scan.dxe:
        tree["DOS"] = {n: p.read_bytes() for n, p in scan.dxe.items()}
    if scan.extras:
        tree["EXTRA"] = {n: p.read_bytes() for n, p in scan.extras.items()}
    return tree


def write_tools_iso(wrappers_dir: Path, out_path: Path) -> WrapperScan:
    """Scansiona i wrapper e scrive l'ISO. Solleva ValueError se non ci sono
    file Glide, cosi' non si crea un CD vuoto senza accorgersene."""
    scan = scan_wrappers(wrappers_dir)
    if not scan.has_glide:
        raise ValueError(scan.summary())
    data = build_iso(build_tools_tree(scan), volume_id="Q3DFX_TOOLS")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(out_path)
    return scan
