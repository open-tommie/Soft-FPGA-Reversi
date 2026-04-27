# Architecture

## 全体図

```
┌──────────────────────────────────────────────────────────┐
│                  Raspberry Pi Pico 2                      │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  C++ (Pico SDK, Cortex-M33 / Hazard3 @ 150MHz)      │ │
│  │                                                     │ │
│  │  USB-CDC ─┐                                         │ │
│  │           ├─▶ ring_buffer ──▶ proto.parse()         │ │
│  │  UART  ───┘                       │                 │ │
│  │                                   ▼                 │ │
│  │                              FSM (3 状態)            │ │
│  │                                   │                 │ │
│  │                                   ▼                 │ │
│  │                          reversi_host.drive()       │ │
│  │                                   │                 │ │
│  │                                   ▼                 │ │
│  │  ┌────────────────────────────────────────────────┐ │ │
│  │  │ Verilator-generated C++ (Vothello_top)         │ │ │
│  │  │   ├─ legal_bb                                  │ │ │
│  │  │   ├─ flip_calc                                 │ │ │
│  │  │   ├─ pick_lsb                                  │ │ │
│  │  │   └─ apply_move                                │ │ │
│  │  └────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
              ▲                                ▲
              │ USB                            │ UART (115200)
              ▼                                ▼
       ┌──────────────┐                ┌──────────────┐
       │ ホスト PC    │                │ Othello サーバ│
       │ (cpu_tester) │                │ (tommieChat) │
       └──────────────┘                └──────────────┘
```

## 責務分離

| 層 | 担当 |
| --- | --- |
| Verilog アクセラレータ | bitboard 演算（純粋計算） |
| C++ DUT ドライバ | MMIO 風レジスタ R/W、`eval()` 制御 |
| C++ プロトコル層 | UART テキスト I/O、行バッファ、FSM |
| Pico SDK | hardware UART / USB-CDC / GPIO |

## アクセラレータの MMIO レジスタ（案）

| Addr | R/W | 内容 |
| --- | --- | --- |
| 0x00 | W   | `black_lo[31:0]` |
| 0x04 | W   | `black_hi[31:0]` |
| 0x08 | W   | `white_lo[31:0]` |
| 0x0C | W   | `white_hi[31:0]` |
| 0x10 | W   | `cmd[3:0]` + `side[0]` + `start[0]` |
| 0x14 | R   | `done[0]`, `has_legal[0]` |
| 0x18 | R   | `legal_lo[31:0]` |
| 0x1C | R   | `legal_hi[31:0]` |
| 0x20 | R   | `best_move[5:0]` |
| 0x24 | R   | `flip_lo[31:0]` |
| 0x28 | R   | `flip_hi[31:0]` |
| 0x2C | R   | `eval_score[15:0]` |

### コマンド種別 (`cmd[3:0]`)

| 値 | 意味 |
| --- | --- |
| `0x1` | `FIND_LEGAL` — 合法手 bitmap を返す |
| `0x2` | `PICK_FIRST` — lsb の手を返す（Python 互換） |
| `0x3` | `APPLY` — `best_move` の手で black/white を更新して書き戻し |
| `0x4` | `EVAL` — 静的評価値（後段、最初は省略可） |

## Bitboard 表現

- `bit_index = r * 8 + c`（a1 = bit0, h8 = bit63）
- BLACK と WHITE は独立した 64bit。EMPTY は両方 0
- 手番は `side` ビット（0=BLACK / 1=WHITE）
