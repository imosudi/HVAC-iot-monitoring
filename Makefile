# ------------------------------------------------------------------------------
# Software-Defined Vehicle (SDV) Automotive IoT HVAC Monitoring
# Master Automation and Build Pipeline
# ------------------------------------------------------------------------------

VENV ?= .venv
PYTHON ?= $(shell if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo python3; fi)
PYTEST ?= $(shell if [ -f $(VENV)/bin/pytest ]; then echo $(VENV)/bin/pytest; elif [ -f $(VENV)/bin/py.test ]; then echo $(VENV)/bin/py.test; else echo pytest; fi)

.PHONY: help setup-prerequisites setup-venv setup-pki deploy-gateway stop-gateway init-onem2m test test-unit test-integration run-web simulate-telemetry simulate-telemetry-native simulate-telemetry-legacy inject-faults clean

help:
	@echo "Available build and orchestration targets:"
	@echo "  setup-prerequisites       Install Docker/Podman and system dependencies on Ubuntu Server"
	@echo "  setup-venv                Initialise Python virtual environment and simulation dependencies"
	@echo "  setup-pki                 Generate X.509 Root CA, broker, and client certificates"
	@echo "  deploy-gateway            Launch the onboard vehicular MEC container mesh"
	@echo "  stop-gateway              Halt all MEC container services"
	@echo "  init-onem2m               Initialise the /sdv-cse semantic resource tree"
	@echo "  run-web                   Launch the public-facing Flask web application locally"
	@echo "  test                      Execute all unit and integration tests"
	@echo "  test-unit                 Execute unit tests only"
	@echo "  test-integration          Execute integration tests only"
	@echo "  simulate-telemetry        Stream synthetic sensor frames via native oneM2M TS-0010 route"
	@echo "  simulate-telemetry-legacy Stream synthetic sensor frames via legacy Node-RED route"
	@echo "  inject-faults             Run the adversarial fault-injection test suite"
	@echo "  clean                     Remove temporary test caches and logs"

setup-prerequisites:
	@echo "Verifying and installing system prerequisites on Ubuntu Server..."
	@bash scripts/setup/install_ubuntu_prerequisites.sh

setup-venv:
	@echo "Configuring Python virtual environment in $(VENV)..."
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(VENV)/bin/pip install --upgrade pip
	@$(VENV)/bin/pip install -r requirements-dev.txt
	@echo "Python virtual environment configured successfully at $(VENV)."

setup-pki:
	@echo "Generating X.509 certificate infrastructure..."
	@bash scripts/pki/generate_certs.sh

deploy-gateway:
	@echo "Starting vehicular MEC gateway container mesh..."
	@bash deploy/deploy_gateway.sh

stop-gateway:
	@echo "Stopping vehicular MEC gateway container mesh..."
	@cd deploy && docker compose down

init-onem2m:
	@echo "Provisioning oneM2M /sdv-cse resource hierarchy..."
	@bash scripts/onem2m/init_tree.sh

run-web:
	@echo "Starting public-facing Web portal..."
	@$$(if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo $(PYTHON); fi) services/web_portal/app.py

test:
	@if [ ! -f $(VENV)/bin/pytest ] && [ ! -f $(VENV)/bin/py.test ] && ! pytest --version >/dev/null 2>&1; then \
		echo "Pytest not found in active environment. Initialising $(VENV)..."; \
		$(MAKE) setup-venv; \
	fi
	@echo "Executing complete test suite (Tier 1 & Tier 2)..."
	@$$(if [ -f $(VENV)/bin/pytest ]; then echo $(VENV)/bin/pytest; elif [ -f $(VENV)/bin/py.test ]; then echo $(VENV)/bin/py.test; else echo $(PYTEST); fi) -v

test-unit:
	@if [ ! -f $(VENV)/bin/pytest ] && [ ! -f $(VENV)/bin/py.test ] && ! pytest --version >/dev/null 2>&1; then \
		echo "Pytest not found in active environment. Initialising $(VENV)..."; \
		$(MAKE) setup-venv; \
	fi
	@echo "Executing unit tests (Tier 1)..."
	@$$(if [ -f $(VENV)/bin/pytest ]; then echo $(VENV)/bin/pytest; elif [ -f $(VENV)/bin/py.test ]; then echo $(VENV)/bin/py.test; else echo $(PYTEST); fi) -v tests/unit/

test-integration:
	@if [ ! -f $(VENV)/bin/pytest ] && [ ! -f $(VENV)/bin/py.test ] && ! pytest --version >/dev/null 2>&1; then \
		echo "Pytest not found in active environment. Initialising $(VENV)..."; \
		$(MAKE) setup-venv; \
	fi
	@echo "Executing integration tests (Tier 2)..."
	@$$(if [ -f $(VENV)/bin/pytest ]; then echo $(VENV)/bin/pytest; elif [ -f $(VENV)/bin/py.test ]; then echo $(VENV)/bin/py.test; else echo $(PYTEST); fi) -v tests/integration/

simulate-telemetry:
	@if [ ! -f $(VENV)/bin/python ] && [ ! -f $(VENV)/bin/python3 ] && ! $(PYTHON) -c "import paho.mqtt.client" >/dev/null 2>&1; then \
		echo "Python virtual environment or 'paho-mqtt' package missing. Initialising $(VENV)..."; \
		$(MAKE) setup-venv; \
	fi
	@echo "Streaming synthetic vehicular telemetry via native oneM2M TS-0010 route..."
	@$$(if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo $(PYTHON); fi) scripts/testing/simulate_telemetry.py \
		--host localhost \
		--port 8883 \
		--ca-cert deploy/mosquitto/certs/ca.crt \
		--client-cert deploy/mosquitto/certs/client_esp32.crt \
		--client-key deploy/mosquitto/certs/client_esp32.key \
		--route native \
		--mode normal \
		$(ARGS)

simulate-telemetry-native: simulate-telemetry

simulate-telemetry-legacy:
	@if [ ! -f $(VENV)/bin/python ] && [ ! -f $(VENV)/bin/python3 ] && ! $(PYTHON) -c "import paho.mqtt.client" >/dev/null 2>&1; then \
		echo "Python virtual environment or 'paho-mqtt' package missing. Initialising $(VENV)..."; \
		$(MAKE) setup-venv; \
	fi
	@echo "Streaming synthetic vehicular telemetry via legacy Node-RED route..."
	@$$(if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo $(PYTHON); fi) scripts/testing/simulate_telemetry.py \
		--host localhost \
		--port 8883 \
		--ca-cert deploy/mosquitto/certs/ca.crt \
		--client-cert deploy/mosquitto/certs/client_esp32.crt \
		--client-key deploy/mosquitto/certs/client_esp32.key \
		--route legacy \
		--mode normal \
		$(ARGS)

inject-faults:
	@if [ ! -f $(VENV)/bin/python ] && [ ! -f $(VENV)/bin/python3 ] && ! $(PYTHON) -c "import paho.mqtt.client" >/dev/null 2>&1; then \
		echo "Python virtual environment or 'paho-mqtt' package missing. Initialising $(VENV)..."; \
		$(MAKE) setup-venv; \
	fi
	@echo "Injecting adversarial faults into edge pipeline..."
	@$$(if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo $(PYTHON); fi) scripts/testing/inject_faults.py \
		--host localhost \
		--port 8883 \
		--ca-cert deploy/mosquitto/certs/ca.crt \
		--client-cert deploy/mosquitto/certs/client_esp32.crt \
		--client-key deploy/mosquitto/certs/client_esp32.key

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@rm -rf .coverage


