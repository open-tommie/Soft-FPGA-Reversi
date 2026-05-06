#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
使い方:
  scripts/doBuildPico.sh                   # バージョン更新 + ビルドのみ
  scripts/doBuildPico.sh --flash           # ビルド後 pick_lsb を書き込む（デフォルト）
  scripts/doBuildPico.sh --flash lsb       # ビルド後 pick_lsb を書き込む
  scripts/doBuildPico.sh --flash 1         # --flash lsb と同じ
  scripts/doBuildPico.sh --flash max_gain  # ビルド後 pick_max_gain を書き込む
  scripts/doBuildPico.sh --flash 2         # --flash max_gain と同じ
  scripts/doBuildPico.sh --flash corner    # ビルド後 pick_corner を書き込む
  scripts/doBuildPico.sh --flash 3         # --flash corner と同じ

ビルド成果物:
  firmware/build/firmware_lsb.uf2       -- pick_lsb      (行優先最初の合法手)
  firmware/build/firmware_max_gain.uf2  -- pick_max_gain (反転駒数最大の合法手)
  firmware/build/firmware_corner.uf2    -- pick_corner   (角優先)

BOOTSEL で書き込む場合:
  1. Pico 2 の BOOTSEL ボタンを押しながら USB 接続
  2. RPI-RP2350 ドライブに .uf2 をドラッグ＆ドロップ
     - pick_lsb:      firmware/build/firmware_lsb.uf2
     - pick_max_gain: firmware/build/firmware_max_gain.uf2
     - pick_corner:   firmware/build/firmware_corner.uf2
EOF
}

FLASH_ELF=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage; exit 0 ;;
        --flash)
            FLASH_ELF="firmware/build/firmware_lsb.elf"  # デフォルト: lsb
            shift
            case "${1:-}" in
                lsb|1)      FLASH_ELF="firmware/build/firmware_lsb.elf";      shift ;;
                max_gain|2) FLASH_ELF="firmware/build/firmware_max_gain.elf"; shift ;;
                corner|3)   FLASH_ELF="firmware/build/firmware_corner.elf";   shift ;;
            esac
            ;;
        *)
            echo "Unknown option: '$1'" >&2; usage >&2; exit 2 ;;
    esac
done

cd "${SCRIPT_DIR}"
./doVersionUp.sh
./build-pico.sh

if [[ -n "${FLASH_ELF}" ]]; then
    ./flash.sh "${FLASH_ELF}"
fi
