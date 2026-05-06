// rtl/pick_corner.v
//
// 合法手の中で角（a1/h1/a8/h8）を最優先して選ぶ（純粋組合せ）。
//
// 戦略:
//   1. legal_bb & CORNER_MASK が非ゼロ → 角の中から pick_lsb で選ぶ
//   2. 角が合法手にない → legal_bb 全体から pick_lsb にフォールバック
//
// 入力/出力は pick_lsb と同一インターフェース。

`default_nettype none

module pick_corner (
    input  wire [63:0] in_bits,
    output wire        valid,
    output wire [5:0]  index,
    output wire [63:0] one_hot
);

    // a1=bit0, h1=bit7, a8=bit56, h8=bit63
    localparam [63:0] CORNER_MASK = 64'h8100_0000_0000_0081;

    wire [63:0] corner_moves = in_bits & CORNER_MASK;
    wire [63:0] candidates   = |corner_moves ? corner_moves : in_bits;

    pick_lsb u_lsb (
        .in_bits(candidates),
        .valid  (valid),
        .index  (index),
        .one_hot(one_hot)
    );

endmodule

`default_nettype wire
