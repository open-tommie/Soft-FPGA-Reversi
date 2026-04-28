// rtl/flip_calc.v
//
// Othello: 着手位置 move_idx に own 駒を置いたとき裏返る opp 駒の bitmap。
// 純粋組合せ論理。
//
// 入力:
//   own[63:0]    着手側 (これから置く色) の駒
//   opp[63:0]    相手色の駒
//   move_idx     着手位置 (0..63、行優先 a1=0, h8=63)
// 出力:
//   flip[63:0]   裏返される opp 駒の bitmap (own 側の色になる)
//
// 不正手 (move 位置に何もキャプチャできない、move 位置が既に駒で埋まっている等)
// では flip = 0 を返す。
//
// アルゴリズム (legal_bb と同型、起点だけ own → move_one_hot):
//   各方向 d ごとに:
//     1) move_one_hot から d 方向に shift して隣接 opp を取る (run の 1 段目)
//     2) 5 回まで shift を続けて opp の連続列 (最大 6 駒) を取る
//     3) その先 (run+1 step) に own があれば run 全体が flip 対象
//        own がなければその方向の flip は 0
//   8 方向の flip を OR で集約。

`default_nettype none

module flip_calc (
    input  wire [63:0] own,
    input  wire [63:0] opp,
    input  wire [5:0]  move_idx,
    output wire [63:0] flip
);

    wire [63:0] move_one_hot = 64'd1 << move_idx;

    localparam [63:0] MASK_NOT_A = 64'hFEFEFEFEFEFEFEFE;
    localparam [63:0] MASK_NOT_H = 64'h7F7F7F7F7F7F7F7F;

    // ========== East (col +1, shift << 1, mask !A) ==========
    wire [63:0] e1 = ((move_one_hot << 1) & MASK_NOT_A) & opp;
    wire [63:0] e2 = ((e1            << 1) & MASK_NOT_A) & opp;
    wire [63:0] e3 = ((e2            << 1) & MASK_NOT_A) & opp;
    wire [63:0] e4 = ((e3            << 1) & MASK_NOT_A) & opp;
    wire [63:0] e5 = ((e4            << 1) & MASK_NOT_A) & opp;
    wire [63:0] e6 = ((e5            << 1) & MASK_NOT_A) & opp;
    wire [63:0] e_run = e1 | e2 | e3 | e4 | e5 | e6;
    wire        e_capture = |(((e_run << 1) & MASK_NOT_A) & own);
    wire [63:0] e_flip = {64{e_capture}} & e_run;

    // ========== West (col -1, shift >> 1, mask !H) ==========
    wire [63:0] w1 = ((move_one_hot >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w2 = ((w1            >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w3 = ((w2            >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w4 = ((w3            >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w5 = ((w4            >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w6 = ((w5            >> 1) & MASK_NOT_H) & opp;
    wire [63:0] w_run = w1 | w2 | w3 | w4 | w5 | w6;
    wire        w_capture = |(((w_run >> 1) & MASK_NOT_H) & own);
    wire [63:0] w_flip = {64{w_capture}} & w_run;

    // ========== South (row +1, shift << 8) ==========
    wire [63:0] s1 = (move_one_hot << 8) & opp;
    wire [63:0] s2 = (s1            << 8) & opp;
    wire [63:0] s3 = (s2            << 8) & opp;
    wire [63:0] s4 = (s3            << 8) & opp;
    wire [63:0] s5 = (s4            << 8) & opp;
    wire [63:0] s6 = (s5            << 8) & opp;
    wire [63:0] s_run = s1 | s2 | s3 | s4 | s5 | s6;
    wire        s_capture = |((s_run << 8) & own);
    wire [63:0] s_flip = {64{s_capture}} & s_run;

    // ========== North (row -1, shift >> 8) ==========
    wire [63:0] n1 = (move_one_hot >> 8) & opp;
    wire [63:0] n2 = (n1            >> 8) & opp;
    wire [63:0] n3 = (n2            >> 8) & opp;
    wire [63:0] n4 = (n3            >> 8) & opp;
    wire [63:0] n5 = (n4            >> 8) & opp;
    wire [63:0] n6 = (n5            >> 8) & opp;
    wire [63:0] n_run = n1 | n2 | n3 | n4 | n5 | n6;
    wire        n_capture = |((n_run >> 8) & own);
    wire [63:0] n_flip = {64{n_capture}} & n_run;

    // ========== SE (row +1, col +1, shift << 9, mask !A) ==========
    wire [63:0] se1 = ((move_one_hot << 9) & MASK_NOT_A) & opp;
    wire [63:0] se2 = ((se1           << 9) & MASK_NOT_A) & opp;
    wire [63:0] se3 = ((se2           << 9) & MASK_NOT_A) & opp;
    wire [63:0] se4 = ((se3           << 9) & MASK_NOT_A) & opp;
    wire [63:0] se5 = ((se4           << 9) & MASK_NOT_A) & opp;
    wire [63:0] se6 = ((se5           << 9) & MASK_NOT_A) & opp;
    wire [63:0] se_run = se1 | se2 | se3 | se4 | se5 | se6;
    wire        se_capture = |(((se_run << 9) & MASK_NOT_A) & own);
    wire [63:0] se_flip = {64{se_capture}} & se_run;

    // ========== SW (row +1, col -1, shift << 7, mask !H) ==========
    wire [63:0] sw1 = ((move_one_hot << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw2 = ((sw1           << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw3 = ((sw2           << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw4 = ((sw3           << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw5 = ((sw4           << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw6 = ((sw5           << 7) & MASK_NOT_H) & opp;
    wire [63:0] sw_run = sw1 | sw2 | sw3 | sw4 | sw5 | sw6;
    wire        sw_capture = |(((sw_run << 7) & MASK_NOT_H) & own);
    wire [63:0] sw_flip = {64{sw_capture}} & sw_run;

    // ========== NE (row -1, col +1, shift >> 7, mask !A) ==========
    wire [63:0] ne1 = ((move_one_hot >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne2 = ((ne1           >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne3 = ((ne2           >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne4 = ((ne3           >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne5 = ((ne4           >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne6 = ((ne5           >> 7) & MASK_NOT_A) & opp;
    wire [63:0] ne_run = ne1 | ne2 | ne3 | ne4 | ne5 | ne6;
    wire        ne_capture = |(((ne_run >> 7) & MASK_NOT_A) & own);
    wire [63:0] ne_flip = {64{ne_capture}} & ne_run;

    // ========== NW (row -1, col -1, shift >> 9, mask !H) ==========
    wire [63:0] nw1 = ((move_one_hot >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw2 = ((nw1           >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw3 = ((nw2           >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw4 = ((nw3           >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw5 = ((nw4           >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw6 = ((nw5           >> 9) & MASK_NOT_H) & opp;
    wire [63:0] nw_run = nw1 | nw2 | nw3 | nw4 | nw5 | nw6;
    wire        nw_capture = |(((nw_run >> 9) & MASK_NOT_H) & own);
    wire [63:0] nw_flip = {64{nw_capture}} & nw_run;

    wire [63:0] raw_flip = e_flip | w_flip | s_flip | n_flip
                         | se_flip | sw_flip | ne_flip | nw_flip;

    // move 位置が既に own / opp で埋まっている (= 空マスでない) 場合は
    // 不正手として flip = 0 を返す。Python golden の find_flips は
    // board[r][c] != EMPTY で空リストを返す挙動と一致させる。
    wire move_on_empty = ((own | opp) & move_one_hot) == 64'd0;
    assign flip = move_on_empty ? raw_flip : 64'd0;

endmodule

`default_nettype wire
