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

#include "stub_mutex.h"
#include "Vothello_top.h"

namespace {

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

}  // namespace

int main() {
    stdio_init_all();

    const uint led_pin = PICO_DEFAULT_LED_PIN;
    gpio_init(led_pin);
    gpio_set_dir(led_pin, GPIO_OUT);

    sleep_ms(2000);  // USB-CDC ホスト接続待ち

    auto* const ctx = new VerilatedContext;
    auto* const dut = new Vothello_top{ctx, "othello_top"};
    apply_reset(dut);

    bool led = false;
    uint32_t led_div = 0;
    while (true) {
        // RX: 1 byte 取れれば DUT に投入 (1-cycle pulse)
        const int c = getchar_timeout_us(0);
        if (c >= 0) {
            dut->rx_byte = static_cast<uint8_t>(c);
            dut->rx_valid = 1;
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
