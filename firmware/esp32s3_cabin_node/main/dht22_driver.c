/**
 * @file dht22_driver.c
 * @brief DHT22 1-Wire communication driver with microsecond bit timing.
 */

#include "dht22_driver.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "rom/ets_sys.h"
#include "driver/gpio.h"

static const char *TAG = "DHT22";
static uint8_t s_dht_gpio = 4;

esp_err_t dht22_init(uint8_t gpio_pin)
{
    s_dht_gpio = gpio_pin;
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << s_dht_gpio),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    return gpio_config(&io_conf);
}

esp_err_t dht22_read_measurement(dht22_measurement_t *measurement)
{
    if (!measurement) return ESP_ERR_INVALID_ARG;
    measurement->is_valid = false;

    uint8_t data[5] = {0};

    /* Send start signal: pull low for at least 18 ms */
    gpio_set_direction(s_dht_gpio, GPIO_MODE_OUTPUT);
    gpio_set_level(s_dht_gpio, 0);
    ets_delay_us(20000);

    /* Release line and switch to input with pull-up */
    gpio_set_level(s_dht_gpio, 1);
    ets_delay_us(30);
    gpio_set_direction(s_dht_gpio, GPIO_MODE_INPUT);

    /* Wait for response from sensor: 80us low followed by 80us high */
    int timeout = 0;
    while (gpio_get_level(s_dht_gpio) == 1) {
        if (++timeout > 100) return ESP_ERR_TIMEOUT;
        ets_delay_us(1);
    }

    timeout = 0;
    while (gpio_get_level(s_dht_gpio) == 0) {
        if (++timeout > 100) return ESP_ERR_TIMEOUT;
        ets_delay_us(1);
    }

    timeout = 0;
    while (gpio_get_level(s_dht_gpio) == 1) {
        if (++timeout > 100) return ESP_ERR_TIMEOUT;
        ets_delay_us(1);
    }

    /* Read 40 data bits */
    for (int bit = 0; bit < 40; bit++) {
        timeout = 0;
        while (gpio_get_level(s_dht_gpio) == 0) {
            if (++timeout > 100) return ESP_ERR_TIMEOUT;
            ets_delay_us(1);
        }

        int duration_us = 0;
        while (gpio_get_level(s_dht_gpio) == 1) {
            duration_us++;
            if (duration_us > 100) return ESP_ERR_TIMEOUT;
            ets_delay_us(1);
        }

        /* 26-28us = bit '0', 70us = bit '1' */
        if (duration_us > 40) {
            data[bit / 8] |= (1 << (7 - (bit % 8)));
        }
    }

    /* Validate 8-bit checksum: sum of first 4 bytes */
    uint8_t checksum = data[0] + data[1] + data[2] + data[3];
    if (checksum != data[4]) {
        ESP_LOGE(TAG, "Checksum mismatch: calculated 0x%02X, received 0x%02X", checksum, data[4]);
        return ESP_ERR_INVALID_CRC;
    }

    int16_t raw_hum = ((int16_t)data[0] << 8) | data[1];
    int16_t raw_temp = (((int16_t)data[2] & 0x7F) << 8) | data[3];
    if (data[2] & 0x80) {
        raw_temp = -raw_temp;
    }

    measurement->humidity_pct = raw_hum / 10.0f;
    measurement->temperature_c = raw_temp / 10.0f;
    measurement->is_valid = true;

    return ESP_OK;
}
