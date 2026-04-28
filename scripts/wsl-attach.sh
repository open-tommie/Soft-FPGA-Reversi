#!/usr/bin/env bash
#
# wsl-attach.sh
#   WSL2 のシェルから wsl-attach.ps1 を呼ぶ薄いラッパー。
#   本体は scripts/wsl-attach.ps1（Windows PowerShell 側で実行される）。
#
# 使い方:
#   scripts/wsl-attach.sh             # = -Mode attach
#   scripts/wsl-attach.sh --bind      # = -Mode bind   (UAC 昇格)
#   scripts/wsl-attach.sh --detach    # = -Mode detach
#   scripts/wsl-attach.sh --list      # = -Mode list

set -uo pipefail

mode="attach"
case "${1:-}" in
  ""|attach) mode=attach ;;
  --bind|bind)     mode=bind ;;
  --detach|detach) mode=detach ;;
  --list|list)     mode=list ;;
  -h|--help)
    sed -n '/^# 使い方/,/^$/p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) echo "ERROR: 未知のオプション: $1" >&2; exit 1 ;;
esac

if ! command -v powershell.exe >/dev/null 2>&1; then
  echo "ERROR: powershell.exe が PATH にありません。WSL2 の interop が無効化されている可能性があります。" >&2
  exit 1
fi

DIR=$(cd "$(dirname "$0")" && pwd)
PS_PATH=$(wslpath -w "$DIR/wsl-attach.ps1")

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PS_PATH" -Mode "$mode"
ps_status=$?

# attach モードの後だけ /dev/ttyACM* を確認する。
# 期待: ttyACM0 のみ = Debug Probe (CMSIS-DAP) の UART bridge。
# Pico 2 自身の USB-CDC (busid 2-8 / 2e8a:0009) は Windows 側に残す設計
# (BOOTSEL モード遷移時の干渉を避けるため)。
if [[ "$mode" == "attach" && $ps_status -eq 0 ]]; then
  echo
  echo "===== /dev/ttyACM* (WSL 側 CDC 列挙) ====="
  mapfile -t acm < <(ls -1 /dev/ttyACM* 2>/dev/null)
  if (( ${#acm[@]} == 0 )); then
    echo "(/dev/ttyACM* なし)"
    echo "→ 想定外。Probe が attach されていないか、ドライバ列挙が失敗している。"
  elif (( ${#acm[@]} == 1 )) && [[ "${acm[0]}" == /dev/ttyACM0 ]]; then
    ls -l /dev/ttyACM0
    echo
    echo "→ ttyACM0 のみ = Debug Probe (CMSIS-DAP) の UART bridge。意図通り。"
    echo "  Pico USB-CDC も WSL に流したい場合のみ 'usbipd.exe attach --wsl --busid 2-8'。"
  else
    ls -l /dev/ttyACM*
    echo
    echo "→ 想定 (ttyACM0 のみ) と異なる構成。手動 attach した経緯が無いか確認。"
  fi
fi

exit $ps_status
