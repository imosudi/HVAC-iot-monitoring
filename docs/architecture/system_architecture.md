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
 [ In-Cabin Physical Tier ]                         [ Onboard Vehicular MEC Host ]
 ESP32-S3 Dual-Core SoC                             Raspberry Pi 5 (Podman / Docker Mesh)
 ┌────────────────────────┐                         ┌─────────────────────────────┐
 │ Sensirion SCD30 (I2C)  │                         │ Eclipse Mosquitto Broker    │
 │ DHT22 1-Wire Sensor    │──[mTLS 1.3: Port 8883]─>│ Port 8883, X.509 Client Auth│
 │ 25 kHz Blower PWM      │<────────────────────────│ Topic: sdv/vehicle_01/#     │
 │ PCNT Hall Tachometer   │                         └──────────────┬──────────────┘
 │ WS2812B Optical Status │                                        │
 └────────────────────────┘                                        ▼
                                                    ┌─────────────────────────────┐
                                                    │ Node-RED Ingress IPE        │
                                                    │ Schema Validation & Mca REST│
                                                    └──────────────┬──────────────┘
                                                                   │
                                                                   ▼
                                                    ┌─────────────────────────────┐
                                                    │ oneM2M IN-CSE: /sdv-cse     │
                                                    │ Semantic Resource Hierarchy │
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
                         │ Grafana Observability       │
                         │ Dynamic Blower Thresholds   │
                         └─────────────────────────────┘
```

---

### 2. Physical Sensing and Actuation Tier (Embedded Firmware)

The physical tier executes on an Espressif ESP32-S3 dual-core microcontroller clocked at 240 MHz, running FreeRTOS with strict core affinity:

* **Core 1 (Physical Loop):** Executes transducer sampling, hardware filtering, supersonic PWM generation, and pulse accumulation.
* **Core 0 (Network Loop):** Executes the mbedTLS 1.3 stack, MQTT client state machine, connection keep-alives, and JSON payload serialisation.

#### 2.1 Dual-Transducer Environmental Sensing
* **Sensirion SCD30:** Interfaces over I²C Fast-Mode at 400 kHz on GPIO 8 (SDA) and GPIO 9 (SCL). Samples carbon dioxide concentration via Non-Dispersive Infrared (NDIR) spectroscopy (0 to 10,000 ppm), dry-bulb temperature (-40 to +70 °C), and relative humidity (0 to 100 %). Every 16-bit word is validated using hardware CRC-8 polynomials ($P(x) = x^8 + x^5 + x^4 + 1$).
* **DHT22 (AM2302):** Interfaces over a single-wire digital bus on GPIO 4. Provides redundant temperature (-40 to +80 °C) and humidity measurements. Data frames are verified against a 40-bit parity checksum.

#### 2.2 Supersonic PWM Blower Control
Audible coil whine and magnetostriction in vehicular cabins cause passenger fatigue. The blower motor is modulated via the ESP32-S3 LEDC peripheral configured at **25.0 kHz**, surpassing the human auditory threshold (> 20 kHz). Duty cycles range from 0 to 100% across 10-bit resolution (0 to 1,023 discrete steps).

#### 2.3 Closed-Loop Tachometer Feedback
To confirm motor rotation and detect mechanical stall, a Hall-effect tachometer sensor feeds into the hardware Pulse Counter (PCNT) peripheral on GPIO 19. Pulse accumulation over 1.0-second integration windows calculates rotor revolutions per minute (RPM).

#### 2.4 Optical Status Annunciation
A single-wire WS2812B addressable RGB LED on GPIO 38 provides visual feedback of operational regimes:
* Green: Nominal telemetry streaming.
* Amber: Warning state ($\tau_{\mathrm{age}} > 2.5\,\mathrm{s}$ or $\Delta T > 1.5\,^\circ\mathrm{C}$).
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
           └── sub_downlink_dispatcher (Subscription -> Node-RED Egress)
```

#### 4.2 Interworking Proxy Entity (IPE) Pipeline
The Node-RED Ingress IPE subscribes to the MQTT broker, validates incoming JSON payloads against `docs/schemas/telemetry_schema.json`, and posts standard oneM2M REST `<contentInstance>` primitives to `/sdv-cse/AE_CabinNode_Car01/cnt_raw_telemetry`.

---

### 5. Empirical Data Health Classification Engine

The Python Bridge AE evaluates incoming sensor records against two empirical dimensions:

$$\Delta T = |T_{\mathrm{SCD30}} - T_{\mathrm{DHT22}}|$$
$$\tau_{\mathrm{age}} = t_{\mathrm{eval}} - t_{\mathrm{sample}}$$

Categorical state assignment follows deterministic criteria:
1. **`FRESH`:** $\tau_{\mathrm{age}} \le 2.5\,\mathrm{s}$ and $\Delta T \le 1.5\,^\circ\mathrm{C}$. Data valid for closed-loop control.
2. **`STALE`:** $2.5\,\mathrm{s} < \tau_{\mathrm{age}} \le 10.0\,\mathrm{s}$. Data acceptable for display; control rules employ hold-last-value logic.
3. **`DEGRADED`:** $\Delta T > 1.5\,^\circ\mathrm{C}$. Transducer disagreement; system logs warning and uses conservative sensor readings.
4. **`FAULT`:** $\tau_{\mathrm{age}} > 10.0\,\mathrm{s}$, transducer disconnection, or out-of-bounds readings. Numerical values are excluded from time-series aggregation, and the blower defaults to 50% baseline fail-safe ventilation.

---

### 6. Closed-Loop Regulation and Observability

* **InfluxDB 2.x:** Telemetry and categorical health tags are committed synchronously with nanosecond timestamps into bucket `cabin_telemetry`.
* **Grafana Operational Cockpit:** Displays real-time metrics, differential temperature plots, and tachometer feedback. Closed-loop alert rules trigger when carbon dioxide exceeds 800 ppm, automatically posting actuation directives to `/sdv-cse/AE_CabinNode_Car01/cnt_actuator_commands` to engage 75% cabin purge ventilation until concentration falls below 750 ppm.
