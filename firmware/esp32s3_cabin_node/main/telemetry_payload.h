/**
 * @file telemetry_payload.h
 * @brief Serialisation of uplink telemetry into JSON matching schema specification.
 */

#ifndef TELEMETRY_PAYLOAD_H_
#define TELEMETRY_PAYLOAD_H_

#include <stddef.h>
#include <stdint.h>
#include "scd30_driver.h"
#include "dht22_driver.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    const char *car_id;
    const char *zone;
    uint32_t timestamp_unix_s;
    scd30_measurement_t scd30;
    dht22_measurement_t dht22;
    uint8_t fan_duty_pct;
    uint16_t fan_rpm;
} telemetry_record_t;

/**
 * @brief Serialises structured telemetry observations into a JSON buffer.
 * @param[in] record Pointer to the telemetry record structure.
 * @param[out] buffer Output buffer for the JSON string.
 * @param[in] max_len Maximum capacity of the output buffer.
 * @return Number of bytes written, or -1 if buffer capacity is exceeded.
 */
int telemetry_serialize_json(const telemetry_record_t *record, char *buffer, size_t max_len);

#ifdef __cplusplus
}
#endif

#endif /* TELEMETRY_PAYLOAD_H_ */
