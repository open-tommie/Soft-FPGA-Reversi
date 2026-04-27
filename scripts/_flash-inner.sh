#!/usr/bin/env bash
set -euo pipefail

# コンテナ内で実行される。直接呼ばず scripts/flash.sh から呼び出す。

ELF="${1:-firmware/build/firmware.elf}"

if [[ ! -f "${ELF}" ]]; then
    echo "ELF が見つからない: ${ELF}" >&2
    exit 1
fi

# USB デバイスが見えているか先に確認 (usbipd attach し忘れの早期検出)
if ! lsusb 2>/dev/null | grep -qi 'cmsis\|raspberry pi.*debug\|2e8a:000c'; then
    echo "WARN: CMSIS-DAP / Pico Debug Probe が lsusb に見えない" >&2
    echo "  Windows: usbipd attach --wsl --busid <BUSID>" >&2
    lsusb 2>&1 | sed 's/^/  /' >&2 || true
fi

exec openocd \
    -f interface/cmsis-dap.cfg \
    -f target/rp2350.cfg \
    -c "adapter speed 5000" \
    -c "program ${ELF} verify reset exit"
