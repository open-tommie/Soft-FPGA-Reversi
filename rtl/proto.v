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

    always @(posedge clk) begin
        if (rst) begin
            buf_len  <= 0;
            state    <= S_RECV;
            tx_valid <= 0;
            tx_byte  <= 0;
            tx_idx   <= 0;
            tx_end   <= 0;
        end else begin
            tx_valid <= 0;  // デフォルト下げ。S_TX で必要なときだけ立てる。
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
