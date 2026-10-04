/**
 * @file ws2812b_indicator.h
 * @brief Optical telemetry indicator for system state and cabin air quality.
 */

#ifndef WS2812B_INDICATOR_H_
#define WS2812B_INDICATOR_H_

#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    LED_STATE_NOMINAL_GREEN = 0,    /* CO2 <= 800 ppm, Health FRESH */
    LED_STATE_PURGE_AMBER,          /* 800 < CO2 <= 1200 ppm, Low-speed purge */
    LED_STATE_ALARM_RED,            /* CO2 > 1200 ppm, Maximum duty cycle */
    LED_STATE_OVERRIDE_BLUE,        /* Operator manual override active */
    LED_STATE_CONNECTING_CYAN       /* mTLS handshake or network negotiation */
} led_status_state_t;

/**
 * @brief Initialises the WS2812B RGB indicator on specified GPIO.
 */
esp_err_t ws2812b_init(uint8_t gpio_pin);

/**
 * @brief Sets the visual status state of the optical indicator.
 */
esp_err_t ws2812b_set_state(led_status_state_t state);

#ifdef __cplusplus
}
#endif

#endif /* WS2812B_INDICATOR_H_ */
