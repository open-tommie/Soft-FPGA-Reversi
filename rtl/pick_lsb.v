// rtl/pick_lsb.v
//
// 64bit 入力から最下位の立っている bit を抽出 (純粋組合せ)。
//
// 用途: legal_bb の出力 (合法手 bitboard) から「行優先 a1, b1, c1, ..., h8」
//       の順序で最初に現れる手を選ぶ (Python golden `legal_moves()` の
//       返却順と一致)。
//
// 出力:
//   valid    入力に少なくとも 1 bit 立っていれば 1
//   index    最下位 set bit の位置 (0..63)。valid=0 のときは 0
//   one_hot  最下位 set bit のみが立った 64bit (1 << index)。valid=0 で 0
//
// 実装メモ:
//   - one_hot は古典的トリック x & -x で 1 命令相当
//   - index は 6bit priority encoder。高 → 低の順に if で上書きすると
//     最後に書き込まれる最下位 set bit が残る (Verilator の合成では
//     casez 相当のロジックに展開される)

`default_nettype none

module pick_lsb (
    input  wire [63:0] in_bits,
    output wire        valid,
    output reg  [5:0]  index,
    output wire [63:0] one_hot
);

    // 最下位 1 bit のみ抽出 (x & -x)
    assign one_hot = in_bits & (~in_bits + 64'd1);
    assign valid   = |in_bits;

    integer i;
    always @* begin
        index = 6'd0;
        // 高位から走査して上書き → 最後に当たる最下位の set bit が残る
        for (i = 63; i >= 0; i = i - 1) begin
            if (in_bits[i]) index = i[5:0];
        end
    end

endmodule

`default_nettype wire
