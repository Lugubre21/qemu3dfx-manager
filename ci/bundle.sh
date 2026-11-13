#!/usr/bin/env bash
# Crea la cartella "qemu3dfx/" autosufficiente che l'app installa:
#   bin/          qemu-system-i386, qemu-img (+ DLL su Windows)
#   lib/          OpenGlide e librerie necessarie (Linux/macOS)
#   share/qemu/   BIOS, VGA BIOS, keymap
#   wrappers/     wrapper per il guest
#   SOURCES.txt   da dove vengono i sorgenti (licenza GPL)
#
# Uso: bundle.sh <piattaforma> <prefisso QEMU> <prefisso OpenGlide>
#                <cartella wrapper> <cartella sorgente QEMU> <uscita>
set -euo pipefail

PLATFORM=$1; QPREFIX=$2; GPREFIX=$3; WRAPPERS=$4; QSRC=$5; OUT=$6
B="$OUT/qemu3dfx"
rm -rf "$B"
mkdir -p "$B/bin" "$B/lib" "$B/share/qemu" "$B/wrappers"
cp -R "$WRAPPERS"/. "$B/wrappers/"

case "$PLATFORM" in
# ---------------------------------------------------------------- Linux
linux-*)
  cp "$QPREFIX/bin/qemu-system-i386" "$QPREFIX/bin/qemu-img" "$B/bin/"
  cp -R "$QPREFIX/share/qemu/." "$B/share/qemu/"
  # QEMU fa dlopen("libglide2x.so"): serve il file con esattamente quel nome.
  for g in libglide2x libglide3x; do
    cp -L "$GPREFIX/lib/$g.so" "$B/lib/$g.so"
  done
  # Copia le dipendenze non garantite dal sistema. Restano esclusi glibc e
  # le librerie legate a driver grafici, X/Wayland e server audio, che
  # devono venire dal sistema dell'utente.
  EXCLUDE='^(linux-vdso|ld-linux|libc\.|libm\.|libdl\.|librt\.|libpthread\.|libresolv\.|libutil\.|libGL|libEGL|libGLX|libGLdispatch|libOpenGL|libdrm|libgbm|libvulkan|libX|libxcb|libwayland|libasound|libpulse|libpipewire|libjack|libdbus|libsystemd|libudev|libstdc\+\+|libgcc_s)'
  for f in "$B/bin/"* "$B/lib/"*.so; do
    ldd "$f" | awk '/=> \//{print $1" "$3}' | while read -r name path; do
      if ! echo "$name" | grep -Eq "$EXCLUDE" && [ ! -e "$B/lib/$name" ]; then
        cp -L "$path" "$B/lib/$name"
      fi
    done
  done
  ;;
# ---------------------------------------------------------------- macOS
macos-*)
  cp "$QPREFIX/bin/qemu-system-i386" "$QPREFIX/bin/qemu-img" "$B/bin/"
  cp -R "$QPREFIX/share/qemu/." "$B/share/qemu/"
  for g in libglide2x libglide3x; do
    cp -L "$GPREFIX/lib/$g.dylib" "$B/lib/$g.dylib"
  done
  # Copia le dylib di Homebrew in lib/ e riscrive i riferimenti, cosi' il
  # pacchetto funziona anche dove Homebrew non c'e'.
  dylibbundler -of -b -cd \
    -x "$B/bin/qemu-system-i386" -x "$B/bin/qemu-img" \
    -x "$B/lib/libglide2x.dylib" -x "$B/lib/libglide3x.dylib" \
    -d "$B/lib/" -p @executable_path/../lib/
  # Le modifiche invalidano le firme: firma ad-hoc, con l'entitlement per
  # usare Hypervisor.framework (HVF) su qemu-system-i386.
  codesign --force -s - "$B/lib/"*.dylib
  codesign --force -s - "$B/bin/qemu-img"
  codesign --force -s - --entitlements "$QSRC/accel/hvf/entitlements.plist" \
    "$B/bin/qemu-system-i386"
  ;;
# ---------------------------------------------------------------- Windows
windows-*)
  # Su Windows "make install" mette eseguibili e firmware nella radice del
  # prefisso; per sicurezza li cerchiamo anche in bin/ e share/qemu/.
  QEXE=$(find "$QPREFIX" -maxdepth 2 -name qemu-system-i386.exe | head -n1)
  QROOT=$(dirname "$QEXE")
  cp "$QEXE" "$QROOT/qemu-img.exe" "$B/bin/"
  for dir in "$QROOT" "$QPREFIX" "$QPREFIX/share/qemu"; do
    [ -d "$dir" ] || continue
    find "$dir" -maxdepth 1 -type f \
      \( -name '*.bin' -o -name '*.rom' -o -name '*.img' -o -name '*.fd' \
         -o -name '*.dtb' -o -name '*.ndrv' \) -exec cp {} "$B/share/qemu/" \;
    for d in keymaps firmware; do
      if [ -d "$dir/$d" ]; then cp -R "$dir/$d" "$B/share/qemu/"; fi
    done
  done
  # QEMU fa LoadLibrary("glide2x.dll"), poi "libglide2x.dll".
  for g in glide2x glide3x; do
    dll=$(ls "$GPREFIX"/bin/lib"$g"*.dll | head -n1)
    cp "$dll" "$B/bin/$g.dll"
  done
  # DLL di MSYS2 necessarie agli eseguibili e a OpenGlide.
  for f in "$B/bin/"*.exe "$B/bin/"*.dll; do
    ldd "$f" | awk '/\/ucrt64\//{print $3}' | while read -r dep; do
      if [ ! -e "$B/bin/$(basename "$dep")" ]; then cp "$dep" "$B/bin/"; fi
    done
  done
  rmdir "$B/lib" 2>/dev/null || true
  ;;
*) echo "piattaforma sconosciuta: $PLATFORM"; exit 1 ;;
esac

cat > "$B/SOURCES.txt" <<EOF
Questo pacchetto contiene software libero distribuito con licenza GPL.
Sorgenti corrispondenti:
  QEMU ${QEMU_VERSION:-?}: https://download.qemu.org/qemu-${QEMU_VERSION:-}.tar.xz
  qemu-3dfx (patch e wrapper): https://github.com/kjliew/qemu-3dfx/tree/${QEMU3DFX_SHA:-master}
  OpenGlide (qemu-xtra): https://github.com/kjliew/qemu-xtra/tree/${XTRA_SHA:-master}
  Script di build: cartella ci/ del repository di QEMU-3dfx Manager
Licenze: GPL-2.0 (QEMU, qemu-3dfx), LGPL-2.1 (OpenGlide).
EOF
echo "Pacchetto pronto in $B"
du -sh "$B"
