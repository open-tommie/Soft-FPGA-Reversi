#!/usr/bin/env bash
set -euo pipefail

# Docker 内で HIL テスト (verif/tb_hil) を実行する。
#
# 前提:
#   - usbipd attach で Probe (2e8a:000c) と Pico CDC (2e8a:000a) が WSL2 から見える
#       scripts/wsl-attach.sh
#   - firmware/build/firmware.elf が存在する
#       scripts/build-pico.sh
#
# 使い方:
#   scripts/test-hil.sh                          # 全 HIL テストを実行
#   scripts/test-hil.sh --no-flash               # フラッシュをスキップ (既書き込み状態)
#   scripts/test-hil.sh -k hello                 # pytest -k で絞る
#   scripts/test-hil.sh --elf path/to/other.elf  # 別 ELF を書き込む
#   scripts/test-hil.sh -- -ra -v                # pytest 追加フラグ

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

USER_UID="$(id -u)"
USER_GID="$(id -g)"
export USER_UID USER_GID

exec docker compose -f docker/compose.yml run --rm test-hil \
    scripts/_test-hil-inner.sh "$@"
