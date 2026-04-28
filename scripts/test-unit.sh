#!/usr/bin/env bash
set -euo pipefail

# Verilator + cocotb で verif/tb_unit のユニットテストを Docker 内で回す。
# Pico SDK / Probe には依存しないので usbipd attach 等は不要。
#
# 使い方:
#   scripts/test-unit.sh                     # 全 cocotb テスト
#   scripts/test-unit.sh MODULE=test_xxx     # 単一モジュールのみ
#   scripts/test-unit.sh -- clean            # cocotb make clean

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

USER_UID="$(id -u)"
USER_GID="$(id -g)"
export USER_UID USER_GID

exec docker compose -f docker/compose.yml run --rm test-unit "$@"
