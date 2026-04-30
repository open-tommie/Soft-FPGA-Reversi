// firmware/src/main.cpp
//
// Pico 2 上の最薄ホスト。プロトコル FSM は rtl/proto.v 側にあるので、
// このファイルは「USB-CDC ↔ DUT バイト線」の中継しかしない。
//
// ループ単位の処理:
//   1. stdin にバイトがあれば取って rx_byte / rx_valid に乗せる
//   2. clk を 1 cycle 進める
//   3. tx_valid が立っていれば tx_byte を stdout に出す
//
// ループは ~1 µs 周期で回るので 115200 baud (= 87 µs/byte) に十分間に合う。

#include <cstdio>

#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/structs/sysinfo.h"

// リンカスクリプトが定義するシンボル（namespace の外に置かないとリンクできない）
extern "C" {
extern char __flash_binary_start;
extern char __flash_binary_end;
extern char __bss_end__;
}

#include "stub_mutex.h"
#include "Vothello_top.h"

namespace {

// eval() 実測用アキュムレータ（time_us_32 はマイクロ秒単位）
static uint32_t s_eval_us    = 0;
static uint32_t s_tick_count = 0;

void tick(Vothello_top* dut) {
    const uint32_t t0 = time_us_32();
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    s_eval_us += time_us_32() - t0;
    ++s_tick_count;
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

// ID コマンド応答: デバイス情報

void id_report() {
    constexpr uint32_t kFlashKb = PICO_FLASH_SIZE_BYTES / 1024u;
    constexpr uint32_t kRamKb   = 520u;
    const uint32_t prog_kb =
        static_cast<uint32_t>(&__flash_binary_end - &__flash_binary_start) / 1024u;
    // __bss_end__ は SRAM_BASE(0x20000000) からのオフセットで静的使用量を示す
    const uint32_t bss_kb =
        static_cast<uint32_t>(
            reinterpret_cast<uintptr_t>(&__bss_end__) - 0x20000000u) / 1024u;
    const uint32_t prog_pct = prog_kb * 100u / kFlashKb;
    const uint32_t bss_pct  = bss_kb  * 100u / kRamKb;
    const uint32_t clk_mhz  = clock_get_hz(clk_sys) / 1000000u;
    // CHIP_ID[31:28] = revision (0=B0, 1=B1, 2=B2)
    const uint32_t chip_rev = (sysinfo_hw->chip_id >> 28u) & 0xFu;
    char bld[11];
    date_iso(bld);
    printf("ID pf=" PICO_PLATFORM_STR
           " chip=B%u flash=%uKB prog=%uKB(%u%%) ram=%uKB bss=%uKB(%u%%)"
           " clk=%uMHz git=%s bld=%s\r\n",
           static_cast<unsigned>(chip_rev),
           static_cast<unsigned>(kFlashKb),
           static_cast<unsigned>(prog_kb),  static_cast<unsigned>(prog_pct),
           static_cast<unsigned>(kRamKb),
           static_cast<unsigned>(bss_kb),   static_cast<unsigned>(bss_pct),
           static_cast<unsigned>(clk_mhz),
           GIT_HASH,
           bld);
}

// BM コマンド応答: "BM clk=X.XXXMHz tick=XXXns\n"
// 浮動小数を避け整数演算のみで出力する
void bench_report_protocol() {
    if (s_tick_count == 0) {
        printf("BM no-data\r\n");
        return;
    }
    // ns_per_tick = us_total * 1000 / ticks
    const uint32_t ns_per_tick = (s_eval_us * 1000u) / s_tick_count;
    // clk_khz = 1_000_000 / ns_per_tick
    const uint32_t clk_khz = (ns_per_tick > 0u) ? (1000000u / ns_per_tick) : 0u;
    printf("BM clk=%lu.%03luMHz tick=%luns\r\n",
           (unsigned long)(clk_khz / 1000u),
           (unsigned long)(clk_khz % 1000u),
           (unsigned long)ns_per_tick);
}

void apply_reset(Vothello_top* dut) {
    dut->rst = 1;
    dut->rx_valid = 0;
    for (int i = 0; i < 4; ++i) tick(dut);
    dut->rst = 0;
}

}  // namespace

int main() {
    stdio_init_all();

    const uint led_pin = PICO_DEFAULT_LED_PIN;
    gpio_init(led_pin);
    gpio_set_dir(led_pin, GPIO_OUT);

    sleep_ms(2000);  // USB-CDC ホスト接続待ち
    while (getchar_timeout_us(0) >= 0) {}  // 接続時の余分バイトを flush

    auto* const ctx = new VerilatedContext;
    auto* const dut = new Vothello_top{ctx, "othello_top"};
    apply_reset(dut);

    // BM/ID コマンドインターセプト用ラインバッファ。
    // 行終端は LF (CR+LF / LF 単独どちらも受け付ける)。
    // "BM" / "ID" は DUT に渡さず C++ 側で応答する。
    char rx_linebuf[36] = {};
    int  rx_linebuf_len = 0;
    bool rx_line_ready  = false;
    int  rx_replay_pos  = 0;

    bool led = false;
    uint32_t led_div = 0;
    while (true) {
        // Phase A: UART → rx_linebuf（ライン未完成のときだけ読む）
        if (!rx_line_ready) {
            const int c = getchar_timeout_us(0);
            if (c >= 0) {
                if (rx_linebuf_len < 35)
                    rx_linebuf[rx_linebuf_len++] = static_cast<char>(c);
                if (c == '\n') {
                    // LF で行確定。先頭 2 文字でコマンド判定（CR は無視）
                    const char c0 = rx_linebuf[0];
                    const char c1 = (rx_linebuf_len >= 2) ? rx_linebuf[1] : 0;
                    if (c0 == 'B' && c1 == 'M') {
                        bench_report_protocol();
                        rx_linebuf_len = 0;
                    } else if (c0 == 'I' && c1 == 'D') {
                        id_report();
                        rx_linebuf_len = 0;
                    } else {
                        rx_line_ready = true;
                        rx_replay_pos = 0;
                    }
                }
            }
        }

        // Phase B: rx_linebuf → DUT（1 byte/cycle）
        if (rx_line_ready && rx_replay_pos < rx_linebuf_len) {
            dut->rx_byte  = static_cast<uint8_t>(rx_linebuf[rx_replay_pos++]);
            dut->rx_valid = 1;
            if (rx_replay_pos >= rx_linebuf_len) {
                rx_line_ready  = false;
                rx_linebuf_len = 0;
                rx_replay_pos  = 0;
            }
        } else {
            dut->rx_valid = 0;
        }

        tick(dut);

        // TX: DUT が 1 byte 出していれば stdout に流す
        if (dut->tx_valid) {
            putchar_raw(static_cast<int>(dut->tx_byte));
        }

        if ((++led_div & 0xFFFF) == 0) {
            led = !led;
            gpio_put(led_pin, led);
        }
    }
}
