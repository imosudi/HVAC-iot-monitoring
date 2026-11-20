# 03. System Architecture Document (SAD)

## Software-Defined Vehicle (SDV) Cyber-Physical Cabin Environmental Monitoring and Closed-Loop HVAC Regulation System

---

## Document Control & Attribution

| Attribute | Specification Detail |
| :--- | :--- |
| **Document Designation** | System Architecture Document (SAD) |
| **Project Title** | Cyber-Physical Cabin Environmental Monitoring & Closed-Loop HVAC Regulation in Software-Defined Vehicles |
| **Researcher & Architecture** | **Isiaka Mosudi** (Middleware & Distributed Systems Architecture) |
| **Research Team** | **Isiaka Mosudi**, Ashok Ramalingam, Pooja Janwalkar, AnnaMaria Moçi, Julia Philip |
| **GitHub Repository** | [https://github.com/imosudi/HVAC-iot-monitoring](https://github.com/imosudi/HVAC-iot-monitoring) |
| **Status & Compliance** | Released / Verified (ISO/IEC/IEEE 42010, ETSI GS MEC 003, ETSI TS 118 101) |

---

## 1. Architectural Evolution: Monolithic to Service-Oriented SDVs
Historically, automotive climate control has been implemented as a closed, federated subsystem. A dedicated HVAC ECU communicated over isolated Controller Area Network (CAN) or Local Interconnect Network (LIN) buses, hardwired to thermistors, blend door actuators, and blower motor relays. This monolithic design suffers from critical structural shortcomings:
1. **Proprietary Rigidity:** Sensor data and control heuristics remain siloed within OEM firmware, preventing cross-domain telemetry fusion (e.g., driver biometrics or navigation-based pre-conditioning).
2. **Inflexible Lifecycle Management:** Firmware updates require dealer service interventions or dangerous monolithic ECU flashing over UDS.
3. **Absence of Semantic Interoperability:** Sensor values exist as raw binary CAN signals without standardised data typing, ontological definitions, or security assertions.

The SDV paradigm transforms this architecture into a **service-oriented cyber-physical continuum**:
- Physical transducers interface with low-power micro-ECUs (Espressif ESP32-S3) executing deterministic FreeRTOS real-time operating systems.
- Telemetry is transported over an automotive edge service mesh hosted on a vehicular gateway (Raspberry Pi 5) secured via **Mutual TLS 1.3** and strict topic-based Access Control Lists (ACLs).
- Semantic normalisation is performed using an **ETSI oneM2M Common Services Entity (IN-CSE: `/sdv-cse`)**, establishing vendor-neutral resource trees.
- Telemetry integrity is continuously certified by a deterministic **4-state Data Health Classifier** (`FRESH`, `STALE`, `DEGRADED`, `FAULT`), feeding into an InfluxDB 2.x time-series store and triggering closed-loop actuation dispatch through a Grafana operations cockpit and custom management portal.

![Figure 1: Automotive E/E Architectural Evolution — Monolithic Federated ECUs to Modern Service-Oriented SDV Architecture](../assets/sdv_federated_vs_service_oriented.png)

---

## 2. End-to-End Cyber-Physical Topology
The platform implements an end-to-end, multi-tier cyber-physical topology with strict physical separation across three host environments:
1. **Firmware Tier — Smart Cabin Sensing & Actuation Node (Micro-ECU):** Espressif ESP32-S3 microcontroller directly interfacing with a single unified **Sensirion SCD30** transducer (NDIR CO₂, Temperature, RH over I²C with CRC-8) and actuator emulation circuits (Blue PWM Purge LED, Red Heat LED, Green Eco LED, Amber Alert LED).
2. **Vehicle-Based Components — Module 2: Standalone Vehicle AE (Raspberry Pi 5):** In-vehicle compute host running containerised Vehicle AE services (`sdv_edge_serial_client`, `sdv_actuator_module`) with **0 open ingress ports** and outbound-only WAN links.
3. **Server / Network-Based Components — Module 1: Standalone Base CSE Infrastructure (Central Server / VM):** High-availability server hosting the **ACME oneM2M IN-CSE (`/sdv-cse`, Zero AEs at boot, Baseline Governance)**, built-in **ACMEScripts** engine (replacing Node-RED), Eclipse Mosquitto mTLS broker, `sdv_bridge_ae` data health service, InfluxDB 2.x time-series engine, Grafana operations cockpit, and `sdv_web_portal`.

![Figure 2: SDV End-to-End Cyber-Physical Architecture & Service Topology](../assets/sdv_architecture_flowchart.png)

---

## 3. Architectural Decomposition & Layering Patterns
The platform adheres strictly to the Layered Architecture Pattern across five discrete operational tiers:
1. **Perception & Transduction Layer:** Direct physical acquisition via calibrated sensors operating under strict hardware bounds.
2. **Ingress, Protocol Adaptation & Transport Layer:** Encapsulation of UART frames into MQTT v5.0/v3.1.1 frames secured via TLS 1.3, verified against JSON schemas.
3. **Semantic Middleware Layer:** ETSI oneM2M resource tree hierarchy providing RESTful CRUDN operations, persistent resource addressing, and subscription dispatch.
4. **Data Health & Analytics Layer:** Deterministic piecewise state machine execution, psychrometric drift tracking, and high-frequency time-series persistence.
5. **Presentation & Supervisory Operations Layer:** Web dashboards, real-time gauges, and interactive TUI consoles facilitating operational diagnostics and manual override dispatch.

---

## 4. Microservice Mesh and Containerisation Pattern
Except for the ESP32-S3 firmware, all system services are packaged as hardened Docker containers linked through an isolated Docker bridge network (`sdv_mec_mesh`) on the Base CSE platform, and host networking on the edge vehicle gateway to permit native access to serial USB controllers (`/dev/ttyUSB0` or `/dev/ttyACM0`).

---

## 5. Multi-Access Edge Computing & Fog Interworking
The architecture adheres to the Multi-Access Edge Computing (ETSI GS MEC 003) pattern. The in-cabin gateway performs local frame buffering and validation. If the backhaul wireless uplink to the Base CSE platform suffers intermittent attenuation or complete severance, the edge gateway caches up to $48\text{ hours}$ of historical telemetry, whilst the Micro-ECU maintains autonomous closed-loop failsafe regulation without cloud dependency.

---

## 6. Closed-Loop Feedback Control Trajectory

![Figure 3: Closed-Loop Telemetry & Actuation Feedback Signal Trajectory](../assets/sdv_closed_loop_flow.png)

The primary cyber-physical feedback loop regulates cabin air quality dynamically:
1. **Sensing:** Single Sensirion SCD30 samples $\text{CO}_2$, $T$, and $\text{RH}$ every $2\text{ seconds}$ over I²C with hardware CRC-8 verification.
2. **Uplink Dispatch:** Micro-ECU serialises readings into JSON and pushes them across UART to the Raspberry Pi 5 Vehicle AE.
3. **Transport & Ingress:** `sdv_edge_serial_client` transmits the payload outbound across MQTT (mTLS 1.3) to the server-based Mosquitto broker.
4. **Semantic Registration:** ACME IN-CSE's native TS-0010 MQTT binding and **ACMEScripts** wrap the payload into an `<m2m:cin>` resource under `/sdv-cse/vehicle-001/raw-telemetry`.
5. **Health Certification:** oneM2M fires an HTTP webhook notification to `sdv_bridge_ae` (and/or ACMEScripts). The classifier confirms SCD30 CRC-8 integrity, bounds, and latency ($\text{Age} \le 2.5\text{s}$) and marks the record as `FRESH`.
6. **Persistence:** The classified frame is stored in InfluxDB 2.x.
7. **Control Decision:** If $\text{CO}_2 > 800\text{ ppm}$, an actuation directive is issued. If $\text{CO}_2 > 1{,}200\text{ ppm}$, high-speed emergency purge is commanded (`PWM = 100%`).
8. **Downlink Dispatch:** A new `<m2m:cin>` is created in `/sdv-cse/vehicle-001/commands`.
9. **Actuation Notification:** ACME IN-CSE / **ACMEScripts** dispatches the downlink directive directly over TS-0010 MQTT (`sdv/vehicle_01/control/cmd`).
10. **Actuation Modulation:** `sdv_actuator_module` receives the command and issues `CMD:PWM=100,MODE=AUTOMATIC` to the ESP32-S3, which ramps the Blue Purge LED to 100% duty cycle, opens the fresh air damper, and monitors tachometer RPM to confirm fan rotation.

---

## 7. End-to-End Sequence Workflows

![Figure 4: End-to-End Uplink Telemetry and Downlink Actuation Sequence](../assets/sdv_sequence_diagram.png)

---

## 8. Multi-Host Network Topologies
The architecture supports dual operational configurations:
- **Scenario A (Consolidated Dev Stack):** All microservices co-located on a single host (`127.0.0.1`), interfacing with the ESP32-S3 over local USB.
- **Scenario B (Distributed Production Topology):** Multi-host physical partitioning:
  - **Host 1 (Central Server / VM):** Base CSE Infrastructure Platform (ACME IN-CSE, Mosquitto mTLS Broker, InfluxDB 2.7, Grafana Enterprise, Bridge AE, Web Portal).
  - **Host 2 (In-Vehicle Edge Gateway - Raspberry Pi 5):** Vehicle AE Microservices Stack (`edge_serial_client`, `actuator_module`).
  - **Host 3 (Smart Cabin Node):** ESP32-S3 connected to Raspberry Pi 5 via internal USB/UART.

![Figure 10: Distributed Multi-Host Cyber-Physical Production Topology and Protocol Interconnects](../assets/sdv_distributed_topology.png)
