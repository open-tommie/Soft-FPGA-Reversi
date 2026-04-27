# verif/

検証コード。RTL を 2 系統のテストハーネスから叩く。

## tb_cocotb/

Python (cocotb) からシミュレータ越しに DUT を制御し、`reversi_rules.py`（tommieChat 由来の golden 参照実装）と挙動比較する。

- 単機能ユニットテスト: `legal_bb` / `flip_calc` / `pick_lsb` / `apply_move`
- 乱数局面 N=10000 程度で全数比較
- 実行: `make SIM=verilator` 想定

## tb_protocol/

C++ ホスト + Verilator で UART テキストプロトコルレベルの End-to-End シナリオ回帰を回す。

- `scenarios/*.txt` は tommieChat の `test/reversi/scenarios/` を参照する
  （submodule か copy。差分を出さない運用にする）
- 期待: ホスト Linux ビルドで全 PASS、同じ Verilog ソースを Pico 2 実機ビルドにも流して回帰

## golden 参照実装

`reversi_rules.py` を **唯一の真実** とする。Verilog の挙動が Python と異なれば Verilog を直す。
