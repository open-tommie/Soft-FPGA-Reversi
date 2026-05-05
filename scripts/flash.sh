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
#   scripts/flash.sh                               # firmware_lsb (デフォルト)
#   scripts/flash.sh firmware/build/firmware_max_gain.elf
#   scripts/flash.sh path/to/other.elf             # 任意の ELF

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

ELF="${1:-firmware/build/firmware_lsb.elf}"
if [[ ! -f "${ELF}" ]]; then
    echo "ELF が見つからない: ${ELF}" >&2
    echo "scripts/build-pico.sh を先に実行" >&2
    exit 1
fi

USER_UID="$(id -u)"
USER_GID="$(id -g)"
export USER_UID USER_GID ELF

# PowerShell から参照できる Windows パス (\\wsl.localhost\Ubuntu-24.04\...)
WIN_PATH="$(wslpath -w "${REPO_ROOT}" 2>/dev/null || echo "<WSL パス取得失敗>")"

# USB バスが WSL2 に見えているか確認
if [[ ! -d /dev/bus/usb ]]; then
    echo "" >&2
    echo "エラー: /dev/bus/usb が見つかりません。" >&2
    echo "" >&2
    echo "  USB デバイスが WSL2 にアタッチされていません。" >&2
    echo "  以下を確認してください:" >&2
    echo "" >&2
    echo "  1. Debug Probe と Pico 2 を PC に USB 接続する" >&2
    echo "  2. usbipd でアタッチする:" >&2
    echo "" >&2
    echo "     [WSL から]" >&2
    echo "       scripts/wsl-attach.sh" >&2
    echo "" >&2
    echo "     [PowerShell (管理者) から]" >&2
    echo "       cd \"${WIN_PATH}\"" >&2
    echo "       .\\scripts\\wsl-attach.ps1" >&2
    echo "" >&2
    echo "     [手動で busid を指定する場合]" >&2
    echo "       usbipd attach --wsl --busid <BUSID>  # Probe の BUSID を指定" >&2
    echo "" >&2
    exit 1
fi

# Debug Probe (VID:PID = 2e8a:000c) が見えているか確認
if ! lsusb 2>/dev/null | grep -q "2e8a:000c"; then
    echo "" >&2
    echo "エラー: Debug Probe (CMSIS-DAP) が見つかりません。" >&2
    echo "" >&2
    echo "  lsusb に 2e8a:000c が現れていません。" >&2
    echo "  以下を確認してください:" >&2
    echo "" >&2
    echo "  1. Debug Probe が PC に接続されているか確認する" >&2
    echo "  2. usbipd でアタッチする:" >&2
    echo "" >&2
    echo "     [WSL から]" >&2
    echo "       scripts/wsl-attach.sh" >&2
    echo "" >&2
    echo "     [PowerShell (管理者) から]" >&2
    echo "       cd \"${WIN_PATH}\"" >&2
    echo "       .\\scripts\\wsl-attach.ps1" >&2
    echo "" >&2
    echo "  3. 現在アタッチ済みのデバイスを確認する:" >&2
    echo "       lsusb" >&2
    echo "" >&2
    exit 1
fi

docker compose -f docker/compose.yml run --rm flash

echo ""
echo "書き込み完了: firmware.elf を Pico 2 に書き込みました。"
echo "  Pico 2 が自動リセットされ、新しいファームウェアで起動しています。"
