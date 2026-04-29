#!/usr/bin/env bash
set -euo pipefail

# host/ (Pico SDK 非依存版) を Docker コンテナ内でビルドする。
# 成果物: host/build/reversi_host
#
# 使い方:
#   scripts/build-host.sh                   # ビルドのみ
#   scripts/build-host.sh -- run            # ビルド後 ./reversi_host を起動 (stdin 待ち)
#   scripts/build-host.sh -- run --debug    # 起動 + 主要レジスタを stderr に出力
#   echo PI | scripts/build-host.sh -- run  # stdin からシナリオを流し込む

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

USER_UID="$(id -u)"
USER_GID="$(id -g)"
export USER_UID USER_GID

exec docker compose -f docker/compose.yml run --rm build-host "$@"
