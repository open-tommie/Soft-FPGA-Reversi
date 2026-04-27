#!/usr/bin/env bash
set -euo pipefail

# Pico Debug Probe (CMSIS-DAP) 経由で ELF を Pico 2 (RP2350) に書き込む。
#
# 前提:
#   - Windows 側で usbipd-win が Probe を WSL2 にアタッチ済み
#       usbipd attach --wsl --busid <BUSID>
#   - Probe の SWD/UART を Pico 2 に接続済み
#
# 使い方:
#   scripts/flash.sh                          # firmware/build/firmware.elf
#   scripts/flash.sh path/to/other.elf        # 任意の ELF

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

ELF="${1:-firmware/build/firmware.elf}"
if [[ ! -f "${ELF}" ]]; then
    echo "ELF が見つからない: ${ELF}" >&2
    echo "scripts/build-pico.sh を先に実行" >&2
    exit 1
fi

USER_UID="$(id -u)"
USER_GID="$(id -g)"
export USER_UID USER_GID ELF

exec docker compose -f docker/compose.yml run --rm flash
