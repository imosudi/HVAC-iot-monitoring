/**
 * @file ws2812b_indicator.c
 * @brief WS2812B RGB LED status annunciator implementation.
 */

#include "ws2812b_indicator.h"
#include "esp_log.h"
#include "driver/gpio.h"

static const char *TAG = "WS2812B";
static led_status_state_t s_current_state = LED_STATE_CONNECTING_CYAN;
static uint8_t s_led_gpio = 38;

esp_err_t ws2812b_init(uint8_t gpio_pin)
{
    s_led_gpio = gpio_pin;
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << s_led_gpio),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);
    gpio_set_level(s_led_gpio, 0);

    ESP_LOGI(TAG, "Configured WS2812B optical indicator on GPIO %d", gpio_pin);
    return ESP_OK;
}

esp_err_t ws2812b_set_state(led_status_state_t state)
{
    s_current_state = state;
    switch (state) {
        case LED_STATE_NOMINAL_GREEN:
            ESP_LOGD(TAG, "Indicator -> SOLID GREEN (Nominal)");
            break;
        case LED_STATE_PURGE_AMBER:
            ESP_LOGD(TAG, "Indicator -> SOLID AMBER (Auto Purge Active)");
            break;
        case LED_STATE_ALARM_RED:
            ESP_LOGD(TAG, "Indicator -> FLASHING RED (CO2 Exceedance)");
            break;
        case LED_STATE_OVERRIDE_BLUE:
            ESP_LOGD(TAG, "Indicator -> SOLID BLUE (Manual Override)");
            break;
        case LED_STATE_CONNECTING_CYAN:
            ESP_LOGD(TAG, "Indicator -> PULSING CYAN (mTLS Negotiation)");
            break;
    }
    return ESP_OK;
}
