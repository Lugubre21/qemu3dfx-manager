# QEMU-3dfx Manager

App per Windows, macOS e Linux che usa [QEMU-3dfx](https://github.com/kjliew/qemu-3dfx) come VMware o Parallels:

- libreria di macchine virtuali
- creazione guidata
- snapshot
- CD "3dfx Tools" con i wrapper Glide e OpenGL per il guest
- installazione automatica di QEMU-3dfx quando non è presente

## Come funziona la distribuzione

Il progetto usa due workflow GitHub Actions, in `.github/workflows/`:

| Workflow | Cosa fa | Quando |
|---|---|---|
| **Build QEMU-3dfx** | Compila QEMU + patch qemu-3dfx, OpenGlide (lato host) e i wrapper del guest per Windows, Linux, Mac Intel e Mac Apple Silicon. Pubblica una release `qemu3dfx-<data>` con `manifest.json`. | A mano, da Actions; serve solo quando vuoi aggiornare QEMU-3dfx |
| **Build app** | Crea gli installer dell'app: `Setup.exe` per Windows, `.dmg` per Mac Intel e ARM, `AppImage` per Linux. | Ad ogni tag `v*` (es. `v0.2.0`) |

Quando l'app parte e non trova QEMU-3dfx, propone di installarlo. In quel caso:

1. scarica dalla release `qemu3dfx-*` più recente il pacchetto per il sistema in uso;
2. ne verifica lo SHA-256;
3. lo installa nella cartella dati dell'app.

Nessun compilatore è richiesto sul computer dell'utente.

## Primo avvio su GitHub (una volta sola)

1. Crea un account su github.com e un repository **pubblico** chiamato, ad esempio, `qemu3dfx-manager`. Pubblico serve sia perché l'app scarica senza login, sia perché i runner di Actions sono gratuiti per i repository pubblici.
2. In `q3dfx/config.py` sostituisci `TUO-UTENTE/qemu3dfx-manager` con `tuonome/qemu3dfx-manager`.
3. Carica il progetto. Dal Terminale del Mac, nella cartella del progetto:
   ```
   git init
   git add .
   git commit -m "QEMU-3dfx Manager 0.2.0"
   git branch -M main
   git remote add origin https://github.com/tuonome/qemu3dfx-manager.git
   git push -u origin main
   ```
4. Su GitHub apri **Actions** → **Build QEMU-3dfx** → **Run workflow**. La prima build richiede circa 30-60 minuti e alla fine compare la release `qemu3dfx-...`.
5. Crea gli installer dell'app:
   ```
   git tag v0.2.0
   git push origin v0.2.0
   ```
   Il workflow **Build app** pubblica la release `v0.2.0` con gli installer.

## Build in locale (senza GitHub)

PyInstaller crea l'app solo per il sistema su cui gira. Sul Mac:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-build.txt
python packaging/build_local.py
```

Il risultato è in `dist/`. Su Windows serve anche [Inno Setup 6](https://jrsoftware.org/isinfo.php).

Per provare l'app dai sorgenti, senza creare installer:

```
pip install -r requirements.txt
python main.py
```

## Note per gli utenti

- **macOS**: l'app non è firmata con un certificato Apple Developer. Al primo avvio fai tasto destro → **Apri** → **Apri**.
- **Windows**: SmartScreen può mostrare "Windows ha protetto il PC". Premi **Ulteriori informazioni** → **Esegui comunque**. Per l'accelerazione serve la funzionalità **Piattaforma hypervisor Windows** (Windows Hypervisor Platform).
- **Linux**: l'AppImage richiede `libxcb-cursor0` (Qt 6) e, per l'accelerazione, l'accesso a `/dev/kvm`. Per l'accesso a KVM aggiungi l'utente al gruppo `kvm`.
- **Mac Apple Silicon**: i guest x86 girano in emulazione (TCG), quindi più lentamente che su un Mac Intel.

## Struttura

```
main.py                     avvio dell'app
q3dfx/config.py             repository GitHub da cui scaricare QEMU-3dfx
q3dfx/core/                 logica senza Qt (testabile): VM, comandi QEMU,
                            QMP, ISO 9660, installer
q3dfx/ui/                   interfaccia PySide6
ci/                         script di build di QEMU-3dfx usati dal workflow
packaging/                  PyInstaller, Inno Setup, dmg, AppImage, icone
.github/workflows/          i due workflow
```

## Licenze

QEMU e qemu-3dfx sono GPL-2.0, OpenGlide è LGPL-2.1. Ogni release `qemu3dfx-*` indica nelle note e in `SOURCES.txt` i commit esatti dei sorgenti usati, come richiesto dalla GPL. Gli script di build sono nella cartella `ci/` di questo repository.

## Limiti noti

- **Coherence** (finestre del guest sul desktop host) non è inclusa: richiede un agente da scrivere in C/Win32 dentro il guest.
- I wrapper DOS (OVL/DXE) vengono compilati solo se nel workflow sono disponibili le toolchain Open Watcom e DJGPP. I wrapper per Windows 9x/2000/XP sono invece obbligatori: se mancano, il workflow si ferma con un errore.
- Il pacchetto QEMU per macOS usa librerie di Homebrew compilate per la versione di macOS del runner (macOS 15). Sui Mac con un macOS più vecchio potrebbe non avviarsi.
