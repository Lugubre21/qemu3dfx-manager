"""Installazione di QEMU-3dfx gia' compilato, scaricato da GitHub Releases.

Formato atteso di una release (prodotta da .github/workflows/build-qemu3dfx.yml):
  - manifest.json: {"qemu_version", "qemu3dfx_commit", "assets": {
        "<piattaforma>": {"file", "sha256", "size"}}}
  - un archivio per piattaforma (.zip su Windows, .tar.gz altrove) che
    contiene la cartella "qemu3dfx/" con bin/, lib/, share/qemu/, wrappers/.

Nessuna dipendenza oltre la libreria standard, cosi' e' testabile senza Qt.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import __version__
from ..config import QEMU_RELEASE_PREFIX
from .settings import app_data_dir

API = "https://api.github.com/repos/{repo}/releases?per_page=30"
USER_AGENT = f"QEMU-3dfx-Manager/{__version__}"
TOP_DIR = "qemu3dfx"
STATE_FILE = "installed.json"

ProgressFn = Callable[[int, int], None]     # (byte scaricati, totale)
CancelFn = Callable[[], bool]


class InstallError(RuntimeError):
    pass


class Cancelled(InstallError):
    pass


# --------------------------------------------------------------------------
# Piattaforma
# --------------------------------------------------------------------------

def platform_key() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    if system == "Windows":
        # Windows su ARM esegue i binari x64 in emulazione.
        return "windows-x64"
    if system == "Darwin":
        return f"macos-{arch}"
    if system == "Linux":
        if arch != "x64":
            raise InstallError("Per Linux sono disponibili solo build x86-64.")
        return "linux-x64"
    raise InstallError(f"Sistema non supportato: {system}")


def install_root() -> Path:
    return app_data_dir() / "qemu3dfx"


# --------------------------------------------------------------------------
# Installazione presente
# --------------------------------------------------------------------------

@dataclass
class InstalledQemu:
    root: Path
    qemu_version: str
    commit: str
    tag: str

    @property
    def bin_dir(self) -> Path:
        return self.root / "bin"

    @property
    def lib_dir(self) -> Path:
        return self.root / "lib"

    @property
    def share_dir(self) -> Path:
        return self.root / "share" / "qemu"

    @property
    def wrappers_dir(self) -> Path:
        return self.root / "wrappers"

    def describe(self) -> str:
        return (f"QEMU {self.qemu_version} + qemu-3dfx {self.commit[:8]} "
                f"(release {self.tag})")


def current_install(root: Path | None = None) -> InstalledQemu | None:
    base = (root or install_root()) / "current"
    try:
        data = json.loads((base / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    exe = "qemu-system-i386.exe" if platform.system() == "Windows" else "qemu-system-i386"
    if not (base / "bin" / exe).exists():
        return None
    return InstalledQemu(base, data.get("qemu_version", "?"),
                         data.get("qemu3dfx_commit", ""), data.get("tag", ""))


# --------------------------------------------------------------------------
# Ricerca della release
# --------------------------------------------------------------------------

@dataclass
class ReleaseInfo:
    tag: str
    qemu_version: str
    commit: str
    url: str
    file: str
    sha256: str
    size: int


def _get(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json, application/octet-stream, */*",
    })
    return urllib.request.urlopen(req, timeout=timeout)   # noqa: S310 - URL https fisso


def _get_json(url: str):
    try:
        with _get(url) as r:
            return json.loads(r.read().decode("utf-8"))
    except OSError as e:
        raise InstallError(f"Impossibile contattare {url.split('/')[2]}: {e}") from e
    except ValueError as e:
        raise InstallError(f"Risposta non valida da {url}") from e


def find_latest(repo: str, key: str | None = None,
                api_template: str = API) -> ReleaseInfo:
    """Trova la release QEMU-3dfx piu' recente che ha un pacchetto per la
    piattaforma corrente."""
    if not repo or "/" not in repo or repo.startswith("TUO-UTENTE/"):
        raise InstallError(
            "Repository GitHub non configurato: impostalo nelle Impostazioni "
            "(formato utente/repository).")
    key = key or platform_key()
    releases = _get_json(api_template.format(repo=repo))
    if not isinstance(releases, list):
        raise InstallError(f"Il repository {repo} non esiste o non e' pubblico.")
    for rel in releases:                      # GitHub le restituisce dalla piu' recente
        tag = rel.get("tag_name", "")
        if rel.get("draft") or not tag.startswith(QEMU_RELEASE_PREFIX):
            continue
        assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        if "manifest.json" not in assets:
            continue
        manifest = _get_json(assets["manifest.json"])
        entry = (manifest.get("assets") or {}).get(key)
        if not entry or entry.get("file") not in assets:
            continue
        return ReleaseInfo(
            tag=tag,
            qemu_version=manifest.get("qemu_version", "?"),
            commit=manifest.get("qemu3dfx_commit", ""),
            url=assets[entry["file"]],
            file=entry["file"],
            sha256=entry["sha256"].lower(),
            size=int(entry.get("size", 0)),
        )
    raise InstallError(
        f"Nessuna release \"{QEMU_RELEASE_PREFIX}*\" con un pacchetto per "
        f"{key} nel repository {repo}. Esegui prima il workflow "
        "\"Build QEMU-3dfx\" su GitHub.")


# --------------------------------------------------------------------------
# Download, verifica, estrazione
# --------------------------------------------------------------------------

def download(info: ReleaseInfo, dest: Path, progress: ProgressFn | None = None,
             cancelled: CancelFn | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    h = hashlib.sha256()
    done = 0
    try:
        with _get(info.url, timeout=60) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or info.size or 0)
            while True:
                if cancelled and cancelled():
                    raise Cancelled("Download annullato")
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except Cancelled:
        part.unlink(missing_ok=True)
        raise
    except OSError as e:
        part.unlink(missing_ok=True)
        raise InstallError(f"Download non riuscito: {e}") from e

    if h.hexdigest() != info.sha256:
        part.unlink(missing_ok=True)
        raise InstallError("Il file scaricato e' danneggiato (SHA-256 diverso). "
                           "Riprova.")
    part.replace(dest)
    return dest


def _safe_extract(archive: Path, dest: Path) -> None:
    try:
        _extract(archive, dest)
    except (tarfile.TarError, zipfile.BadZipFile, OSError) as e:
        raise InstallError(f"Archivio non valido: {e}") from e


def _extract(archive: Path, dest: Path) -> None:
    dest_r = dest.resolve()
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                target = (dest / name).resolve()
                if dest_r not in target.parents and target != dest_r:
                    raise InstallError(f"Percorso non valido nell'archivio: {name}")
            z.extractall(dest)
    else:
        with tarfile.open(archive, "r:*") as t:
            if hasattr(tarfile, "data_filter"):
                # Blocca percorsi assoluti, "..", device e link fuori cartella.
                t.extractall(dest, filter="data")
            else:
                for m in t.getmembers():
                    target = (dest / m.name).resolve()
                    if (dest_r not in target.parents and target != dest_r) or \
                            m.issym() or m.islnk() or m.isdev():
                        raise InstallError(f"Elemento non valido: {m.name}")
                t.extractall(dest)


def install_archive(archive: Path, info: ReleaseInfo,
                    root: Path | None = None) -> InstalledQemu:
    """Estrae in una cartella temporanea e poi sostituisce 'current'.

    Se qualcosa va storto la versione precedente resta intatta.
    """
    root = root or install_root()
    root.mkdir(parents=True, exist_ok=True)
    staging = root / "staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        _safe_extract(archive, staging)
        new = staging / TOP_DIR
        exe = "qemu-system-i386.exe" if platform.system() == "Windows" else "qemu-system-i386"
        if not (new / "bin" / exe).exists():
            raise InstallError("Pacchetto incompleto: manca " + exe)
        if platform.system() != "Windows":
            for p in (new / "bin").iterdir():
                p.chmod(p.stat().st_mode | 0o755)
        (new / STATE_FILE).write_text(json.dumps({
            "tag": info.tag,
            "qemu_version": info.qemu_version,
            "qemu3dfx_commit": info.commit,
            "platform": platform_key(),
        }, indent=2), encoding="utf-8")

        current, previous = root / "current", root / "previous"
        shutil.rmtree(previous, ignore_errors=True)
        if current.exists():
            current.rename(previous)
        new.rename(current)
        shutil.rmtree(previous, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    inst = current_install(root)
    assert inst is not None
    return inst


def install_latest(repo: str, progress: ProgressFn | None = None,
                   cancelled: CancelFn | None = None,
                   status: Callable[[str], None] | None = None,
                   root: Path | None = None,
                   api_template: str = API) -> InstalledQemu:
    say = status or (lambda _m: None)
    say("Ricerca dell'ultima versione...")
    info = find_latest(repo, api_template=api_template)
    root = root or install_root()
    archive = root / "downloads" / info.file
    say(f"Download di {info.file}...")
    download(info, archive, progress, cancelled)
    say("Installazione...")
    try:
        return install_archive(archive, info, root)
    finally:
        archive.unlink(missing_ok=True)
