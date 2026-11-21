"""
Downlink Actuation Directive Listener for Vehicle Edge Node.

Subscribes to oneM2M downlink MQTT notifications and SDV actuation command topics
(sdv/{vehicle_id}/control/cmd), validates commands against the JSON schema contract,
and forwards them to the ActuatorController.
"""

import json
import logging
import os
import ssl
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional
import urllib.error
import urllib.request

import jsonschema

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

logger = logging.getLogger("sdv.actuator.listener")


class DownlinkListener:
    """Manages subscription to downlink actuation directives."""

    def __init__(
        self,
        base_host: str = "localhost",
        mqtt_port: int = 8883,
        http_port: int = 8080,
        vehicle_id: str = "vehicle-001",
        on_command_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        ca_cert: str = "",
        client_cert: str = "",
        client_key: str = "",
    ) -> None:
        self.base_host = base_host
        self.mqtt_port = mqtt_port
        self.http_port = http_port
        self.vehicle_id = vehicle_id
        self.on_command = on_command_callback
        self.ca_cert = ca_cert
        self.client_cert = client_cert
        self.client_key = client_key

        self.mqtt_client: Optional[Any] = None
        self.schema: Dict[str, Any] = {}
        self.last_processed_ri: str = ""
        self._load_schema()
        self._init_mqtt()

    def _load_schema(self) -> None:
        """Loads the actuator_command_schema.json."""
        candidates = [
            Path("/app/schemas/actuator_command_schema.json"),
            Path(__file__).resolve().parent.parent / "schemas" / "actuator_command_schema.json",
            Path(__file__).resolve().parent.parent.parent.parent / "docs" / "schemas" / "actuator_command_schema.json",
        ]
        for p in candidates:
            if p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        self.schema = json.load(f)
                    logger.info("Loaded actuator schema contract from %s", p)
                    return
                except Exception as exc:
                    logger.warning("Error loading schema %s: %s", p, exc)
        logger.warning("Actuator command schema not found. Permissive validation will be used.")

    def _init_mqtt(self) -> None:
        """Connects to Mosquitto and subscribes to actuation topics."""
        if mqtt is None:
            logger.warning("paho-mqtt unavailable. Actuator listener will rely on oneM2M REST polling.")
            return

        try:
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"actuator_listener_{self.vehicle_id}_{int(time.time())}",
            )

            def on_connect(cl, userdata, flags, rc, properties=None):
                if rc == 0:
                    logger.info("Actuator listener connected to Mosquitto (%s:%d)", self.base_host, self.mqtt_port)
                    # 1. SDV direct downlink topic
                    std_topic = f"sdv/{self.vehicle_id}/control/cmd"
                    cl.subscribe(std_topic, qos=1)
                    # 2. oneM2M TS-0010 notification request topic
                    m2m_topic = f"/oneM2M/req/+/id-sdv/json"
                    cl.subscribe(m2m_topic, qos=1)
                    logger.info("Subscribed to actuation topics: '%s' and '%s'", std_topic, m2m_topic)
                else:
                    logger.warning("Mosquitto broker connection returned code: %d", rc)

            def on_message(cl, userdata, msg):
                try:
                    raw_payload = msg.payload.decode("utf-8")
                    self._process_raw_payload(raw_payload)
                except Exception as exc:
                    logger.warning("Failed to decode downlink payload: %s", exc)

            client.on_connect = on_connect
            client.on_message = on_message

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
            logger.warning("Failed to start MQTT downlink subscriber: %s", exc)

    def _process_raw_payload(self, raw_str: str) -> None:
        """Parses standard JSON or oneM2M notification primitive."""
        try:
            data = json.loads(raw_str)
        except Exception:
            return

        cmd_dict = None
        # Check if oneM2M TS-0010 notification primitive
        if "pc" in data and "m2m:sgn" in data["pc"]:
            sgn = data["pc"]["m2m:sgn"]
            rep = sgn.get("nev", {}).get("rep", {})
            cin = rep.get("m2m:cin", {})
            con = cin.get("con", "")
            if isinstance(con, str):
                try:
                    cmd_dict = json.loads(con)
                except Exception:
                    cmd_dict = None
            elif isinstance(con, dict):
                cmd_dict = con
        elif "target_pwm" in data or "target_fan_pwm" in data:
            cmd_dict = data

        if cmd_dict and self.on_command:
            # Validate against schema if available
            if self.schema:
                try:
                    jsonschema.validate(instance=cmd_dict, schema=self.schema)
                except jsonschema.ValidationError as err:
                    logger.warning("Downlink actuation command schema violation: %s", err.message)
            self.on_command(cmd_dict)

    def poll_onem2m_commands(self) -> None:
        """Polls the Base CSE commands container for latest ContentInstance (<m2m:cin>)."""
        try:
            url = f"http://{self.base_host}:{self.http_port}/sdv-cse/{self.vehicle_id}/commands/la"
            headers = {
                "X-M2M-Origin": f"C_{self.vehicle_id}",
                "X-M2M-RI": f"act_poll_{int(time.time() * 1000)}",
                "X-M2M-RVI": "3",
            }
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    cin = body.get("m2m:cin", {})
                    ri = cin.get("ri", "")
                    if ri and ri != self.last_processed_ri:
                        self.last_processed_ri = ri
                        con = cin.get("con", "")
                        if isinstance(con, str):
                            try:
                                cmd = json.loads(con)
                                if self.on_command and ("target_pwm" in cmd or "target_fan_pwm" in cmd):
                                    self.on_command(cmd)
                            except Exception:
                                pass
        except Exception:
            pass

    def close(self) -> None:
        """Disconnects the MQTT client."""
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception:
                pass
            self.mqtt_client = None
