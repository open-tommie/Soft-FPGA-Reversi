#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
使い方:
  scripts/doRunHost.sh [--algo lsb|max_gain]

オプション:
  --algo lsb       pick_lsb      — 行優先最初の合法手 (デフォルト)
  --algo max_gain  pick_max_gain — 反転駒数最大の合法手
  -h, --help       このヘルプを表示して終了

例:
  scripts/doRunHost.sh                          # pick_lsb でビルド＆起動
  scripts/doRunHost.sh --algo max_gain          # pick_max_gain でビルド＆起動
  printf 'PI\r\nVE\r\n' | scripts/doRunHost.sh --algo max_gain
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

cd "${SCRIPT_DIR}"
./doVersionUp.sh
exec ./build-host.sh "$@" -- run
