# Lessons Learned — 旧 Soft-FPGA-Othello からの教訓

旧プロジェクト [Soft-FPGA-Othello](https://github.com/open-tommie/Soft-FPGA-Othello)（TD4 派生の TD16 自作 CPU + Othello アクセラレータ構成）で詰まった点と、本プロジェクトでの方針。

## 失敗ポイント

### 1. 自作 CPU を間に挟んだ

TD16（自作 CPU）に Othello アクセラレータをぶら下げる構成にしたため、

- Verilog の規模が桁で増えた（命令デコーダ・レジスタファイル・メモリインタフェース・命令ROM ロード機構）
- Verilator 生成 C++ の flash 占有が膨らみ Pico 2 リソースが圧迫された
- バグの切り分けが「CPU 側 / アクセラレータ側 / 命令列 / ホスト」の 4 軸になり、ほぼ追えない
- ホスト C++ から「アクセラレータの単機能テスト」を叩くまでに自作 CPU 経由が必要

**本来 Pico 2 の Cortex-M33 (Hazard3) 自体が CPU**。ここに自作 CPU を重ねる必然性はなかった。

### 2. UART をビット単位で Verilog に書こうとした方針

115200 baud のシリアル受信機を Verilog 内に実装すると、Verilator で 1 ビットあたり数百〜千 `eval()` を回す必要があり、実機での思考時間が桁違いに伸びる。

### 3. リファレンス実装と Verilog の照合が後回しだった

「全部書いてから動かす」アプローチで、`reversi_rules.py` との突合が遅れ、どこで挙動が乖離したか不明な状態が長く続いた。

## 本プロジェクトでの方針

### A. アクセラレータ単独構成

Verilog は Othello の純粋な計算 IP（合法手 bitmap, 反転計算, 評価, 適用）に限定する。
プロトコル・FSM・I/O は **Pico SDK 上の C++ 側** に置く。

```
USB-CDC ─┐
         │  C++ (Pico SDK)
UART  ───┤    ├─ プロトコルパーサ (PI/VE/SB/SW/MO/PA/BO/EB/EW/ED)
         │    ├─ FSM (IDLE / MY_TURN / WAIT_OPP)
         │    └─ Verilog DUT ドライバ ──▶ Verilog: Othello Accelerator
```

### B. DUT インタフェースはバイト粒度以上

UART のビット同期は Verilog に書かない。バイトが揃った瞬間に `dut.rx_valid=1; eval();` する。
これだけで Verilator 実行時間が桁で減る。

### C. Python リファレンス実装 = 単一情報源

[tommieChat](https://github.com/open-tommie/24-mmo-Tommie-chat) の `test/reversi/reversi_rules.py` を
唯一の golden として全テストが参照する。Verilog の挙動が Python と異なれば **Verilog を直す**。

### D. シナリオ回帰を最初に立てる

`test/reversi/scenarios/*.txt` と `--replay` 形式を最初の MVP の段階で回せるようにする。
後付けで導入しようとすると、過去のバグが回帰に乗らない。

### E. ホスト Verilator ビルドと実機 Pico 2 ビルドを同居

同じ Verilog ソースを 2 つの harness で動かす:

- ホスト: Linux + Verilator + cocotb で全 RTL ユニット + シナリオ回帰
- 実機:  Pico SDK + Verilator + USB-CDC で `cpu_tester` 経由のシナリオ回帰

ホスト側で機能を固め、実機側は I/O とリソースだけ気にすればよい状態を作る。

## ブートストラップ手順

1. Pico 2 で Hello UF2 が出る `firmware/` を最小で通す（Verilog なし）
2. 空 Verilog DUT を Verilator で C++ 化 → firmware/ にリンクして UF2 が通る（flash/SRAM サイズ計測）
3. C++ のみで UART テキストプロトコル骨格（PI→PO, VE→VE01...）を実装、`cpu_tester` で疎通
4. Verilog で `legal_bb` 1 機能だけ実装、cocotb で `reversi_rules.legal_moves` と全合法局面照合
5. C++ から MMIO 経由で legal_bb を呼んで PICK_FIRST 結果を MO 送信、シナリオ回帰へ
6. APPLY コマンド追加 → 全シナリオ PASS が新 MVP の完了条件
7. 強化 AI（αβ, 評価関数）は別ブランチで
