/**
 * @file mtls_client.h
 * @brief Mutual TLS 1.3 MQTT client interface for telemetry egress and command ingress.
 */

#ifndef MTLS_CLIENT_H_
#define MTLS_CLIENT_H_

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*command_callback_t)(uint8_t target_pwm, bool is_override);

/**
 * @brief Initialises the mTLS MQTT client with X.509 certificate credentials.
 * @param broker_uri MQTT URI (e.g., "mqtts://mosquitto.sdv.local:8883").
 * @param client_cert Pointer to PEM client certificate string.
 * @param client_key Pointer to PEM client private key string.
 * @param ca_cert Pointer to PEM Root CA certificate string.
 * @param cb Callback invoked when a downlink command is received.
 */
esp_err_t mtls_client_init(
    const char *broker_uri,
    const char *client_cert,
    const char *client_key,
    const char *ca_cert,
    command_callback_t cb
);

/**
 * @brief Starts the MQTT client network task.
 */
esp_err_t mtls_client_start(void);

/**
 * @brief Publishes telemetry payload string to configured vehicle topic.
 * @param topic MQTT publication topic.
 * @param payload JSON formatted telemetry string.
 * @return ESP_OK on success.
 */
esp_err_t mtls_client_publish(const char *topic, const char *payload);

/**
 * @brief Returns current broker connection status.
 */
bool mtls_client_is_connected(void);

#ifdef __cplusplus
}
#endif

#endif /* MTLS_CLIENT_H_ */
