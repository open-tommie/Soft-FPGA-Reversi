// rtl/othello_top.v
//
// firmware にリンクされる最上位モジュール。
// HW 合成は想定していない: ホスト側で Verilator により C++ 化され、
// firmware にリンクされて Pico 2 上で実行される。
//
// 構成:
//   - proto:    UART テキストプロトコル (PI/VE/ER02) — Step 3
//   - legal_bb: Othello 合法手 bitboard 計算 (純粋組合せ) — Step 4
//
// Step 4 段階の legal_bb 入出力は dbg_* port として top に露出する。
// firmware 側で直接駆動して動作確認できる。
// Step 5 で proto の MO 受信パスから legal_bb を駆動する結線に書き換える
// 予定で、その時点で dbg_* は撤去される。

`default_nettype none

module othello_top (
    input  wire        clk,
    input  wire        rst,

    // RX byte stream (firmware: stdin → 1-cycle pulse)
    input  wire        rx_valid,
    input  wire [7:0]  rx_byte,

    // TX byte stream (firmware: 1 cycle ごとに valid を見て stdout へ)
    output wire        tx_valid,
    output wire [7:0]  tx_byte,

    // Step 4 デバッグ用: legal_bb を直接駆動して観測する。
    // Step 5 で proto の MO ハンドリングと結線したら撤去予定。
    input  wire [63:0] dbg_black,
    input  wire [63:0] dbg_white,
    input  wire        dbg_side,
    output wire [63:0] dbg_legal
);

    proto u_proto (
        .clk      (clk),
        .rst      (rst),
        .rx_valid (rx_valid),
        .rx_byte  (rx_byte),
        .tx_valid (tx_valid),
        .tx_byte  (tx_byte)
    );

    legal_bb u_legal_bb (
        .black (dbg_black),
        .white (dbg_white),
        .side  (dbg_side),
        .legal (dbg_legal)
    );

endmodule

`default_nettype wire
