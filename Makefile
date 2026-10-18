# ------------------------------------------------------------------------------
# Software-Defined Vehicle (SDV) Automotive IoT HVAC Monitoring
# Master Automation and Build Pipeline
# ------------------------------------------------------------------------------

VENV ?= .venv
PYTHON ?= $(shell if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo python3; fi)
PYTEST ?= $(shell if [ -f $(VENV)/bin/pytest ]; then echo $(VENV)/bin/pytest; elif [ -f $(VENV)/bin/py.test ]; then echo $(VENV)/bin/py.test; else echo pytest; fi)

.PHONY: help menu setup-prerequisites setup-venv setup-pki deploy-gateway deploy-lean deploy-localhost deploy-remote deploy-base-cse deploy-vehicle-ae stop-gateway init-onem2m init-base-cse validate-base-cse test test-unit test-integration run-web simulate-telemetry simulate-telemetry-native simulate-telemetry-legacy inject-faults clean

help:
	@echo "Available build and orchestration targets:"
	@echo "  menu                      Launch the interactive terminal deployment and diagnostics dashboard"
	@echo "  setup-prerequisites       Install Docker/Podman and system dependencies on Ubuntu Server"
	@echo "  setup-venv                Initialise Python virtual environment and simulation dependencies"
	@echo "  setup-pki                 Generate X.509 Root CA, broker, and client certificates"
	@echo "  deploy-gateway            Launch the onboard vehicular MEC container mesh (defaults to localhost lean)"
	@echo "  deploy-lean               Deploy lean container mesh with vanilla Base CSE (zero AEs) & validate"
	@echo "  deploy-localhost          Deploy complete stack on localhost for local dev, simulation & testing"
	@echo "  deploy-remote             Deploy or validate distributed environment on configured remote hosts"
	@echo "  deploy-base-cse           Deploy Module 1 (Base CSE Infrastructure) on central Server / VM host"
	@echo "  deploy-vehicle-ae         Deploy Module 2 (Vehicle AE) on Raspberry Pi 5 targeting Base CSE"
	@echo "  stop-gateway              Halt all MEC container services"
	@echo "  init-onem2m               Initialise the /sdv-cse semantic resource tree (with AE_CabinNode_Car01)"
	@echo "  init-base-cse             Initialise vanilla oneM2M Base CSE (zero AEs, baseline governance)"
	@echo "  validate-base-cse         Execute automated Base CSE & environment verification suite"
	@echo "  run-web                   Launch the public-facing Flask web application locally"
	@echo "  test                      Execute all unit and integration tests"
	@echo "  test-unit                 Execute unit tests only"
	@echo "  test-integration          Execute integration tests only"
	@echo "  simulate-telemetry        Stream synthetic sensor frames via native oneM2M TS-0010 route"
	@echo "  simulate-telemetry-legacy Stream synthetic sensor frames via legacy Node-RED route"
	@echo "  inject-faults             Run the adversarial fault-injection test suite"
	@echo "  clean                     Remove temporary test caches and logs"

menu:
	@bash deploy/menu.sh

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
	@bash deploy/deploy_gateway.sh $(if $(TARGET),--target $(TARGET),--localhost)

deploy-lean:
	@echo "Deploying vehicular MEC gateway container mesh in lean mode (vanilla Base CSE)..."
	@bash deploy/deploy_gateway.sh --lean $(if $(TARGET),--target $(TARGET),--localhost)

deploy-localhost:
	@echo "Deploying complete SDV stack on localhost..."
	@bash deploy/deploy_gateway.sh --localhost --lean

deploy-remote:
	@echo "Deploying distributed SDV stack on remote hosts via SSH (Base CSE & Vehicle AE)..."
	@bash deploy/deploy_remote.sh \
		$(if $(BASE_HOST),--base-host $(BASE_HOST),) \
		$(if $(BASE_USER),--base-user $(BASE_USER),) \
		$(if $(BASE_PORT),--base-port $(BASE_PORT),) \
		$(if $(BASE_KEY),--base-key $(BASE_KEY),) \
		$(if $(VEHICLE_HOST),--vehicle-host $(VEHICLE_HOST),) \
		$(if $(VEHICLE_USER),--vehicle-user $(VEHICLE_USER),) \
		$(if $(VEHICLE_PORT),--vehicle-port $(VEHICLE_PORT),) \
		$(if $(VEHICLE_KEY),--vehicle-key $(VEHICLE_KEY),) \
		$(if $(VEHICLE_ID),--vehicle-id $(VEHICLE_ID),) \
		$(if $(MODULE),--module $(MODULE),)

deploy-base-cse:
	@echo "Deploying Module 1: Base CSE Infrastructure on Server/VM..."
	@if [ "$$(echo $(TARGET) | tr '[:upper:]' '[:lower:]')" = "remote" ] || [ -n "$(BASE_HOST)" -a "$(BASE_HOST)" != "localhost" -a "$(BASE_HOST)" != "127.0.0.1" ]; then \
		bash deploy/deploy_remote.sh --module base-cse $(if $(BASE_HOST),--base-host $(BASE_HOST),) $(if $(BASE_USER),--base-user $(BASE_USER),) $(if $(BASE_KEY),--base-key $(BASE_KEY),); \
	else \
		bash deploy/deploy_base_cse.sh $(if $(TARGET),--target $(TARGET),) $(if $(BASE_HOST),--base-host $(BASE_HOST),); \
	fi

deploy-vehicle-ae:
	@echo "Deploying Module 2: Vehicle AE Module on in-vehicle Raspberry Pi 5..."
	@if [ "$$(echo $(TARGET) | tr '[:upper:]' '[:lower:]')" = "remote" ] || [ -n "$(VEHICLE_HOST)" -a "$(VEHICLE_HOST)" != "localhost" -a "$(VEHICLE_HOST)" != "127.0.0.1" ]; then \
		bash deploy/deploy_remote.sh --module vehicle-ae $(if $(BASE_HOST),--base-host $(BASE_HOST),) $(if $(VEHICLE_HOST),--vehicle-host $(VEHICLE_HOST),) $(if $(VEHICLE_USER),--vehicle-user $(VEHICLE_USER),) $(if $(VEHICLE_KEY),--vehicle-key $(VEHICLE_KEY),) $(if $(VEHICLE_ID),--vehicle-id $(VEHICLE_ID),); \
	else \
		bash deploy/deploy_vehicle_ae.sh $(if $(TARGET),--target $(TARGET),) $(if $(BASE_HOST),--base-host $(BASE_HOST),) $(if $(VEHICLE_ID),--vehicle-id $(VEHICLE_ID),); \
	fi

stop-gateway:
	@echo "Stopping vehicular MEC gateway container mesh..."
	@cd deploy && docker compose down

init-onem2m:
	@echo "Provisioning oneM2M /sdv-cse resource hierarchy..."
	@bash scripts/onem2m/init_tree.sh

init-base-cse:
	@echo "Initialising vanilla oneM2M Base CSE (zero Application Entities)..."
	@bash scripts/onem2m/init_base_cse.sh $(if $(TARGET),--target $(TARGET),) $(if $(BASE_HOST),--host $(BASE_HOST),)

validate-base-cse:
	@echo "Executing Base CSE automated validation & verification suite..."
	@$$(if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo $(PYTHON); fi) scripts/testing/validate_base_cse.py

run-web:
	@echo "Starting public-facing Web portal..."
	@$$(if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo $(PYTHON); fi) services/web_portal/app.py

test:
	@if [ ! -f $(VENV)/bin/pytest ] || ! $$(if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo $(PYTHON); fi) -c "import jsonschema, flask" >/dev/null 2>&1; then \
		echo "Test dependencies missing in active environment. Reconciling $(VENV)..."; \
		$(MAKE) setup-venv; \
	fi
	@echo "Executing complete test suite (Tier 1 & Tier 2)..."
	@$$(if [ -f $(VENV)/bin/pytest ]; then echo $(VENV)/bin/pytest; elif [ -f $(VENV)/bin/py.test ]; then echo $(VENV)/bin/py.test; else echo $(PYTEST); fi) -v

test-unit:
	@if [ ! -f $(VENV)/bin/pytest ] || ! $$(if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo $(PYTHON); fi) -c "import jsonschema, flask" >/dev/null 2>&1; then \
		echo "Test dependencies missing in active environment. Reconciling $(VENV)..."; \
		$(MAKE) setup-venv; \
	fi
	@echo "Executing unit tests (Tier 1)..."
	@$$(if [ -f $(VENV)/bin/pytest ]; then echo $(VENV)/bin/pytest; elif [ -f $(VENV)/bin/py.test ]; then echo $(VENV)/bin/py.test; else echo $(PYTEST); fi) -v tests/unit/

test-integration:
	@if [ ! -f $(VENV)/bin/pytest ] || ! $$(if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; elif [ -f $(VENV)/bin/python3 ]; then echo $(VENV)/bin/python3; else echo $(PYTHON); fi) -c "import jsonschema, flask" >/dev/null 2>&1; then \
		echo "Test dependencies missing in active environment. Reconciling $(VENV)..."; \
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
		--client-key deploy/mosquitto/certs/client_esp32.key \
		$(ARGS)

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@rm -rf .coverage


