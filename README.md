# Soft-FPGA-Reversi

Verilog で書いた Othello (Reversi) アクセラレータを Verilator で C++ 化し、
Raspberry Pi Pico 2 上の Pico SDK ファームウェアから呼び出すプロジェクト。

旧 [Soft-FPGA-Othello](https://github.com/open-tommie/Soft-FPGA-Othello) を
**自作CPU(TD16)を排し、純粋なアクセラレータのみ**の構成に作り直したもの。

## Status
WIP — 初期スケルトン。

## See also
- `etc/lessons-learned.md` — 旧プロジェクトで失敗した経緯
