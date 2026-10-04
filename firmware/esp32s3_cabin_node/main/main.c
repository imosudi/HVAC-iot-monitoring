/**
 * @file main.c
 * @brief Application entry point and FreeRTOS task scheduling for ESP32-S3 cabin node.
 *
 * Automotive IoT HVAC Monitoring - FHTW-AIOT Research Cluster
 */

#include <stdio.h>
#include <string.h>
#include <time.h>
#include "esp_log.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include "app_config.h"
#include "scd30_driver.h"
#include "dht22_driver.h"
#include "pwm_fan_control.h"
#include "tachometer.h"
#include "ws2812b_indicator.h"
#include "telemetry_payload.h"
#include "mtls_client.h"

static const char *TAG = "CabinNode_Main";

static QueueHandle_t s_telemetry_queue = NULL;

static void on_downlink_command(uint8_t target_pwm, bool is_override)
{
    ESP_LOGI(TAG, "Downlink command received: target_pwm=%d%%, override=%s (Modulating Blue LED Actuator)",
             target_pwm, is_override ? "YES" : "NO");

    pwm_fan_set_duty(target_pwm);
    if (target_pwm > 50) {
        gpio_set_level(GPIO_ACTUATOR_GREEN_VENT, 0);
    } else {
        gpio_set_level(GPIO_ACTUATOR_GREEN_VENT, 1);
    }

    if (is_override) {
        ws2812b_set_state(LED_STATE_OVERRIDE_BLUE);
    }
}

/**
 * @brief FreeRTOS Task pinned to Core 1: Deterministic sensor acquisition and motor control.
 */
static void sensor_acquisition_task(void *pvParameters)
{
    ESP_LOGI(TAG, "Sensor acquisition task running on Core %d", xPortGetCoreID());

    scd30_measurement_t scd30_data;
    dht22_measurement_t dht22_data;
    telemetry_record_t record;

    while (1) {
        /* 1. Sample Sensirion SCD30 */
        bool scd30_ready = false;
        scd30_get_data_ready_status(&scd30_ready);
        if (scd30_ready) {
            scd30_read_measurement(&scd30_data);
        } else {
            scd30_data.is_valid = false;
        }

        /* 2. Sample DHT22 */
        dht22_read_measurement(&dht22_data);

        /* 3. Read Actuator Feedback */
        uint16_t current_rpm = tachometer_get_rpm(TACHO_SAMPLE_WINDOW_MS, TACHO_PULSES_PER_REV);
        uint8_t current_duty = pwm_fan_get_duty();

        /* 4. Drive Coloured LED Actuators based on cabin environmental state */
        if (scd30_data.is_valid) {
            if (scd30_data.co2_ppm > CO2_THRESHOLD_HIGH_PPM) {
                ws2812b_set_state(LED_STATE_ALARM_RED);
                pwm_fan_set_duty(100);
                gpio_set_level(GPIO_ACTUATOR_GREEN_VENT, 0);
                gpio_set_level(GPIO_ACTUATOR_RED_HEAT, 0);
            } else if (scd30_data.co2_ppm > CO2_THRESHOLD_NOMINAL_PPM) {
                ws2812b_set_state(LED_STATE_PURGE_AMBER);
                pwm_fan_set_duty(75);
                gpio_set_level(GPIO_ACTUATOR_GREEN_VENT, 0);
                gpio_set_level(GPIO_ACTUATOR_RED_HEAT, 0);
            } else if (scd30_data.temperature_c < 19.0f) {
                ws2812b_set_state(LED_STATE_NOMINAL_GREEN);
                pwm_fan_set_duty(0);
                gpio_set_level(GPIO_ACTUATOR_GREEN_VENT, 0);
                gpio_set_level(GPIO_ACTUATOR_RED_HEAT, 1);
            } else {
                ws2812b_set_state(LED_STATE_NOMINAL_GREEN);
                pwm_fan_set_duty(25);
                gpio_set_level(GPIO_ACTUATOR_GREEN_VENT, 1);
                gpio_set_level(GPIO_ACTUATOR_RED_HEAT, 0);
            }
        }


        /* 5. Pack structured telemetry frame */
        record.car_id = SDV_CAR_ID;
        record.zone = SDV_CABIN_ZONE;
        record.timestamp_unix_s = (uint32_t)time(NULL);
        record.scd30 = scd30_data;
        record.dht22 = dht22_data;
        record.fan_duty_pct = current_duty;
        record.fan_rpm = current_rpm;

        if (s_telemetry_queue != NULL) {
            xQueueOverwrite(s_telemetry_queue, &record);
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

/**
 * @brief FreeRTOS Task pinned to Core 0: Cryptographic network transport.
 */
static void network_transport_task(void *pvParameters)
{
    ESP_LOGI(TAG, "Network transport task running on Core %d", xPortGetCoreID());

    telemetry_record_t record;
    char json_buffer[512];

    while (1) {
        if (xQueueReceive(s_telemetry_queue, &record, portMAX_DELAY) == pdTRUE) {
            if (telemetry_serialize_json(&record, json_buffer, sizeof(json_buffer)) > 0) {
                if (mtls_client_is_connected()) {
                    mtls_client_publish(SDV_TOPIC_TELEMETRY, json_buffer);
                } else {
                    ESP_LOGD(TAG, "Holding telemetry: mTLS connection pending...");
                }
            }
        }
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "Initialising SDV Cyber-Physical Cabin Node (ESP32-S3)...");

    /* Initialise Non-Volatile Storage (NVS) */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    /* Initialise Hardware Peripherals */
    ESP_ERROR_CHECK(ws2812b_init(GPIO_WS2812B_RGB));
    ws2812b_set_state(LED_STATE_CONNECTING_CYAN);

    /* Initialise Coloured LED Actuators (driven as physical actuators for MVP bench) */
    gpio_config_t led_actuator_cfg = {
        .pin_bit_mask = (1ULL << GPIO_ACTUATOR_RED_HEAT) | (1ULL << GPIO_ACTUATOR_GREEN_VENT),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&led_actuator_cfg);
    gpio_set_level(GPIO_ACTUATOR_GREEN_VENT, 1);
    gpio_set_level(GPIO_ACTUATOR_RED_HEAT, 0);

    /* Initialise Blue Purge LED Actuator via PWM */
    ESP_ERROR_CHECK(pwm_fan_init(GPIO_ACTUATOR_BLUE_PURGE));
    pwm_fan_set_duty(FAN_DEFAULT_DUTY_PCT);

    ESP_ERROR_CHECK(tachometer_init(GPIO_FAN_TACHOMETER));
    ESP_ERROR_CHECK(scd30_init(GPIO_SCD30_SDA, GPIO_SCD30_SCL));
    scd30_start_continuous_measurement(0);

    ESP_ERROR_CHECK(dht22_init(GPIO_DHT22_DATA));


    /* Create Telemetry Queue */
    s_telemetry_queue = xQueueCreate(1, sizeof(telemetry_record_t));

    /* Initialise mTLS Client */
    mtls_client_init("mqtts://localhost:8883", NULL, NULL, NULL, on_downlink_command);
    mtls_client_start();

    /* Spawn Core-Segregated FreeRTOS Tasks */
    xTaskCreatePinnedToCore(
        sensor_acquisition_task,
        "sensors_core1",
        STACK_SIZE_SENSORS,
        NULL,
        TASK_PRIORITY_SENSORS,
        NULL,
        1
    );

    xTaskCreatePinnedToCore(
        network_transport_task,
        "network_core0",
        STACK_SIZE_NETWORK,
        NULL,
        TASK_PRIORITY_NETWORK,
        NULL,
        0
    );

    ESP_LOGI(TAG, "All FreeRTOS subsystem tasks successfully scheduled.");
}
