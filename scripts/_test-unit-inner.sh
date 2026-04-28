#!/usr/bin/env bash
set -euo pipefail

# コンテナ内で実行される。直接呼ばず scripts/test-unit.sh から呼び出す。
# 名前付きボリューム /opt/unit-venv に venv をキャッシュし再起動時の install を省く。

VENV=/opt/unit-venv

if [[ ! -x "${VENV}/bin/cocotb-config" ]]; then
    python3 -m venv "${VENV}"
    "${VENV}/bin/pip" install -q --upgrade pip
fi

# requirements が更新されていれば差分のみ install
"${VENV}/bin/pip" install -q -r verif/tb_unit/requirements.txt

# venv の bin を PATH 先頭に。cocotb の Makefile が cocotb-config を呼ぶため。
export PATH="${VENV}/bin:${PATH}"

# cocotb は make ベース。引数があれば素通し。
exec make -C verif/tb_unit "$@"
