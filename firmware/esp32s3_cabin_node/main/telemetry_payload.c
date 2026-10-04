/**
 * @file telemetry_payload.c
 * @brief Implementation of structured JSON serialization conforming to telemetry schema.
 */

#include "telemetry_payload.h"
#include <stdio.h>

int telemetry_serialize_json(const telemetry_record_t *record, char *buffer, size_t max_len)
{
    if (!record || !buffer || max_len == 0) return -1;

    char scd30_co2[16] = "null";
    char scd30_temp[16] = "null";
    char scd30_hum[16] = "null";

    if (record->scd30.is_valid) {
        snprintf(scd30_co2, sizeof(scd30_co2), "%.1f", record->scd30.co2_ppm);
        snprintf(scd30_temp, sizeof(scd30_temp), "%.2f", record->scd30.temperature_c);
        snprintf(scd30_hum, sizeof(scd30_hum), "%.1f", record->scd30.humidity_pct);
    }

    char dht22_temp[16] = "null";
    char dht22_hum[16] = "null";

    if (record->dht22.is_valid) {
        snprintf(dht22_temp, sizeof(dht22_temp), "%.2f", record->dht22.temperature_c);
        snprintf(dht22_hum, sizeof(dht22_hum), "%.1f", record->dht22.humidity_pct);
    }

    int written = snprintf(
        buffer, max_len,
        "{"
        "\"car_id\":\"%s\","
        "\"zone\":\"%s\","
        "\"timestamp_unix_s\":%u,"
        "\"scd30\":{\"co2_ppm\":%s,\"temperature_c\":%s,\"humidity_pct\":%s},"
        "\"dht22\":{\"temperature_c\":%s,\"humidity_pct\":%s},"
        "\"actuator_state\":{\"pwm_duty_pct\":%u,\"tachometer_rpm\":%u,\"carrier_freq_hz\":25000}"
        "}",
        record->car_id ? record->car_id : "vehicle_01",
        record->zone ? record->zone : "cabin_front",
        (unsigned int)record->timestamp_unix_s,
        scd30_co2, scd30_temp, scd30_hum,
        dht22_temp, dht22_hum,
        record->fan_duty_pct,
        record->fan_rpm
    );

    if (written < 0 || (size_t)written >= max_len) {
        return -1;
    }

    return written;
}
