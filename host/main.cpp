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
// EOF を受け取ると DUT に CR+LF (2 byte) を流して残応答を吐かせ、tx_valid
// が一定 cycle 静まったら終了する。これでシナリオファイルを `<` リダイレクト
// した時に綺麗に終わる。
//
// 重要: Pico 版は UART (~87µs/byte) で自然に律速されるが、ホスト版は
// stdin pipe から無限速で食えてしまう。proto.v の FSM は CR+LF 受領後
// S_DISPATCH / S_TX に遷移していて RX を取り込まないので、ナイーブに
// 流すと "応答中の次行" が丸ごと落ちる。
// → CR+LF を流したら tx_valid が立って下がりきるまで stdin を読まない。

#include <fcntl.h>
#include <time.h>
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

// eval() 実測用アキュムレータ
static uint64_t s_eval_ns  = 0;
static uint64_t s_tick_count = 0;

static inline uint64_t now_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<uint64_t>(ts.tv_sec) * 1000000000ULL +
           static_cast<uint64_t>(ts.tv_nsec);
}

void tick(Vothello_top* dut) {
    const uint64_t t0 = now_ns();
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    s_eval_ns += now_ns() - t0;
    ++s_tick_count;
    dut->contextp()->timeInc(1);
}

// verbose=true: stderr 向けの詳細フォーマット
// verbose=false: プロトコル応答 "BM clk=X.XXXMHz tick=XX.Xns\n"
void bench_report(FILE* out, bool verbose) {
    if (s_tick_count == 0) return;
    const double ns_per_tick = static_cast<double>(s_eval_ns) /
                               static_cast<double>(s_tick_count);
    const double soft_clk_hz = 1e9 / ns_per_tick;
    if (verbose) {
        fprintf(out,
            "[bench] ticks=%llu  eval_total=%.3f ms"
            "  per_tick=%.1f ns  soft-FPGA clk=%.3f MHz\n",
            (unsigned long long)s_tick_count,
            static_cast<double>(s_eval_ns) / 1e6,
            ns_per_tick,
            soft_clk_hz / 1e6);
    } else {
        fprintf(out, "BM clk=%.3fMHz tick=%.1fns\r\n",
            soft_clk_hz / 1e6, ns_per_tick);
        std::fflush(out);
    }
}

// __DATE__ ("Mmm DD YYYY") → "YYYY-MM-DD" に変換する
static void date_iso(char out[11]) {
    static const char kMon[] = "JanFebMarAprMayJunJulAugSepOctNovDec";
    const char* d = __DATE__;
    int mi = 0;
    for (; mi < 12; ++mi)
        if (d[0]==kMon[mi*3] && d[1]==kMon[mi*3+1] && d[2]==kMon[mi*3+2]) break;
    const int dd = (d[4]==' ') ? (d[5]-'0') : ((d[4]-'0')*10+(d[5]-'0'));
    out[0]=d[7]; out[1]=d[8]; out[2]=d[9]; out[3]=d[10];
    out[4]='-';
    out[5]='0'+(mi+1)/10; out[6]='0'+(mi+1)%10;
    out[7]='-';
    out[8]='0'+dd/10;     out[9]='0'+dd%10;
    out[10]='\0';
}

// /proc と /etc/os-release からプラットフォーム文字列を構築する
// 例: "WSL2 Ubuntu24"、"Ubuntu24"、"Linux"
static void platform_str(char* out, int out_size) {
    bool is_wsl2 = false;
    {
        std::FILE* f = std::fopen("/proc/sys/kernel/osrelease", "r");
        if (f) {
            char buf[128] = {};
            if (std::fgets(buf, sizeof(buf), f))
                is_wsl2 = std::strstr(buf, "WSL2") || std::strstr(buf, "microsoft");
            std::fclose(f);
        }
    }

    char os_name[32] = "Linux";
    char os_ver[16]  = "";
    {
        std::FILE* f = std::fopen("/etc/os-release", "r");
        if (f) {
            char line[128];
            while (std::fgets(line, sizeof(line), f)) {
                const char* val;
                char* p;
                if (std::strncmp(line, "NAME=", 5) == 0) {
                    val = line + 5;
                    if (*val == '"') ++val;
                    p = os_name;
                    while (*val && *val != '"' && *val != '\n' &&
                           p < os_name + (int)sizeof(os_name) - 1)
                        *p++ = *val++;
                    *p = '\0';
                } else if (std::strncmp(line, "VERSION_ID=", 11) == 0) {
                    val = line + 11;
                    if (*val == '"') ++val;
                    p = os_ver;
                    // "24.04" をそのまま取得
                    while (*val && *val != '"' && *val != '\n' &&
                           p < os_ver + (int)sizeof(os_ver) - 1)
                        *p++ = *val++;
                    *p = '\0';
                }
            }
            std::fclose(f);
        }
    }

    if (is_wsl2)
        std::snprintf(out, out_size, "WSL2 %s%s", os_name, os_ver);
    else
        std::snprintf(out, out_size, "%s%s", os_name, os_ver);
}

void id_report(FILE* out) {
    char bld[11];
    date_iso(bld);
    char pf[48];
    platform_str(pf, sizeof(pf));
    fprintf(out, "ID pf=%s git=%s vl=%s bld=%s\r\n",
            pf, GIT_HASH, VERILATOR_VER, bld);
    std::fflush(out);
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

    auto* const ctx = new VerilatedContext;

    // --debug のとき +debug plusarg を追加して Verilog 側の $display/$strobe を有効化
    // ctx->commandArgs は dut 生成・eval() より前に呼ぶ必要がある
    const char* vl_argv[33];
    int vl_argc = 0;
    for (int i = 0; i < argc && vl_argc < 32; ++i) vl_argv[vl_argc++] = argv[i];
    if (debug_mode) vl_argv[vl_argc++] = "+debug";
    ctx->commandArgs(vl_argc, const_cast<char**>(vl_argv));

    auto* const dut = new Vothello_top{ctx, "othello_top"};
    apply_reset(dut);

    set_stdin_nonblocking();

    bool stdin_eof = false;
    bool eof_lf_sent = false;
    bool last_was_crlf = false;  // 最後にディスパッチされた行が CR+LF で終わったか
    int quiescent = 0;
    uint64_t cycle = 0;

    // CR+LF を流した後の「応答待ち」フラグ。tx_valid が一度立って、
    // その後 KSettleCycles cycle 連続で 0 になるまで次の RX を読まない。
    bool awaiting_response = false;
    bool seen_tx_in_response = false;
    int  tx_quiet = 0;
    constexpr int kSettleCycles = 4;

    // BM/ID コマンドインターセプト用ラインバッファ。
    // 行終端は CR+LF (etc/protocol.md)。stdin から CR+LF までを 1 行として
    // 区切り、"BM\r\n" / "ID\r\n" は DUT に渡さず C++ 側で応答する。
    // それ以外の行はバイト列をそのまま (CR+LF も含めて) DUT に流す。
    char rx_linebuf[36] = {};
    int  rx_linebuf_len = 0;
    bool rx_line_ready  = false;  // CR+LF まで揃った → リプレイ待ち
    int  rx_replay_pos  = 0;

    while (true) {
        const bool dut_ready = !awaiting_response;

        // Phase A: stdin → rx_linebuf（ライン未完成 かつ DUT 準備済み or 行途中）
        if (!rx_line_ready && !stdin_eof && (dut_ready || rx_linebuf_len > 0)) {
            uint8_t b;
            switch (read_stdin_byte(&b)) {
                case RxState::Byte:
                    if (rx_linebuf_len < 34)
                        rx_linebuf[rx_linebuf_len++] = static_cast<char>(b);
                    // CR+LF を行終端として検出
                    if (rx_linebuf_len >= 2 &&
                        rx_linebuf[rx_linebuf_len - 2] == '\r' &&
                        rx_linebuf[rx_linebuf_len - 1] == '\n') {
                        // 4 bytes ("XX\r\n") のコマンドをインターセプト
                        if (rx_linebuf_len == 4 &&
                            rx_linebuf[0] == 'B' && rx_linebuf[1] == 'M') {
                            bench_report(stdout, false);
                            rx_linebuf_len = 0;
                            last_was_crlf  = true;
                        } else if (rx_linebuf_len == 4 &&
                                   rx_linebuf[0] == 'I' && rx_linebuf[1] == 'D') {
                            id_report(stdout);
                            rx_linebuf_len = 0;
                            last_was_crlf  = true;
                        } else {
                            rx_line_ready = true;
                            rx_replay_pos = 0;
                        }
                    }
                    break;
                case RxState::Empty:
                    break;
                case RxState::Eof:
                    stdin_eof = true;
                    // バッファに残った途中行へ CR+LF を補完してキュー
                    if (rx_linebuf_len > 0) {
                        if (rx_linebuf_len < 35)
                            rx_linebuf[rx_linebuf_len++] = '\r';
                        if (rx_linebuf_len < 35)
                            rx_linebuf[rx_linebuf_len++] = '\n';
                        rx_line_ready = true;
                        rx_replay_pos = 0;
                    } else if (!last_was_crlf) {
                        rx_linebuf[0]  = '\r';
                        rx_linebuf[1]  = '\n';
                        rx_linebuf_len = 2;
                        rx_line_ready  = true;
                        rx_replay_pos  = 0;
                    }
                    break;
            }
        }

        // stdin_eof かつバッファ空 → quiescent カウント用フラグを立てる
        if (stdin_eof && !rx_line_ready && rx_linebuf_len == 0)
            eof_lf_sent = true;

        // Phase B: rx_linebuf → DUT（1 byte/cycle、DUT 準備済みのときのみ）
        if (rx_line_ready && dut_ready) {
            const uint8_t b = static_cast<uint8_t>(rx_linebuf[rx_replay_pos++]);
            dut->rx_byte  = b;
            dut->rx_valid = 1;
            // LF を流し終えた瞬間にディスパッチ確定 (LF 単独 / CR+LF どちらも)
            last_was_crlf = (b == '\n');
            if (b == '\n') {
                awaiting_response   = true;
                seen_tx_in_response = false;
                tx_quiet            = 0;
            }
            if (rx_replay_pos >= rx_linebuf_len) {
                rx_line_ready  = false;
                rx_linebuf_len = 0;
                rx_replay_pos  = 0;
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

    bench_report(stderr, true);
    delete dut;
    delete ctx;
    return 0;
}
