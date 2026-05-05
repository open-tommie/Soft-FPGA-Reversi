#!/usr/bin/env bash
# rtl/proto.v の VE_STR にコミット番号を埋め込む。
#
# 使い方:
#   scripts/doVersionUp.sh              # 手動実行
#
# git pre-commit フックとして登録すると自動実行:
#   ln -s ../../scripts/doVersionUp.sh .git/hooks/pre-commit
#
# 更新後は Docker ビルドが必要:
#   scripts/build-pico.sh  /  scripts/build-host.sh

set -euo pipefail

RTL_FILE="rtl/proto.v"
BASE_VE_NAME="+VE02SW-FPGA-pico2-reversi-01"
BASE_VE_CHARS=${#BASE_VE_NAME}   # 29

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

if [[ ! -f "${RTL_FILE}" ]]; then
    echo "❌ Error: Target file ${RTL_FILE} does not exist."
    exit 1
fi

COMMIT_COUNT=$(git rev-list --count HEAD)
COMMIT_HASH=$(git rev-parse --short=7 HEAD)

DIRTY=""
if ! git diff --quiet || ! git diff --cached --quiet; then
    DIRTY="+"
fi

NEW_VE_STR="${BASE_VE_NAME}.${COMMIT_COUNT}"
NEW_VE_CHARS=$(( BASE_VE_CHARS + 1 + ${#COMMIT_COUNT} ))

echo "DEBUG: COMMIT_COUNT=${COMMIT_COUNT}"
echo "DEBUG: COMMIT_HASH=${COMMIT_HASH}${DIRTY}"
echo "DEBUG: NEW_VE_STR=${NEW_VE_STR}  (${NEW_VE_CHARS} chars)"

# VE_STR 行を更新（既存の .NNN サフィックスも上書き）
sed -i "s|    localparam        VE_STR       = \"[^\"]*\";|    localparam        VE_STR       = \"${NEW_VE_STR}\";|" "${RTL_FILE}"

# VE_STR_CHARS 行を更新
sed -i "s|    localparam integer VE_STR_CHARS = [0-9]*;|    localparam integer VE_STR_CHARS = ${NEW_VE_CHARS};|" "${RTL_FILE}"

# pre-commit フックとして呼ばれた場合は git add
if [[ "$0" == *pre-commit* ]]; then
    git add "${RTL_FILE}"
fi

echo "${RTL_FILE}: VE_STR → \"${NEW_VE_STR}\" (${NEW_VE_CHARS} chars)"
