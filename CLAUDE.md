# CLAUDE.md

- `.env` や機微ファイルは読まない、出力しない。
- `~/` への直接アクセスは禁止（プロジェクト配下のみ参照・編集する）。

## Project Overview

Soft-FPGA-Reversi — Verilog で書いた Othello (Reversi) アクセラレータを Verilator で C++ 化し、
Raspberry Pi Pico 2 (RP2350 / Cortex-M33 or Hazard3) 上の Pico SDK ファームウェアから呼び出す。
旧 [Soft-FPGA-Othello](https://github.com/open-tommie/Soft-FPGA-Othello) を**自作 CPU (TD16) を排し、
純粋なアクセラレータのみ**の構成に作り直したもの。失敗の経緯は [`etc/lessons-learned.md`](etc/lessons-learned.md)。

ホスト ([tommieChat](https://github.com/open-tommie/24-mmo-Tommie-chat)) との通信は UART テキストプロトコル
（PI/VE/SB/SW/MO/PA/BO/EB/EW/ED）。リファレンス実装は tommieChat の `test/reversi/reversi_rules.py`
が **唯一の golden** で、Verilog の挙動が Python と異なれば **Verilog を直す**。

## Build & Dev Commands (planned)

```bash
# ホスト Verilator 回帰（cocotb ユニット + シナリオ回帰）
scripts/build-host.sh

# Pico 2 ファームウェア
scripts/build-pico.sh        # → firmware/build/firmware.uf2

# 実機書き込み（BOOTSEL マウント先に UF2 を D&D）
scripts/flash.sh
```

開発環境は [`docker/`](docker/) の Dockerfile で固定（Pico SDK + arm-none-eabi-gcc + Verilator + cocotb）。
ホスト直で揃えると CI と差分が出やすいので Docker 推奨。

## Architecture

```
USB-CDC ─┐
         │  C++ (Pico SDK)
UART  ───┤    ├─ プロトコルパーサ (PI/VE/SB/SW/MO/PA/BO/EB/EW/ED)
         │    ├─ FSM (IDLE / MY_TURN / WAIT_OPP)
         │    └─ Verilog DUT ドライバ ──▶ Verilog: Othello Accelerator
```

| 層 | 担当 |
| --- | --- |
| Verilog アクセラレータ ([`rtl/`](rtl/)) | bitboard 演算（純粋計算: legal_bb / flip_calc / pick_lsb / apply_move） |
| C++ DUT ドライバ ([`firmware/src/reversi_host.*`](firmware/src/)) | MMIO 風レジスタ R/W、`eval()` 制御 |
| C++ プロトコル層 ([`firmware/src/proto.*`](firmware/src/)) | UART テキスト I/O、行バッファ、FSM |
| Pico SDK ランタイム | hardware UART / USB-CDC / GPIO |

詳細は [`etc/architecture.md`](etc/architecture.md)（MMIO レジスタマップ、コマンド種別、bitboard 表現）。

## Directory Layout

| Path | 役割 |
| --- | --- |
| [`rtl/`](rtl/) | Verilog ソース（Othello アクセラレータ本体） |
| [`verif/`](verif/) | 検証コード（cocotb ユニット + プロトコル E2E 回帰） |
| [`firmware/`](firmware/) | Pico SDK ファームウェア（C++ ホスト） |
| [`etc/`](etc/) | 設計ドキュメント、教訓 |
| [`scripts/`](scripts/) | ビルド・書き込み補助スクリプト |
| [`docker/`](docker/) | 開発環境（Verilator + Pico SDK + cocotb） |
| `.github/workflows/` | CI（ホスト Verilator 回帰のみ） |

## Bootstrap 手順（現在地）

1. **Pico 2 で Hello UF2 が出る `firmware/` を最小で通す（Verilog なし）** ← 今ここ
2. 空 Verilog DUT を Verilator で C++ 化 → firmware/ にリンクして UF2 が通る（flash/SRAM 計測）
3. C++ のみで UART テキストプロトコル骨格（PI→PO, VE→VE01...）を実装、`cpu_tester` で疎通
4. Verilog で `legal_bb` 1 機能だけ実装、cocotb で `reversi_rules.legal_moves` と全合法局面照合
5. C++ から MMIO 経由で legal_bb を呼んで PICK_FIRST 結果を MO 送信、シナリオ回帰へ
6. APPLY コマンド追加 → 全シナリオ PASS が新 MVP の完了条件
7. 強化 AI（αβ, 評価関数）は別ブランチで

## Key Conventions

- **応答は日本語** — Claude の応答・説明・コミットメッセージは日本語で書く。
- **自動コミットしない** — コミットはユーザーが明示的に指示した場合のみ。
- **エラーハンドリング** — `catch` や戻り値チェックでエラーを握りつぶさない。必ずログ出力する。
- **Verilog は Python リファレンスと一致させる** — `reversi_rules.py` を golden として全テストが参照。
  Verilog の挙動が Python と異なれば **Verilog を直す**（Python ではなく）。
- **UART はバイト粒度以上で扱う** — Verilog にビット同期 UART は書かない。Pico の hardware UART
  でバイト化してから DUT に push する（旧プロジェクトの失敗教訓 `etc/lessons-learned.md` B 項）。
- **C++ flash 節約** — `<iostream>` `<string>` `<vector>` を引き込まない。
  コンパイルフラグは `-Os -fno-exceptions -fno-rtti -fno-unwind-tables -DNDEBUG`。
- **シナリオ回帰を最初から維持** — `test/reversi/scenarios/*.txt` 形式の回帰を MVP 段階から回す。
  後付けで導入すると過去のバグが回帰に乗らない。
- **Markdown の文法チェック** — `*.md` 編集後は誤字脱字を確認し、`npx markdownlint-cli <file>`
  で lint を通してから完了とする。
- **PlantUML** — `*.puml` を編集したら `plantuml -checkonly <file>` で構文チェックしてから PNG 化する。
- **lint / 型チェック / sed の実行** — 許可不要。
- **配下の編集** — `~/29-soft-FPGA-reversi/` 以下は無許可で参照・編集してよい。

## Documentation

- [`etc/architecture.md`](etc/architecture.md) — アーキテクチャ詳細（MMIO レジスタ、bitboard 表現）
- [`etc/lessons-learned.md`](etc/lessons-learned.md) — 旧 Soft-FPGA-Othello からの教訓と本プロジェクト方針
- [`etc/protocol.md`](etc/protocol.md) — UART テキストプロトコル仕様（参照）
- [`firmware/README.md`](firmware/README.md) — ファームウェアのファイル構成・ビルド方針
