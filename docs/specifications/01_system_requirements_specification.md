# 01. System Requirements Specification (SRS)

## Software-Defined Vehicle (SDV) Cyber-Physical Cabin Environmental Monitoring and Closed-Loop HVAC Regulation System

---

## Document Control & Attribution

| Attribute | Specification Detail |
| :--- | :--- |
| **Document Designation** | System Requirements Specification (SRS) |
| **Project Title** | Cyber-Physical Cabin Environmental Monitoring & Closed-Loop HVAC Regulation in Software-Defined Vehicles |
| **Researcher & Architecture** | **Isiaka Mosudi** (Middleware & Distributed Systems Architecture) |
| **Research Team** | **Isiaka Mosudi**, Ashok Ramalingam, Pooja Janwalkar, AnnaMaria Moçi, Julia Philip |
| **GitHub Repository** | [https://github.com/imosudi/HVAC-iot-monitoring](https://github.com/imosudi/HVAC-iot-monitoring) |
| **Status & Compliance** | Released / Verified (ETSI TS 118 101, oneM2M TS-0001, IEEE 29148, RFC 8446) |

---

## 1. Document Purpose, Scope, and System Context
The modern automotive industry is transitioning rapidly toward the **Software-Defined Vehicle (SDV)** paradigm, where vehicle comfort, climate, and air quality systems are decoupled from fixed-function hardware electronic control units (ECUs). This System Requirements Specification (SRS) establishes the formal engineering requirements for an open-standard, cyber-physical platform engineered for **real-time vehicular cabin environmental monitoring and closed-loop heating, ventilation, and air conditioning (HVAC) regulation**.

The system context encompasses:
1. Physical cabin perception via an embedded **Smart Cabin Node (Micro-ECU)** sampling carbon dioxide ($\text{CO}_2$), dry-bulb temperature ($T$), and relative humidity ($\text{RH}$).
2. An automotive edge computing platform (**Vehicular Edge Gateway**) executing ingress translation, JSON schema verification, and secure MQTT telemetry transport over Mutual TLS 1.3.
3. Centralised service layer middleware (**Base CSE Infrastructure**) implementing standard ETSI oneM2M primitives, deterministic data health validation, time-series persistence, and supervisory closed-loop actuation dispatch.

## 2. Applicable Standards & Conformance
The system architecture and software interfaces strictly conform to the following international standards:
- **ETSI TS 118 101 Rel 4 / oneM2M TS-0001:** oneM2M Functional Architecture.
- **oneM2M TS-0004:** Service Layer Core Protocol Specification (HTTP/REST binding).
- **oneM2M TS-0010:** MQTT Protocol Binding.
- **IETF RFC 8446:** The Transport Layer Security (TLS) Protocol Version 1.3.
- **IETF RFC 5280:** Internet X.509 Public Key Infrastructure Certificate Profile.
- **JSON Schema Draft 2020-12:** Automated payload validation specification.
- **ETSI GS MEC 003:** Multi-Access Edge Computing (MEC) Framework and Reference Architecture.
- **IEEE Std 29148-2018:** Systems and Software Engineering — Requirements Engineering.
- **ISO/IEC/IEEE 42010:2022:** Systems and Software Engineering — Architecture Description.

## 3. User Personas, Operational Regimes & Stakeholders
The system serves four primary stakeholder personas:
1. **Vehicle Occupant / Driver:** Requires an ergonomic, drowsiness-free passenger cabin with automatic cabin purging when $\text{CO}_2$ exceeds safe thresholds, operating with inaudible acoustic blower noise ($<25\text{ dBA}$).
2. **Automotive Systems Engineer:** Requires open standards (oneM2M), deterministic data integrity guarantees, and strict hardware-in-the-loop (HIL) bench validation.
3. **Fleet Operations Supervisor:** Requires real-time multi-vehicle telemetry visualisation, historical psychrometric analytics, and declarative fleet onboarding via REST APIs and Grafana.
4. **Commissioning / Test Technician:** Requires automated multi-host deployment tools, hardware reachability audits, and dynamic fault injection capabilities via an interactive terminal operations dashboard (`make menu`).

## 4. Functional Requirements (FR) Catalogue

| Requirement ID | Functional Specification Summary | Subsystem | Source Location | Verification Method |
| :--- | :--- | :--- | :--- | :--- |
| **FR-PER-001** | Dual-channel optical NDIR $\text{CO}_2$ ($400\text{--}10{,}000\text{ ppm}$), temperature, and humidity acquisition via Sensirion SCD30 at $\ge 0.5\text{ Hz}$. | Micro-ECU Firmware | [`firmware/esp32s3_cabin_node/main/scd30_driver.c`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/firmware/esp32s3_cabin_node/main/scd30_driver.c) | Bench Sensor Test |
| **FR-PER-002** | Redundant capacitive humidity and NTC temperature acquisition via DHT22 for empirical cross-validation. | Micro-ECU Firmware | [`firmware/esp32s3_cabin_node/main/dht22_driver.c`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/firmware/esp32s3_cabin_node/main/dht22_driver.c) | Bench Sensor Test |
| **FR-PER-003** | Ultrasonic $25\text{ kHz}$ LEDC PWM blower modulation with 10-bit duty resolution ($0\text{--}1023$ counts) for acoustic coil whine elimination. | Micro-ECU Firmware | [`firmware/esp32s3_cabin_node/main/pwm_fan_control.c`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/firmware/esp32s3_cabin_node/main/pwm_fan_control.c) | Oscilloscope Audit |
| **FR-PER-004** | Discrete coloured LED actuation suite emulating cabin HVAC subcomponents (Blue: Purge Blower; Red: Heater; Green: Eco-Vent; Amber: Defrost). | Micro-ECU Firmware | [`firmware/esp32s3_cabin_node/main/app_config.h`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/firmware/esp32s3_cabin_node/main/app_config.h) | Visual Inspection |
| **FR-PER-005** | Hardware Pulse Counter (PCNT) closed-loop tachometer monitoring with mechanical slip and stall detection ($<100\text{ RPM}$ at $\ge 30\%$ PWM). | Micro-ECU Firmware | [`firmware/esp32s3_cabin_node/main/tachometer.c`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/firmware/esp32s3_cabin_node/main/tachometer.c) | Pulse Gen Test |
| **FR-ING-001** | Dynamic USB serial discovery (`/dev/ttyUSB*`, `/dev/ttyACM*`) with hot-plug polling on vehicular gateway. | Edge Serial Client | [`services/edge_client/src/serial_reader.py`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/services/edge_client/src/serial_reader.py) | HIL Plug Test |
| **FR-ING-002** | Automated mathematical simulation fallback executing sinusoidal diurnal temperature and occupancy $\text{CO}_2$ models when hardware is disconnected. | Edge Serial Client | [`services/edge_client/src/serial_reader.py`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/services/edge_client/src/serial_reader.py) | Unit Test |
| **FR-ING-003** | Outbound telemetry validation against JSON Schema Draft 2020-12 prior to message broker dispatch. | Edge Serial Client | [`services/edge_client/schemas/telemetry_schema.json`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/services/edge_client/schemas/telemetry_schema.json) | Schema Unit Test |
| **FR-MID-001** | Interworking Proxy Entity (IPE) protocol bridging from MQTT v5.0/v3.1.1 frames into oneM2M `<m2m:cin>` REST resources. | Node-RED IPE | [`deploy/nodered/flows.json`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/deploy/nodered/flows.json) | Integration Test |
| **FR-MID-002** | oneM2M Release 4 semantic tree management (`/sdv-cse`) supporting `<m2m:ae>`, `<m2m:cnt>`, `<m2m:cin>`, `<m2m:sub>`, and `<m2m:acp>`. | ACME oneM2M CSE | [`deploy/onem2m/acme.ini`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/deploy/onem2m/acme.ini) | CSE Validation Test |
| **FR-INT-001** | Deterministic 4-state Data Health Classification (`FRESH`, `STALE`, `DEGRADED`, `FAULT`) based on sensor divergence and latency. | Bridge AE Service | [`services/bridge_ae/src/health_classifier.py`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/services/bridge_ae/src/health_classifier.py) | Unit Test |
| **FR-INT-002** | Strict non-coercive telemetry semantics preserving JSON `null` values without zero-filling or synthetic averaging during sensor faults. | Bridge AE Service | [`services/bridge_ae/src/health_classifier.py`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/services/bridge_ae/src/health_classifier.py) | Regression Test |
| **FR-INT-003** | High-throughput time-series persistence to InfluxDB 2.x bucket `cabin_telemetry` with granular tags and fields. | Bridge AE Service | [`services/bridge_ae/src/influx_writer.py`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/services/bridge_ae/src/influx_writer.py) | InfluxDB Query |
| **FR-ACT-001** | Downlink actuation dispatch from oneM2M `<cnt_actuation_cmd>` notifications to MQTT topic `sdv/<car_id>/control/cmd`. | Node-RED / ACM | [`services/actuator_module/src/downlink_listener.py`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/services/actuator_module/src/downlink_listener.py)| E2E Integration |
| **FR-ACT-002** | Command bounds enforcement ($0\text{--}100\%$ PWM) and mode arbitration (`AUTOMATIC`, `MANUAL_OVERRIDE`, `FAILSAFE`). | Actuator Controller| [`services/actuator_module/src/actuator_controller.py`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/services/actuator_module/src/actuator_controller.py)| Boundary Unit Test |
| **FR-WDM-001** | Web Operations Cockpit (`sdv_web_portal` on port 8000) providing real-time gauges, oneM2M resource tree explorer, and manual override API. | Web Portal | [`services/web_portal/app.py`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/services/web_portal/app.py) | Web API Unit Test |
| **FR-TUI-001** | Interactive Terminal Operations Console ([`deploy/menu.sh`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/deploy/menu.sh) via `make menu`) providing multi-host provisioning, automated passwordless SSH key configuration (`--setup-passwordless`), pre-flight audits, and hardware diagnostics. | Terminal Console | [`deploy/menu.sh`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/deploy/menu.sh) | Shell TUI & Pre-Flight Test |

## 5. Non-Functional Requirements (NFR) Catalogue

| Requirement ID | Category | Target Metric | Architectural Solution |
| :--- | :--- | :--- | :--- |
| **NFR-LAT-001** | Latency | Telemetry Ingress Latency $< 250\text{ ms}$ (Empirical: $85\text{ ms}$) | Lightweight MQTT transport + in-memory oneM2M dispatch. |
| **NFR-LAT-002** | Latency | Downlink Actuation Latency $< 100\text{ ms}$ (Empirical: $42\text{ ms}$) | Asynchronous oneM2M webhooks + persistent MQTT connections. |
| **NFR-LAT-003** | Latency | Health Classification Time $< 1.0\text{ ms}$ (Empirical: $0.8\text{ ms}$) | Vectorised piecewise mathematics in Python health classifier. |
| **NFR-THP-001** | Throughput | Ingestion Throughput $> 500\text{ frames/second}$ | Non-blocking event loop + batched InfluxDB Line Protocol writes. |
| **NFR-REL-001** | Reliability | Zero data loss during transient backhaul dropouts | Gateway local frame queue buffering up to $48\text{ hours}$ of metrics. |
| **NFR-REL-002** | Resilience | Autonomous closed-loop failsafe upon total backhaul loss | FreeRTOS autonomous fallback heuristic + 5s Task Watchdog (TWDT). |
| **NFR-SEC-001** | Security | Cryptographic authentication across all network boundaries | Mutual TLS 1.3 (RFC 8446) with 4096-bit Root CA and X.509 certs. |
| **NFR-SEC-002** | Security | Granular least-privilege topic isolation | Mosquitto topic ACLs preventing cross-tenant publishing/listening. |
| **NFR-SEC-003** | Security | oneM2M Middleware Access Governance | oneM2M Access Control Policies (`<acp>`) with originator validation. |
| **NFR-ERG-001** | Ergonomics | Inaudible blower modulation in passenger compartment | Ultrasonic $25\text{ kHz}$ LEDC PWM carrier exceeding human hearing range. |
| **NFR-SAF-001** | Safety | Immediate cutoff upon mechanical motor stall | Tachometer PCNT feedback triggers motor cut within $500\text{ ms}$ of stall. |
| **NFR-MAI-001** | Usability | Rapid automated provisioning and multi-host deployment | Interactive terminal dashboard ([`deploy/menu.sh`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/deploy/menu.sh) via `make menu`). |

## 6. Constraints, Assumptions, and Operational Boundaries
1. **Transducer Operating Range:** SCD30 operational from $400\text{ ppm}$ to $10{,}000\text{ ppm}$ $\text{CO}_2$ ($\pm 30\text{ ppm} + 3\%$), $-40^\circ\text{C}$ to $+70^\circ\text{C}$ temperature, and $0\%\text{--}95\%\text{ RH}$.
2. **Electrical Power Budget:** Micro-ECU logic rail restricted to $3.3\text{V DC} \pm 5\%$ ($<120\text{ mA}$ average); sensor and blower rail powered by $5.0\text{V DC}$.
3. **Serial Communication:** Micro-ECU to gateway link locked at $115{,}200\text{ baud}$, 8 data bits, no parity, 1 stop bit (`115200 8N1`).
4. **Network Boundaries:** Cleartext MQTT (port 1883) is strictly bound to `127.0.0.1`; all external vehicular backhaul traffic MUST terminate TLS 1.3 on port 8883.
