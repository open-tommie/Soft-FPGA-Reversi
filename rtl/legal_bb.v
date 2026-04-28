// rtl/legal_bb.v
//
// Othello 合法手 bitboard 計算 (純粋組合せ論理)。
//
// 入力:
//   black[63:0]  黒駒 bitboard
//   white[63:0]  白駒 bitboard
//   side         0 = 黒の手番, 1 = 白の手番
// 出力:
//   legal[63:0]  side が指せる合法手の bitboard (1 立っている bit が合法位置)
//
// bit 配置 (etc/protocol.md §7 / Python golden 準拠):
//   bit_index = row * 8 + col, a1 = bit 0, h8 = bit 63
//   - col 0 = a-file, col 7 = h-file
//   - row 0 = rank 1,  row 7 = rank 8
//
// アルゴリズム (古典的 bitboard 8 方向 flood):
//   各方向 d について、own から始めて opp を 1〜6 駒辿り、その先の empty を
//   合法手として捕捉する。8 方向を独立に並列計算して OR で集約。
//
//   - 各方向の 1 cycle shift で隣接 opp を取る (d 方向に own→opp の連結)
//   - その後 5 回まで shift を続けて opp を辿る (Othello は最大 6 駒挟む)
//   - 最後に 1 回 shift して empty に当たれば合法手
//
// シフトと境界マスク (a/h-file の wrap-around 防止):
//   E  : << 1 + MASK_NOT_A
//   W  : >> 1 + MASK_NOT_H
//   S  : << 8 (no mask)
//   N  : >> 8 (no mask)
//   SE : << 9 + MASK_NOT_A
//   SW : << 7 + MASK_NOT_H
//   NE : >> 7 + MASK_NOT_A
//   NW : >> 9 + MASK_NOT_H

`default_nettype none

module legal_bb (
    input  wire [63:0] black,
    input  wire [63:0] white,
    input  wire        side,
    output wire [63:0] legal
);

    wire [63:0] own   = side ? white : black;
    wire [63:0] opp   = side ? black : white;
    wire [63:0] empty = ~(black | white);

    // a-file / h-file 除外マスク
    localparam [63:0] MASK_NOT_A = 64'hFEFEFEFEFEFEFEFE;
    localparam [63:0] MASK_NOT_H = 64'h7F7F7F7F7F7F7F7F;

    // ========== East (col +1, shift << 1, mask !A) ==========
    wire [63:0] e1 = ((own  << 1) & MASK_NOT_A) & opp;
    wire [63:0] e2 = ((e1   << 1) & MASK_NOT_A) & opp;
    wire [63:0] e3 = ((e2   << 1) & MASK_NOT_A) & opp;
    wire [63:0] e4 = ((e3   << 1) & MASK_NOT_A) & opp;
    wire [63:0] e5 = ((e4   << 1) & MASK_NOT_A) & opp;
    wire [63:0] e6 = ((e5   << 1) & MASK_NOT_A) & opp;
    wire [63:0] e_legal = (((e1|e2|e3|e4|e5|e6) << 1) & MASK_NOT_A) & empty;

    // ========== West (col -1, shift >> 1, mask !H) ==========
    wire [63:0] w1 = ((own  >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w2 = ((w1   >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w3 = ((w2   >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w4 = ((w3   >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w5 = ((w4   >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w6 = ((w5   >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w_legal = (((w1|w2|w3|w4|w5|w6) >> 1) & MASK_NOT_H) & empty;

    // ========== South (row +1, shift << 8) ==========
    wire [63:0] s1 = (own << 8) & opp;
    wire [63:0] s2 = (s1  << 8) & opp;
    wire [63:0] s3 = (s2  << 8) & opp;
    wire [63:0] s4 = (s3  << 8) & opp;
    wire [63:0] s5 = (s4  << 8) & opp;
    wire [63:0] s6 = (s5  << 8) & opp;
    wire [63:0] s_legal = ((s1|s2|s3|s4|s5|s6) << 8) & empty;

    // ========== North (row -1, shift >> 8) ==========
    wire [63:0] n1 = (own >> 8) & opp;
    wire [63:0] n2 = (n1  >> 8) & opp;
    wire [63:0] n3 = (n2  >> 8) & opp;
    wire [63:0] n4 = (n3  >> 8) & opp;
    wire [63:0] n5 = (n4  >> 8) & opp;
    wire [63:0] n6 = (n5  >> 8) & opp;
    wire [63:0] n_legal = ((n1|n2|n3|n4|n5|n6) >> 8) & empty;

    // ========== SE (row +1, col +1, shift << 9, mask !A) ==========
    wire [63:0] se1 = ((own  << 9) & MASK_NOT_A) & opp;
    wire [63:0] se2 = ((se1  << 9) & MASK_NOT_A) & opp;
    wire [63:0] se3 = ((se2  << 9) & MASK_NOT_A) & opp;
    wire [63:0] se4 = ((se3  << 9) & MASK_NOT_A) & opp;
    wire [63:0] se5 = ((se4  << 9) & MASK_NOT_A) & opp;
    wire [63:0] se6 = ((se5  << 9) & MASK_NOT_A) & opp;
    wire [63:0] se_legal = (((se1|se2|se3|se4|se5|se6) << 9) & MASK_NOT_A) & empty;

    // ========== SW (row +1, col -1, shift << 7, mask !H) ==========
    wire [63:0] sw1 = ((own  << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw2 = ((sw1  << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw3 = ((sw2  << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw4 = ((sw3  << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw5 = ((sw4  << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw6 = ((sw5  << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw_legal = (((sw1|sw2|sw3|sw4|sw5|sw6) << 7) & MASK_NOT_H) & empty;

    // ========== NE (row -1, col +1, shift >> 7, mask !A) ==========
    wire [63:0] ne1 = ((own  >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne2 = ((ne1  >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne3 = ((ne2  >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne4 = ((ne3  >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne5 = ((ne4  >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne6 = ((ne5  >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne_legal = (((ne1|ne2|ne3|ne4|ne5|ne6) >> 7) & MASK_NOT_A) & empty;

    // ========== NW (row -1, col -1, shift >> 9, mask !H) ==========
    wire [63:0] nw1 = ((own  >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw2 = ((nw1  >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw3 = ((nw2  >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw4 = ((nw3  >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw5 = ((nw4  >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw6 = ((nw5  >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw_legal = (((nw1|nw2|nw3|nw4|nw5|nw6) >> 9) & MASK_NOT_H) & empty;

    // 8 方向の合法手を集約
    assign legal = e_legal | w_legal | s_legal | n_legal
                 | se_legal | sw_legal | ne_legal | nw_legal;

endmodule

`default_nettype wire
