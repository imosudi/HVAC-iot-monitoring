/**
 * @file scd30_driver.h
 * @brief Sensirion SCD30 optical NDIR CO2, temperature, and humidity sensor driver.
 */

#ifndef SCD30_DRIVER_H_
#define SCD30_DRIVER_H_

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float co2_ppm;
    float temperature_c;
    float humidity_pct;
    bool is_valid;
} scd30_measurement_t;

/**
 * @brief Initialises the I2C master peripheral on configured SDA and SCL GPIOs.
 * @return ESP_OK on success, or an error code on bus failure.
 */
esp_err_t scd30_init(uint8_t sda_pin, uint8_t scl_pin);

/**
 * @brief Triggers continuous measurement on the SCD30 transducer.
 * @param ambient_pressure_mbar Atmospheric pressure compensation (0 for default).
 * @return ESP_OK on success.
 */
esp_err_t scd30_start_continuous_measurement(uint16_t ambient_pressure_mbar);

/**
 * @brief Checks if fresh measurement data is ready on the transducer.
 * @param[out] ready Pointer to boolean receiving readiness state.
 * @return ESP_OK on success.
 */
esp_err_t scd30_get_data_ready_status(bool *ready);

/**
 * @brief Reads CO2, temperature, and relative humidity, validating CRC-8 checksums.
 * @param[out] measurement Pointer to structure receiving transducer readings.
 * @return ESP_OK on success, or ESP_ERR_INVALID_CRC on data corruption.
 */
esp_err_t scd30_read_measurement(scd30_measurement_t *measurement);

#ifdef __cplusplus
}
#endif

#endif /* SCD30_DRIVER_H_ */
