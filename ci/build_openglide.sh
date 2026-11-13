#!/usr/bin/env bash
# Compila OpenGlide di kjliew/qemu-xtra: e' la libreria lato host che QEMU
# carica (libglide2x/libglide3x) per disegnare con OpenGL le chiamate Glide.
#
# Uso: build_openglide.sh <checkout qemu-xtra> <prefisso install>
set -euo pipefail

XTRA=$(cd "$1" && pwd)
PREFIX=$2
JOBS=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)

cd "$XTRA/openglide"
autoreconf -fi
./configure --prefix="$PREFIX" --enable-shared --disable-static --disable-sdltest
make -j"$JOBS"
make install

ls -la "$PREFIX"/lib/libglide* "$PREFIX"/bin/*glide* 2>/dev/null || true
