"""
Public-Facing Flask Web Application.

Provides the foundational HTTP interface for the Software-Defined Vehicle (SDV)
cabin monitoring and HVAC regulation system. The index view serves a clean,
blank template without UI/UX styling, reserving presentation design for the
dedicated user interface specification.

Note: In accordance with architectural constraints, this application uses direct
module-level Flask instantiation rather than an application factory pattern.
"""

import logging
from flask import Flask, jsonify, render_template

try:
    from services.web_portal.portal_config import config
except ImportError:
    try:
        from .portal_config import config
    except (ImportError, ValueError):
        from portal_config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("WebPortal")

# Direct module-level instantiation (strictly avoiding application factory pattern)
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = config.secret_key


@app.route("/", methods=["GET"])
def index():
    """Serves the initial blank index page devoid of UI/UX styling."""
    return render_template("index.html"), 200


@app.route("/health", methods=["GET"])
def health():
    """Service liveness and readiness probe."""
    return jsonify({
        "status": "UP",
        "service": "web_portal",
        "version": "1.0.0"
    }), 200


if __name__ == "__main__":
    logger.info("Starting public-facing Flask web portal on %s:%d", config.host, config.port)
    app.run(host=config.host, port=config.port, debug=config.debug)
