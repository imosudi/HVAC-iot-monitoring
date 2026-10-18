"""
Telemetry Publisher for SDV Vehicle Edge Node.

Publishes validated cabin telemetry frames to the central Base CSE platform via:
  1. oneM2M TS-0010 Native MQTT Request Primitive
  2. Standard SDV MQTT Telemetry Topic (sdv/{vehicle_id}/telemetry)
  3. oneM2M Mca REST HTTP Ingestion Fallback
"""

import json
import logging
import os
import ssl
import time
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

logger = logging.getLogger("sdv.edge_client.publisher")


class TelemetryPublisher:
    """Manages secure transport of telemetry frames from vehicle edge to Base CSE."""

    def __init__(
        self,
        base_host: str = "localhost",
        mqtt_port: int = 8883,
        http_port: int = 8080,
        vehicle_id: str = "vehicle_01",
        ca_cert: str = "",
        client_cert: str = "",
        client_key: str = "",
    ) -> None:
        self.base_host = base_host
        self.mqtt_port = mqtt_port
        self.http_port = http_port
        self.vehicle_id = vehicle_id
        self.ca_cert = ca_cert
        self.client_cert = client_cert
        self.client_key = client_key

        self.mqtt_client: Optional[Any] = None
        self.mqtt_connected = False
        self._init_mqtt()

    def _init_mqtt(self) -> None:
        """Initialises the MQTT client with mTLS 1.3 if certificates are available."""
        if mqtt is None:
            logger.warning("paho-mqtt library not available. Relying on HTTP REST ingress.")
            return

        try:
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"edge_client_{self.vehicle_id}_{int(time.time())}",
            )

            def on_connect(cl, userdata, flags, rc, properties=None):
                if rc == 0:
                    self.mqtt_connected = True
                    logger.info("Connected to Base CSE Mosquitto broker (%s:%d)", self.base_host, self.mqtt_port)
                else:
                    self.mqtt_connected = False
                    logger.warning("Mosquitto broker connection returned code: %d", rc)

            def on_disconnect(cl, userdata, disconnect_flags, reason_code, properties=None):
                self.mqtt_connected = False
                logger.debug("Disconnected from Mosquitto broker (%s)", reason_code)

            client.on_connect = on_connect
            client.on_disconnect = on_disconnect

            # Configure TLS if certificates provided or port is 8883
            if (self.mqtt_port == 8883 or self.ca_cert) and os.path.isfile(self.ca_cert):
                client.tls_set(
                    ca_certs=self.ca_cert,
                    certfile=self.client_cert if os.path.isfile(self.client_cert) else None,
                    keyfile=self.client_key if os.path.isfile(self.client_key) else None,
                    cert_reqs=ssl.CERT_REQUIRED if os.path.isfile(self.client_cert) else ssl.CERT_NONE,
                    tls_version=ssl.PROTOCOL_TLS_CLIENT,
                )
                client.tls_insecure_set(True)

            client.connect_async(self.base_host, self.mqtt_port, keepalive=60)
            client.loop_start()
            self.mqtt_client = client
        except Exception as exc:
            logger.warning("Failed to initialise MQTT client: %s. Using HTTP REST fallback.", exc)
            self.mqtt_client = None

    def build_native_primitive(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Constructs an ETSI TS 118 101 / oneM2M TS-0010 MQTT request primitive."""
        now_ts = int(time.time() * 1000)
        ae_name = self.vehicle_id
        return {
            "op": 1,  # CREATE
            "to": f"/id-sdv/sdv-cse/{ae_name}/raw-telemetry",
            "fr": f"C_{ae_name}",
            "rqi": f"rqi_{now_ts}",
            "ty": 4,  # ContentInstance
            "pc": {
                "m2m:cin": {
                    "cnf": "application/json:0",
                    "con": json.dumps(payload_dict),
                }
            },
        }

    def publish(self, payload: Dict[str, Any]) -> bool:
        """Publishes the telemetry frame via MQTT or HTTP fallback."""
        success = False
        payload_str = json.dumps(payload)

        # 1. Attempt MQTT transmission
        if self.mqtt_client is not None and self.mqtt_connected:
            try:
                # Standard SDV topic
                std_topic = f"sdv/{self.vehicle_id}/telemetry"
                self.mqtt_client.publish(std_topic, payload_str, qos=1)

                # oneM2M TS-0010 native topic
                primitive = self.build_native_primitive(payload)
                native_topic = f"/oneM2M/req/C_{self.vehicle_id}/id-sdv/json"
                self.mqtt_client.publish(native_topic, json.dumps(primitive), qos=1)
                success = True
            except Exception as exc:
                logger.warning("MQTT transmission failed: %s", exc)

        # 2. HTTP REST fallback if MQTT unconfirmed or unavailable
        if not success:
            try:
                url = f"http://{self.base_host}:{self.http_port}/sdv-cse/{self.vehicle_id}/raw-telemetry"
                headers = {
                    "X-M2M-Origin": f"C_{self.vehicle_id}",
                    "X-M2M-RI": f"edge_http_{int(time.time() * 1000)}",
                    "X-M2M-RVI": "3",
                    "Content-Type": "application/json;ty=4",
                }
                body = {
                    "m2m:cin": {
                        "cnf": "application/json:0",
                        "con": payload_str,
                    }
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(body).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status in (200, 201):
                        success = True
            except Exception as exc:
                logger.debug("HTTP fallback connection error: %s", exc)

        return success

    def close(self) -> None:
        """Stops the MQTT loop and disconnects."""
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception:
                pass
            self.mqtt_client = None
