#!/usr/bin/env bash
set -euo pipefail

# Pico 2 ELF / UF2 のサイズと中身を 1 コマンドで覗く。
# サイズ調整やリファクタの前後比較に。
#
# 使い方:
#   scripts/size.sh                          # 既定 ELF (firmware/build/firmware.elf)
#   scripts/size.sh path/to/other.elf        # ELF 指定
#   scripts/size.sh --symbols 50             # シンボル top 50 まで
#   scripts/size.sh --diff /tmp/before.elf   # 2 ELF のサイズ + シンボル差分
#   scripts/size.sh --map                    # .map ファイルから配置のハイライト
#   scripts/size.sh --strings <pat>          # ELF 内の文字列を grep
#   scripts/size.sh --bloaty                 # bloaty で compileunits + sections の origin tree
#   scripts/size.sh --bloaty-diff <other>    # bloaty で 2 ELF を比較
#   scripts/size.sh -h                       # ヘルプ

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

ELF="firmware/build/firmware.elf"
MODE="default"
TOP_N=20
DIFF_ELF=""
STR_PATTERN=""

usage() {
    sed -n '4,12p' "$0" | sed 's/^# //; s/^#$//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)      usage ;;
        --symbols)      MODE="symbols";     TOP_N="${2:-20}"; shift 2 ;;
        --diff)         MODE="diff";        DIFF_ELF="$2";    shift 2 ;;
        --map)          MODE="map";         shift ;;
        --strings)      MODE="strings";     STR_PATTERN="${2:-.}"; shift 2 ;;
        --bloaty)       MODE="bloaty";      shift ;;
        --bloaty-diff)  MODE="bloaty-diff"; DIFF_ELF="$2";    shift 2 ;;
        -*)             echo "unknown option: $1" >&2; exit 2 ;;
        *)              ELF="$1"; shift ;;
    esac
done

[[ -f "${ELF}" ]] || { echo "ELF が無い: ${ELF}" >&2; exit 1; }

# Docker 1 回で複数コマンドを連続実行 (cold start を 1 回にするため)
run_in_dev() {
    docker compose -f docker/compose.yml run --rm dev bash -c "$1"
}

# diff の比較 ELF はコンテナの /work 配下に居る必要がある (compose の mount 仕様)。
# repo 外 (例: /tmp/before.elf) を渡された場合は build/ 配下に一時コピーする。
stage_diff_elf() {
    local src="$1"
    if [[ "${src}" = /work/* || "${src}" != /* ]]; then
        # 既に /work 配下、または repo 相対パス
        echo "${src}"
        return
    fi
    local dst="firmware/build/.size-baseline.elf"
    cp "${src}" "${dst}"
    echo "${dst}"
    # 呼び出し側でクリーンアップは行わない (上書きされるだけなので放置)
}

case "${MODE}" in
default)
    # よく使う 2 セット: size 概要 + 大きいシンボル top N
    run_in_dev "
        echo '=== arm-none-eabi-size ==='
        arm-none-eabi-size '${ELF}'
        echo
        echo '=== top ${TOP_N} symbols (demangled) ==='
        arm-none-eabi-nm --size-sort -r --print-size '${ELF}' \
            | head -${TOP_N} \
            | arm-none-eabi-c++filt
        echo
        echo '=== section sizes (top 10) ==='
        arm-none-eabi-size -A '${ELF}' | sort -k2 -n -r | head -10
    "
    ;;

symbols)
    run_in_dev "
        arm-none-eabi-nm --size-sort -r --print-size '${ELF}' \
            | head -${TOP_N} \
            | arm-none-eabi-c++filt
    "
    ;;

diff)
    [[ -f "${DIFF_ELF}" ]] || { echo "比較 ELF が無い: ${DIFF_ELF}" >&2; exit 1; }
    DIFF_ELF="$(stage_diff_elf "${DIFF_ELF}")"
    run_in_dev "
        echo '=== size diff (left = ${DIFF_ELF}, right = ${ELF}) ==='
        diff -u <(arm-none-eabi-size -A '${DIFF_ELF}' | sort) \
                <(arm-none-eabi-size -A '${ELF}' | sort) \
            || true
        echo
        echo '=== symbol top-30 diff ==='
        diff -u <(arm-none-eabi-nm --size-sort -r --print-size '${DIFF_ELF}' \
                   | head -30 | arm-none-eabi-c++filt) \
                <(arm-none-eabi-nm --size-sort -r --print-size '${ELF}' \
                   | head -30 | arm-none-eabi-c++filt) \
            || true
    "
    ;;

map)
    MAP="${ELF%.elf}.elf.map"
    [[ -f "${MAP}" ]] || { echo ".map が無い: ${MAP}" >&2; exit 1; }
    echo "=== ${MAP} のハイライト ==="
    grep -nE '^\.(text|rodata|data|bss)\b' "${MAP}" | head -10
    echo
    echo "=== 入力 .o 別の貢献度 (top 30 by size) ==="
    awk '/^ \.[a-z]+\./ && NF>=4 {
        size = strtonum("0x" substr($3, 3))
        if (size > 0) printf "%8d  %s\n", size, $4
    }' "${MAP}" | sort -n -r | head -30
    ;;

strings)
    run_in_dev "
        arm-none-eabi-strings '${ELF}' | grep -E '${STR_PATTERN}' | head -50
    "
    ;;

bloaty)
    # compileunits: どのソースファイルが何 byte 占めるか
    # sections: それを ELF セクションでさらに分解 (.text / .rodata / .bss など)
    # -s file: ファイルサイズ基準 (vm より直感的)
    run_in_dev "
        echo '=== bloaty: compileunits → sections (top 25) ==='
        bloaty -d compileunits,sections -s file -n 25 '${ELF}'
        echo
        echo '=== bloaty: sections → symbols (top 20、何が太ったか高解像度で見る) ==='
        bloaty -d sections,symbols -s file -n 20 --demangle=short '${ELF}'
    "
    ;;

bloaty-diff)
    [[ -f "${DIFF_ELF}" ]] || { echo "比較 ELF が無い: ${DIFF_ELF}" >&2; exit 1; }
    DIFF_ELF="$(stage_diff_elf "${DIFF_ELF}")"
    # bloaty の `-- before.elf` 構文で size delta を出す
    # (右に書いた方が baseline、左の ELF との差分が表示される)
    run_in_dev "
        echo '=== bloaty diff: ${ELF} vs baseline ${DIFF_ELF} ==='
        echo '(VM/FILE 列が ELF - baseline の差分)'
        echo
        echo '--- by compileunits ---'
        bloaty -d compileunits -s file -n 20 '${ELF}' -- '${DIFF_ELF}'
        echo
        echo '--- by sections,symbols ---'
        bloaty -d sections,symbols -s file -n 20 --demangle=short '${ELF}' -- '${DIFF_ELF}'
    "
    ;;
esac
