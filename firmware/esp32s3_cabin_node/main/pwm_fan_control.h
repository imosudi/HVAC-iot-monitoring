/**
 * @file pwm_fan_control.h
 * @brief LEDC peripheral driver generating 25.0 kHz ultrasonic PWM fan modulation.
 */

#ifndef PWM_FAN_CONTROL_H_
#define PWM_FAN_CONTROL_H_

#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialises the LEDC timer on specified GPIO pin at 25 kHz carrier frequency.
 */
esp_err_t pwm_fan_init(uint8_t gpio_pin);

/**
 * @brief Sets centrifugal blower motor duty cycle percentage.
 * @param duty_pct Commanded duty cycle (0 to 100%).
 * @return ESP_OK on success.
 */
esp_err_t pwm_fan_set_duty(uint8_t duty_pct);

/**
 * @brief Gets the current commanded duty cycle percentage.
 */
uint8_t pwm_fan_get_duty(void);

#ifdef __cplusplus
}
#endif

#endif /* PWM_FAN_CONTROL_H_ */
