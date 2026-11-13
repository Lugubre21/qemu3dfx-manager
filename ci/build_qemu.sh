#!/usr/bin/env bash
# Compila QEMU con le patch qemu-3dfx, seguendo il README ufficiale.
# Funziona su Linux, macOS e nella shell MSYS2 UCRT64 di Windows.
#
# Uso: build_qemu.sh <checkout qemu-3dfx> <versione QEMU> <prefisso install>
set -euo pipefail

SRC=$(cd "$1" && pwd)
QEMU_VERSION=$2
PREFIX=$3
JOBS=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)

# La patch giusta si sceglie da major.minor: 9.2.2 -> *-qemu92x-mesa-glide.patch
MM=$(echo "$QEMU_VERSION" | cut -d. -f1,2 | tr -d .)
PATCH=$(ls "$SRC"/*-qemu"${MM}"x-mesa-glide.patch 2>/dev/null | head -n1 || true)
if [ -z "$PATCH" ]; then
  echo "::error::Nessuna patch qemu-3dfx per QEMU $QEMU_VERSION. Patch disponibili:"
  ls "$SRC"/*-mesa-glide.patch
  exit 1
fi
echo "Patch: $(basename "$PATCH")"

# Come nel README: il sorgente QEMU va estratto DENTRO il checkout di
# qemu-3dfx, perche' scripts/sign_commit legge il commit di quel repository
# e lo scrive in QEMU. I wrapper del guest portano lo stesso commit: QEMU e
# wrapper devono quindi venire dallo stesso checkout.
cd "$SRC"
curl -fsSL --retry 3 -o "qemu-$QEMU_VERSION.tar.xz" \
  "https://download.qemu.org/qemu-$QEMU_VERSION.tar.xz"
tar xf "qemu-$QEMU_VERSION.tar.xz"
cd "qemu-$QEMU_VERSION"
rsync -r ../qemu-0/hw/3dfx ../qemu-1/hw/mesa ./hw/
patch -p0 -i "$PATCH"
bash ../scripts/sign_commit

mkdir -p ../build && cd ../build
EXTRA=()
case "$(uname -s)" in
  Darwin) EXTRA+=(--enable-cocoa) ;;
esac
../"qemu-$QEMU_VERSION"/configure \
  --prefix="$PREFIX" \
  --target-list=i386-softmmu \
  --disable-docs \
  --enable-sdl \
  --enable-opengl \
  --enable-slirp \
  "${EXTRA[@]}"
make -j"$JOBS"
make install

# Il binario deve contenere i dispositivi di pass-through.
QEMU_BIN=$(ls "$PREFIX"/bin/qemu-system-i386* "$PREFIX"/qemu-system-i386* 2>/dev/null | head -n1)
if ! strings "$QEMU_BIN" | grep -qi glide; then
  echo "::error::Il binario non sembra contenere il pass-through Glide"
  exit 1
fi
echo "QEMU-3dfx installato in $PREFIX"
