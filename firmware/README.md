# firmware/

Raspberry Pi Pico 2 上で動く Pico SDK ファームウェア。

## 役割

Verilator が出力した DUT (`Vothello_top.cpp`) を C++ ラッパに組み込み、UART テキストプロトコル
（PI/VE/SB/SW/MO/PA/BO/EB/EW/ED）をパースしてアクセラレータを駆動する。

## 構成（予定）

| ファイル | 役割 |
| --- | --- |
| `src/main.cpp` | Pico SDK エントリ、UART/USB-CDC 初期化、メインループ |
| `src/proto.cpp` / `.h` | プロトコルパーサ + FSM (IDLE / MY_TURN / WAIT_OPP) |
| `src/reversi_host.cpp` / `.h` | DUT ドライバ（MMIO 風レジスタ R/W ラッパ） |
| `src/ring_buffer.cpp` / `.h` | UART 行バッファ・送信 FIFO |
| `src/verilated_min.cpp` | Verilator ランタイムの最小実装 |
| `CMakeLists.txt` | Pico SDK 標準ビルド |

## ビルド方針

- Pico SDK 標準（`pico_sdk_init()` → `add_executable()` → `target_link_libraries()`）。
- Verilator は `verilator --cc rtl/othello_top.v` で `obj_dir/` に出力 →
  生成 `.cpp` を `target_sources()` に追加する CMake マクロを用意。
- C++ フラグ: `-Os -fno-exceptions -fno-rtti -fno-unwind-tables -DNDEBUG`。
- `<iostream>` `<string>` `<vector>` を引き込まないこと（flash・SRAM 節約）。

## 重要な設計判断

- **UART のビット同期は Verilog に書かない**。Pico の hardware UART (or PIO UART) で
  バイト化した上で、DUT にはバイト粒度で push する。これにより `eval()` 回数が桁で減る。
