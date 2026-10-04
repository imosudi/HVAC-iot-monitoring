/**
 * @file pwm_fan_control.c
 * @brief LEDC timer configuration for 25.0 kHz carrier PWM motor control.
 */

#include "pwm_fan_control.h"
#include "esp_log.h"
#include "driver/ledc.h"

static const char *TAG = "PWM_Fan";

#define LEDC_TIMER_SPEED_MODE      LEDC_LOW_SPEED_MODE
#define LEDC_TIMER_DUTY_RES        LEDC_TIMER_10_BIT
#define LEDC_PWM_FREQ_HZ           25000
#define LEDC_CHANNEL_NUM           LEDC_CHANNEL_0

static uint8_t s_current_duty_pct = 0;

esp_err_t pwm_fan_init(uint8_t gpio_pin)
{
    ledc_timer_config_t ledc_timer = {
        .speed_mode       = LEDC_TIMER_SPEED_MODE,
        .duty_resolution  = LEDC_TIMER_DUTY_RES,
        .timer_num        = LEDC_TIMER_0,
        .freq_hz          = LEDC_PWM_FREQ_HZ,
        .clk_cfg          = LEDC_AUTO_CLK
    };
    esp_err_t err = ledc_timer_config(&ledc_timer);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure LEDC timer: %s", esp_err_to_name(err));
        return err;
    }

    ledc_channel_config_t ledc_channel = {
        .speed_mode     = LEDC_TIMER_SPEED_MODE,
        .channel        = LEDC_CHANNEL_NUM,
        .timer_sel      = LEDC_TIMER_0,
        .intr_type      = LEDC_INTR_DISABLE,
        .gpio_num       = gpio_pin,
        .duty           = 0,
        .hpoint         = 0
    };
    err = ledc_channel_config(&ledc_channel);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure LEDC channel: %s", esp_err_to_name(err));
        return err;
    }

    ESP_LOGI(TAG, "Configured 25.0 kHz PWM on GPIO %d (10-bit resolution)", gpio_pin);
    return ESP_OK;
}

esp_err_t pwm_fan_set_duty(uint8_t duty_pct)
{
    if (duty_pct > 100) duty_pct = 100;
    s_current_duty_pct = duty_pct;

    /* 10-bit: 0 to 1023 duty steps */
    uint32_t duty_val = (uint32_t)((duty_pct / 100.0f) * 1023.0f + 0.5f);

    esp_err_t err = ledc_set_duty(LEDC_TIMER_SPEED_MODE, LEDC_CHANNEL_NUM, duty_val);
    if (err != ESP_OK) return err;

    return ledc_update_duty(LEDC_TIMER_SPEED_MODE, LEDC_CHANNEL_NUM);
}

uint8_t pwm_fan_get_duty(void)
{
    return s_current_duty_pct;
}
