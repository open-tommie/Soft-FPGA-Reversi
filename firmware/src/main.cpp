#include <cstdio>
#include <memory>

#include "pico/stdlib.h"

#include "stub_mutex.h"
#include "Vothello_top.h"

namespace {
constexpr uint32_t kBlinkIntervalMs = 500;

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

    uint32_t loop = 0;
    while (true) {
        gpio_put(led_pin, loop & 1);
        tick_dut(dut.get());
        printf("hello pico2 loop=%lu dut.tick=%lu\n",
               static_cast<unsigned long>(loop),
               static_cast<unsigned long>(dut->tick));
        ++loop;
        sleep_ms(kBlinkIntervalMs);
    }
}
