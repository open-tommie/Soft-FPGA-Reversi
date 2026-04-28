# tb_hil — 実機 HIL テスト

Pico 2 + Debug Probe を実機接続した状態で走らせる pytest スイート。
Step 1（Hello UF2）の検証から始め、Step 3 以降のプロトコル骨格・シナリオ回帰へ拡張していく。

## 前提

- `usbipd attach` で **Pico 2 (USB-CDC)** と **Debug Probe (CMSIS-DAP)** が WSL2 から見えること

  ```bash
  scripts/wsl-attach.sh           # 既に bind 済みなら attach のみ
  ls /dev/ttyACM* && lsusb | grep 2e8a
  ```

- ELF が存在すること

  ```bash
  scripts/build-pico.sh           # → firmware/build/firmware.elf
  ```

- Docker (`docker compose`) が動くこと（推奨実行モード）。
  ホスト直モードの場合は Python venv に pyserial と pytest

## 実行

### 推奨: Docker 経由 (build-pico.sh / flash.sh と同じ流儀)

```bash
scripts/test-hil.sh                          # 全 HIL テスト
scripts/test-hil.sh --no-flash               # 既書き込み状態で再テスト
scripts/test-hil.sh -k hello                 # 名前で絞る
scripts/test-hil.sh --elf path/to/other.elf  # 別 ELF を書き込む
```

`scripts/test-hil.sh` は `docker compose run --rm test-hil` を呼ぶラッパー。
コンテナ内で venv (`/opt/hil-venv`、名前付きボリューム) が作られ、
2 回目以降は再利用される。

### WSL2 ホスト直 (デバッグ用、依存追加が必要)

```bash
python3 -m venv .venv
.venv/bin/pip install -r verif/tb_hil/requirements.txt
.venv/bin/pytest verif/tb_hil
```

## オプション

| フラグ | 意味 |
| --- | --- |
| `--no-flash` | セッション開始時のフラッシュをスキップ（既書き込み状態を再利用） |
| `--port /dev/ttyACMx` | USB-CDC ポートを変更（既定: `/dev/ttyACM0`） |
| `--baud 921600` | ボーレート変更（既定: `115200`） |
| `--elf path/to/other.elf` | 別 ELF を書き込む |

## 構造

| ファイル | 役割 |
| --- | --- |
| `conftest.py` | `flashed_firmware` (session-scoped flash) / `dut` (`serial.Serial`) / `expect` (行マッチヘルパ) |
| `pytest.ini` | testpaths, markers (`slow`, `flash`) |
| `requirements.txt` | pytest + pyserial |
| `test_hello_uf2.py` | Step 1: `Hello, world!` の出現と 1 Hz 周期確認 |

## 流れ

```text
pytest 起動
  └─ session フィクスチャ: flash 実行 (1 回だけ)
       │   コンテナ内: scripts/_flash-inner.sh を直接呼ぶ
       │   ホスト直  : scripts/flash.sh (内部で docker run)
       └─ Pico 2 が自動リセット → 起動
            └─ test_*: dut = serial.Serial(/dev/ttyACM0)
                 └─ expect(dut, r"Hello, world!") で行マッチ
```

## 拡張方針

- **Step 3 (UART テキストプロトコル)**: `test_proto_pi_ve.py` を追加し、
  `dut.write(b"PI\n")` → `expect(r"^PO ")` 形式で疎通確認
- **シナリオ回帰**: tommieChat の `test/reversi/scenarios/` の `*.txt` を
  `verif/tb_protocol/scenarios/` 経由で読み込み、各局面で `dut.write` →
  `reversi_rules.legal_moves(board)` と `expect` 結果を比較
- **Verilator host との共用**: `dut` フィクスチャを差し替えるだけで
  「USB-CDC 経由」と「Verilator stdin/stdout 経由」を切替可能にし、
  Step 2 の host 回帰と同じテスト本体を流す

## 注意

- フラッシュ後の Pico 2 は新しい VID:PID (`2e8a:000a`) で再列挙される。
  `usbipd-win` の永続バインドが効いていれば自動 attach されるが、
  効いていない場合は `scripts/wsl-attach.sh` の再実行が必要
- `dut` フィクスチャは `port` を 100 ms × 30 回までリトライする（再列挙待ち）
- Windows 側で Serial Monitor が `/dev/ttyACM0` 相当を開いていると
  アタッチが排他で失敗する。テスト前に閉じる
- Docker モードでは `/dev` をバインドしているため CDC 再列挙に追従できる。
  ホスト直モードと挙動差が出る場合は Docker モードを優先
