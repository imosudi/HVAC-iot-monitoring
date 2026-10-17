"""HTTP endpoint processing oneM2M subscription notifications for the Bridge AE."""

import json
import logging
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


@app.route("/health", methods=["GET"])
def health():
    """Service liveness probe."""
    return jsonify({"status": "UP", "service": "BridgeAE"}), 200


@app.route("/notification", methods=["POST"])
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

