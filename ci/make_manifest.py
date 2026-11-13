"""Crea manifest.json per una release QEMU-3dfx.

Uso: python make_manifest.py <cartella con gli archivi> <versione QEMU>
                             <commit qemu-3dfx> <commit qemu-xtra>
Gli archivi devono chiamarsi qemu3dfx-<piattaforma>.zip / .tar.gz.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

folder, qemu_version, commit, xtra = Path(sys.argv[1]), *sys.argv[2:5]
assets = {}
for f in sorted(folder.iterdir()):
    m = re.fullmatch(r"qemu3dfx-(.+?)\.(zip|tar\.gz)", f.name)
    if not m:
        continue
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    assets[m.group(1)] = {"file": f.name, "sha256": h, "size": f.stat().st_size}

if not assets:
    sys.exit("nessun archivio trovato")
manifest = {
    "format": 1,
    "qemu_version": qemu_version,
    "qemu3dfx_commit": commit,
    "qemu_xtra_commit": xtra,
    "assets": assets,
}
(folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
