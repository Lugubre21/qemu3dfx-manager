#!/usr/bin/env bash
# Crea un AppImage da dist/QEMU-3dfx Manager/ (eseguire dalla radice del progetto).
# Uso: bash packaging/linux/make_appimage.sh <versione>
set -euo pipefail

VERSION=$1
SRC="dist/QEMU-3dfx Manager"
APPDIR=dist/AppDir
OUT="dist/QEMU-3dfx-Manager-$VERSION-x86_64.AppImage"

[ -d "$SRC" ] || { echo "Manca $SRC: esegui prima PyInstaller"; exit 1; }

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/qemu3dfx-manager"
cp -R "$SRC"/. "$APPDIR/usr/lib/qemu3dfx-manager/"
cp packaging/icons/app.png "$APPDIR/qemu3dfx-manager.png"

cat > "$APPDIR/qemu3dfx-manager.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=QEMU-3dfx Manager
Comment=Macchine virtuali retro con accelerazione Glide e OpenGL
Exec=qemu3dfx-manager
Icon=qemu3dfx-manager
Categories=System;Emulator;
Terminal=false
EOF

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/qemu3dfx-manager/QEMU-3dfx Manager" "$@"
EOF
chmod +x "$APPDIR/AppRun"

TOOL=dist/appimagetool
if [ ! -x "$TOOL" ]; then
  curl -fsSL -o "$TOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi
# --appimage-extract-and-run: funziona anche senza FUSE (es. in CI).
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT"
echo "Creato $OUT"
