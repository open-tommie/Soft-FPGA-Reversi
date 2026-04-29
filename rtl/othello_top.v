// rtl/othello_top.v
//
// firmware にリンクされる最上位モジュール。
// HW 合成は想定していない: ホスト側で Verilator により C++ 化され、
// firmware にリンクされて Pico 2 上で実行される。
//
// 構成:
//   - proto: UART テキストプロトコル本体。内部に
//            game_state / legal_bb / pick_lsb / coord を持つ。
//
// firmware からは rx/tx の byte 線のみ公開。

`default_nettype none

module othello_top (
    input  wire        clk,
    input  wire        rst,
    // RX byte stream (firmware: stdin → 1-cycle pulse)
    input  wire        rx_valid,
    input  wire [7:0]  rx_byte,
    // TX byte stream (firmware: 1 cycle ごとに valid を見て stdout へ)
    output wire        tx_valid,
    output wire [7:0]  tx_byte
);

    proto u_proto (
        .clk      (clk),
        .rst      (rst),
        .rx_valid (rx_valid),
        .rx_byte  (rx_byte),
        .tx_valid (tx_valid),
        .tx_byte  (tx_byte)
    );

endmodule

`default_nettype wire
