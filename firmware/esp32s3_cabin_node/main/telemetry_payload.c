/**
 * @file telemetry_payload.c
 * @brief Implementation of structured JSON serialization conforming to scd30_only telemetry schema.
 */

#include "telemetry_payload.h"
#include <stdio.h>

int telemetry_serialize_json(const telemetry_record_t *record, char *buffer, size_t max_len)
{
    if (!record || !buffer || max_len == 0) return -1;

    char scd30_co2[16] = "null";
    char scd30_temp[16] = "null";
    char scd30_hum[16] = "null";
    const char *alert_co2 = "false";
    const char *alert_temp = "false";
    const char *alert_hum = "false";

    if (record->scd30.is_valid) {
        snprintf(scd30_co2, sizeof(scd30_co2), "%.1f", record->scd30.co2_ppm);
        snprintf(scd30_temp, sizeof(scd30_temp), "%.2f", record->scd30.temperature_c);
        snprintf(scd30_hum, sizeof(scd30_hum), "%.1f", record->scd30.humidity_pct);
        alert_co2 = (record->scd30.co2_ppm >= 800.0f) ? "true" : "false";
        alert_temp = (record->scd30.temperature_c < 18.0f || record->scd30.temperature_c > 30.0f) ? "true" : "false";
        alert_hum = (record->scd30.humidity_pct < 30.0f || record->scd30.humidity_pct > 60.0f) ? "true" : "false";
    }

    int written = snprintf(
        buffer, max_len,
        "{"
        "\"car_id\":\"%s\","
        "\"zone\":\"%s\","
        "\"timestamp_unix_s\":%u,"
        "\"sensor_profile\":\"scd30_only\","
        "\"scd30\":{\"co2_ppm\":%s,\"temperature_c\":%s,\"humidity_pct\":%s},"
        "\"alerts\":{\"co2\":%s,\"temperature\":%s,\"humidity\":%s},"
        "\"actuator_state\":{\"pwm_duty_pct\":%u,\"tachometer_rpm\":%u,\"carrier_freq_hz\":25000}"
        "}",
        record->car_id ? record->car_id : "vehicle_01",
        record->zone ? record->zone : "cabin_front",
        (unsigned int)record->timestamp_unix_s,
        scd30_co2, scd30_temp, scd30_hum,
        alert_co2, alert_temp, alert_hum,
        record->fan_duty_pct,
        record->fan_rpm
    );

    if (written < 0 || (size_t)written >= max_len) {
        return -1;
    }

    return written;
}
