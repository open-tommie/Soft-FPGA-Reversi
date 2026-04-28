#!/usr/bin/env bash
set -euo pipefail

# Pico からの USB-CDC / UART 出力を素読みするだけのラッパ。
#
# 使い方:
#   scripts/serial.sh                 # /dev/ttyACM1 (Probe UART 中継) を 115200 で
#   scripts/serial.sh /dev/ttyACM0    # 別ポート指定
#   scripts/serial.sh /dev/ttyACM1 9600
#
# 終了は Ctrl-C。`stty` を呼ぶので tty への書込み権限が要る (dialout グループ参加)。

PORT="${1:-/dev/ttyACM1}"
BAUD="${2:-115200}"

if [[ ! -e "${PORT}" ]]; then
    echo "ポートが無い: ${PORT}" >&2
    echo "usbipd attach し忘れの可能性。scripts/wsl-attach.sh を確認" >&2
    exit 1
fi

stty -F "${PORT}" "${BAUD}" raw -echo -ixon -ixoff cs8 -cstopb -parenb
exec cat "${PORT}"
