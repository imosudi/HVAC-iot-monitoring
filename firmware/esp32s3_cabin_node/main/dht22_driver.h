/**
 * @file dht22_driver.h
 * @brief DHT22 / AM2302 1-Wire capacitive humidity and temperature sensor driver.
 */

#ifndef DHT22_DRIVER_H_
#define DHT22_DRIVER_H_

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float temperature_c;
    float humidity_pct;
    bool is_valid;
} dht22_measurement_t;

/**
 * @brief Initialises the GPIO data line for DHT22 1-Wire communication.
 */
esp_err_t dht22_init(uint8_t gpio_pin);

/**
 * @brief Acquires temperature and humidity from the DHT22, validating 40-bit checksum.
 * @param[out] measurement Pointer to structure receiving readings.
 * @return ESP_OK on success, or ESP_ERR_INVALID_CRC on checksum mismatch.
 */
esp_err_t dht22_read_measurement(dht22_measurement_t *measurement);

#ifdef __cplusplus
}
#endif

#endif /* DHT22_DRIVER_H_ */
