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

#include "Vothello_top.h"
#include "verilated.h"

namespace {

constexpr int kQuiescentCycles = 32;  // EOF 後にこの cycle 数 tx_valid=0 が続けば終了

void tick(Vothello_top* dut) {
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
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
    Verilated::commandArgs(argc, argv);

    auto* const ctx = new VerilatedContext;
    auto* const dut = new Vothello_top{ctx, "othello_top"};
    apply_reset(dut);

    set_stdin_nonblocking();

    bool stdin_eof = false;
    bool eof_lf_sent = false;
    bool last_was_lf = false;
    int quiescent = 0;

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

        tick(dut);

        // TX: DUT が 1 byte 出していれば stdout に流す
        if (dut->tx_valid) {
            std::fputc(static_cast<int>(dut->tx_byte), stdout);
            std::fflush(stdout);
            quiescent = 0;
            seen_tx_in_response = true;
            tx_quiet = 0;
        } else {
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
