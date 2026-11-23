"""HTTP endpoint processing oneM2M subscription notifications for the Bridge AE."""

import json
import logging
import time
import urllib.request
from typing import Any, Dict, Tuple
from flask import Flask, jsonify, request

try:
    from .config import config
    from .health_classifier import HealthClassifier
    from .influx_writer import InfluxWriter
except (ImportError, ValueError):
    from config import config
    from health_classifier import HealthClassifier
    from influx_writer import InfluxWriter


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("BridgeAE")

app = Flask(__name__)
classifier = HealthClassifier(
    max_latency_s=config.max_latency_s,
    max_stale_s=config.max_stale_s,
    max_delta_t_c=config.max_delta_t_c
)
writer = InfluxWriter()
_last_dispatched: Dict[str, Tuple[Tuple[Any, ...], float]] = {}


def _evaluate_and_dispatch_hvac(car_id: str, payload: Dict[str, Any]) -> None:
    """Evaluates SCD30 thresholds and dispatches <m2m:cin> directives to oneM2M commands."""
    if not config.closed_loop_enabled:
        return
    scd30 = payload.get("scd30")
    if not isinstance(scd30, dict):
        return

    co2 = scd30.get("co2_ppm")
    temp = scd30.get("temperature_c")
    rh = scd30.get("humidity_pct")
    if co2 is None or temp is None or rh is None:
        return

    prev = _last_dispatched.get(car_id)
    prev_actions = prev[0] if prev else None

    target_pwm = 25
    fan_on = True
    if co2 >= 1500:
        target_pwm = 100
    elif co2 >= 1000:
        target_pwm = 75
    elif co2 >= 800 or (prev_actions and prev_actions[0] >= 50 and co2 >= 750):
        target_pwm = 50
    elif temp < 19.0:
        target_pwm = 0
        fan_on = False

    actions = {
        "fan": fan_on,
        "ac": bool(temp > 30.0 or (prev_actions and prev_actions[2] and temp >= 29.5)),
        "heater": bool(temp < 18.0 or (prev_actions and prev_actions[3] and temp <= 18.5)),
        "humidifier": bool(rh < 30.0 or (prev_actions and prev_actions[4] and rh <= 32.0)),
        "dehumidifier": bool(rh > 60.0 or (prev_actions and prev_actions[5] and rh >= 58.0)),
    }

    state_key = (target_pwm, actions["fan"], actions["ac"], actions["heater"], actions["humidifier"], actions["dehumidifier"])
    now = time.time()
    if prev and prev[0] == state_key and (now - prev[1]) < config.closed_loop_refresh_s:
        return

    ae_id = car_id.replace("_", "-") if car_id.startswith("vehicle_") else car_id
    cmd_payload = {
        "target_pwm": target_pwm,
        "mode": "AUTOMATIC",
        "timestamp_unix_s": int(now),
        "source_entity": "BridgeAE_ClosedLoop",
        "actions": actions,
    }
    body = {"m2m:cin": {"cnf": "application/json:0", "con": json.dumps(cmd_payload)}}
    url = f"{config.onem2m_cse_url.rstrip('/')}/{ae_id}/commands"
    headers = {
        "X-M2M-Origin": config.onem2m_admin_origin,
        "X-M2M-RI": f"bridge_cmd_{int(now * 1000)}",
        "X-M2M-RVI": "3",
        "Content-Type": "application/json;ty=4",
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status in (200, 201):
                _last_dispatched[car_id] = (state_key, now)
                logger.info("Closed-loop directive dispatched -> %s: PWM=%d%% actions=%s", ae_id, target_pwm, actions)
    except Exception as exc:
        logger.debug("Closed-loop dispatch skipped (%s): %s", url, exc)


@app.route("/health", methods=["GET"])
def health():
    """Service liveness probe."""
    return jsonify({"status": "UP", "service": "BridgeAE"}), 200


@app.route("/notification", methods=["POST"])
@app.route("/fleet-ingest", methods=["POST"])
def process_notification():
    """
    Receives oneM2M notification primitive triggered by new ContentInstance.
    ETSI TS 118 101 event notification handler.
    """
    try:
        body = request.get_json(force=True)
    except Exception as exc:
        logger.warning("Malformed notification payload: %s", exc)
        return jsonify({"error": "Invalid JSON"}), 400

    # Extract ContentInstance representation (m2m:sgn -> nev -> rep -> m2m:cin)
    cin_data = None
    if isinstance(body, dict):
        sgn = body.get("m2m:sgn", body)
        nev = sgn.get("nev", {})
        rep = nev.get("rep", {})
        cin_data = rep.get("m2m:cin", rep)

    if not cin_data:
        logger.debug("Received verification or empty subscription trigger.")
        return jsonify({"status": "ACK"}), 200

    con_str = cin_data.get("con")
    if not con_str:
        logger.warning("Empty content field in ContentInstance.")
        return jsonify({"error": "Missing content"}), 400

    # Parse inner telemetry JSON payload
    try:
        if isinstance(con_str, str):
            payload = json.loads(con_str)
        else:
            payload = con_str
    except Exception as exc:
        logger.error("Failed to parse telemetry JSON from content instance: %s", exc)
        return jsonify({"error": "Corrupt content string"}), 400

    # Evaluate algorithmic data health state
    state, tau_age, delta_t = classifier.evaluate_frame(payload)
    car_id = payload.get("car_id") or payload.get("vehicle_id") or "vehicle_01"

    # Compute mathematical derivative (dT_cabin/dt - dT_ext/dt)
    scd30 = payload.get("scd30", {})
    t_cabin = scd30.get("temperature_c") if isinstance(scd30, dict) else None
    sample_time = payload.get("timestamp_unix_s")
    ext = payload.get("exterior", {}) if isinstance(payload.get("exterior"), dict) else {}
    t_ext = ext.get("temperature_c")

    dt_cabin, dt_diff = (None, None)
    if t_cabin is not None and sample_time is not None:
        dt_cabin, dt_diff = classifier.compute_thermal_derivative(
            car_id=car_id,
            current_temp_c=float(t_cabin),
            timestamp_unix_s=float(sample_time),
            ext_temp_c=float(t_ext) if t_ext is not None else None
        )

    logger.info(
        "Evaluated frame: car_id=%s, state=%s, tau_age=%.2fs, delta_t=%s, dT/dt=%s",
        car_id, state.value, tau_age,
        f"{delta_t:.2f}°C" if delta_t is not None else "N/A",
        f"{dt_cabin:.4f}°C/s" if dt_cabin is not None else "N/A"
    )

    # Persist record to InfluxDB with categorical metadata and mathematical derivatives
    writer.write_telemetry(
        payload, state, tau_age, delta_t,
        dt_derivative=dt_cabin,
        dt_diff_derivative=dt_diff
    )
    _evaluate_and_dispatch_hvac(car_id, payload)

    return jsonify({
        "status": "PROCESSED",
        "health_state": state.value,
        "tau_age_s": tau_age,
        "delta_t_c": delta_t,
        "dt_cabin_derivative": dt_cabin,
        "dt_diff_derivative": dt_diff
    }), 200


@app.route("/emergency-monitor", methods=["POST"])
def process_emergency_monitor():
    """
    Receives oneM2M subscription notifications for emergency threshold events (e.g. toxic CO elevation).
    """
    try:
        body = request.get_json(force=True)
    except Exception as exc:
        logger.warning("Malformed emergency notification payload: %s", exc)
        return jsonify({"error": "Invalid JSON"}), 400

    cin_data = None
    if isinstance(body, dict):
        sgn = body.get("m2m:sgn", body)
        nev = sgn.get("nev", {})
        rep = nev.get("rep", {})
        cin_data = rep.get("m2m:cin", rep)

    if not cin_data:
        logger.debug("Received verification or empty subscription trigger on emergency monitor.")
        return jsonify({"status": "ACK"}), 200

    con_str = cin_data.get("con")
    try:
        payload = json.loads(con_str) if isinstance(con_str, str) else con_str
    except Exception:
        payload = {"raw": con_str}

    logger.critical("EMERGENCY MONITOR EVENT DETECTED: %s", json.dumps(payload))
    return jsonify({"status": "EMERGENCY_ACKNOWLEDGED"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.port)

