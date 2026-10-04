/**
 * @file scd30_driver.c
 * @brief Sensirion SCD30 I2C driver implementation with CRC-8 validation.
 */

#include "scd30_driver.h"
#include <string.h>
#include "esp_log.h"
#include "driver/i2c.h"

static const char *TAG = "SCD30";

#define I2C_MASTER_NUM             I2C_NUM_0
#define I2C_MASTER_FREQ_HZ         400000
#define I2C_MASTER_TIMEOUT_MS      100

#define SCD30_I2C_ADDR             0x61
#define SCD30_CMD_START_CONT_MEAS  0x0010
#define SCD30_CMD_GET_DATA_READY   0x0202
#define SCD30_CMD_READ_MEASUREMENT 0x0300

#define CRC8_POLYNOMIAL            0x31
#define CRC8_INIT                  0xFF

static uint8_t scd30_compute_crc(const uint8_t *data, size_t count)
{
    uint8_t crc = CRC8_INIT;
    for (size_t i = 0; i < count; i++) {
        crc ^= data[i];
        for (uint8_t bit = 8; bit > 0; --bit) {
            if (crc & 0x80) {
                crc = (crc << 1) ^ CRC8_POLYNOMIAL;
            } else {
                crc = (crc << 1);
            }
        }
    }
    return crc;
}

esp_err_t scd30_init(uint8_t sda_pin, uint8_t scl_pin)
{
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = sda_pin,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_io_num = scl_pin,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = I2C_MASTER_FREQ_HZ,
    };
    esp_err_t err = i2c_param_config(I2C_MASTER_NUM, &conf);
    if (err != ESP_OK) return err;
    return i2c_driver_install(I2C_MASTER_NUM, conf.mode, 0, 0, 0);
}

esp_err_t scd30_start_continuous_measurement(uint16_t ambient_pressure_mbar)
{
    uint8_t cmd[5];
    cmd[0] = (uint8_t)(SCD30_CMD_START_CONT_MEAS >> 8);
    cmd[1] = (uint8_t)(SCD30_CMD_START_CONT_MEAS & 0xFF);
    cmd[2] = (uint8_t)(ambient_pressure_mbar >> 8);
    cmd[3] = (uint8_t)(ambient_pressure_mbar & 0xFF);
    cmd[4] = scd30_compute_crc(&cmd[2], 2);

    return i2c_master_write_to_device(I2C_MASTER_NUM, SCD30_I2C_ADDR, cmd, sizeof(cmd), pdMS_TO_TICKS(I2C_MASTER_TIMEOUT_MS));
}

esp_err_t scd30_get_data_ready_status(bool *ready)
{
    uint8_t cmd[2] = {
        (uint8_t)(SCD30_CMD_GET_DATA_READY >> 8),
        (uint8_t)(SCD30_CMD_GET_DATA_READY & 0xFF)
    };
    esp_err_t err = i2c_master_write_to_device(I2C_MASTER_NUM, SCD30_I2C_ADDR, cmd, sizeof(cmd), pdMS_TO_TICKS(I2C_MASTER_TIMEOUT_MS));
    if (err != ESP_OK) return err;

    uint8_t rx[3];
    err = i2c_master_read_from_device(I2C_MASTER_NUM, SCD30_I2C_ADDR, rx, sizeof(rx), pdMS_TO_TICKS(I2C_MASTER_TIMEOUT_MS));
    if (err != ESP_OK) return err;

    if (scd30_compute_crc(rx, 2) != rx[2]) {
        ESP_LOGE(TAG, "Data-ready status CRC error");
        return ESP_ERR_INVALID_CRC;
    }

    uint16_t status = ((uint16_t)rx[0] << 8) | rx[1];
    *ready = (status == 1);
    return ESP_OK;
}

esp_err_t scd30_read_measurement(scd30_measurement_t *measurement)
{
    if (!measurement) return ESP_ERR_INVALID_ARG;
    measurement->is_valid = false;

    uint8_t cmd[2] = {
        (uint8_t)(SCD30_CMD_READ_MEASUREMENT >> 8),
        (uint8_t)(SCD30_CMD_READ_MEASUREMENT & 0xFF)
    };
    esp_err_t err = i2c_master_write_to_device(I2C_MASTER_NUM, SCD30_I2C_ADDR, cmd, sizeof(cmd), pdMS_TO_TICKS(I2C_MASTER_TIMEOUT_MS));
    if (err != ESP_OK) return err;

    uint8_t rx[18];
    err = i2c_master_read_from_device(I2C_MASTER_NUM, SCD30_I2C_ADDR, rx, sizeof(rx), pdMS_TO_TICKS(I2C_MASTER_TIMEOUT_MS));
    if (err != ESP_OK) return err;

    /* Validate CRCs across 6 two-byte words */
    for (int i = 0; i < 6; i++) {
        if (scd30_compute_crc(&rx[i * 3], 2) != rx[i * 3 + 2]) {
            ESP_LOGE(TAG, "CRC-8 error on word index %d", i);
            return ESP_ERR_INVALID_CRC;
        }
    }

    /* Convert big-endian IEEE-754 floating point observations */
    uint32_t co2_raw = ((uint32_t)rx[0] << 24) | ((uint32_t)rx[1] << 16) | ((uint32_t)rx[3] << 8) | (uint32_t)rx[4];
    uint32_t temp_raw = ((uint32_t)rx[6] << 24) | ((uint32_t)rx[7] << 16) | ((uint32_t)rx[9] << 8) | (uint32_t)rx[10];
    uint32_t hum_raw = ((uint32_t)rx[12] << 24) | ((uint32_t)rx[13] << 16) | ((uint32_t)rx[15] << 8) | (uint32_t)rx[16];

    memcpy(&measurement->co2_ppm, &co2_raw, sizeof(float));
    memcpy(&measurement->temperature_c, &temp_raw, sizeof(float));
    memcpy(&measurement->humidity_pct, &hum_raw, sizeof(float));
    measurement->is_valid = true;

    return ESP_OK;
}
