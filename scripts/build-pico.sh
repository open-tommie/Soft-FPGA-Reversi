#!/usr/bin/env bash
set -euo pipefail

# Pico 2 (RP2350) ファームウェアを Docker コンテナ内でビルドし、
# ビルド成功後に Debug Probe 経由で書き込む。
# 成果物: firmware/build/firmware.uf2

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

USER_UID="$(id -u)"
USER_GID="$(id -g)"
export USER_UID USER_GID

docker compose -f docker/compose.yml run --rm firmware
scripts/flash.sh
