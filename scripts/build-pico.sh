#!/usr/bin/env bash
set -euo pipefail

# Pico 2 (RP2350) ファームウェアを Docker コンテナ内でビルドする。
# 成果物: firmware/build/firmware.uf2

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

USER_UID="$(id -u)"
USER_GID="$(id -g)"
export USER_UID USER_GID

exec docker compose -f docker/compose.yml run --rm firmware
