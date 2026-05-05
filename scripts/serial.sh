#!/usr/bin/env bash
set -euo pipefail

# Pico との双方向シリアル通信ラッパ (picocom)。
#
# 使い方:
#   scripts/serial.sh                 # /dev/ttyACM* で最初に見つかったポートを 115200 で
#   scripts/serial.sh /dev/ttyACM0    # ポート直接指定
#   scripts/serial.sh /dev/ttyACM0 9600
#
# CRLF:
#   送信: CR → CR+LF 変換 (--omap crcrlf)  ※ Enter キーは CR を送出する
#   受信: CR+LF はターミナルがそのまま処理（--imap なし）
#
# 終了は Ctrl-A → Ctrl-X。dialout グループ参加が必要。

BAUD="${2:-115200}"

if [[ -n "${1:-}" ]]; then
    PORT="${1}"
else
    # /dev/ttyACM* の中で最初に見つかったデバイスを自動選択
    PORT="$(ls /dev/ttyACM* 2>/dev/null | head -1)"
    if [[ -z "${PORT}" ]]; then
        echo "" >&2
        echo "エラー: /dev/ttyACM* が見つかりません。" >&2
        echo "" >&2
        echo "  Pico 2 が WSL2 に認識されていません。" >&2
        echo "  以下を確認してください:" >&2
        echo "" >&2
        echo "  1. Pico 2 を PC に USB 接続する" >&2
        echo "  2. usbipd でアタッチする:" >&2
        echo "       scripts/wsl-attach.sh" >&2
        echo "  3. 現在のデバイスを確認する:" >&2
        echo "       ls /dev/ttyACM*" >&2
        echo "" >&2
        exit 1
    fi
    echo "ポート自動選択: ${PORT}"
fi

if [[ ! -e "${PORT}" ]]; then
    echo "" >&2
    echo "エラー: ポートが見つかりません: ${PORT}" >&2
    echo "  usbipd attach し忘れの可能性。scripts/wsl-attach.sh を確認" >&2
    echo "" >&2
    exit 1
fi

if ! command -v picocom &>/dev/null; then
    echo "エラー: picocom がインストールされていません。" >&2
    echo "  sudo apt-get install -y picocom" >&2
    exit 1
fi

echo "接続中: ${PORT}  ${BAUD}bps  (終了: Ctrl-A → Ctrl-X)"
exec picocom -b "${BAUD}" --omap crcrlf --echo --quiet "${PORT}"
