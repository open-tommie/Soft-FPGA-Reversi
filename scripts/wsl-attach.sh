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

set -euo pipefail

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

exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PS_PATH" -Mode "$mode"
