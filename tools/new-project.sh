#!/bin/bash
# new-project.sh - copy a template into projects/<name> (a working video).   bash tools/new-project.sh my-launch [starter|shorts]
#   starter (default): 1920x1080, 6 s product-style film.   shorts: 1080x1920, archival footage + captions + end-card loop (see templates/shorts/README.md).
set -euo pipefail
[ $# -ge 1 ] && [ $# -le 2 ] || { echo "usage: bash tools/new-project.sh <name> [starter|shorts]"; exit 2; }
REPO="$(cd "$(dirname "$0")/.." && pwd)"; DEST="$REPO/projects/$1"; TPL="${2:-starter}"
[ -d "$REPO/templates/$TPL" ] || { echo "no template '$TPL' (try: $(ls "$REPO/templates" | tr '\n' ' '))"; exit 2; }
[ ! -e "$DEST" ] || { echo "$DEST already exists"; exit 1; }
cp -R "$REPO/templates/$TPL" "$DEST"
echo "Created projects/$1  -  preview: node tools/render.js projects/$1 --stills 1,3"
