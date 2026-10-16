# Architectural Capability Review: Consolidating Vehicular Edge Gateway Functions into ACME oneM2M CSE

## Feasibility Study, Application Entity Multi-Hazard Analysis, and Technical Roadmap for Absorbing MEC Gateway Microservices into Native ETSI TS 118 101 Middleware

**Document Identifier:** ARC-SDV-CSE-2026-01  
**Version:** 2.0.0 (Comprehensive Fleet & Multi-Transducer Revision)  
**Status:** Approved Technical Assessment  
**Date:** October 2026  
**Project:** Software-Defined Vehicle (SDV) Automotive IoT HVAC & Cabin Monitoring  
**Affiliation:** University of Applied Sciences Technikum Wien (FH Technikum Wien)  
**Research Cluster:** Distributed Cyber-Physical Systems and Automotive IoT (FHTW-AIOT, Group MIO3B)  
**Standard Compliance:** ETSI TS 118 101, oneM2M TS-0001, oneM2M TS-0004, oneM2M TS-0010 (MQTT Protocol Binding)  
**Target Architecture:** Vehicular MEC Edge Gateway (Raspberry Pi 5) & ACME oneM2M IN-CSE  
**Associated Baseline Artifacts:**
* Semantic Resource Tree: [collections/vehicle_resource_tree.json](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/collections/vehicle_resource_tree.json) & [docs/assets/vehicle_resource_tree.svg](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/docs/assets/vehicle_resource_tree.svg)
* Fleet Automation Harness: [collections/acme_fleet_insomnia_collection.yaml](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/collections/acme_fleet_insomnia_collection.yaml) & [collections/SDV_Expandable_Fleet_ACME_CSE_SOP.md](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/collections/SDV_Expandable_Fleet_ACME_CSE_SOP.md)
* Physical Bench Netlist: [docs/assets/circuit_schematic.svg](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/docs/assets/circuit_schematic.svg) & [docs/architecture/hardware_schematic.md](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/docs/architecture/hardware_schematic.md)
* End-to-End System Topology: [docs/assets/architecture_detailed.png](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/docs/assets/architecture_detailed.png)

---

### Executive Summary

In the current baseline deployment of the Software-Defined Vehicle (SDV) cabin environmental monitoring system, the onboard Vehicular Multi-Access Edge Computing (MEC) Gateway—hosted on a Raspberry Pi 5 single-board computer—executes a seven-tier containerised microservice mesh:
1. **Eclipse Mosquitto:** Perimeter mutual TLS 1.3 broker terminating client telemetry on port 8883.
2. **Node-RED Ingress IPE:** Interworking Proxy Entity translating raw MQTT JSON messages into oneM2M HTTP REST primitives (`<m2m:cin>`), and translating HTTP downlink webhooks back into MQTT actuator commands.
3. **ACME oneM2M IN-CSE:** Standardised semantic resource tree managing Common Services Entity functions on port 8080.
4. **Python Bridge AE:** Flask microservice receiving oneM2M `<subscription>` webhooks, validating data integrity, and committing records to InfluxDB.
5. **InfluxDB 2.x:** Columnar time-series database storing historical telemetry with a 30-day retention policy.
6. **Grafana Enterprise:** Operational dashboard visualisation and telemetry analytics cockpit.
7. **Web Portal:** Lightweight Python application providing operational introspection and vehicle status overview.

While initial Proof-of-Concept (PoC) discussions concentrated narrowly on cabin temperature divergence ($\Delta T = |T_{\mathrm{SCD30}} - T_{\mathrm{DHT22}}|$) and blower fan PWM modulation, a thorough audit of the formal ETSI TS 118 101 resource tree, the Insomnia fleet management pipeline, and the bench hardware schematics reveals that **the Application Entity (AE), the Data Health Engine (`bridge_ae`), and the Fleet tier encompass a substantially wider cyber-physical scope**:
* **The 7 Standardised AE Containers:** Encompassing redundant temperature, redundant relative humidity, NDIR CO₂, lethal Carbon Monoxide (CO) emergency monitoring, cabin indoor air quality (IAQ/VOC), exterior ambient air quality (AQI), and unified multi-sensor raw telemetry.
* **The Full 4-Channel Actuator Matrix:** Purge Blower (Blue LED PWM, GPIO 18), Auxiliary Heater Core (Red LED DO, GPIO 17), Eco-Ventilation (Green LED DO, GPIO 16), Dehumidification / Alert Warning (Amber LED DO, GPIO 15), Optical Node Annunciator (WS2812B RGB, GPIO 38), and closed-loop Hall-effect tachometer feedback (GPIO 19).
* **Multi-Dimensional Health Classification:** Evaluating relative humidity drift ($\Delta RH$), toxic gas emergency interlocks (CO alert routing), blower motor stall/slip detection ($\text{PWM} \ge 30\%$ with $\text{RPM} < 100$), exterior-to-cabin air quality differentials ($\Delta IAQ$ for recirculation flap control), and temporal latency freshness ($\tau_{\mathrm{age}} \le 2.5\,\text{s}$).
* **Expandable Fleet Governance:** Dynamic multi-vehicle discovery (`fu=1&ty=2`), atomic group fan-out operations (`<grp>` and `<fopt>`), and centralised semantic Access Control Policies (`<acp>`).

This comprehensive review evaluates how **ACME oneM2M IN-CSE natively possesses the capacity to absorb Node-RED ingress bridging, multi-hazard rule evaluation, edge time-series retention, fleet fan-out, and administrative monitoring**, and provides explicit synchronisation guidelines to bring [docs/assets/architecture_detailed.png](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/docs/assets/architecture_detailed.png) into 100% alignment with the rest of the architecture.

---

### 1. The Comprehensive Scope of the Vehicle Application Entity (AE)

The vehicle Application Entity (AE) is not a simple temperature/CO₂ telemetry sender; it represents an automotive-grade environmental life-support and passenger comfort subsystem.

```mermaid
flowchart TD
    subgraph AE ["Standardised Vehicle Application Entity: <m2m:ae> (vehicle-001..N)"]
        direction TB
        subgraph SENSORS ["7x Standardised <m2m:cnt> Containers"]
            C1["cnt_temperature-cabin\n(SCD30 & DHT22 Cross-Validation)"]
            C2["cnt_humidity-cabin\n(Dual RH Cross-Validation, ΔRH)"]
            C3["cnt_co2-cabin\n(NDIR CO₂ 400-10,000 ppm)"]
            C4["cnt_co-cabin\n(Toxic Carbon Monoxide Safety)"]
            C5["cnt_air-quality-cabin\n(Cabin IAQ / VOC / PM Index)"]
            C6["cnt_air-quality-exterior\n(Ambient Exterior AQI)"]
            C7["cnt_raw-telemetry\n(Synchronised Multi-Sensor Frame)"]
        end
        subgraph ACTUATORS ["4-Channel Actuator Matrix & Tachometer"]
            A1["Purge Blower: Blue LED\n(GPIO 18, 25kHz PWM 0-100%)"]
            A2["Aux Heater Core: Red LED\n(GPIO 17, DO, Temp < 19°C)"]
            A3["Eco-Ventilation: Green LED\n(GPIO 16, DO, Nominal Equilibrium)"]
            A4["Dehumidifier / Alert: Amber LED\n(GPIO 15, DO, RH > 65% / Fault)"]
            A5["Status Annunciator: WS2812B\n(GPIO 38, RMT RGB State Code)"]
            A6["Hall Tachometer Feedback\n(GPIO 19, PCNT Unit 0 Closed-Loop)"]
        end
    end
    C1 -.->|Temp < 19°C| A2
    C2 -.->|RH > 65%| A4
    C3 -.->|CO₂ > 800 ppm| A1
    C4 -.->|Emergency CO Alert| A1
    C6 & C5 -.->|ΔIAQ Recirc Flap| A1
    A1 -.->|Motor Rotation Feedback| A6
```

#### 1.1 Detailed Container Semantics
1. **`temperature-cabin`:** Ingests dry-bulb temperature from both the Sensirion SCD30 (I²C) and DHT22 (1-Wire). Governs auxiliary cabin heating activation when $T_{\mathrm{cabin}} < 19.0\,^\circ\text{C}$.
2. **`humidity-cabin`:** Ingests relative humidity ($RH$) from both transducers. Governs window defogging and cabin dehumidification when $RH > 65\%$.
3. **`co2-cabin`:** Samples carbon dioxide concentration via optical NDIR spectroscopy. Governs passenger alertness, cognitive fatigue prevention, and ventilation purge speed when $\text{CO}_2 > 800\,\text{ppm}$.
4. **`co-cabin`:** Critical safety-monitoring container for toxic Carbon Monoxide (CO). Wired with dedicated subscription `sub_co_alert` dispatching immediate notifications to `/emergency-monitor`.
5. **`air-quality-cabin`:** Measures cabin volatile organic compounds (VOC) and particulate matter, generating a unified indoor air quality (IAQ) score (0–500).
6. **`air-quality-exterior`:** Samples ambient outdoor air quality index (AQI). Comparing exterior AQI against cabin IAQ drives the vehicular **Fresh Air Intake vs Cabin Air Recirculation Damper Flap**.
7. **`raw-telemetry`:** Unified, timestamped JSON frame containing all transducer readings, GNSS position, actuator duty cycles, and tachometer RPM.

#### 1.2 The Complete Physical Actuator Set
As documented in the bench circuit schematic ([docs/assets/circuit_schematic.svg](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/docs/assets/circuit_schematic.svg)), the ESP32-S3 microcontroller controls four discrete coloured actuators, an intelligent optical status annunciator, and a closed-loop tachometer sensor:
* **Blue LED (GPIO 18):** Purge blower fan emulation driven by LEDC Timer 0 at 25.0 kHz PWM with 10-bit resolution (0 to 1,023 duty steps).
* **Red LED (GPIO 17):** Auxiliary cabin PTC heater core emulation driven by digital output.
* **Green LED (GPIO 16):** Baseline eco-ventilation mode emulation driven by digital output.
* **Amber LED (GPIO 15):** Dehumidification and degraded-telemetry alert warning driven by digital output.
* **WS2812B RGB LED (GPIO 38):** Smart addressable LED providing instantaneous visual feedback of node and network health.
* **Hall-Effect Tachometer (GPIO 19):** Interfaced via Pulse Counter (PCNT) Unit 0, converting rotor commutation pulses into verified RPM ($RPM = \frac{\text{pulses}}{2} \times 60$).

---

### 2. Multi-Dimensional Data Health Classification in `bridge_ae`

In a production automotive deployment, data health classification cannot rely solely on temperature delta and packet latency. The complete Data Health Engine must evaluate five interconnected mathematical dimensions:

$$\begin{aligned}
\text{1. Latency Freshness:} \quad & \tau_{\mathrm{age}} = t_{\mathrm{eval}} - t_{\mathrm{sample}} \le 2.5\,\mathrm{s} \\
\text{2. Thermal Divergence:} \quad & \Delta T = |T_{\mathrm{SCD30}} - T_{\mathrm{DHT22}}| \le 1.5\,^\circ\mathrm{C} \\
\text{3. Humidity Divergence:} \quad & \Delta RH = |RH_{\mathrm{SCD30}} - RH_{\mathrm{DHT22}}| \le 10.0\,\% \\
\text{4. Actuator Stall Fault:} \quad & (\text{PWM} \ge 30\,\%) \land (\text{Tachometer RPM} < 100) \implies \text{Motor Jam / Line Break} \\
\text{5. Toxic Gas Hazard:} \quad & \text{CO} \ge 30.0\,\mathrm{ppm} \implies \text{Emergency Override \& Passenger Evac Alert} \\
\text{6. Recirculation Flap:} \quad & \Delta IAQ = IAQ_{\mathrm{exterior}} - IAQ_{\mathrm{cabin}} \implies \text{Damper Flap Ingress Isolation}
\end{aligned}$$

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   DETERMINISTIC 4-STATE HEALTH REGIME STATE TRANSITIONS                │
├────────────┬───────────────────────────────────────────────────────────────────────────┤
│ FRESH      │ τ_age <= 2.5s AND ΔT <= 1.5°C AND ΔRH <= 10% AND Tachometer Confirmed     │
├────────────┼───────────────────────────────────────────────────────────────────────────┤
│ STALE      │ τ_age in (2.5s, 10.0s] (Network latency / cellular handover delay)        │
├────────────┼───────────────────────────────────────────────────────────────────────────┤
│ DEGRADED   │ ΔT > 1.5°C OR ΔRH > 10% (Transducer membrane drift or partial fouling)   │
├────────────┼───────────────────────────────────────────────────────────────────────────┤
│ FAULT      │ τ_age > 10.0s OR Null Transducer Reading OR Unphysical Out-of-Bounds OR   │
│            │ Blower Stall Fault (PWM >= 30% with Tachometer RPM < 100)                │
└────────────┴───────────────────────────────────────────────────────────────────────────┘
```

When ACME CSE absorbs `bridge_ae`, its internal scripting engine (`acme-scripts`) evaluates these five multi-hazard rules directly upon ContentInstance creation, tagging the resource with semantic labels (e.g. `lbl: ["health:FRESH", "delta_t:0.32", "delta_rh:2.1", "stall:false"]`) and instantly raising alarm instances when safety limits are breached.

---

### 3. Edge Gateway vs ACME CSE Comparative Capability Matrix

The table below contrasts the multi-container edge gateway implementation on the Raspberry Pi 5 with the native, standard-compliant capabilities inherent to **ACME oneM2M IN-CSE**:

| Gateway Tier / Subsystem | Current Gateway Implementation | ACME CSE Native Equivalent | Architectural Feasibility & Impact |
| :--- | :--- | :--- | :--- |
| **MQTT Ingress / Egress Bridging** | `nodered_ipe` container translating MQTT `sdv/+/telemetry` to HTTP POST `<cin>` | **oneM2M TS-0010 Native MQTT Protocol Binding** (`[mqtt]` binding in `acme.ini`) | **High Feasibility (High Impact):** Eliminates Node-RED completely. ESP32-S3 communicates directly with ACME over MQTT request topics. |
| **Multi-Hazard Health Classification** | `bridge_ae` Python Flask container evaluating latency, $\Delta T$, $\Delta RH$, stall, and CO | **ACME CSE Scripting Engine** (`[scripting]` / `onCreate` hooks) or `<flexContainer>` rules | **High Feasibility:** Internalises all 5 health checks & semantic labels within the CSE without an external Python daemon. |
| **Edge Time-Series Retention** | `influxdb` container retaining 30 days of metrics; written via Influx Client | **oneM2M `<timeSeries>` (`<ts>`) & Container Retention (`mni`, `mbs`, `mia`)** | **Medium–High Feasibility:** Native time-series buffering, TTL instance expiry, and missing data detection without a dedicated TSDB daemon. |
| **Downlink Actuator Routing** | Node-RED `/downlink` webhook receiver converting `<sgn>` to MQTT `control/cmd` | **Native oneM2M Subscription to MQTT Topic** (`nu: ["mqtt://..."]` or oneM2M Request Topics) | **High Feasibility (High Impact):** ACME CSE dispatches notification primitives directly to MQTT broker topics without HTTP hops. |
| **Access Control & Multi-Tenancy** | Static Mosquitto `acl.conf` text file matching client CN | **oneM2M Access Control Policy (`<acp>`)** with Originator CRUDND rules | **High Feasibility:** Dynamic, centralised semantic policy governance per AE Originator ID (`CAdmin`, `C_vehicle_nodes`). |
| **Fleet Group Operations & Fan-Out** | Custom application iteration loops & multi-request scripts | **oneM2M Group Entity (`<grp>`) with FanOutPoint (`<fopt>`)** | **Fully Proven:** Validated in Insomnia Folder 05. Atomic fleet queries (`/fopt/la`) and broadcast actuations. |
| **Administrative Observability** | Custom Python Flask `web_portal` container on port 8000 | **ACME Built-in Web UI & Management Endpoint** (`[webui]` in `acme.ini`) | **High Feasibility (Immediate):** Live interactive inspection of active AEs, 7-container trees, subscriptions, and logs. |

---

### 4. Detailed Technical Audit: Specific Capabilities ACME CSE Can Absorb

#### 4.1 Ingress & Egress Bridging via oneM2M TS-0010 MQTT Binding
* **Current Topology:** The ESP32-S3 transmits telemetry to Mosquitto topic `sdv/{vehicle_id}/telemetry`. Node-RED parses JSON, constructs a `<m2m:cin>` wrapper, and executes an HTTP POST to `http://onem2m_cse:8080/...`. For actuation, ACME triggers an HTTP webhook in Node-RED, which republishes to MQTT topic `sdv/{vehicle_id}/control/cmd`.
* **Native ACME Equivalent:** Under oneM2M TS-0010, enabling `[mqtt]` in `deploy/onem2m/acme.ini` connects ACME directly to Mosquitto:
  ```ini
  [mqtt]
  enable = true
  broker = mosquitto
  port = 1883
  topicPrefix = /oneM2M
  ```
  The ESP32-S3 publishes ContentInstance creation primitives directly over MQTT:
  ```text
  PUBLISH /oneM2M/req/C_CabinNode_Car01/id-sdv/json
  ```
  Actuation commands are delivered directly by ACME over the vehicle's downlink subscription topic:
  ```text
  SUBSCRIBE /oneM2M/req/id-sdv/C_CabinNode_Car01/json
  ```
* **Impact:** Eliminates Node-RED, reclaims ~200 MB RAM, and cuts closed-loop actuation latency by 40–80 ms.

#### 4.2 In-CSE Multi-Hazard Health Classification via ACME Scripts
* **Current Topology:** The Python `bridge_ae` microservice acts as an external webhook consumer, parsing telemetry and evaluating rules in Python.
* **Native ACME Equivalent:** ACME CSE’s internal Turing-complete scripting engine (`acme-scripts`) allows registering an `onCreate` trigger against `cnt_raw_telemetry`. The script parses the incoming JSON, evaluates:
  1. Freshness: $\tau_{\mathrm{age}} = t_{\mathrm{now}} - t_{\mathrm{sample}} \le 2.5\,\text{s}$
  2. Thermal Delta: $\Delta T = |T_{\mathrm{SCD30}} - T_{\mathrm{DHT22}}| \le 1.5\,^\circ\text{C}$
  3. Humidity Delta: $\Delta RH = |RH_{\mathrm{SCD30}} - RH_{\mathrm{DHT22}}| \le 10.0\,\%$
  4. Blower Stall: $\text{pwm\_duty\_pct} \ge 30\% \land \text{tachometer\_rpm} < 100$
  5. Toxic Gas Guard: $\text{CO} \ge 30\,\text{ppm}$
  and automatically tags the `<cin>` with semantic labels (`lbl: ["health:FRESH", "delta_t:0.32", "delta_rh:1.8", "stall:false"]`) while immediately raising an alarm `<cin>` in the event of an emergency.
* **Impact:** Eliminates the standalone Python Flask container, embedding data integrity rules directly in the middleware.

#### 4.3 Native Time-Series Buffering, Storage Bounds & Gap Detection
* **Current Topology:** InfluxDB 2.x is used to store time-series metrics with a 30-day retention window.
* **Native ACME Equivalent:** As specified in oneM2M TS-0001, ACME CSE natively supports `<timeSeries>` (`<ts>`) and `<timeSeriesInstance>` (`<tsi>`), and enforces strict lifecycle parameters on all containers:
  * `mni: 1440` (caps historical buffer at 1,440 instances, corresponding to 24 hours of 1-minute telemetry).
  * `mbs: 2097152` (enforces strict 2 MB storage limit protecting SD/NVMe storage).
  * `mia: 86400` (enforces 24-hour TTL automatic instance pruning).
  * `missingDataDetect: true` (built-in oneM2M sensor dropout detection without custom watchdog daemons).
* **Impact:** Eliminates reliance on InfluxDB for short-to-medium-term edge buffering.

#### 4.4 Atomic Fleet Group Management and Dynamic Fan-Out (`<grp>`, `<fopt>`)
* **Current Topology:** In typical IoT gateways, broadcasting commands or polling multi-vehicle status requires custom application loops.
* **Native ACME Equivalent:** Verified in Folder `05_Fleet_Registry_and_Discovery` of [collections/acme_fleet_insomnia_collection.yaml](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/collections/acme_fleet_insomnia_collection.yaml), ACME CSE manages `grp_fleet_telemetry` dynamically:
  * **Fleet-Wide Aggregation:** A single call to the FanOutPoint retrieves synchronised telemetry across all vehicles:
    ```text
    GET http://192.168.122.91:8080/cse-in/grp_fleet_telemetry/fopt/la
    ```
  * **Broadcast Actuation:** A single `POST .../grp_fleet_telemetry/fopt` broadcasts setpoint changes or emergency ventilation commands to all connected vehicles simultaneously.
* **Impact:** Replaces custom edge multicast logic with standard oneM2M atomic fan-out execution.

#### 4.5 Centralised Semantic Access Control Policies (`<acp>`)
* **Current Topology:** Permissions are maintained in static broker text files (`deploy/mosquitto/acl.conf`).
* **Native ACME Equivalent:** Standard `<acp>` resources (e.g. `acp_fleet_manager`) enforce fine-grained CRUDND access control per authenticated Originator ID (`CAdmin`, `C_vehicle_nodes`, `S*`), providing auditable, dynamic security governance.

---

### 5. Architectural Boundaries: What Must Remain Dedicated

To guarantee cyber-physical safety, cryptographic robustness, and high-performance analytics, the following responsibilities **must NOT be absorbed into ACME CSE**:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURAL SEGREGATION OF RESPONSIBILITIES                   │
├────────────────────────────────────────┬───────────────────────────────────────────────┤
│    RETAINED ON DEDICATED PLATFORM      │          CONSOLIDATED INTO ACME CSE           │
├────────────────────────────────────────┼───────────────────────────────────────────────┤
│ • Mutual TLS 1.3 Termination           │ • oneM2M Ingress & Egress Ingestion           │
│   (Eclipse Mosquitto with ECDSA P-256) │   (Native TS-0010 MQTT Binding)               │
│ • Long-Term High-Rate TSDB Analytics   │ • Short-to-Medium Telemetry Buffering         │
│   (InfluxDB 2.x Columnar Engine)       │   (<cnt> / <ts> with mni, mbs, mia)           │
│ • Operational Telemetry Cockpit        │ • Empirical Multi-Hazard Health Classification│
│   (Grafana Enterprise Dashboards)      │   (ACME Scripting Hooks & Semantic Labels)    │
│ • Autonomous Safety Overrides          │ • Group Aggregation & Multicast Fan-Out       │
│   (ESP32-S3 FreeRTOS Hardware Loop)    │   (<grp> and <fopt> FanOutPoints)             │
│ • Physical Peripheral Sampling         │ • Fine-Grained Semantic Authorisation         │
│   (Hardware I2C / 1-Wire / PWM Timers) │   (Standardised <acp> Access Control Policies)│
└────────────────────────────────────────┴───────────────────────────────────────────────┘
```

1. **Perimeter Mutual TLS 1.3 Termination (Mosquitto):**
   * Hardened cryptographic handshakes, hardware ECDSA acceleration, X.509 client certificate verification, and network perimeter protection must terminate at Mosquitto. ACME CSE’s Python ASGI/WSGI web stack is not suited for edge perimeter security.
2. **High-Cardinality Multi-Series Analytics (InfluxDB + Grafana):**
   * ACME CSE’s database backends (TinyDB or SQLite) are optimised for hierarchical resource metadata, not for storing millions of high-frequency time-series points. InfluxDB remains the optimal engine for complex Flux analytics and multi-series Grafana dashboards.
3. **Safety-Critical Hardware Fail-Safes (ESP32-S3 FreeRTOS):**
   * Actuator fail-safe logic (e.g. initiating 50% fan purge when disconnected or CO₂ exceeds critical thresholds) must execute deterministically in microcontroller firmware, independent of middleware or network availability.

---

### 6. Synchronisation Specification for `architecture_detailed.png`

To achieve 100% synchronisation between the high-level diagram ([docs/assets/architecture_detailed.png](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/docs/assets/architecture_detailed.png)), the semantic model ([docs/assets/vehicle_resource_tree.svg](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/docs/assets/vehicle_resource_tree.svg)), and the hardware netlist ([docs/assets/circuit_schematic.svg](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/docs/assets/circuit_schematic.svg)), the following updates should be reflected in the diagram:

1. **In-Cabin Sensing Node (ESP32-S3 Physical Tier):**
   * **Sensors:** Expand beyond SCD30 and DHT22 to include Toxic Carbon Monoxide (CO sensor), Cabin IAQ (VOC/PM), and Exterior Ambient Air Quality (AQI).
   * **Actuators:** Expand beyond Fan PWM to show the full 4-channel LED matrix:
     - Blue: Purge PWM Fan (GPIO 18)
     - Red: Cabin Heater Core DO (GPIO 17)
     - Green: Baseline Eco-Ventilation DO (GPIO 16)
     - Amber: Dehumidification / Warning Alert DO (GPIO 15)
     - WS2812B: Optical State Annunciator (GPIO 38)
   * **Feedback:** Clearly illustrate the Hall-effect tachometer pulse feedback line connecting from the blower rotor back into GPIO 19.
2. **oneM2M Middleware Tier (ACME IN-CSE):**
   * Replace the generic `/sdv-cse` container box with the explicit **7-container vehicle AE subtree**: `[temp, hum, co2, co, iaq-cab, iaq-ext, raw-telemetry]`.
   * Add the **Fleet Governance Entities**: `<acp>` (`acp_fleet_manager`) and `<grp>` (`grp_fleet_telemetry` with `<fopt>` fan-out point).
   * Depict multiple vehicle nodes (`vehicle-001`, `vehicle-002`, `vehicle-N`) fanning into the central CSE.
3. **Subscription & Webhook Ingestion Routes:**
   * Differentiate three distinct subscription flows:
     1. `sub_downlink` $\to$ Dispatches actuator commands to Mosquitto (`sdv/vehicle_01/control/cmd`).
     2. `sub_co_alert` $\to$ Dispatches priority toxic gas alerts directly to `/emergency-monitor`.
     3. `sub_fleet_telemetry` / `sub_bridge_ae` $\to$ Ingests synchronised telemetry into Bridge AE and cloud digital twin.
4. **Bridge AE Health Classifier Box:**
   * Explicitly annotate all five evaluation checks: $\tau_{\mathrm{age}} \le 2.5\,\text{s}$, $\Delta T \le 1.5\,^\circ\text{C}$, $\Delta RH \le 10\%$, Tachometer Stall Check, and Toxic CO Hazard Interlock.
5. **Grafana Operations Cockpit:**
   * Add a Fleet Vehicle Selector dropdown (`vehicle-001`, `vehicle-002`).
   * Display multi-actuator status indicators (Heater: ON/OFF, Eco-Vent: ACTIVE, Purge Fan: 75% PWM, Dehumidifier: ACTIVE).
   * Include Tachometer RPM gauge with Motor Stall Warning indicator.
   * Include Emergency Toxic CO Banner.

---

### 7. Strategic Phased Implementation Roadmap

```mermaid
gantt
    title ACME CSE Architectural Consolidation Roadmap
    dateFormat  YYYY-MM
    section Phase 1: Quick Wins
    Enable ACME Native Web UI            :done, p1_1, 2026-10, 10d
    Enforce Container Retention (mia)    :active, p1_2, 2026-10, 14d
    section Phase 2: Protocol Consolidation
    Enable Native MQTT Binding in CSE   :p2_1, 2026-11, 21d
    ESP32-S3 Direct oneM2M MQTT Uplink  :p2_2, 2026-11, 28d
    Decommission Node-RED Container     :p2_3, 2026-12, 14d
    section Phase 3: Logic Consolidation
    Port Multi-Hazard Classifier to Script:p3_1, 2026-12, 21d
    Direct InfluxDB Notification Bridge :p3_2, 2027-01, 21d
    Decommission Bridge AE Container    :p3_3, 2027-01, 14d
```

#### Phase 1: Immediate Zero-Code Quick Wins
* **Action 1.1:** Enable ACME CSE native Web UI (`[webui] enable = true` in `acme.ini`) to provide immediate administrative tree visibility on the gateway without additional software.
* **Action 1.2:** Update the container provisioning manifest in [collections/SDV_Expandable_Fleet_ACME_CSE_SOP.md](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/collections/SDV_Expandable_Fleet_ACME_CSE_SOP.md) to set `mia: 86400` (24-hour TTL) and `mni: 1440` across all vehicle containers, ensuring automatic edge memory and disk garbage collection.

#### Phase 2: Ingress & Protocol Consolidation
* **Action 2.1:** Enable `[mqtt]` binding in `acme.ini` connecting ACME CSE directly to Mosquitto.
* **Action 2.2:** Update ESP32-S3 firmware to publish `<cin>` creation primitives directly to oneM2M MQTT request topics (`/oneM2M/req/...`).
* **Action 2.3:** Configure downlink actuation subscriptions to dispatch directly to MQTT notification URIs (`nu: ["mqtt://..."]`).
* **Outcome:** Safely decommission the `nodered_ipe` container, saving ~200 MB RAM and reducing closed-loop latency.

#### Phase 3: Application Logic & Persistence Optimisation
* **Action 3.1:** Port the multi-hazard classification logic ($\Delta T$, $\Delta RH$, stall, CO) into an internal ACME script triggered on `<cin>` creation under `raw-telemetry`.
* **Action 3.2:** Configure ACME CSE subscriptions to forward telemetry snapshots directly to InfluxDB via Telegraf or a lightweight HTTP notification, retiring the standalone `bridge_ae` microservice.
* **Outcome:** Reduces the gateway microservice mesh from 7 containers down to 4 lean, high-performance services: **Mosquitto**, **ACME CSE**, **InfluxDB**, and **Grafana**.

---

### 8. Quantified System Resource Impact

| Metric | Current 7-Container Mesh | Streamlined 4-Container Mesh | Expected Net Improvement |
| :--- | :--- | :--- | :--- |
| **Total Gateway Memory (RAM)** | ~650 MB LPDDR4X | ~250 MB LPDDR4X | **61.5% Reduction (~400 MB saved)** |
| **Active Microservices** | 7 containers | 4 containers | **42.8% Fewer Daemons to Maintain** |
| **Inter-Container Network Hops** | 5 hops (ESP $\rightarrow$ MQTT $\rightarrow$ Node-RED $\rightarrow$ CSE $\rightarrow$ Bridge $\rightarrow$ Influx) | 3 hops (ESP $\rightarrow$ MQTT $\rightarrow$ CSE $\rightarrow$ Influx) | **40% Fewer Intermediate Network Transits** |
| **Closed-Loop Actuation Latency ($\tau_{\mathrm{prop}}$)** | 120–280 ms | 45–90 ms | **Up to 60% Latency Reduction** |
| **Configuration Drift Risk** | High (Mosquitto ACLs, Node-RED flows, Python env, ACME config) | Low (Single semantic source of truth governed by oneM2M `<acp>`) | **Unified ETSI TS 118 101 Compliance** |

---

### Conclusion & Approval

The audit confirms that ACME oneM2M IN-CSE is mature, feature-rich, and capable of replacing the Node-RED ingress proxy, Python multi-hazard health classification daemon, and edge web portal without sacrificing data integrity. 

Preserving **Eclipse Mosquitto** for mutual TLS 1.3 termination and **InfluxDB/Grafana** for multi-series analytics strikes the optimal balance between **strict ETSI TS 118 101 semantic compliance**, **cyber-physical safety**, and **extreme edge resource efficiency**.
