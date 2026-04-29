// host/main.cpp
//
// Pico SDK 非依存のホスト版ドライバ。Docker 内 Ubuntu 24.04 で
// rtl/othello_top.v を Verilator 化したモデルを stdin/stdout に接続する。
//
// firmware/src/main.cpp との対応:
//   - getchar_timeout_us(0)  ↔  非ブロッキング read(0,...)
//   - putchar_raw            ↔  fputc + fflush
//   - LED 点滅 / sleep_ms 等の Pico 機能は持たない
//
// EOF を受け取ると DUT に LF を 1 byte 流して残応答を吐かせ、tx_valid が
// 一定 cycle 静まったら終了する。これでシナリオファイルを `<` リダイレクト
// した時に綺麗に終わる。
//
// 重要: Pico 版は UART (~87µs/byte) で自然に律速されるが、ホスト版は
// stdin pipe から無限速で食えてしまう。proto.v の FSM は LF 受領後
// S_DISPATCH / S_TX に遷移していて RX を取り込まないので、ナイーブに
// 流すと "応答中の次行" が丸ごと落ちる。
// → LF を流したら tx_valid が立って下がりきるまで stdin を読まない。

#include <fcntl.h>
#include <unistd.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "Vothello_top.h"
#include "Vothello_top___024root.h"
#include "verilated.h"

namespace {

constexpr int kQuiescentCycles = 32;  // EOF 後にこの cycle 数 tx_valid=0 が続けば終了

// proto.v S_* localparam と一致させる
static const char* state_name(uint8_t s) {
    switch (s) {
        case 0: return "RECV";
        case 1: return "DISP";
        case 2: return "TX  ";
        case 3: return "WGST";
        case 4: return "PLAC";
        default: return "?   ";
    }
}

// proto.v TX_MODE_* localparam と一致させる
static const char* tx_mode_name(uint8_t m) {
    switch (m) {
        case 0: return "ROM";
        case 1: return "MO ";
        case 2: return "BS ";
        default: return "?  ";
    }
}

static int popcount64(uint64_t v) {
    int n = 0;
    for (; v; v >>= 1) n += static_cast<int>(v & 1u);
    return n;
}

// tick(dut) 後に呼ぶ。rx_valid/tx_valid が立っているか state が非 RECV のときのみ
// 表示する想定で呼び出し側がフィルタする。出力は stderr。
void debug_print(const Vothello_top* dut, uint64_t cycle) {
    const Vothello_top___024root* r = dut->rootp;

    const uint8_t  state    = r->othello_top__DOT__u_proto__DOT__state;
    const uint8_t  buf_len  = r->othello_top__DOT__u_proto__DOT__buf_len;
    const uint8_t  side     = r->othello_top__DOT__u_proto__DOT__gs_my_side;
    const uint64_t blk      = r->othello_top__DOT__u_proto__DOT__gs_black;
    const uint64_t wht      = r->othello_top__DOT__u_proto__DOT__gs_white;
    const uint64_t legal    = r->othello_top__DOT__u_proto__DOT__lb_legal;
    const uint8_t  ps_idx   = r->othello_top__DOT__u_proto__DOT__ps_index;
    const uint64_t ps_oh    = r->othello_top__DOT__u_proto__DOT__ps_one_hot;
    const uint64_t flip     = r->othello_top__DOT__u_proto__DOT__fc_flip;
    const uint8_t  tx_mode  = r->othello_top__DOT__u_proto__DOT__tx_mode;
    const uint8_t  tx_idx   = r->othello_top__DOT__u_proto__DOT__tx_idx;
    const uint8_t  tx_end   = r->othello_top__DOT__u_proto__DOT__tx_end;

    // bit_index → 座標文字 (coord.v format と同じ規約: bit = row*8+col, a1=0)
    char ps_coord[3] = {'-', '-', '\0'};
    if (ps_oh) {
        ps_coord[0] = static_cast<char>('a' + (ps_idx & 0x7u));
        ps_coord[1] = static_cast<char>('1' + ((ps_idx >> 3) & 0x7u));
    }

    fprintf(stderr,
        "[%6llu] %s buf=%2d side=%c"
        " blk=%016llx wht=%016llx"
        " leg=%016llx(n=%d)"
        " ps=%s flp=%016llx"
        " txm=%s tx=%d/%d\n",
        (unsigned long long)cycle,
        state_name(state), buf_len,
        side ? 'W' : 'B',
        (unsigned long long)blk,
        (unsigned long long)wht,
        (unsigned long long)legal, popcount64(legal),
        ps_coord,
        (unsigned long long)flip,
        tx_mode_name(tx_mode), tx_idx, tx_end);
}

void tick(Vothello_top* dut) {
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    dut->contextp()->timeInc(1);
}

void apply_reset(Vothello_top* dut) {
    dut->rst = 1;
    dut->rx_valid = 0;
    for (int i = 0; i < 4; ++i) tick(dut);
    dut->rst = 0;
}

void set_stdin_nonblocking() {
    const int flags = fcntl(STDIN_FILENO, F_GETFL, 0);
    if (flags < 0) return;
    fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK);
}

// stdin が EOF (read==0) を返したかどうか。-1/EAGAIN は「今は来てない」だけ。
enum class RxState { Byte, Empty, Eof };

RxState read_stdin_byte(uint8_t* out) {
    uint8_t buf;
    const ssize_t n = read(STDIN_FILENO, &buf, 1);
    if (n == 1) {
        *out = buf;
        return RxState::Byte;
    }
    if (n == 0) return RxState::Eof;
    return RxState::Empty;
}

}  // namespace

int main(int argc, char** argv) {
    bool debug_mode = false;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--debug") == 0) debug_mode = true;
    }

    Verilated::commandArgs(argc, argv);

    auto* const ctx = new VerilatedContext;
    auto* const dut = new Vothello_top{ctx, "othello_top"};
    apply_reset(dut);

    set_stdin_nonblocking();

    bool stdin_eof = false;
    bool eof_lf_sent = false;
    bool last_was_lf = false;
    int quiescent = 0;
    uint64_t cycle = 0;

    // LF を流した後の「応答待ち」フラグ。tx_valid が一度立って、
    // その後 KSettleCycles cycle 連続で 0 になるまで次の RX を読まない。
    bool awaiting_response = false;
    bool seen_tx_in_response = false;
    int  tx_quiet = 0;
    constexpr int kSettleCycles = 4;

    while (true) {
        const bool dut_ready = !awaiting_response;

        // RX: ready のときだけ 1 byte 取って DUT に投入
        if (dut_ready && !stdin_eof) {
            uint8_t b;
            switch (read_stdin_byte(&b)) {
                case RxState::Byte:
                    dut->rx_byte = b;
                    dut->rx_valid = 1;
                    last_was_lf = (b == '\n');
                    if (last_was_lf) {
                        awaiting_response = true;
                        seen_tx_in_response = false;
                        tx_quiet = 0;
                    }
                    break;
                case RxState::Empty:
                    dut->rx_valid = 0;
                    break;
                case RxState::Eof:
                    stdin_eof = true;
                    dut->rx_valid = 0;
                    break;
            }
        } else if (dut_ready && stdin_eof && !eof_lf_sent) {
            // 行末が LF で終わっていないシナリオでも残応答を吐けるよう
            // EOF 検出時に LF を補う。最後に流したバイトが既に LF なら不要。
            eof_lf_sent = true;
            if (!last_was_lf) {
                dut->rx_byte = '\n';
                dut->rx_valid = 1;
                awaiting_response = true;
                seen_tx_in_response = false;
                tx_quiet = 0;
            } else {
                dut->rx_valid = 0;
            }
        } else {
            dut->rx_valid = 0;
        }

        const bool had_rx = (dut->rx_valid != 0);
        tick(dut);
        ++cycle;

        // TX: DUT が 1 byte 出していれば stdout に流す
        if (dut->tx_valid) {
            std::fputc(static_cast<int>(dut->tx_byte), stdout);
            std::fflush(stdout);
            quiescent = 0;
            seen_tx_in_response = true;
            tx_quiet = 0;
        }

        if (debug_mode) {
            // S_RECV かつ入出力なしの idle cycle は表示しない
            const uint8_t post_state = dut->rootp->othello_top__DOT__u_proto__DOT__state;
            if (had_rx || dut->tx_valid || post_state != 0) {
                debug_print(dut, cycle);
            }
        }

        if (!dut->tx_valid) {
            ++tx_quiet;
            // 応答が落ち着いたら次の行を流せる状態に戻す。
            // tx_valid が 1 度も立たない応答 (= 空応答) は無いので、
            // seen_tx_in_response が前提条件。
            if (awaiting_response && seen_tx_in_response &&
                tx_quiet >= kSettleCycles) {
                awaiting_response = false;
            }
            if (stdin_eof && eof_lf_sent && !awaiting_response) {
                if (++quiescent >= kQuiescentCycles) break;
            }
        }
    }

    delete dut;
    delete ctx;
    return 0;
}
