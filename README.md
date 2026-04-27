# Soft-FPGA-Reversi

Verilog で書いた Othello (Reversi) アクセラレータを Verilator で C++ 化し、
Raspberry Pi Pico 2 上の Pico SDK ファームウェアから呼び出すプロジェクト。

旧 [Soft-FPGA-Othello](https://github.com/open-tommie/Soft-FPGA-Othello) を
**自作 CPU (TD16) を排し、純粋なアクセラレータのみ**の構成に作り直したもの。

## Status

WIP — 初期スケルトン。

## Architecture

```
USB-CDC ─┐
         │  C++ (Pico SDK)
UART  ───┤    ├─ プロトコルパーサ (PI/VE/SB/SW/MO/PA/BO/EB/EW/ED)
         │    ├─ FSM (IDLE / MY_TURN / WAIT_OPP)
         │    └─ Verilog DUT ドライバ ──▶ Verilog: Othello Accelerator
```

詳細は [`etc/architecture.md`](etc/architecture.md)。

## Directory layout

| Path | 役割 |
| --- | --- |
| [`rtl/`](rtl/) | Verilog ソース（Othello アクセラレータ本体） |
| [`verif/`](verif/) | 検証コード（cocotb ユニット + プロトコル E2E 回帰） |
| [`firmware/`](firmware/) | Pico SDK ファームウェア（C++ ホスト） |
| [`etc/`](etc/) | 設計ドキュメント、教訓 |
| [`scripts/`](scripts/) | ビルド・書き込み補助スクリプト |
| [`docker/`](docker/) | 開発環境（Verilator + Pico SDK + cocotb） |
| `.github/workflows/` | CI（ホスト Verilator 回帰のみ） |

## Build (planned)

```bash
# ホスト Verilator 回帰
scripts/build-host.sh

# Pico 2 ファームウェア
scripts/build-pico.sh   # → firmware/build/firmware.uf2

# 書き込み
scripts/flash.sh
```

## See also

- [`etc/lessons-learned.md`](etc/lessons-learned.md) — 旧プロジェクトで失敗した経緯
- [`etc/architecture.md`](etc/architecture.md) — アーキテクチャ詳細
- [`etc/protocol.md`](etc/protocol.md) — UART テキストプロトコル仕様（参照）

## License

MIT
