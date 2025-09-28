#!/usr/bin/env zsh
set -euo pipefail

PORT=${1:-/dev/tty.usbmodem83201}
FWDIR=~/Downloads/mp
FWBIN=ESP32_GENERIC_C3-20250911-v1.26.1.bin
SRC="/Users/juurikas/Documents/GitHub/bsides_badge/software"

echo "Using PORT=$PORT"
mkdir -p "$FWDIR"
cd "$FWDIR"

if [[ ! -f "$FWBIN" ]]; then
  echo "Downloading firmware $FWBIN..."
  curl -LO "https://micropython.org/resources/firmware/$FWBIN"
fi

echo "== Put badge in bootloader: hold SELECT/BOOT, tap RESET =="
read "?Press [Enter] when ready..."

esptool --port "$PORT" --chip esp32c3 erase_flash
esptool --port "$PORT" --chip esp32c3 --baud 921600 write_flash 0x0 "$FWBIN" \
  || esptool --port "$PORT" --chip esp32c3 --baud 460800 write_flash 0x0 "$FWBIN"

echo "Copying software from $SRC ..."
mpremote connect "$PORT" fs cp -r "$SRC"/* :/

echo "Done. Opening REPL..."
mpremote connect "$PORT" repl
