"""Writer ISO 9660 (Level 1) minimale, senza dipendenze esterne.

Basta per creare CD dati leggibili da DOS, Windows 9x e NT: nomi 8.3 in
maiuscolo e directory annidate. Niente Joliet ne' Rock Ridge, che per i
file dei wrapper non servono.
"""

from __future__ import annotations

import datetime as _dt
import re
import struct
from dataclasses import dataclass, field

SECTOR = 2048

_D_CHARS = re.compile(r"[^A-Z0-9_]")


def _both16(v: int) -> bytes:
    return struct.pack("<H", v) + struct.pack(">H", v)


def _both32(v: int) -> bytes:
    return struct.pack("<I", v) + struct.pack(">I", v)


def _sectors(n: int) -> int:
    return (n + SECTOR - 1) // SECTOR


def to_83(name: str, is_dir: bool) -> str:
    """Converte un nome in un identificatore ISO 9660 Level 1 valido."""
    up = name.upper()
    if is_dir:
        return _D_CHARS.sub("_", up)[:8] or "_"
    base, dot, ext = up.rpartition(".")
    if not dot:
        base, ext = up, ""
    base = _D_CHARS.sub("_", base)[:8] or "_"
    ext = _D_CHARS.sub("_", ext)[:3]
    return f"{base}.{ext}" if ext else base


@dataclass
class _Dir:
    name: str                      # identificatore ISO ("" per la radice)
    parent: "_Dir | None"
    dirs: list["_Dir"] = field(default_factory=list)
    files: list[tuple[str, bytes]] = field(default_factory=list)
    lba: int = 0
    size: int = 0
    number: int = 0                # indice nella path table (1-based)


def _dir_record(ident: bytes, lba: int, size: int, is_dir: bool,
                date: bytes) -> bytes:
    pad = b"\x00" if len(ident) % 2 == 0 else b""
    length = 33 + len(ident) + len(pad)
    return (bytes([length, 0]) + _both32(lba) + _both32(size) + date +
            bytes([2 if is_dir else 0, 0, 0]) + _both16(1) +
            bytes([len(ident)]) + ident + pad)


def _record_date(t: _dt.datetime) -> bytes:
    return bytes([t.year - 1900, t.month, t.day, t.hour, t.minute, t.second, 0])


def _volume_date(t: _dt.datetime) -> bytes:
    return t.strftime("%Y%m%d%H%M%S").encode() + b"00\x00"


def _a_str(s: str, n: int) -> bytes:
    return s.upper().encode("ascii", "replace")[:n].ljust(n, b" ")


def build_iso(tree: dict, volume_id: str = "CDROM") -> bytes:
    """Crea un'immagine ISO da un albero {nome: bytes | dict}.

    I nomi vengono convertiti in 8.3 maiuscolo; due nomi che collidono dopo
    la conversione fanno sollevare ValueError invece di sovrascriversi.
    """
    now = _dt.datetime.now().replace(microsecond=0)
    rdate = _record_date(now)

    root = _Dir("", None)

    def fill(d: _Dir, node: dict) -> None:
        seen: set[str] = set()
        for name, val in sorted(node.items(), key=lambda kv: kv[0].upper()):
            is_dir = isinstance(val, dict)
            ident = to_83(name, is_dir)
            if ident in seen:
                raise ValueError(f"Nome duplicato dopo la conversione 8.3: {ident}")
            seen.add(ident)
            if is_dir:
                sub = _Dir(ident, d)
                d.dirs.append(sub)
                fill(sub, val)
            else:
                d.files.append((ident, bytes(val)))
        d.dirs.sort(key=lambda x: x.name)
        d.files.sort(key=lambda x: x[0])

    fill(root, tree)

    # Ordine della path table: per livello, poi per numero del padre, poi nome.
    ordered: list[_Dir] = []
    level = [root]
    while level:
        ordered.extend(level)
        level = [c for d in level for c in d.dirs]
    for i, d in enumerate(ordered, 1):
        d.number = i

    def entries(d: _Dir) -> list[bytes]:
        # Lunghezze provvisorie: servono solo per calcolare la dimensione.
        recs = [_dir_record(b"\x00", 0, 0, True, rdate),
                _dir_record(b"\x01", 0, 0, True, rdate)]
        recs += [_dir_record(c.name.encode(), 0, 0, True, rdate) for c in d.dirs]
        recs += [_dir_record(f"{n};1".encode(), 0, 0, False, rdate)
                 for n, _ in d.files]
        return recs

    def packed_size(recs: list[bytes]) -> int:
        # Un record di directory non puo' attraversare il confine di settore.
        pos = 0
        for r in recs:
            if pos % SECTOR + len(r) > SECTOR:
                pos += SECTOR - pos % SECTOR
            pos += len(r)
        return _sectors(pos) * SECTOR

    # Path table
    def path_table(big: bool) -> bytes:
        out = b""
        for d in ordered:
            ident = d.name.encode() or b"\x00"
            parent = d.parent.number if d.parent else 1
            fmt = ">IH" if big else "<IH"
            out += bytes([len(ident), 0]) + struct.pack(fmt, d.lba, parent) + ident
            if len(ident) % 2:
                out += b"\x00"
        return out

    pt_size = len(path_table(False))
    pt_sectors = _sectors(pt_size)

    # Allocazione: 16 settori di system area, PVD, terminatore, path tables.
    lba = 16 + 2
    l_pt, lba = lba, lba + pt_sectors
    m_pt, lba = lba, lba + pt_sectors
    for d in ordered:
        d.size = packed_size(entries(d))
        d.lba, lba = lba, lba + d.size // SECTOR
    file_lba: dict[tuple[int, str], int] = {}
    for d in ordered:
        for n, data in d.files:
            file_lba[(d.number, n)] = lba
            lba += max(1, _sectors(len(data)))
    total = lba

    img = bytearray(total * SECTOR)

    def put(at_lba: int, data: bytes) -> None:
        o = at_lba * SECTOR
        img[o:o + len(data)] = data

    # Directory
    for d in ordered:
        parent = d.parent or d
        recs = [_dir_record(b"\x00", d.lba, d.size, True, rdate),
                _dir_record(b"\x01", parent.lba, parent.size, True, rdate)]
        recs += [_dir_record(c.name.encode(), c.lba, c.size, True, rdate)
                 for c in d.dirs]
        recs += [_dir_record(f"{n};1".encode(), file_lba[(d.number, n)],
                             len(data), False, rdate) for n, data in d.files]
        buf = bytearray()
        for r in recs:
            if len(buf) % SECTOR + len(r) > SECTOR:
                buf += b"\x00" * (SECTOR - len(buf) % SECTOR)
            buf += r
        put(d.lba, bytes(buf))

    # File
    for d in ordered:
        for n, data in d.files:
            put(file_lba[(d.number, n)], data)

    put(l_pt, path_table(False))
    put(m_pt, path_table(True))

    # Primary Volume Descriptor
    vdate = _volume_date(now)
    zero_date = b"0" * 16 + b"\x00"
    pvd = bytearray(SECTOR)
    pvd[0:7] = b"\x01CD001\x01"
    pvd[8:40] = _a_str("", 32)
    pvd[40:72] = _a_str(_D_CHARS.sub("_", volume_id.upper()), 32)
    pvd[80:88] = _both32(total)
    pvd[120:124] = _both16(1)
    pvd[124:128] = _both16(1)
    pvd[128:132] = _both16(SECTOR)
    pvd[132:140] = _both32(pt_size)
    pvd[140:144] = struct.pack("<I", l_pt)
    pvd[148:152] = struct.pack(">I", m_pt)
    pvd[156:190] = _dir_record(b"\x00", root.lba, root.size, True, rdate)
    pvd[190:318] = _a_str("", 128)
    pvd[318:446] = _a_str("", 128)
    pvd[446:574] = _a_str("", 128)
    pvd[574:702] = _a_str("QEMU-3DFX MANAGER", 128)
    pvd[702:813] = b" " * 111
    pvd[813:830] = vdate
    pvd[830:847] = vdate
    pvd[847:864] = zero_date
    pvd[864:881] = zero_date
    pvd[881] = 1
    put(16, bytes(pvd))

    term = bytearray(SECTOR)
    term[0:7] = b"\xffCD001\x01"
    put(17, bytes(term))

    return bytes(img)
