/**
 * @file tachometer.h
 * @brief PCNT pulse counter driver calculating blower motor angular velocity (RPM).
 */

#ifndef TACHOMETER_H_
#define TACHOMETER_H_

#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialises the PCNT hardware pulse counter on specified tachometer input pin.
 */
esp_err_t tachometer_init(uint8_t gpio_pin);

/**
 * @brief Reads accumulated Hall-effect pulses and computes rotational speed in RPM.
 * @param sample_window_ms Measurement sampling window in milliseconds.
 * @param pulses_per_rev Number of pulses generated per full mechanical revolution.
 * @return Computed rotor speed in RPM.
 */
uint16_t tachometer_get_rpm(uint32_t sample_window_ms, uint8_t pulses_per_rev);

#ifdef __cplusplus
}
#endif

#endif /* TACHOMETER_H_ */
