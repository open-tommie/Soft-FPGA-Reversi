#!/usr/bin/env bash
set -euo pipefail

# コンテナ内で実行される。直接呼ばず scripts/test-hil.sh から呼び出す。
# 名前付きボリューム /opt/hil-venv に venv をキャッシュし、再起動時の install を省く。

VENV=/opt/hil-venv

if [[ ! -x "${VENV}/bin/pytest" ]]; then
    python3 -m venv "${VENV}"
    "${VENV}/bin/pip" install -q --upgrade pip
fi

# requirements が更新されていれば差分のみ install (pip キャッシュ /ccache/pip 経由)
"${VENV}/bin/pip" install -q -r verif/tb_hil/requirements.txt

# Probe / Pico の存在を早期検出
if ! lsusb 2>/dev/null | grep -qi 'cmsis\|2e8a:000c'; then
    echo "WARN: Debug Probe (CMSIS-DAP / 2e8a:000c) が lsusb に見えない" >&2
    echo "  Windows: scripts/wsl-attach.sh で attach 済みか確認" >&2
fi
if ! lsusb 2>/dev/null | grep -qi '2e8a:000a\|2e8a:000f'; then
    echo "INFO: Pico 2 が lsusb に見えない (--no-flash 指定なら無視可)" >&2
fi

# pytest は verif/tb_hil をデフォルトの testpaths に持つ (pytest.ini)
exec "${VENV}/bin/pytest" verif/tb_hil "$@"
