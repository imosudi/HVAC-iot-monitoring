/**
 * @file tachometer.c
 * @brief Pulse Counter (PCNT) implementation computing blower rotor RPM.
 */

#include "tachometer.h"
#include "esp_log.h"
#include "driver/pulse_cnt.h"

static const char *TAG = "Tachometer";

static pcnt_unit_handle_t s_pcnt_unit = NULL;
static pcnt_channel_handle_t s_pcnt_chan = NULL;

esp_err_t tachometer_init(uint8_t gpio_pin)
{
    pcnt_unit_config_t unit_config = {
        .high_limit = 20000,
        .low_limit = -1,
    };
    esp_err_t err = pcnt_new_unit(&unit_config, &s_pcnt_unit);
    if (err != ESP_OK) return err;

    pcnt_chan_config_t chan_config = {
        .edge_gpio_num = gpio_pin,
        .level_gpio_num = -1,
    };
    err = pcnt_new_channel(s_pcnt_unit, &chan_config, &s_pcnt_chan);
    if (err != ESP_OK) return err;

    err = pcnt_channel_set_edge_action(s_pcnt_chan, PCNT_CHANNEL_EDGE_ACTION_INCREASE, PCNT_CHANNEL_EDGE_ACTION_HOLD);
    if (err != ESP_OK) return err;

    err = pcnt_unit_enable(s_pcnt_unit);
    if (err != ESP_OK) return err;

    err = pcnt_unit_clear_count(s_pcnt_unit);
    if (err != ESP_OK) return err;

    err = pcnt_unit_start(s_pcnt_unit);
    if (err != ESP_OK) return err;

    ESP_LOGI(TAG, "Initialised PCNT tachometer on GPIO %d", gpio_pin);
    return ESP_OK;
}

uint16_t tachometer_get_rpm(uint32_t sample_window_ms, uint8_t pulses_per_rev)
{
    if (!s_pcnt_unit || sample_window_ms == 0 || pulses_per_rev == 0) return 0;

    int pulse_count = 0;
    pcnt_unit_get_count(s_pcnt_unit, &pulse_count);
    pcnt_unit_clear_count(s_pcnt_unit);

    if (pulse_count < 0) pulse_count = 0;

    /* RPM = (pulses / (pulses_per_rev * (window_ms / 1000))) * 60 */
    float window_seconds = sample_window_ms / 1000.0f;
    float rpm_float = ((float)pulse_count / ((float)pulses_per_rev * window_seconds)) * 60.0f;

    return (uint16_t)(rpm_float + 0.5f);
}
