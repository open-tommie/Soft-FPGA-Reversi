# 04-Docker 構成

ビルド・書き込み・テストを **Docker サービスで統一** した構成のメモ。
ホスト汚染ゼロ、CI と実機開発で同じイメージ・同じ手順を流す。

## 全体図

```text
host (WSL2)                           container (sfr-dev:local)
─────────────                         ───────────────────────────
scripts/build-pico.sh ─┬─▶ docker compose run firmware
                       │   └─ scripts/_build-pico-inner.sh
                       │        └─ cmake + ninja → firmware/build/
                       │
scripts/flash.sh ──────┼─▶ docker compose run flash (root, /dev/bus/usb)
                       │   └─ scripts/_flash-inner.sh
                       │        └─ openocd → Pico 2 (SWD 経由)
                       │
scripts/test-hil.sh ───┴─▶ docker compose run test-hil (privileged, /dev)
                           └─ scripts/_test-hil-inner.sh
                                └─ pytest verif/tb_hil
                                     └─ flashed_firmware fixture
                                          └─ _flash-inner.sh (in-container)
```

3 本のホスト wrapper はすべて同じ流儀:

```bash
USER_UID=$(id -u) USER_GID=$(id -g) \
    docker compose -f docker/compose.yml run --rm <service> <inner-script> "$@"
```

## サービス一覧

| サービス | ユーザ | デバイス / 特権 | 役割 |
| --- | --- | --- | --- |
| `dev` | non-root | なし | 対話シェル (`docker compose run dev`)。手動デバッグ用 |
| `firmware` | non-root | なし | `_build-pico-inner.sh` で CMake + Ninja ビルド |
| `flash` | root | `/dev/bus/usb` | `_flash-inner.sh` で openocd 経由フラッシュ |
| `test-hil` | root, `privileged` | `/dev` 全体 | `_test-hil-inner.sh` で pytest 実行 + 内部で flash |

## 設計上のポイント

### 共通ベース (YAML anchor)

```yaml
x-base: &base
  image: sfr-dev:local
  build: { context: ., dockerfile: Dockerfile, args: { USER_UID, USER_GID } }
  volumes:
    - ../:/work
    - sfr-ccache:/ccache
  working_dir: /work
  environment:
    - CCACHE_DIR=/ccache
```

各サービスは `<<: *base` で共通定義を継承し、必要なものだけ上書きする。
ただし `volumes` / `environment` / `devices` などのリストは
**マージではなく置き換え** なので、test-hil のように追加が必要なときは全列挙。

### USER_UID / USER_GID 引き渡し

ホスト側 wrapper で `export USER_UID=$(id -u) USER_GID=$(id -g)` し、
Compose の `args` で Dockerfile に渡す。これでバインドマウントした
`/work` 配下に作られるファイルがホストユーザ所有になる
（root 所有の root-owned 成果物を撒き散らさない）。

flash / test-hil は `user: "0"` を明示して root で動かす理由:

- openocd が libusb 経由で Probe を叩くために `/dev/bus/usb` の owner 制約を超える必要がある
- 同様に test-hil は CDC（`/dev/ttyACM0`）アクセスのため

### `privileged: true` + `/dev` バインド (test-hil のみ)

flash サービスは `devices: - /dev/bus/usb` だけで足りる。
test-hil は加えて `/dev/ttyACM0` を pyserial が開く必要があるが、

- フラッシュ後に Pico 2 が再列挙し、CDC の minor 番号が変わる
- 静的な `devices: - /dev/ttyACM0` は再列挙に追従しない

ため `/dev:/dev` バインド + `privileged: true` で **live `/dev` を共有** する。
dev 用構成限定の妥協（本番デプロイでは絶対にやらない）。

### docker-in-docker の回避

test-hil コンテナ内から `flash.sh` を呼ぶと `docker compose run` が
コンテナの中でさらに docker を呼ぶことになる。これを避けるため、
`compose.yml` で `SFR_IN_CONTAINER=1` を test-hil の environment に設定し、
`verif/tb_hil/conftest.py` の `flashed_firmware` フィクスチャが分岐:

| 実行環境 | 呼ぶスクリプト |
| --- | --- |
| test-hil コンテナ内 (`SFR_IN_CONTAINER=1`) | `scripts/_flash-inner.sh`（openocd を直接） |
| WSL2 ホスト直 | `scripts/flash.sh`（内部で `docker compose run flash`） |

## 名前付きボリューム

| 名前 | マウント先 | 用途 |
| --- | --- | --- |
| `sfr-ccache` | `/ccache` | C++ ビルドの ccache + pip キャッシュ (`/ccache/pip`) |
| `sfr-hil-venv` | `/opt/hil-venv` | HIL テスト用 venv（pytest, pyserial）。再ビルドで毎回 install しないため |

ホストにファイルが漏れないので `.gitignore` への追記不要。
削除したいときは `docker volume rm sfr_sfr-ccache sfr_sfr-hil-venv`。

## 命名規約

- ホスト wrapper: `scripts/<verb>.sh`（例: `build-pico.sh`, `flash.sh`, `test-hil.sh`）
- コンテナ内ランナー: `scripts/_<verb>-inner.sh`（先頭 `_` で「直接呼ばない」を明示）
- inner は host wrapper / 別 inner からのみ呼ばれる前提。引数透過 (`"$@"`)

新しいサービスを足すときもこの 1:1 対応を維持する。

## トラブルシュート

| 症状 | 原因 / 対処 |
| --- | --- |
| `permission denied: /work/firmware/build/...` | USER_UID/USER_GID を export し忘れ。wrapper 経由で起動する |
| `unable to find a matching CMSIS-DAP device` (in flash/test-hil) | usbipd attach がない。`scripts/wsl-attach.sh` を再実行 |
| test-hil で `/dev/ttyACM0: No such file or directory` | Pico 側がまだ再列挙中。conftest の `dut` フィクスチャが 3 秒リトライするのでほとんど吸収される |
| `failed to register layer: ...` | Docker Desktop の WSL backend が劣化。`wsl --shutdown` → 再起動 |
| ccache が効かない | `CCACHE_DIR` 未設定。base anchor の `environment` を継承しているか確認 |

## 関連

- [02-準備.md](02-準備.md) — usbipd と前提環境
- [03-テスト戦略.md](03-テスト戦略.md) — テストレイヤと tb_hil の中身
- [`../docker/compose.yml`](../docker/compose.yml) — 本体
- [`../docker/Dockerfile`](../docker/Dockerfile) — ツールチェイン pin
