#!/usr/bin/env bash
# Compila i wrapper per il guest (Glide e OpenGL per Windows 9x/2000/XP e,
# se le toolchain sono disponibili, quelli per DOS).
#
# Uso: build_wrappers.sh <checkout qemu-3dfx> <cartella di uscita>
#
# Toolchain (dal README di qemu-3dfx):
#   - mingw32 (i686-w64-mingw32): DLL Win32 - OBBLIGATORIA
#   - Open Watcom: wrapper DOS32 GLIDE2X.OVL - facoltativa
#   - DJGPP (i586/i686-pc-msdosdjgpp): wrapper .DXE - facoltativa
# Le facoltative, se presenti nel PATH, vengono usate in automatico.
set -uo pipefail

SRC=$(cd "$1" && pwd)
OUT=$2
mkdir -p "$OUT"

build_dir() {
  local dir=$1
  echo "== $dir"
  mkdir -p "$SRC/wrappers/$dir/build"
  cd "$SRC/wrappers/$dir/build" || return 1
  bash ../../../scripts/conf_wrapper || return 1
  # -k: se manca una toolchain facoltativa, gli altri target vengono
  # comunque compilati. Gli obbligatori sono controllati sotto.
  make -k || echo "::warning::alcuni target di wrappers/$dir non sono stati compilati"
}

build_dir 3dfx
build_dir mesa

# Raccoglie i binari prodotti e quelli gia' forniti dal repository
# (driver .VXD/.SYS e INSTDRV.EXE), mantenendo le sottocartelle.
cd "$SRC/wrappers"
find . -type f \( -iname '*.dll' -o -iname '*.vxd' -o -iname '*.sys' \
     -o -iname '*.exe' -o -iname '*.ovl' -o -iname '*.dxe' \) \
     -not -path '*/.git/*' -print0 |
  while IFS= read -r -d '' f; do
    mkdir -p "$OUT/$(dirname "$f")"
    cp "$f" "$OUT/$f"
  done

missing=0
for req in glide.dll glide2x.dll glide3x.dll opengl32.dll; do
  if ! find "$OUT" -iname "$req" | grep -q .; then
    echo "::error::wrapper obbligatorio mancante: $req"
    missing=1
  fi
done
for opt in fxmemmap.vxd fxptl.sys instdrv.exe glide2x.ovl; do
  find "$OUT" -iname "$opt" | grep -q . || echo "::warning::wrapper non trovato: $opt"
done
echo "Wrapper raccolti:"
find "$OUT" -type f | sort
exit $missing
