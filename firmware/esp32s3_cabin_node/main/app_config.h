/**
 * @file app_config.h
 * @brief Hardware pinout definitions, operating boundaries, and task priorities.
 *
 * Automotive IoT HVAC Monitoring - FHTW-AIOT Research Cluster
 */

#ifndef APP_CONFIG_H_
#define APP_CONFIG_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --- Fleet and Zone Identifiers --- */
#define SDV_CAR_ID                 "vehicle_01"
#define SDV_CABIN_ZONE             "cabin_front"
#define SDV_TOPIC_TELEMETRY        "sdv/vehicle_01/telemetry"
#define SDV_TOPIC_COMMAND          "sdv/vehicle_01/control/cmd"

/* --- GPIO Pin Assignments --- */
#define GPIO_SCD30_SDA             (8)
#define GPIO_SCD30_SCL             (9)
#define GPIO_DHT22_DATA            (4)
#define GPIO_FAN_PWM               (18)
#define GPIO_FAN_TACHOMETER        (19)
#define GPIO_WS2812B_RGB           (38)

/* --- Actuation and Timer Parameters --- */
#define FAN_PWM_FREQUENCY_HZ       (25000)   /* 25 kHz carrier frequency to avoid audible whine */
#define FAN_PWM_RESOLUTION_BITS    (10)      /* 1024 discrete duty steps */
#define FAN_DEFAULT_DUTY_PCT       (50)      /* Failsafe baseline duty cycle */
#define TACHO_PULSES_PER_REV       (2)       /* Bipolar Hall-effect sensor: 2 pulses/rev */
#define TACHO_SAMPLE_WINDOW_MS     (1000)

/* --- Control Thresholds --- */
#define CO2_THRESHOLD_NOMINAL_PPM  (800.0f)
#define CO2_THRESHOLD_HIGH_PPM     (1200.0f)
#define TEMP_THRESHOLD_COMFORT_MAX (24.0f)

/* --- FreeRTOS Task Configurations --- */
#define TASK_PRIORITY_NETWORK      (5)
#define TASK_PRIORITY_SENSORS      (4)
#define TASK_PRIORITY_ACTUATOR     (4)

#define STACK_SIZE_NETWORK         (8192)
#define STACK_SIZE_SENSORS         (4096)
#define STACK_SIZE_ACTUATOR        (2048)

#ifdef __cplusplus
}
#endif

#endif /* APP_CONFIG_H_ */
