// rtl/othello_top.v
//
// Bootstrap Step 2: Verilator 経由で C++ 化し firmware にリンクする
// ことのみを目的とした最小スタブ。MMIO や bitboard ロジックは
// Bootstrap Step 4 (legal_bb 実装) で追加する。

`default_nettype none

module othello_top (
    input  wire        clk,
    input  wire        rst,
    output reg  [31:0] tick
);

    always @(posedge clk) begin
        if (rst) tick <= 32'd0;
        else     tick <= tick + 32'd1;
    end

endmodule

`default_nettype wire
