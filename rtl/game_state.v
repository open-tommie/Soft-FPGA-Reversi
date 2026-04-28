// rtl/game_state.v
//
// 対局中の内部状態を保持するレジスタファイル。proto.v からのコマンド
// パルスで遷移する。盤面更新ロジック (apply_move / flip_calc) はここには
// 持たず、proto.v 側 (or step 6 で別モジュール) が計算した結果を
// cmd_set_board で書き込む構成にする (関心の分離)。
//
// 保持する状態:
//   black[63:0]   黒駒 bitboard
//   white[63:0]   白駒 bitboard
//   my_side       自分の色 (0=Black, 1=White)。SB/SW 受信で確定
//   phase[1:0]    対局フェーズ (etc/protocol.md §57 状態機械)
//                   PHASE_IDLE      0  対局なし、待機
//                   PHASE_MY_TURN   1  自分の手番。legal_bb を回して送信
//                   PHASE_WAIT_OPP  2  相手の手待ち。MO/PA 受信を待つ
//
// コマンドパルス (1 cycle High で動作、複数同時時は cmd_init が最優先):
//   cmd_init        SB/SW 受信時。標準初期盤面 + my_side セット + 適切な phase
//                     init_side=0 (SB) → my_side=0, phase=MY_TURN
//                     init_side=1 (SW) → my_side=1, phase=WAIT_OPP
//   cmd_set_board   in_black/in_white を black/white にラッチ (MO 処理時)
//   cmd_set_phase   in_phase を phase にラッチ (フェーズ手動遷移時)

`default_nettype none

module game_state (
    input  wire        clk,
    input  wire        rst,

    // SB/SW 受信時の初期化
    input  wire        cmd_init,
    input  wire        init_side,        // 0=Black, 1=White

    // 盤面の差し替え (proto.v が apply_move 計算後に書き戻す想定)
    input  wire        cmd_set_board,
    input  wire [63:0] in_black,
    input  wire [63:0] in_white,

    // フェーズ手動遷移 (例: 自分の手送信完了 → WAIT_OPP, EB/EW/ED → IDLE)
    input  wire        cmd_set_phase,
    input  wire [1:0]  in_phase,

    // 観測
    output reg  [63:0] black,
    output reg  [63:0] white,
    output reg         my_side,
    output reg  [1:0]  phase
);

    // フェーズ定義 (proto.v からも参照する想定なので localparam)
    localparam [1:0] PHASE_IDLE     = 2'd0;
    localparam [1:0] PHASE_MY_TURN  = 2'd1;
    localparam [1:0] PHASE_WAIT_OPP = 2'd2;

    // 標準 Othello 初期盤面 (etc/protocol.md §7 / Python init_board() 準拠)
    //   d4 = WHITE (bit 27), e4 = BLACK (bit 28)
    //   d5 = BLACK (bit 35), e5 = WHITE (bit 36)
    localparam [63:0] INIT_BLACK = (64'd1 << 28) | (64'd1 << 35);
    localparam [63:0] INIT_WHITE = (64'd1 << 27) | (64'd1 << 36);

    always @(posedge clk) begin
        if (rst) begin
            black   <= 64'd0;
            white   <= 64'd0;
            my_side <= 1'b0;
            phase   <= PHASE_IDLE;
        end else if (cmd_init) begin
            // SB/SW: 初期盤面 + side + phase 一括セット
            black   <= INIT_BLACK;
            white   <= INIT_WHITE;
            my_side <= init_side;
            // 黒先手なので Black=自分なら自分の手番、White=自分なら相手待ち
            phase   <= (init_side == 1'b0) ? PHASE_MY_TURN : PHASE_WAIT_OPP;
        end else begin
            // cmd_init より低い優先順位の更新は独立に処理
            if (cmd_set_board) begin
                black <= in_black;
                white <= in_white;
            end
            if (cmd_set_phase) begin
                phase <= in_phase;
            end
        end
    end

endmodule

`default_nettype wire
