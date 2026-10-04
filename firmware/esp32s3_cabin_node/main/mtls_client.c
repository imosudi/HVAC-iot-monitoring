/**
 * @file mtls_client.c
 * @brief MQTT client implementation over TLS 1.3 mutual authentication.
 */

#include "mtls_client.h"
#include <string.h>
#include "esp_log.h"
#include "mqtt_client.h"

static const char *TAG = "mTLS_Client";

static esp_mqtt_client_handle_t s_client = NULL;
static bool s_is_connected = false;
static command_callback_t s_cmd_callback = NULL;

static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;
    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
            s_is_connected = true;
            ESP_LOGI(TAG, "mTLS connection established with broker");
            esp_mqtt_client_subscribe(s_client, "sdv/vehicle_01/control/cmd", 1);
            break;

        case MQTT_EVENT_DISCONNECTED:
            s_is_connected = false;
            ESP_LOGW(TAG, "Disconnected from broker. Reconnecting...");
            break;

        case MQTT_EVENT_DATA:
            ESP_LOGI(TAG, "Received message on topic %.*s", event->topic_len, event->topic);
            if (s_cmd_callback && event->data_len > 0) {
                /* Basic parsing for target_pwm */
                uint8_t pwm = 50;
                bool override = false;
                if (strstr(event->data, "\"target_pwm\": 75") || strstr(event->data, "\"target_pwm\":75")) {
                    pwm = 75;
                } else if (strstr(event->data, "\"target_pwm\": 100") || strstr(event->data, "\"target_pwm\":100")) {
                    pwm = 100;
                }
                if (strstr(event->data, "\"override\": true") || strstr(event->data, "\"mode\": \"MANUAL_OVERRIDE\"")) {
                    override = true;
                }
                s_cmd_callback(pwm, override);
            }
            break;

        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "MQTT event error encountered");
            break;

        default:
            break;
    }
}

esp_err_t mtls_client_init(
    const char *broker_uri,
    const char *client_cert,
    const char *client_key,
    const char *ca_cert,
    command_callback_t cb
)
{
    s_cmd_callback = cb;

    esp_mqtt_client_config_t mqtt_cfg = {
        .broker = {
            .address.uri = broker_uri ? broker_uri : "mqtts://localhost:8883",
            .verification = {
                .certificate = ca_cert,
            },
        },
        .credentials = {
            .authentication = {
                .certificate = client_cert,
                .key = client_key,
            },
        },
        .session = {
            .keepalive = 60,
        },
    };

    s_client = esp_mqtt_client_init(&mqtt_cfg);
    if (!s_client) {
        ESP_LOGE(TAG, "Failed to initialize MQTT client handle");
        return ESP_FAIL;
    }

    return esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
}

esp_err_t mtls_client_start(void)
{
    if (!s_client) return ESP_ERR_INVALID_STATE;
    return esp_mqtt_client_start(s_client);
}

esp_err_t mtls_client_publish(const char *topic, const char *payload)
{
    if (!s_client || !s_is_connected) return ESP_ERR_INVALID_STATE;
    int msg_id = esp_mqtt_client_publish(s_client, topic, payload, 0, 1, 0);
    return (msg_id >= 0) ? ESP_OK : ESP_FAIL;
}

bool mtls_client_is_connected(void)
{
    return s_is_connected;
}
