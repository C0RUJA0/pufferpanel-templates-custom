#!/bin/sh
set -eu

PORT="${1:-}"

SOURCE="/pufferpanel/linux64/steamclient.so"
DEST="/pufferpanel/Pal/Binaries/Linux/steamclient.so"

DEFAULT="/pufferpanel/DefaultPalWorldSettings.ini"
CONFIG="/pufferpanel/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini"
MIRROR="/pufferpanel/.pufferpanel-palworld-vars.json"

GAME="/pufferpanel/Pal/Binaries/Linux/PalServer-Linux-Shipping"


fail() {
    echo "PALWORLD_START_ERROR: $*" >&2
    exit 1
}


case "$PORT" in
    ""|*[!0-9]*)
        fail "invalid game port"
        ;;
esac


[ -f "$SOURCE" ] || \
    fail "steamclient source missing"

[ -f "$DEFAULT" ] || \
    fail "DefaultPalWorldSettings.ini missing"

[ -f "$MIRROR" ] || \
    fail "PufferPanel variable mirror missing"

[ -f "$GAME" ] || \
    fail "PalServer-Linux-Shipping missing"


if [ ! -f "$DEST" ]; then
    cp "$SOURCE" "$DEST" || \
        fail "failed to install steamclient.so"
fi


chmod +x "$GAME" || \
    fail "failed to chmod game binary"


mkdir -p \
    /pufferpanel/Pal/Saved/Config/LinuxServer \
    || fail "failed to create config directory"


if [ ! -s "$CONFIG" ]; then
    cp "$DEFAULT" "$CONFIG" || \
        fail "failed to initialize PalWorldSettings.ini"
fi


/usr/local/bin/palworld-settings-sync \
    --default "$DEFAULT" \
    --active "$CONFIG" \
    --mirror "$MIRROR" \
    || fail "generic variable sync failed"


chown 1000:1000 "$CONFIG" || \
    fail "failed to set config ownership"

chmod 644 "$CONFIG" || \
    fail "failed to set config permissions"


exec runuser -u ubuntu -- \
    env HOME=/home/ubuntu \
    "$GAME" Pal \
    -port="$PORT"
