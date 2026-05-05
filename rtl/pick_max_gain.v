// rtl/pick_max_gain.v
//
// 合法手の中で着手後の自駒が最大になる手を選ぶ (純粋組合せ)。
//
// 各合法手について flip_calc で反転駒数を求め、最大のものを選ぶ。
// 同数の場合は bit index 最小 (行優先で最初) の手を返す。
//
// 入力:
//   in_bits[63:0]  合法手 bitboard (legal_bb の出力)
//   own[63:0]      着手側の現在駒
//   opp[63:0]      相手側の現在駒
// 出力:
//   valid          in_bits != 0 なら 1
//   index[5:0]     選択した手の bit index (0..63)
//   one_hot[63:0]  選択した手の one-hot (1 << index)。valid=0 のとき 0

`default_nettype none

module pick_max_gain (
    input  wire [63:0] in_bits,
    input  wire [63:0] own,
    input  wire [63:0] opp,
    output wire        valid,
    output reg  [5:0]  index,
    output wire [63:0] one_hot
);

    assign valid   = |in_bits;
    assign one_hot = valid ? (64'd1 << index) : 64'd0;

    // 64 手分の flip bitmap を並列計算
    wire [63:0] flip [0:63];
    genvar g;
    generate
        for (g = 0; g < 64; g = g + 1) begin : gen_flip
            flip_calc u_flip (
                .own      (own),
                .opp      (opp),
                .move_idx (g[5:0]),
                .flip     (flip[g])
            );
        end
    endgenerate

    // 各手の反転駒数 (popcount) と最大手選択を 1 always に統合
    reg [6:0] gain [0:63];
    reg [6:0] best_gain;
    integer   i, j;

    always @* begin
        // step 1: gain[i] = popcount(flip[i])
        for (i = 0; i < 64; i = i + 1) begin
            gain[i] = 7'd0;
            for (j = 0; j < 64; j = j + 1)
                gain[i] = gain[i] + {6'd0, flip[i][j]};
        end

        // step 2: 合法手の中で最大 gain の最小 index を選ぶ
        // i = 63→0 の順に >= で更新すると最小 index が最後に残る
        best_gain = 7'd0;
        index     = 6'd0;
        for (i = 63; i >= 0; i = i - 1) begin
            if (in_bits[i] && (gain[i] >= best_gain)) begin
                best_gain = gain[i];
                index     = i[5:0];
            end
        end
    end

endmodule

`default_nettype wire
