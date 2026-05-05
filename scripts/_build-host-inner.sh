#!/usr/bin/env bash
set -euo pipefail

# コンテナ内で実行される。直接呼ばず scripts/build-host.sh から呼び出す。
#
# 引数:
#   [--algo lsb|max_gain]  アルゴリズム選択 (省略時: lsb)
#   (なし)                 → ビルドのみ
#   run                    → ビルド後 host/build/reversi_host を起動 (stdin 待ち)
#   run --debug            → 起動時に主要レジスタを stderr に毎 cycle 表示

# --algo オプション解析
PICK_STRATEGY_VAL=0
if [[ "${1:-}" == "--algo" ]]; then
    case "${2:-}" in
        lsb)      PICK_STRATEGY_VAL=0 ;;
        max_gain) PICK_STRATEGY_VAL=1 ;;
        *) echo "Unknown algo: '${2:-}' (lsb|max_gain)" >&2; exit 2 ;;
    esac
    shift 2
fi

cmake -S host -B host/build -G Ninja -DPICK_STRATEGY="${PICK_STRATEGY_VAL}"   >&2
cmake --build host/build                                                       >&2

# 先頭 "--" は docker compose 経由の常套句。あれば剥がす。
if [[ "${1:-}" == "--" ]]; then
    shift
fi

case "${1:-}" in
    "")
        ;;
    run)
        shift
        exec ./host/build/reversi_host "$@"
        ;;
    *)
        # 想定外の引数は警告して終了 (誤投入で勝手に exec しない)
        echo "Unknown arg: $1 (expected '' or 'run')" >&2
        exit 2
        ;;
esac
