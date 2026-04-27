# rtl/

Verilog ソース（Othello アクセラレータ本体）。

## ファイル構成（予定）

| ファイル | 役割 |
| --- | --- |
| `othello_top.v` | アクセラレータ最上位。MMIO バス + コア接続 |
| `othello_core.v` | bitboard 演算ステートマシン |
| `flip_calc.v` | 8 方向同時シフトで反転 bitmap を計算 |
| `legal_bb.v` | 合法手 bitmap を生成 |
| `pick_lsb.v` | lsb 抽出（Python 参照実装と一致する手順序） |

## 設計方針

- I/O は **バイト粒度以上** のハンドシェイク。UART のビット同期は Verilog に書かない。
- 盤面は bitboard (`black[63:0]`, `white[63:0]`)。bit 順は `bit_index = r*8 + c`（a1 = bit0）。
- `pick_lsb` の手順序は Python `reversi_rules.legal_moves()` と完全一致させる（行優先 a1, b1, …）。
- Verilator + Pico SDK で C++ 化した時に `<iostream>` `<string>` 等を引き込まない構造にする。
