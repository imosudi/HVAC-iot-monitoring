# 02. Use Case & Scenario Documents (UCSD)

## Software-Defined Vehicle (SDV) Cyber-Physical Cabin Environmental Monitoring and Closed-Loop HVAC Regulation System

---

## Document Control & Attribution

| Attribute | Specification Detail |
| :--- | :--- |
| **Document Designation** | Use Case & Scenario Documents (UCSD) |
| **Project Title** | Cyber-Physical Cabin Environmental Monitoring & Closed-Loop HVAC Regulation in Software-Defined Vehicles |
| **Researcher & Architecture** | **Isiaka Mosudi** (Middleware & Distributed Systems Architecture) |
| **Research Team** | **Isiaka Mosudi**, Ashok Ramalingam, Pooja Janwalkar, AnnaMaria Moçi, Julia Philip |
| **GitHub Repository** | [https://github.com/imosudi/HVAC-iot-monitoring](https://github.com/imosudi/HVAC-iot-monitoring) |
| **Status & Compliance** | Released / Verified (IEEE 29148, oneM2M TS-0001) |

---

## 1. Actor Taxonomy & Cyber-Physical Role Matrix
The platform defines eight distinct actors interacting with the cyber-physical system:

| Actor ID | Actor Designation | Role Description & Demarcation |
| :--- | :--- | :--- |
| **ACT-01** | **In-Cabin Passenger** | Generates metabolic $\text{CO}_2$ and humidity; benefits from automated air quality regulation. |
| **ACT-02** | **Vehicle Driver** | Operates the vehicle; subject to drowsiness degradation if $\text{CO}_2 > 1200\text{ ppm}$. |
| **ACT-03** | **AD-ECU / Autonomous Agent** | Autonomous driving computer requiring cabin occupant alertness assurances. |
| **ACT-04** | **Fleet Operations Supervisor** | Monitors multi-vehicle fleet health via Grafana and Web Portal; executes remote overrides. |
| **ACT-05** | **Test / Commissioning Engineer**| Utilises `make menu` TUI to deploy stacks, audit hardware, and run fault injection tests. |
| **ACT-06** | **Micro-ECU Sensor Node (SCN)**| Samples physical environment, performs local cross-checks, drives PWM blower and LED array. |
| **ACT-07** | **Vehicular Edge Gateway** | Buffers serial telemetry, validates schemas, and maintains mTLS 1.3 uplink transport. |
| **ACT-08** | **Base CSE Central Infrastructure**| Hosts oneM2M resource tree, certifies data health, and records time-series analytics. |

---

## 2. Primary Nominal Operational Use Cases

### UC-01: Continuous Cabin Air Quality Monitoring & Nominal Eco-Ventilation
- **Primary Actor:** Micro-ECU (ACT-06) / Vehicular Edge Gateway (ACT-07).
- **Trigger:** Periodic $2.0\text{ s}$ sampling timer fires on ESP32-S3 FreeRTOS core.
- **Pre-Conditions:** Transducers initialised; mTLS 1.3 connection to Mosquitto established.
- **Main Success Scenario:**
  1. Micro-ECU samples SCD30 ($\text{CO}_2 = 620\text{ ppm}$, $T = 22.4^\circ\text{C}$, $\text{RH} = 45\%$) and DHT22 ($T = 22.5^\circ\text{C}$, $\text{RH} = 46\%$).
  2. Micro-ECU validates inter-sensor delta ($|T_{scd30} - T_{dht22}| = 0.1^\circ\text{C} \le 1.5^\circ\text{C}$).
  3. Micro-ECU serialises JSON frame and pushes to Edge Gateway across UART at $115{,}200\text{ baud}$.
  4. Edge Gateway validates frame against `telemetry_schema.json` and publishes to MQTT topic `sdv/vehicle_01/telemetry`.
  5. Node-RED IPE wraps frame into oneM2M `<m2m:cin>` and posts to `/sdv-cse/AE_CabinNode_Car01/cnt_raw_telemetry`.
  6. Bridge AE validates data latency ($\tau_{age} = 0.45\text{ s} \le 2.5\text{ s}$) and classifies record as `FRESH`.
  7. InfluxDB stores metrics; Green Eco LED illuminates on Micro-ECU; blower maintains quiet $25\%$ PWM baseline.
- **Post-Conditions:** Cabin metrics committed to InfluxDB; Green LED active; cabin air remains fresh.

### UC-02: Passenger Respiration Surge & Elevated Air Flushing
- **Primary Actor:** In-Cabin Passenger (ACT-01) / Base CSE (ACT-08).
- **Trigger:** Cabin $\text{CO}_2$ exceeds $800\text{ ppm}$ ($800 < \text{CO}_2 \le 1200\text{ ppm}$) due to passenger metabolic exhalation.
- **Main Success Scenario:**
  1. SCD30 measures $\text{CO}_2 = 950\text{ ppm}$. Telemetry ingested and certified `FRESH`.
  2. Actuation heuristic determines elevated flush regime.
  3. Control loop creates `<m2m:cin>` in `/sdv-cse/AE_CabinNode_Car01/cnt_actuation_cmd` with `target_pwm = 60`.
  4. Node-RED receives oneM2M notification and publishes `{"target_pwm": 60, "mode": "AUTOMATIC"}` to `sdv/vehicle_01/control/cmd`.
  5. Edge Actuator Module commands ESP32-S3: `CMD:PWM=60,MODE=AUTOMATIC`.
  6. ESP32-S3 ramps Blue LED to $60\%$ duty cycle and modulates fresh air flap to increase outdoor air intake.
  7. Tachometer registers $1{,}800\text{ RPM}$, confirming air movement.
- **Post-Conditions:** Cabin $\text{CO}_2$ concentration stabilises and drops below $800\text{ ppm}$.

### UC-03: Rapid Emergency Air Purging & Alert Warning
- **Primary Actor:** Driver (ACT-02) / Base CSE (ACT-08).
- **Trigger:** Rapid $\text{CO}_2$ accumulation exceeding safety threshold ($> 1200\text{ ppm}$).
- **Main Success Scenario:**
  1. SCD30 detects $\text{CO}_2 = 1450\text{ ppm}$ in passenger compartment.
  2. Telemetry classified `FRESH`; emergency purge heuristic triggers immediately.
  3. oneM2M downlink dispatches `target_pwm = 100`.
  4. ESP32-S3 ramps Blue LED to $100\%$ duty cycle and activates Amber Alert LED.
  5. Visual warning posted to Grafana dashboard and Web Portal.
  6. High-volume air exchange purges passenger compartment until $\text{CO}_2 < 1000\text{ ppm}$.
- **Post-Conditions:** Drowsiness risk eliminated; system returns to elevated flush regime.

### UC-04: Psychrometric Defrost & Rapid Window Dehumidification Cycle
- **Primary Actor:** Micro-ECU (ACT-06) / Base CSE (ACT-08).
- **Trigger:** Relative humidity spikes $> 70\%$ while window surface temperature drops below dew point $T_{dp}$.
- **Main Success Scenario:**
  1. Bridge AE calculates dew point: $T_{dp} = T - (100 - \text{RH})/5 = 21.0 - (100 - 80)/5 = 17.0^\circ\text{C}$.
  2. With window surface at $15.0^\circ\text{C}$, catastrophic windshield condensation risk is identified.
  3. Downlink command dispatches dehumidification mode (`target_pwm = 50`, `mode = AUTOMATIC`).
  4. ESP32-S3 activates Amber Defrost LED and modulates air blend damper toward windshield vents.
- **Post-Conditions:** Cabin humidity reduced; window fogging prevented.

### UC-05: Cold-Start Auxiliary PTC Cabin Pre-Heating
- **Primary Actor:** Passenger (ACT-01) / Micro-ECU (ACT-06).
- **Trigger:** Cabin temperature drops below comfort baseline ($T_{cabin} < 19.0^\circ\text{C}$).
- **Main Success Scenario:**
  1. Sensor stream reports $T_{scd30} = 14.5^\circ\text{C}$.
  2. Heating heuristic engages auxiliary PTC heating element.
  3. ESP32-S3 illuminates Red Heat LED and commands $25\%$ blower circulation.
  4. Cabin temperature steadily recovers to $21.5^\circ\text{C}$, whereupon Red LED switches off.
- **Post-Conditions:** Cabin thermal comfort restored.

---

## 3. Degraded, Edge, and Fault Condition Use Cases

### UC-06: Inter-Transducer Divergence Detection & Drift Isolation (`DEGRADED`)
- **Trigger:** Thermal drift causes SCD30 and DHT22 to diverge by $> 1.5^\circ\text{C}$ ($|T_{scd30} - T_{dht22}| > 1.5^\circ\text{C}$) or humidity by $> 10\%$.
- **System Response:**
  1. Bridge AE classifier evaluates piecewise condition: $\Delta T > 1.5^\circ\text{C}$.
  2. Health state transitions to `DEGRADED`.
  3. WS2812B LED on Micro-ECU turns solid Amber.
  4. Record written to InfluxDB with tag `health_state=DEGRADED`.
  5. Control loop maintains conservative baseline regulation while alerting maintenance.
- **Post-Conditions:** Fault contained without abrupt service termination; diagnostic log generated.

### UC-07: Ingress Communication Jitter & Stale Telemetry (`STALE`)
- **Trigger:** Telemetry transport delay exceeds nominal latency threshold ($2.5\text{ s} < \tau_{age} \le 10.0\text{ s}$).
- **System Response:**
  1. Bridge AE calculates $\tau_{age} = t_{eval} - t_{sample} = 3.8\text{ s}$.
  2. Health state transitions to `STALE`.
  3. Time-series recorded with `health_state=STALE`.
  4. Downlink actuation holds previous valid control setpoint without sudden step changes.
- **Post-Conditions:** Temporary network jitter absorbed safely.

### UC-08: Sensor Hardware Disconnect & Non-Coercive Fault Containment (`FAULT`)
- **Trigger:** Physical sensor cable severed or $\text{I}^2\text{C}$ bus timeout occurs.
- **System Response:**
  1. Micro-ECU serialises JSON payload with `"temperature_c": null`.
  2. Ingress client passes `null` without zero-coercion.
  3. Bridge AE flags null field and assigns deterministic health state `FAULT`.
  4. Downlink controller drops to safe default ventilation ($25\%$ baseline) instead of engaging maximum heat.
  5. WS2812B illuminates solid RED.
- **Post-Conditions:** Zero-coercion prevents dangerous runaway heating or actuator burnout.

### UC-09: Blower Mechanical Stall & Locked Impeller Safety Shutdown
- **Trigger:** Command is $\ge 30\%$ PWM but tachometer feedback reports $< 100\text{ RPM}$.
- **System Response:**
  1. Micro-ECU PCNT pulse counter observes zero pulses during $1000\text{ ms}$ evaluation window.
  2. Mechanical stall detected.
  3. ESP32-S3 immediately cuts PWM to $0\%$ to prevent motor winding fire.
  4. Diagnostic state `FAULT` reported upstream; alert tone sounded.
- **Post-Conditions:** Motor protected from electrical thermal damage; maintenance alert raised.

### UC-10: Vehicular Backhaul Severance & Autonomous Edge Fallback
- **Trigger:** Vehicular cellular/Wi-Fi connection to Base CSE platform drops completely.
- **System Response:**
  1. Edge Gateway detects MQTT socket severance and begins caching serial frames to local disk buffer.
  2. Micro-ECU notices loss of downlink heartbeat ($> 15\text{ s}$).
  3. Micro-ECU enters autonomous standalone closed-loop fallback mode: internal FreeRTOS task regulates blower PWM based on direct local SCD30 readings.
  4. Upon network restoration, Edge Gateway flushes buffered telemetry with original timestamps.
- **Post-Conditions:** Zero loss of passenger climate safety during backhaul outages.

---

## 4. Administrative, Supervisory & Operational Use Cases

### UC-11: Manual Actuation Override via Web Operations Cockpit
- **Primary Actor:** Fleet Operations Supervisor (ACT-04).
- **Trigger:** Supervisor commands manual fan override (`PWM = 85%`) via Web Portal UI.
- **System Response:**
  1. Web Portal dispatches `POST /api/actuator/dispatch` with payload `{"target_pwm": 85, "mode": "MANUAL_OVERRIDE"}`.
  2. API issues oneM2M `<m2m:cin>` creation to ACME CSE.
  3. oneM2M webhook notifies Node-RED, which publishes to `sdv/vehicle_01/control/cmd`.
  4. ESP32-S3 receives directive, overrides autonomous heuristic, and locks PWM to $85\%$.
- **Post-Conditions:** Manual operational setpoint enforced until supervisory reset.

### UC-12: Interactive TUI Multi-Host Provisioning & Pre-Flight Diagnostics
- **Primary Actor:** Test / Commissioning Engineer (ACT-05).
- **Trigger:** Operator executes `make menu` in terminal.
- **System Response:**
  1. Interactive TUI dashboard launches ([`deploy/menu.sh`](file:///home/mosud/Documents/dev/HVAC-iot-monitoring/deploy/menu.sh)).
  2. Operator selects option `[7]` (Pre-Flight Diagnostics Suite) -> sub-option `[3]` (`--setup-passwordless`) to configure and verify passwordless SSH key authentication against the remote targets (`iotgwai` / `192.168.122.165` and `iotaigw`).
  3. System audits Docker daemons, user group memberships, sysfs GPIOs, and serial ports, returning green verification blocks.
  4. Operator selects option `[1]` (Distributed Multi-Host Deployment): TUI dynamically resolves remote `$HOME` paths on server and Raspberry Pi 5, generates `.env`, copies containers, and bootstraps the distributed service mesh.
- **Post-Conditions:** Multi-host cyber-physical testbed fully verified and operational.
