#!/bin/sh
# Crea strumenti/banco/vecchia/: l'AI di un commit passato, da far giocare contro quella attuale.
# uso (dalla radice del progetto): sh strumenti/banco/vecchia.sh <commit>
set -e
D=strumenti/banco/vecchia
rm -rf "$D" && mkdir -p "$D"
for f in $(git ls-tree --name-only "$1" app/ai/); do git show "$1:$f" | sed 's/app\.ai/vecchia/g' > "$D/$(basename "$f")"; done
echo "pronta in $D (AI del commit $1)"
