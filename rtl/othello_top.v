// rtl/othello_top.v
//
// firmware にリンクされる最上位モジュール。
// HW 合成は想定していない: ホスト側で Verilator により C++ 化され、
// firmware にリンクされて Pico 2 上で実行される。
//
// 構成 (Step 5d 以降):
//   - proto: UART テキストプロトコル本体。内部に
//            game_state / legal_bb / pick_lsb / coord を持つ。
//
// 旧 dbg_* port (Step 4 で legal_bb 単独露出用) は proto が同モジュールを
// 内包したので撤去。firmware からは rx/tx の byte 線だけ見える。

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
