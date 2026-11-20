# System Architecture Specification

## Cyber-Physical Cabin Environmental Monitoring and Closed-Loop HVAC Regulation in Software-Defined Vehicles

**Milestone:** MVP Release 1.0 with MMP and MLP Architectural Continuum  
**Academic Affiliation:** University of Applied Sciences Technikum Wien (FH Technikum Wien)  
**Research Cluster:** Distributed Cyber-Physical Systems and Automotive IoT (FHTW-AIOT, Group MIO3B)  

---

### 1. Architectural Overview and Guiding Principles

The software-defined vehicle (SDV) architectural paradigm decouples vehicular physical sensing and actuation from static electronic control units (ECUs). This project implements an integrated cyber-physical environmental monitoring and closed-loop HVAC regulation pipeline characterised by three structural pillars:

1. **Deterministic Edge Computing (ETSI GS MEC 003):** Sensor processing and real-time actuation operate locally onboard the vehicular MEC host, bounding closed-loop latency ($\tau_{\mathrm{prop}} \le 1{,}200\,\mathrm{ms}$) and preserving vehicle operational continuity during wide-area wireless network blackouts.
2. **Standardised Semantic Middleware (ETSI TS 118 101):** Telemetry streams and actuation directives are abstracted into uniform oneM2M resources (`<AE>`, `<container>`, `<contentInstance>`), decoupling physical sensing hardware from operational dashboards and third-party algorithmic services.
3. **Multi-Horizon Evolution (MVP, MMP, MLP):** The system transitions from a single-zone cabin node and vehicular edge host (MVP) to multi-zone zonal compute architectures with oneM2M Mcc inter-CSE federation (MMP), and ultimately to federated cognitive edge AI with ISO 7730 thermal comfort modelling and cooperative V2X air-quality forecasting (MLP).

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           VEHICULAR CYBER-PHYSICAL SYSTEM                       │
└─────────────────────────────────────────────────────────────────────────────────┘
 [ Firmware Tier: ESP32-S3 ]       [ Vehicle-Based: Module 2 ]       [ Server / Network: Module 1 ]
 ESP32-S3 Dual-Core SoC           Raspberry Pi 5 (Vehicle AE)       Central Server / VM
 ┌────────────────────────┐       ┌───────────────────────────┐     ┌─────────────────────────────┐
 │ Sensirion SCD30 (I2C)  │─UART─>│ sdv_edge_serial_client    │mTLS │ Eclipse Mosquitto Broker    │
 │ CO2, Temp, RH (CRC-8)  │115200 │ (Outbound Only, 0 Ingress)├────>│ Port 8883, X.509 Client Auth│
 │ Coloured LED Actuators │<──────┤ sdv_actuator_module       │<────│ Topic: sdv/vehicle_01/#     │
 │ PCNT / WS2812B Annunc. │       └───────────────────────────┘     └──────────────┬──────────────┘
 └────────────────────────┘                                                        │ TS-0010 MQTT
                                                                                   ▼
                                                                    ┌─────────────────────────────┐
                                                                    │ oneM2M IN-CSE: /sdv-cse     │
                                                                    │ Zero AEs at Boot •          │
                                                                    │ ACMEScripts (Replaces NR)   │
                                                                    └──────────────┬──────────────┘
                                                                                   │
                                                        ┌──────────────────────────┴──────────────┐
                                                        │ Sub_BridgeAE                            │ Sub_Downlink
                                                        ▼                                         ▼
                                         ┌─────────────────────────────┐           ┌─────────────────────────────┐
                                         │ Bridge AE Classifier        │           │ Downlink Command Dispatcher │
                                         │ 4-State Data Health Machine │           │ Translates <cin> to MQTT    │
                                         └──────────────┬──────────────┘           └─────────────────────────────┘
                                                        │
                                                        ▼
                                         ┌─────────────────────────────┐
                                         │ InfluxDB 2.x TSDB           │
                                         │ Nanosecond Line-Protocol    │
                                         └──────────────┬──────────────┘
                                                        │
                                                        ▼
                                         ┌─────────────────────────────┐
                                         │ Grafana & Web Portal        │
                                         │ Dynamic Actuator Thresholds │
                                         └─────────────────────────────┘
```

---

### 2. Physical Sensing and Actuation Tier (Embedded Firmware)

The physical tier executes on an Espressif ESP32-S3 dual-core microcontroller clocked at 240 MHz, running FreeRTOS with strict core affinity:

* **Core 1 (Physical Loop):** Executes transducer sampling, hardware filtering, PWM modulation of coloured LED actuators, and pulse accumulation.
* **Core 0 (Network Loop):** Executes the mbedTLS 1.3 stack, MQTT client state machine, connection keep-alives, and JSON payload serialisation.

#### 2.1 Unified Environmental Sensing (Sensirion SCD30)
* **Sensirion SCD30:** Replaces the legacy dual-sensor (DHT22 + separate CO₂) setup with a single unified transducer interfacing over I²C Fast-Mode at 400 kHz on GPIO 8 (SDA) and GPIO 9 (SCL). Samples carbon dioxide concentration via Non-Dispersive Infrared (NDIR) spectroscopy (400 to 10,000 ppm), dry-bulb temperature (-40 to +70 °C), and relative humidity (0 to 100 %). Every 16-bit word is validated using hardware CRC-8 polynomials ($P(x) = x^8 + x^5 + x^4 + 1$).

#### 2.2 Coloured LED Actuator Emulation Paradigm
For the MVP deployment, physical mechanical actuators (such as 12 V high-current centrifugal blower fans, PTC heater elements, and motorised air flaps) are emulated using discrete coloured LEDs driven directly by the ESP32-S3 microcontroller. This avoids high-voltage power hazards, bench acoustic disturbance, and high thermal dissipation while strictly validating the closed-loop cyber-physical control pipeline:

* **Blue LED Actuator (Purge Ventilation / Cooling):** Driven on GPIO 18 by the LEDC timer using 25.0 kHz PWM with 10-bit resolution (0 to 1,023 duty steps). Luminous intensity visualises commanded fan purge speed (0 to 100% duty cycle) dispatched upon elevated carbon dioxide concentration (> 800 ppm).
* **Red LED Actuator (Cabin Heating):** Driven on GPIO 17, illuminating when cabin temperature drops below 19.0 °C to emulate auxiliary heater core activation.
* **Green LED Actuator (Baseline Eco-Ventilation):** Driven on GPIO 16, illuminating during nominal air quality (CO₂ between 400 and 800 ppm, temperature between 20.0 and 23.5 °C).
* **Amber LED Actuator (Alert / Dehumidification):** Driven on GPIO 15, active during elevated relative humidity (> 65%) or when the Bridge AE flags a `DEGRADED` or `STALE` health status.

#### 2.3 Closed-Loop Actuator Feedback
To confirm actuator command reception and detect electrical fault conditions, the feedback loop reads back GPIO logic states and duty cycles. In bench setups with tachometer pulse emulation, pulse accumulation over 1.0-second integration windows calculates simulated rotor revolutions per minute (RPM).

#### 2.4 Optical Node Health Annunciation
A single-wire WS2812B addressable RGB LED on GPIO 38 provides visual feedback of overall node and network health:
* Green: Nominal telemetry streaming over mutual TLS 1.3.
* Amber: Warning state ($\tau_{\mathrm{age}} > 2.5\,\mathrm{s}$ or SCD30 rate-of-change / CRC retry warning).
* Red: Transducer fault or broker disconnection.
* Blue: High CO₂ purge ventilation active (75% duty cycle).
* Cyan: Closed-loop fail-safe override engaged (50% duty cycle).

---

### 3. Transport Security and Edge Gateway Tier

#### 3.1 Mutual TLS 1.3 Enforcement
All communications crossing the vehicular wireless or wired edge boundary terminate at the Eclipse Mosquitto broker on port 8883. Both the broker and edge clients present X.509 certificates issued by a private vehicular Root CA:
* TLS version restricted to 1.3.
* Server verification flag `require_certificate true`.
* Revocation and subject verification enforce per-vehicle isolation.

#### 3.2 Granular Topic Access Control Lists (ACLs)
Mosquitto enforces vehicular partition boundaries:
* Uplink telemetry: `sdv/{vehicle_id}/telemetry` (Client write, IPE read).
* Downlink actuation: `sdv/{vehicle_id}/control/cmd` (IPE write, Client read).
* Wildcard subscriptions across vehicles are restricted to administrative gateways.

---

### 4. oneM2M Semantic Middleware Architecture

The middleware layer conforms to ETSI TS 118 101, exposing standard Mca and Mcc reference points:

#### 4.1 Resource Hierarchy under `/sdv-cse`
```text
/sdv-cse (CSEBase, IN-CSE)
 └── AE_CabinNode_Car01 (Application Entity)
      ├── cnt_raw_telemetry (Container)
      │    ├── cin_xxxx (ContentInstances: raw frames)
      │    └── sub_bridge_consumer (Subscription -> Bridge AE)
      ├── cnt_co2 (Container: scalar CO2 time series)
      ├── cnt_temperature (Container: primary and redundant temp)
      ├── cnt_humidity (Container: relative humidity)
      ├── cnt_data_health (Container: categorical health states)
      └── cnt_actuator_commands (Container: downlink directives)
           └── sub_downlink_dispatcher (Subscription -> Native oneM2M TS-0010 MQTT Bus)
```

#### 4.2 ACMEScripts & Native TS-0010 MQTT Ingestion
Replacing the legacy Node-RED Ingress IPE, ACME IN-CSE's built-in **ACMEScripts** engine and native `[mqtt]` TS-0010 binding ingest MQTT frames from Mosquitto directly, validate payloads, construct `<contentInstance>` primitives under `/sdv-cse/<vehicle-id>/raw-telemetry`, and evaluate closed-loop actuation rules.

---

### 5. Empirical Data Health Classification Engine

ACMEScripts / the Python Bridge AE evaluate incoming SCD30 sensor records against temporal latency ($\tau_{\mathrm{age}} = t_{\mathrm{eval}} - t_{\mathrm{sample}}$), hardware CRC-8 integrity, physical bounds, and rate-of-change stability:

Categorical state assignment follows deterministic criteria:
1. **`FRESH`:** $\tau_{\mathrm{age}} \le 2.5\,\mathrm{s}$, valid SCD30 CRC-8, and nominal rate-of-change. Data valid for closed-loop control.
2. **`STALE`:** $2.5\,\mathrm{s} < \tau_{\mathrm{age}} \le 10.0\,\mathrm{s}$. Data acceptable for display; control rules employ hold-last-value logic.
3. **`DEGRADED`:** Transient SCD30 rate-of-change spike or I²C CRC retry while $\tau_{\mathrm{age}} \le 10.0\,\mathrm{s}$; system logs warning and applies conservative smoothing.
4. **`FAULT`:** $\tau_{\mathrm{age}} > 10.0\,\mathrm{s}$, transducer disconnection, blower stall, or out-of-bounds readings. Numerical values are excluded from time-series aggregation, and the blower defaults to 50% baseline fail-safe ventilation.

---

### 6. Closed-Loop Regulation and Observability

* **InfluxDB 2.x:** Telemetry and categorical health tags are committed synchronously with nanosecond timestamps into bucket `cabin_telemetry`.
* **Grafana Operational Cockpit:** Displays real-time metrics, differential temperature plots, and tachometer feedback. Closed-loop alert rules trigger when carbon dioxide exceeds 800 ppm, automatically posting actuation directives to `/sdv-cse/AE_CabinNode_Car01/cnt_actuator_commands` to engage 75% cabin purge ventilation until concentration falls below 750 ppm.
