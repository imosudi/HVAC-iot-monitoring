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
    logger.info(
        "Evaluated frame: car_id=%s, state=%s, tau_age=%.2fs, delta_t=%s",
        payload.get("car_id"), state.value, tau_age, f"{delta_t:.2f}°C" if delta_t is not None else "N/A"
    )

    # Persist record to InfluxDB with categorical metadata
    writer.write_telemetry(payload, state, tau_age, delta_t)

    return jsonify({
        "status": "PROCESSED",
        "health_state": state.value,
        "tau_age_s": tau_age,
        "delta_t_c": delta_t
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.port)
