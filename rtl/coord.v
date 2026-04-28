// rtl/coord.v
//
// Othello 座標 ('a1' .. 'h8') と bit_index (0 .. 63) の双方向変換 (純粋組合せ)。
//
// 座標規約 (etc/protocol.md §7 / Python golden 準拠):
//   - 文字小文字必須: 'a'..'h' (列), '1'..'8' (行)
//   - bit_index = row * 8 + col, a1 = bit 0, h8 = bit 63
//
// 用途:
//   parse:  proto.v の MO 受信時に <xy> を bit_index へ変換
//   format: proto.v の MO 送信時に bit_index を <xy> 文字列へ変換
//
// 不正入力 (大文字 / 範囲外 / 数字外) は parse_valid = 0。proto.v 側で ER02
// に変換する。

`default_nettype none

module coord (
    // ====== parse: 2 文字座標 → bit_index ======
    input  wire [7:0] in_col_char,    // 'a' .. 'h'
    input  wire [7:0] in_row_char,    // '1' .. '8'
    output wire [5:0] parse_bit,
    output wire       parse_valid,

    // ====== format: bit_index → 2 文字座標 ======
    input  wire [5:0] in_bit_index,   // 0 .. 63
    output wire [7:0] out_col_char,   // 'a' .. 'h' (lowercase)
    output wire [7:0] out_row_char    // '1' .. '8'
);

    // ---------- parse ----------
    wire col_ok = (in_col_char >= "a") && (in_col_char <= "h");
    wire row_ok = (in_row_char >= "1") && (in_row_char <= "8");
    /* verilator lint_off UNUSEDSIGNAL */
    // 0..7 when valid。上位 5 bit は意図的に捨てる (col_ok/row_ok で別扱い)
    wire [7:0] col_off = in_col_char - "a";
    wire [7:0] row_off = in_row_char - "1";
    /* verilator lint_on UNUSEDSIGNAL */

    assign parse_bit   = {row_off[2:0], col_off[2:0]};
    assign parse_valid = col_ok & row_ok;

    // ---------- format ----------
    wire [2:0] f_col = in_bit_index[2:0];
    wire [2:0] f_row = in_bit_index[5:3];

    assign out_col_char = "a" + {5'd0, f_col};
    assign out_row_char = "1" + {5'd0, f_row};

endmodule

`default_nettype wire
