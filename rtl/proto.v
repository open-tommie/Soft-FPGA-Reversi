// rtl/proto.v
//
// UART テキストプロトコル骨格を Verilog で実装。
// firmware/src/proto.cpp の Verilog 化版。
//
// 速度ではなく「Verilog で書いて Pico 2 上で動く」ことが目的。
//
// 仕様 (etc/protocol.md §61 のサブセット、Bootstrap step 3 相当):
//   - PI         → "PO\n"
//   - VE         → "VE01reversi-fw\n"
//   - その他全部 → "ER02 unknown\n"
//
// インターフェース:
//   - rx_valid を 1 cycle pulse して rx_byte をラッチさせる。
//     LF (0x0A) を受けると行をディスパッチ。
//   - tx_valid は応答送信中、1 byte あたり 1 cycle High。
//     tx_byte は同時に有効。ホスト側はサンプリングするだけで OK。
//   - 行 buffer は 128 byte。BO<64 char> 等の将来拡張用に余裕を持たせる。

`default_nettype none

module proto (
    input  wire        clk,
    input  wire        rst,
    // RX byte stream (1-cycle pulse pattern)
    input  wire        rx_valid,
    input  wire [7:0]  rx_byte,
    // TX byte stream (tx_valid asserted 1 cycle per byte)
    output reg         tx_valid,
    output reg  [7:0]  tx_byte
);

    // ----- 行 buffer -----
    parameter integer BUF_LOG2 = 7;            // 128 entries
    parameter integer BUF_SIZE = 1 << BUF_LOG2;
    reg [7:0]               buf_mem [0:BUF_SIZE-1];
    reg [BUF_LOG2:0]        buf_len;           // 0..BUF_SIZE (8 bit)

    // ----- FSM -----
    localparam [1:0] S_RECV     = 2'd0,
                     S_DISPATCH = 2'd1,
                     S_TX       = 2'd2;
    reg [1:0] state;

    // ----- 連結 ROM -----
    // PO\n  / VE01reversi-fw\n  / ER02 unknown\n
    localparam [5:0] ROM_PO_OFF = 6'd0,  ROM_PO_LEN = 6'd3;
    localparam [5:0] ROM_VE_OFF = 6'd3,  ROM_VE_LEN = 6'd15;
    localparam [5:0] ROM_ER_OFF = 6'd18, ROM_ER_LEN = 6'd13;

    function automatic [7:0] resp_rom(input [5:0] i);
        case (i)
            // "PO\n"
            6'd0:  resp_rom = "P";    6'd1:  resp_rom = "O";    6'd2:  resp_rom = 8'h0A;
            // "VE01reversi-fw\n"
            6'd3:  resp_rom = "V";    6'd4:  resp_rom = "E";    6'd5:  resp_rom = "0";
            6'd6:  resp_rom = "1";    6'd7:  resp_rom = "r";    6'd8:  resp_rom = "e";
            6'd9:  resp_rom = "v";    6'd10: resp_rom = "e";    6'd11: resp_rom = "r";
            6'd12: resp_rom = "s";    6'd13: resp_rom = "i";    6'd14: resp_rom = "-";
            6'd15: resp_rom = "f";    6'd16: resp_rom = "w";    6'd17: resp_rom = 8'h0A;
            // "ER02 unknown\n"
            6'd18: resp_rom = "E";    6'd19: resp_rom = "R";    6'd20: resp_rom = "0";
            6'd21: resp_rom = "2";    6'd22: resp_rom = " ";    6'd23: resp_rom = "u";
            6'd24: resp_rom = "n";    6'd25: resp_rom = "k";    6'd26: resp_rom = "n";
            6'd27: resp_rom = "o";    6'd28: resp_rom = "w";    6'd29: resp_rom = "n";
            6'd30: resp_rom = 8'h0A;
            default: resp_rom = 8'h00;
        endcase
    endfunction

    reg [5:0] tx_idx;     // 現在送信 ROM index
    reg [5:0] tx_end;     // 終了 index (exclusive)

    // ディスパッチ判定 (S_DISPATCH に居るときに評価される)
    wire is_pi = (buf_len == 8'd2) && (buf_mem[0] == "P") && (buf_mem[1] == "I");
    wire is_ve = (buf_len == 8'd2) && (buf_mem[0] == "V") && (buf_mem[1] == "E");
    wire is_sb = (buf_len == 8'd2) && (buf_mem[0] == "S") && (buf_mem[1] == "B");
    wire is_sw = (buf_len == 8'd2) && (buf_mem[0] == "S") && (buf_mem[1] == "W");
    // MO<xy>: 4 byte (M, O, col_char, row_char)。座標妥当性は cd_parse_valid で別判定
    wire is_mo = (buf_len == 8'd4) && (buf_mem[0] == "M") && (buf_mem[1] == "O");

    // ----- Step 5d-1: 内部状態 + 計算モジュール群を instantiate -----
    // この段階ではまだ FSM から駆動しない (cmd_* は全部 0)。次段で結線。

    // game_state: 盤面 + my_side + phase
    reg         gs_cmd_init;
    reg         gs_init_side;
    reg         gs_cmd_set_board;
    reg [63:0]  gs_in_black;
    reg [63:0]  gs_in_white;
    reg         gs_cmd_set_phase;
    reg [1:0]   gs_in_phase;
    /* verilator lint_off UNUSEDSIGNAL */
    wire [63:0] gs_black;
    wire [63:0] gs_white;
    wire        gs_my_side;
    wire [1:0]  gs_phase;
    /* verilator lint_on UNUSEDSIGNAL */

    game_state u_game_state (
        .clk(clk), .rst(rst),
        .cmd_init(gs_cmd_init), .init_side(gs_init_side),
        .cmd_set_board(gs_cmd_set_board),
        .in_black(gs_in_black), .in_white(gs_in_white),
        .cmd_set_phase(gs_cmd_set_phase), .in_phase(gs_in_phase),
        .black(gs_black), .white(gs_white),
        .my_side(gs_my_side), .phase(gs_phase)
    );

    // legal_bb: gs の現在盤面 + my_side で合法手 bitboard を出す
    /* verilator lint_off UNUSEDSIGNAL */
    wire [63:0] lb_legal;
    /* verilator lint_on UNUSEDSIGNAL */
    legal_bb u_legal_bb (
        .black(gs_black), .white(gs_white),
        .side(gs_my_side), .legal(lb_legal)
    );

    // pick_lsb: legal の中で最下位 set bit を選ぶ
    /* verilator lint_off UNUSEDSIGNAL */
    wire        ps_valid;
    wire [5:0]  ps_index;
    wire [63:0] ps_one_hot;
    /* verilator lint_on UNUSEDSIGNAL */
    pick_lsb u_pick_lsb (
        .in_bits(lb_legal),
        .valid(ps_valid), .index(ps_index), .one_hot(ps_one_hot)
    );

    // coord: parse 用は MO 受信時に buf_mem の [2..3] を渡す予定。
    //        format 用は pick_lsb の index を渡し、自分の手の文字列を得る。
    //        Step 5d-1 では parse 入力は 0 固定 (まだ使わない)。
    /* verilator lint_off UNUSEDSIGNAL */
    wire [5:0] cd_parse_bit;
    wire       cd_parse_valid;
    wire [7:0] cd_col_char;
    wire [7:0] cd_row_char;
    /* verilator lint_on UNUSEDSIGNAL */
    // parse 入力は MO<xy> の payload 部 (buf_mem[2..3]) を常時接続。
    // 出力は S_DISPATCH で is_mo のときだけ意味を持つ。
    coord u_coord (
        .in_col_char(buf_mem[2]), .in_row_char(buf_mem[3]),
        .parse_bit(cd_parse_bit), .parse_valid(cd_parse_valid),
        .in_bit_index(ps_index),
        .out_col_char(cd_col_char), .out_row_char(cd_row_char)
    );

    always @(posedge clk) begin
        if (rst) begin
            buf_len  <= 0;
            state    <= S_RECV;
            tx_valid <= 0;
            tx_byte  <= 0;
            tx_idx   <= 0;
            tx_end   <= 0;
            // 5d-1: game_state コマンドはまだ FSM から駆動しない
            gs_cmd_init      <= 0;
            gs_init_side     <= 0;
            gs_cmd_set_board <= 0;
            gs_in_black      <= 0;
            gs_in_white      <= 0;
            gs_cmd_set_phase <= 0;
            gs_in_phase      <= 0;
        end else begin
            tx_valid <= 0;  // デフォルト下げ。S_TX で必要なときだけ立てる。
            // 5d-1: game_state コマンドは毎 cycle 0 に戻す (1-cycle pulse 想定)
            gs_cmd_init      <= 0;
            gs_cmd_set_board <= 0;
            gs_cmd_set_phase <= 0;
            case (state)
                S_RECV: begin
                    if (rx_valid) begin
                        if (rx_byte == 8'h0A) begin
                            state <= S_DISPATCH;
                        end else if (buf_len < BUF_SIZE[BUF_LOG2:0]) begin
                            buf_mem[buf_len[BUF_LOG2-1:0]] <= rx_byte;
                            buf_len <= buf_len + 1'b1;
                        end
                        // overflow 時は単に捨てる。LF が来るまで吸収。
                    end
                end
                S_DISPATCH: begin
                    if (is_pi) begin
                        tx_idx <= ROM_PO_OFF;
                        tx_end <= ROM_PO_OFF + ROM_PO_LEN;
                    end else if (is_ve) begin
                        tx_idx <= ROM_VE_OFF;
                        tx_end <= ROM_VE_OFF + ROM_VE_LEN;
                    end else begin
                        tx_idx <= ROM_ER_OFF;
                        tx_end <= ROM_ER_OFF + ROM_ER_LEN;
                    end
                    // 5d-2: SB/SW を受けたら game_state を初期化する。
                    // 応答自体はまだ ER02 のまま (5d-3 で BS / MO 等に置換予定)。
                    // gs_cmd_init は 1 cycle のみ立てる (default 0 で次 cycle 戻る)
                    if (is_sb) begin
                        gs_cmd_init  <= 1'b1;
                        gs_init_side <= 1'b0;   // Black
                    end else if (is_sw) begin
                        gs_cmd_init  <= 1'b1;
                        gs_init_side <= 1'b1;   // White
                    end
                    // 5d-3a: MO<xy> を受けたら相手の駒を盤面に追加する。
                    //   - 反転 (flip_calc) は step 6 で実装。今は **置くだけ**
                    //   - my_side=0 なら opp は White、my_side=1 なら Black
                    //   - 不正座標 (cd_parse_valid=0) の場合は何もしない
                    if (is_mo && cd_parse_valid) begin
                        gs_cmd_set_board <= 1'b1;
                        if (gs_my_side == 1'b0) begin
                            gs_in_white <= gs_white | (64'd1 << cd_parse_bit);
                            gs_in_black <= gs_black;
                        end else begin
                            gs_in_black <= gs_black | (64'd1 << cd_parse_bit);
                            gs_in_white <= gs_white;
                        end
                    end
                    buf_len <= 0;
                    state <= S_TX;
                end
                S_TX: begin
                    if (tx_idx < tx_end) begin
                        tx_byte  <= resp_rom(tx_idx);
                        tx_valid <= 1'b1;
                        tx_idx   <= tx_idx + 1'b1;
                    end else begin
                        state <= S_RECV;
                    end
                end
                default: state <= S_RECV;
            endcase
        end
    end

endmodule

`default_nettype wire
