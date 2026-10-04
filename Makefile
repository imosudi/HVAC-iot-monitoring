# ------------------------------------------------------------------------------
# Software-Defined Vehicle (SDV) Automotive IoT HVAC Monitoring
# Master Automation and Build Pipeline
# ------------------------------------------------------------------------------

VENV ?= .venv
PYTHON ?= $(shell if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; else echo python3; fi)
PYTEST ?= $(shell if [ -f $(VENV)/bin/pytest ]; then echo $(VENV)/bin/pytest; else echo pytest; fi)

.PHONY: help setup-pki deploy-gateway stop-gateway init-onem2m test test-unit test-integration run-web simulate-telemetry inject-faults clean

help:
	@echo "Available build and orchestration targets:"
	@echo "  setup-pki           Generate X.509 Root CA, broker, and client certificates"
	@echo "  deploy-gateway      Launch the onboard vehicular MEC container mesh"
	@echo "  stop-gateway        Halt all MEC container services"
	@echo "  init-onem2m         Initialise the /sdv-cse semantic resource tree"
	@echo "  run-web             Launch the public-facing Flask web application locally"
	@echo "  test                Execute all unit and integration tests"
	@echo "  test-unit           Execute unit tests only"
	@echo "  test-integration    Execute integration tests only"
	@echo "  simulate-telemetry  Stream synthetic sensor frames to the gateway broker"
	@echo "  inject-faults       Run the adversarial fault-injection test suite"
	@echo "  clean               Remove temporary test caches and logs"

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
	@echo "Starting public-facing Flask web portal..."
	@$(PYTHON) services/web_portal/app.py

test:
	@echo "Executing complete test suite (Tier 1 & Tier 2)..."
	@$(PYTEST) -v

test-unit:
	@echo "Executing unit tests (Tier 1)..."
	@$(PYTEST) -v tests/unit/

test-integration:
	@echo "Executing integration tests (Tier 2)..."
	@$(PYTEST) -v tests/integration/

simulate-telemetry:
	@echo "Streaming synthetic vehicular telemetry..."
	@$(PYTHON) scripts/testing/simulate_telemetry.py --host localhost --port 1883 --mode normal

inject-faults:
	@echo "Injecting adversarial faults into edge pipeline..."
	@$(PYTHON) scripts/testing/inject_faults.py --host localhost --port 1883

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@rm -rf .coverage

