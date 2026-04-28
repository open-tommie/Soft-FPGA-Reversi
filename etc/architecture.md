# Architecture

## 全体図 (Step 6 時点 / MVP 動作)

```text
┌──────────────────────────────────────────────────────────────────┐
│                  Raspberry Pi Pico 2                              │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  C++ (Pico SDK, Cortex-M33 @ 150 MHz)                       │ │
│  │                                                             │ │
│  │  USB-CDC ─┐                                                 │ │
│  │           ├─▶ getchar_timeout_us(0) ──▶ rx_byte/rx_valid    │ │
│  │  UART  ───┘                                  ↓              │ │
│  │                                          tick(dut)           │ │
│  │                                              ↓              │ │
│  │  ┌─────────────────────────────────────────────────────┐   │ │
│  │  │ Vothello_top (Verilator → C++)                      │   │ │
│  │  │   └─ proto.v                                        │   │ │
│  │  │        ├─ game_state.v   (盤面 + side + phase)       │   │ │
│  │  │        ├─ legal_bb.v     (合法手 bitmap)              │   │ │
│  │  │        ├─ pick_lsb.v     (行優先 LSB 選択)            │   │ │
│  │  │        ├─ coord.v        (座標 ↔ bit_index)          │   │ │
│  │  │        └─ flip_calc.v    (8 方向反転計算)              │   │ │
│  │  └─────────────────────────────────────────────────────┘   │ │
│  │                                              ↓              │ │
│  │                                       tx_byte/tx_valid      │ │
│  │                                              ↓              │ │
│  │  USB-CDC ◀─┐                                                │ │
│  │            ├── putchar_raw ◀──────────                      │ │
│  │  UART  ◀───┘                                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
              ▲                                ▲
              │ USB-CDC                        │ UART (115200, 8N1)
              ▼                                ▼
       ┌──────────────┐                ┌──────────────┐
       │ ホスト PC    │                │ Probe UART 中継│
       │ (cpu_tester) │                │ /dev/ttyACM*  │
       └──────────────┘                └──────────────┘
```

## 責務分離 (実装後)

| 層 | 担当 | 行数 |
| --- | --- | ---: |
| C++ ホスト ([`firmware/src/main.cpp`](../firmware/src/main.cpp)) | USB-CDC ↔ DUT バイト中継 + 起動初期化 | ~50 |
| C++ ランタイム ([`firmware/src/cxx_minimal.cpp`](../firmware/src/cxx_minimal.cpp), [`stub_mutex.h`](../firmware/src/stub_mutex.h), [`verilator-runtime/`](../firmware/src/verilator-runtime/)) | C++ 例外/demangler/threads を組込み向けに stub 化 | — |
| Verilog DUT ([`rtl/`](../rtl/)) | プロトコル framing + Othello 全ロジック | ~600 |
| Pico SDK | hardware UART / USB-CDC / GPIO | (外部) |

**当初設計 (etc/lessons-learned.md A) との違い**:
旧計画では「C++ がプロトコル FSM、Verilog は計算 IP のみ、間に MMIO レジスタ」だった。
実装中の判断で「C++ はバイト中継だけ、プロトコル FSM も Verilog 内」に変更
(「Verilog で書いて Pico 2 上で動く」面白さを最大化)。MMIO レジスタ層は撤去。

## Verilog モジュール一覧 ([`rtl/`](../rtl/))

| モジュール | 役割 | 入出力 |
| --- | --- | --- |
| [`othello_top.v`](../rtl/othello_top.v) | 最上位 (`Vothello_top`) | clk/rst, rx_*, tx_* |
| [`proto.v`](../rtl/proto.v) | UART テキストプロトコル FSM (PI/VE/SB/SW/MO 受信、MO+BS 応答) | rx_*, tx_* (othello_top と同一) |
| [`game_state.v`](../rtl/game_state.v) | 内部状態レジスタ: black/white/my_side/phase | cmd_init/set_board/set_phase |
| [`legal_bb.v`](../rtl/legal_bb.v) | 8 方向 bitboard flood で合法手 | (black, white, side) → legal[63:0] |
| [`pick_lsb.v`](../rtl/pick_lsb.v) | 64bit から最下位 set bit 抽出 (= 行優先 a1, b1, …) | in_bits → index, one_hot, valid |
| [`coord.v`](../rtl/coord.v) | 2 文字座標 ↔ bit_index 双方向変換 | parse: chars → bit / format: bit → chars |
| [`flip_calc.v`](../rtl/flip_calc.v) | 着手で反転する opp 駒の bitmap (8 方向) | (own, opp, move_idx) → flip[63:0] |

## proto.v の FSM

```text
   ┌──────────┐
   │ S_RECV   │ ← 起動時、応答送信完了後に戻る
   └────┬─────┘
        │ rx_valid + LF (0x0A)
        ▼
   ┌──────────┐
   │S_DISPATCH│ コマンドを判定し:
   │          │  - PI/VE/不明 → ROM 応答 → S_TX
   │          │  - SB/SW    → game_state.cmd_init pulse
   │          │  - MO<xy>   → 相手駒置く + flip_calc 反転
   │          │              + S_WAIT_GS へ
   └────┬─────┘
        │ SB or 有効 MO のみ
        ▼
   ┌──────────┐
   │S_WAIT_GS │ game_state.black/white の register 更新待ち (1 cycle)
   └────┬─────┘
        ▼
   ┌──────────┐
   │S_PLACE_MY│ legal_bb → pick_lsb で自分の手選択、flip_calc で反転
   │          │ tx_mode = TX_MODE_MO (動的 "MO<xy>\n"), tx_pending_bs=1
   └────┬─────┘
        ▼
   ┌──────────┐
   │  S_TX    │ tx_mode (ROM/MO/BS) で 1 byte/cycle 送信
   │          │ MO 完了 → BS<board>\n をチェイン送信
   └────┬─────┘
        │ tx_idx == tx_end (BS 後)
        ▼
       (S_RECV へ戻る)
```

## Bitboard 表現

- `bit_index = r * 8 + c` (a1 = bit 0, h8 = bit 63)
- BLACK と WHITE は独立した 64bit。EMPTY = (~black & ~white)
- 手番は `side` ビット (0 = BLACK / 1 = WHITE)
- 順序: 行優先 (`for r in range(8): for c in range(8)`) → Python `legal_moves()` と完全一致
- pick_lsb で「行優先で最初に当たる手」が選ばれることが保証される

## プロトコル応答 (現状)

| 受信 | 応答 |
| --- | --- |
| `PI\n` | `PO\n` |
| `VE\n` | `VE01reversi-fw\n` |
| `SB\n` | `MO<xy>\n` + `BS<64char>\n` (黒の初手 d3 + 反転後の盤面) |
| `SW\n` | `ER02 unknown\n` (白先手なので相手の MO を待つ、未対応) |
| `MO<xy>\n` (合法 lowercase) | `MO<my>\n` + `BS<board>\n` (相手の手を盤面に反映 + 自分の手) |
| `MO<XY>\n` (大文字等) | `ER02 unknown\n` (パースエラー) |
| その他 | `ER02 unknown\n` |

`PA` / `BO` / `EB` / `EW` / `ED` は未対応 (将来 Step)。

## 試験ハーネス

[`verif/tb_unit/`](../verif/tb_unit/) — cocotb 単体 (Verilator backend、~10 秒で 53 テスト ~50,000 件)
[`verif/tb_hil/`](../verif/tb_hil/) — pyserial 経由の HIL (Pico 2 + Probe UART 中継)
[`verif/golden/reversi_rules.py`](../verif/golden/reversi_rules.py) — Python 唯一の golden、tommie-chat からコピー
