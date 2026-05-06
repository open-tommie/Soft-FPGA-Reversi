#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
    cat <<'EOF'
使い方:
  scripts/doRunHost.sh [--algo lsb|max_gain|corner] [--serial [device]] [--tcp [host:]port]

オプション:
  --algo lsb|max_gain|corner  アルゴリズム選択 (省略時: lsb)
  --serial [device]           シリアルポート経由で起動
                                device 省略時: /dev/ttyS1 (Windows COM2)
                                COM3 なら /dev/ttyS2、COM4 なら /dev/ttyS3
                                socat でブリッジし Docker 外 (WSL2 上) で直接実行
  --tcp [host:]port           TCP 経由で起動 (HHD Virtual Serial Port など)
                                host 省略時: 127.0.0.1
                                例: --tcp 4000  または  --tcp 127.0.0.1:4000
  -h, --help                  このヘルプを表示して終了

例:
  scripts/doRunHost.sh                               # stdin/stdout, pick_lsb
  scripts/doRunHost.sh --algo corner                 # stdin/stdout, pick_corner
  scripts/doRunHost.sh --serial                      # COM2, pick_lsb
  scripts/doRunHost.sh --serial /dev/ttyS2           # COM3, pick_lsb
  scripts/doRunHost.sh --algo corner --serial        # COM2, pick_corner
  scripts/doRunHost.sh --tcp 4000                    # TCP localhost:4000, pick_lsb
  scripts/doRunHost.sh --algo corner --tcp 4000      # TCP localhost:4000, pick_corner
  printf 'PI\r\nVE\r\n' | scripts/doRunHost.sh       # stdin からシナリオを流し込む

HHD Virtual Serial Port で TCP を使う場合:
  1. HHD で「TCP/IP Ports (RFC2217, Raw)」→ COM1 or COM2 を localhost:4000 にマッピング
  2. scripts/doRunHost.sh --tcp 4000

Windows COM ↔ WSL2 デバイス対応表 (物理ポートの場合):
  COM2 → /dev/ttyS1  (デフォルト)
  COM3 → /dev/ttyS2
  COM4 → /dev/ttyS3

事前準備 (初回のみ):
  sudo apt-get install -y socat
  sudo chmod a+rw /dev/ttyS1   # または: sudo usermod -aG dialout $USER
EOF
}

ALGO_OPT=""
SERIAL_DEV=""
TCP_ADDR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --algo)
            ALGO_OPT="${2:?--algo requires lsb|max_gain|corner}"
            shift 2 ;;
        --serial)
            SERIAL_DEV="/dev/ttyS1"  # デフォルト: COM2
            shift
            if [[ "${1:-}" != "" && "${1:-}" != --* ]]; then
                SERIAL_DEV="$1"; shift
            fi
            ;;
        --tcp)
            shift
            if [[ "${1:-}" == "" || "${1:-}" == --* ]]; then
                echo "エラー: --tcp には port または host:port が必要です。" >&2; exit 2
            fi
            # port のみの場合は 127.0.0.1 を補完
            if [[ "${1}" =~ ^[0-9]+$ ]]; then
                TCP_ADDR="127.0.0.1:${1}"
            else
                TCP_ADDR="${1}"
            fi
            shift
            ;;
        *) echo "Unknown option: '$1'" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -n "${SERIAL_DEV}" && -n "${TCP_ADDR}" ]]; then
    echo "エラー: --serial と --tcp は同時に指定できません。" >&2; exit 2
fi

cd "${SCRIPT_DIR}"
./doVersionUp.sh

if [[ -n "${SERIAL_DEV}" ]]; then
    # ビルドのみ（Docker 内）。起動は WSL2 上で socat 経由。
    if [[ -n "${ALGO_OPT}" ]]; then
        ./build-host.sh --algo "${ALGO_OPT}"
    else
        ./build-host.sh
    fi

    if ! command -v socat &>/dev/null; then
        echo "エラー: socat が見つかりません。" >&2
        echo "  sudo apt-get install -y socat" >&2
        exit 1
    fi
    if [[ ! -e "${SERIAL_DEV}" ]]; then
        echo "エラー: ${SERIAL_DEV} が存在しません。" >&2
        echo "  COM2 = /dev/ttyS1、COM3 = /dev/ttyS2 ..." >&2
        exit 1
    fi

    stty -F "${SERIAL_DEV}" 115200 raw -echo -echoe -echok 2>/dev/null || true
    echo "接続: ${SERIAL_DEV} (115200bps) ↔ reversi_host [${ALGO_OPT:-lsb}]" >&2
    exec socat "${SERIAL_DEV},b115200,raw,echo=0" \
               "EXEC:${REPO_ROOT}/host/build/reversi_host"
elif [[ -n "${TCP_ADDR}" ]]; then
    # ビルドのみ（Docker 内）。起動は WSL2 上で socat 経由。
    if [[ -n "${ALGO_OPT}" ]]; then
        ./build-host.sh --algo "${ALGO_OPT}"
    else
        ./build-host.sh
    fi

    if ! command -v socat &>/dev/null; then
        echo "エラー: socat が見つかりません。" >&2
        echo "  sudo apt-get install -y socat" >&2
        exit 1
    fi

    echo "接続: TCP ${TCP_ADDR} ↔ reversi_host [${ALGO_OPT:-lsb}]" >&2
    exec socat "TCP:${TCP_ADDR}" \
               "EXEC:${REPO_ROOT}/host/build/reversi_host"
else
    if [[ -n "${ALGO_OPT}" ]]; then
        exec ./build-host.sh --algo "${ALGO_OPT}" -- run
    else
        exec ./build-host.sh -- run
    fi
fi
