#include <cstdio>

#include "pico/stdlib.h"

namespace {
constexpr uint32_t kBlinkIntervalMs = 500;
}

int main() {
    stdio_init_all();

    const uint led_pin = PICO_DEFAULT_LED_PIN;
    gpio_init(led_pin);
    gpio_set_dir(led_pin, GPIO_OUT);

    uint32_t tick = 0;
    while (true) {
        gpio_put(led_pin, tick & 1);
        printf("hello pico2 tick=%lu\n", static_cast<unsigned long>(tick));
        ++tick;
        sleep_ms(kBlinkIntervalMs);
    }
}
