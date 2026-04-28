#include <cstdio>
#include <memory>

#include "pico/stdlib.h"

#include "stub_mutex.h"
#include "Vothello_top.h"
#include "proto.h"

namespace {

void emit_line(const char* line, std::size_t len) {
    // stdio_usb / stdio_uart どちらにも出る。CR は付けない (LF のみ)。
    fwrite(line, 1, len, stdout);
    fputc('\n', stdout);
    fflush(stdout);
}

void tick_dut(Vothello_top* dut) {
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
}

}  // namespace

int main() {
    stdio_init_all();

    const uint led_pin = PICO_DEFAULT_LED_PIN;
    gpio_init(led_pin);
    gpio_set_dir(led_pin, GPIO_OUT);

    sleep_ms(2000);  // USB-CDC ホスト接続待ち

    const std::unique_ptr<VerilatedContext> ctx{new VerilatedContext};
    const std::unique_ptr<Vothello_top> dut{new Vothello_top{ctx.get(), "othello_top"}};

    dut->rst = 1;
    tick_dut(dut.get());
    tick_dut(dut.get());
    dut->rst = 0;

    sfr::proto::Parser parser{emit_line};

    bool led = false;
    while (true) {
        // 受信: 非ブロッキングで取れるだけ取る
        int c;
        while ((c = getchar_timeout_us(0)) >= 0) {
            parser.feed_byte(static_cast<uint8_t>(c));
        }

        // DUT を 1 cycle 進める (旧スケッチの動作維持)
        tick_dut(dut.get());

        led = !led;
        gpio_put(led_pin, led);
        sleep_ms(50);
    }
}
