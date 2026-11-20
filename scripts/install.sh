#!/usr/bin/env bash
# Install the Slovar addon into WoW: Forever's AddOns folder.
#   scripts/install.sh          symlink (edit files in the repo, then /reload in game)
#   scripts/install.sh --copy   copy instead (use if the client ignores the symlink)
# Override the target with WOW_ADDONS=/path/to/_forever_/Interface/AddOns
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO/addon/Slovar"
ADDONS="${WOW_ADDONS:-/Volumes/PerkDrive/games/World of Warcraft/_forever_/Interface/AddOns}"
DEST="$ADDONS/Slovar"

if [ ! -d "$ADDONS" ]; then
    echo "AddOns folder not found: $ADDONS"
    echo "Is the drive mounted? Or set WOW_ADDONS=/path/to/_forever_/Interface/AddOns"
    exit 1
fi

if [ "${1:-}" = "--copy" ]; then
    [ -L "$DEST" ] && rm "$DEST"
    mkdir -p "$DEST"
    rsync -a --delete "$SRC/" "$DEST/"
    echo "Copied $SRC -> $DEST"
else
    if [ -e "$DEST" ] && [ ! -L "$DEST" ]; then
        echo "$DEST is a real folder (from an earlier --copy?). Delete it first, or keep using --copy."
        exit 1
    fi
    ln -sfn "$SRC" "$DEST"
    echo "Linked $DEST -> $SRC"
fi
