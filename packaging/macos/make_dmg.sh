#!/usr/bin/env bash
# Crea il .dmg da dist/QEMU-3dfx Manager.app (eseguire dalla radice del progetto).
# Uso: bash packaging/macos/make_dmg.sh <versione> [suffisso-arch]
set -euo pipefail

VERSION=$1
ARCH=${2:-$(uname -m)}
APP="dist/QEMU-3dfx Manager.app"
OUT="dist/QEMU-3dfx-Manager-$VERSION-macos-$ARCH.dmg"

[ -d "$APP" ] || { echo "Manca $APP: esegui prima PyInstaller"; exit 1; }

# Firma ad-hoc: senza un certificato Apple Developer l'app non e'
# "notarizzata", ma la firma evita l'errore "app danneggiata" sui Mac Apple
# Silicon. Al primo avvio: tasto destro > Apri.
codesign --force --deep -s - "$APP"

STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"   # trascina l'app qui per installarla
rm -f "$OUT"
hdiutil create -volname "QEMU-3dfx Manager" -srcfolder "$STAGE" \
  -ov -format UDZO "$OUT"
rm -rf "$STAGE"
echo "Creato $OUT"
