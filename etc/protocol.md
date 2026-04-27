# UART テキストプロトコル仕様（参照）

本プロジェクトは tommieChat 側で定義された UART テキストプロトコル §61 に準拠する。
**正本は tommieChat の `doc/reversi/61-UARTプロトコル仕様.md`**。本ドキュメントはサマリ。

## 物理層

- 115200 baud, 8N1
- 行終端は LF のみ。CR 混入は §4 違反 → `ER03`
- ASCII。非 ASCII は `ER02` 系で弾く

## コマンド一覧（受信側 = 本実装が処理するもの）

| Cmd | 意味 | 応答 |
| --- | --- | --- |
| `PI` | Ping | `PO` |
| `VE` | Version request | `VE01<name>` |
| `SB` | Start as Black | （手番処理開始） |
| `SW` | Start as White | （相手手番待ち） |
| `MO<xy>` | 相手の着手 (xy = a1..h8) | 自分の手 `MO<xy>` ＋ `BS<board>` |
| `PA` | 相手のパス | 自分の手 or `PA` |
| `BO<board>` | 盤面同期 | （内部状態更新） |
| `EB` / `EW` / `ED` | 終局 (Black勝/White勝/Draw) | （IDLE 復帰） |

## 送信コマンド（本実装が送るもの）

| Cmd | 意味 |
| --- | --- |
| `PO` | Pong |
| `VE01<name>` | Version response |
| `MO<xy>` | 自分の着手 |
| `PA` | パス |
| `BS<board>` | 自分視点の盤面スナップショット（突合用） |
| `RS` | 盤面再同期要求（受信した相手手が非合法だった時） |
| `ER01..ER04 <reason>` | プロトコル違反応答 |

## 状態機械

```
IDLE ──SB──▶ MY_TURN ──(my move)──▶ WAIT_OPP ──MO──▶ MY_TURN
  │                                     │
  └──SW──▶ WAIT_OPP                     └──PA──▶ MY_TURN
```

終局コマンド (`EB`/`EW`/`ED`) で常に IDLE へ。

## 重要な仕様一致点（旧プロジェクトでハマった箇所）

- 手の選択順序は **行優先 a1, b1, c1, ..., h8**。これが Python `legal_moves()` の返却順と一致する必要がある
- 座標は小文字必須。`MOA1` などは `ER04`
- コマンド部は 2 文字大文字英字必須。`mo` などは `ER02`
- PI/PO は思考中でも最優先で応答できること（送信 FIFO 化推奨）
- 行バッファは 256 B 以上（`BS<128字>` がある）

## 詳細

正本: <https://github.com/open-tommie/24-mmo-Tommie-chat/blob/main/doc/reversi/61-UART%E3%83%97%E3%83%AD%E3%83%88%E3%82%B3%E3%83%AB%E4%BB%95%E6%A7%98.md>
