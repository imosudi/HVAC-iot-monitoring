# Advanced Internet of Things Systems Development

## Cyber-Physical Cabin Environmental Monitoring and Closed-Loop HVAC Control in Software-Defined Vehicles Using oneM2M Middleware

**Academic Institution:** University of Applied Sciences Technikum Wien (FH Technikum Wien)  
**Degree Programme:** Master of Science in Engineering – IoT and Smart Systems (MIO3B)  
**Research Cluster:** Distributed Cyber-Physical Systems & Automotive IoT (FHTW-AIOT)  
**Document Classification:** Academic Exposé and Technical Architecture Specification  
**Version / Datum:** 1.2.0-STABLE / 30 September 2026  
**Repository Identifier:** [`imosudi/HVAC-iot-monitoring`](https://github.com/imosudi/HVAC-iot-monitoring)  

---

### Authors and Contributor Roles Taxonomy (CRediT)
* **Ashok Ramalingam** – *Firmware Engineering, Hardware Integration, Signal Processing:* Embedded FreeRTOS firmware implementation on ESP32-S3; dual-sensor driver architecture (Sensirion SCD30 $\text{I}^2\text{C}$ & DHT22 1-Wire); supersonic $25\text{ kHz}$ LEDC PWM blower modulation; PCNT Hall-effect tachometer feedback; hardware fail-safe routines.
* **AnnaMaria Moçi** – *Security Architecture, Systems Infrastructure, PKI Governance:* Design and operationalisation of the Public Key Infrastructure (Root CA, intermediate certificate authority, node certificate generation); containerised Eclipse Mosquitto broker orchestration; TLS 1.3 / mTLS port 8883 termination; granular topic-level ACL isolation.
* **Isiaka Mosudi** – *Middleware Systems, Semantic Modelling, Distributed Topology:* oneM2M IN-CSE deployment; ETSI TS 118 101 resource tree formalisation (`<CSEBase>`, `<AE>`, `<container>`, `<contentInstance>`); Access Control Policy (`<accessControlPolicy>`) schema design; asynchronous event subscription pipelines (`Sub_BridgeAE` & `Sub_Downlink`).
* **Julia Philip** – *Interworking Engineering, Protocol Bridging, Ingress Validation:* Node-RED Ingress Interworking Proxy Entity (IPE) design; JSON Schema structural validation engines; constrained protocol mapping (MQTT to oneM2M REST primitives via $\text{Mca}$); bidirectional downlink actuation dispatch.
* **Pooja Janwalkar** – *Data Health Analytics, Time-Series Engineering, Visualisation:* Mathematical formulation and implementation of the Bridge AE Data Health state machine (`FRESH`, `STALE`, `DEGRADED`, `FAULT`); InfluxDB 2.x time-series bucket schema and retention policy; Grafana operations cockpit and automated closed-loop rule engine.

---

### 1. Theoretical Framing, Background, and Motivation
In contemporary automotive systems engineering, vehicular electrical/electronic (E/E) architectures are undergoing a profound paradigm shift: transitioning from federated, domain-specific Electronic Control Units (ECUs) interconnected across legacy Controller Area Network (CAN) or Local Interconnect Network (LIN) physical buses towards centralized Vehicle Computer (VC) and zonal compute architectures. This paradigm—formalized under the **Software-Defined Vehicle (SDV)** movement—decouples hardware-level sensing and actuation from application business logic, enabling dynamic over-the-air (OTA) feature orchestration, fleet-wide data harmonization, and cloud-native service composition.

Within this framework, vehicular passenger compartment environmental monitoring constitutes a critical cyber-physical challenge:
1. **Thermodynamic and Psychrometric Constraints:** Enclosed vehicular cabins exhibit minimal air volume ($2.5 - 4.5\text{ m}^3$) coupled with low effective thermal inertia. Solar radiation across expansive windscreen surfaces induces rapid thermal stratification, while passenger metabolic respiration progressively alters the ambient gas mixture.
2. **Cognitive Ergonomics and Active Safety:** Under air-recirculation modes, ambient Carbon Dioxide ($\text{CO}_2$) routinely escalates from atmospheric background ($\approx 420\text{ ppm}$) to concentrations in excess of $1{,}500 - 2{,}500\text{ ppm}$ within 15 to 30 minutes of vehicular transit. Biomedical and cognitive ergonomic literature (e.g. ISO 7730, ASHRAE Standard 55) confirms that sustained hypercapnia ($>1{,}000\text{ ppm}$) provokes headaches, somnolence, and impaired psychomotor reaction times, directly compromising driver situational awareness.
3. **The Imperative for Semantic Middleware:** Ingesting raw sensor observations directly into automotive application logic produces brittle, vendor-locked software topologies. Telemetry must be rigorously validated, temporally indexed, checked for analytical redundancy, and projected into a standard semantic information model. The **oneM2M** global standard (transposed as **ETSI TS 118 101**) provides an open, vendor-neutral middleware layer that standardizes uniform resource addressing, access control, and asynchronous publish/subscribe event management.

The research framework is guided by six primary engineering axioms:
* **Passenger Physiological Equilibrium:** Continuous regulation of $\text{CO}_2 \le 800\text{ ppm}$ and cabin temperature within human comfort boundaries ($21.0^\circ\text{C} \le T_{\text{cabin}} \le 24.0^\circ\text{C}$).
* **"Honest-by-Design" Data Integrity:** Raw sensor observations are never artificially zeroed, interpolated, or cosmetically coerced upon communication loss or transducer fault.
* **Energy Optimisation:** Avoiding excessive blower duty cycles and unneeded refrigeration compressor engagement to preserve traction battery capacity in battery electric vehicles (BEVs).
* **Open Architectural Interoperability:** Rigorous conformity to oneM2M specifications.
* **Configurable Multi-Zone Extensibility:** The addition of supplemental passenger cabin zones or sensor modalities is realized via declarative configuration files rather than code modification.
* **Deterministic Failure Observability:** Fault conditions (sensor severance, I2C lockup, cryptographic expiry) must fail observably rather than silently.

---

### 2. Research Objectives and Functional Requirements
The primary objective of this investigation is to design, implement, and validate an end-to-end cyber-physical architecture for closed-loop vehicular environmental monitoring and HVAC actuation:
1. **Dual-Channel Transducer Acquisition:** Acquire real-time $\text{CO}_2$ concentration, dry-bulb temperature, and relative humidity utilizing a Sensirion SCD30 optical NDIR sensor, complemented by a secondary DHT22 capacitive transducer for analytical cross-validation ($\Delta T$).
2. **Cryptographic Zero-Trust Transport:** Transport telemetry across an automotive edge service mesh over MQTT secured via Mutual Transport Layer Security (mTLS / TLS 1.3 on port 8883) with per-vehicle topic Access Control Lists (ACLs).
3. **ETSI oneM2M Resource Modelling:** Map vehicle cabins into standardized Application Entities (`<AE>`), telemetric and control containers (`<container>`), ContentInstances (`<contentInstance>`), and subscription triggers (`<subscription>`).
4. **Algorithmic Data Health Engine:** Classify incoming telemetry into deterministic health regimes (`FRESH`, `STALE`, `DEGRADED`, `FAULT`) and ingest timestamped records into InfluxDB 2.x.
5. **Closed-Loop Supersonic Actuation:** Execute automated threshold rules and manual operator overrides dispatched from a Grafana cockpit through oneM2M command subscriptions down to an inaudible $25\text{ kHz}$ PWM centrifugal blower controller with Hall-effect tachometer speed verification.

---

### 3. System Architecture and Component Specifications

![Figure 1: Cabin Environment Monitoring and Closed-loop HVAC Control Architecture](assets/architecture_detailed.png)
*Figure 1: Cyber-physical cabin environmental monitoring and closed-loop HVAC control system architecture.*

#### 3.1 ESP32-S3 Cabin Sensing and Actuation Node
The in-cabin physical tier is governed by an Espressif ESP32-S3 SoC (dual-core Xtensa LX7 at $240\text{ MHz}$, $512\text{ KB}$ SRAM) running FreeRTOS:
* **Transducer Suite:**
  * **Sensirion SCD30:** NDIR optical dual-beam sensor measuring $\text{CO}_2$ ($400 - 10{,}000\text{ ppm}$, accuracy $\pm 30\text{ ppm} + 3\%$), temperature ($-40\text{ to }70^\circ\text{C}$, $\pm 0.4^\circ\text{C}$), and relative humidity ($0 - 100\%$, $\pm 3\%$) over $\text{I}^2\text{C}$ Fast-Mode ($400\text{ kHz}$) on **GPIO 8 (SDA)** and **GPIO 9 (SCL)**.
  * **DHT22 / AM2302:** Digital 1-Wire transducer measuring temperature ($-40\text{ to }80^\circ\text{C}$, $\pm 0.5^\circ\text{C}$) and relative humidity ($0 - 100\%$, $\pm 2 - 5\%$) on **GPIO 4**, establishing a redundant reference channel.
* **Actuation and Visual Subsystems:**
  * **HVAC Centrifugal Blower:** Modulated via LEDC hardware timer generating a $25.0\text{ kHz}$ ultrasonic carrier on **GPIO 18** with 10-bit resolution ($1024$ discrete steps). The $25\text{ kHz}$ frequency supersedes human auditory perception ($>20\text{ kHz}$), preventing acoustic switching coil whine.
  * **Tachometer Feedback:** Dual-pulse Hall-effect sensor connected to the PCNT pulse counter hardware unit on **GPIO 19**, computing actual rotor angular velocity:
    $$\omega_{\text{fan}} = \left( \frac{\Delta \text{Pulses}}{2 \cdot \Delta t} \right) \times 60 \quad [\text{RPM}]$$
  * **Optical Health Annunciator:** Integrated WS2812B RGB LED on **GPIO 38** signaling:
    * 🟢 *Solid Green:* $\text{CO}_2 \le 800\text{ ppm}$, Data Health: `FRESH`.
    * 🟡 *Solid Amber:* $800\text{ ppm} < \text{CO}_2 \le 1{,}200\text{ ppm}$, Automatic Low-Speed Purge Active.
    * 🔴 *Flashing Red ($2\text{ Hz}$):* $\text{CO}_2 > 1{,}200\text{ ppm}$, Maximum Blower Duty Cycle Engaged.
    * 🔵 *Solid Blue:* Operator Manual Override Active.
    * 🔷 *Pulsing Cyan:* Cryptographic mTLS Handshake / Network Negotiation.

#### 3.2 Raspberry Pi 5 Automotive Edge Gateway
The gateway layer executes a containerised microservice mesh orchestrated via Podman / Docker on ARM64 Linux:
* **Eclipse Mosquitto (MQTT Broker):** Terminates TLS 1.3 on port `8883` with mandatory X.509 client certificate verification and topic ACL enforcement (`sdv/<car_id>/#`).
* **Node-RED Ingress IPE (Interworking Proxy Entity):** Validates incoming JSON syntax against structural JSON Schemas, maps sensor fields into standard oneM2M REST representations over the $\text{Mca}$ reference point, and acts as the downlink command dispatcher.
* **oneM2M Common Services Entity (IN-CSE):** Hosts the ETSI-compliant semantic resource hierarchy under `/sdv-cse`, enforces Access Control Policies (`<accessControlPolicy>`), and evaluates event subscriptions (`Sub_BridgeAE` and `Sub_Downlink`).
* **Bridge AE / Consumer:** Autonomous analytical worker evaluating temporal latency $\tau_{\text{age}}$ and cross-validation differential $\Delta T$, applying categorical data health flags.
* **InfluxDB 2.x:** Ingests nanosecond-timestamped metric points into the `cabin_telemetry` bucket under a 30-day retention policy.
* **Grafana Operations Cockpit:** Real-time observability interface rendering psychrometric trends, threshold markers ($1{,}000\text{ ppm}$ reference line), automated rule execution, and manual operator overrides.

---

### 4. Methodological Workflow and Control Semantics

![Figure 2: Closed-Loop HVAC Monitoring and Control Architecture for SDV](assets/sdv_closed_loop_flow.png)
*Figure 2: Systematic closed-loop telemetry and actuation feedback pipeline.*

#### 4.1 Uplink Telemetry Pipeline
1. **Transducer Interrogation:** The ESP32-S3 executes periodic sampling ($1.0\text{ Hz}$) across the Sensirion SCD30 and DHT22.
2. **Local Frame Serialization:** Sensor reads are packed into a cryptographically signed JSON frame containing local hardware timestamps and individual sensor channels.
3. **mTLS Publication:** The frame is transmitted over mutual TLS 1.3 to topic `sdv/vehicle_01/telemetry` on port 8883.
4. **IPE Ingress Validation:** Node-RED validates structural schema adherence, discarding malformed or non-compliant frames.
5. **oneM2M Persistence:** Node-RED issues an HTTP POST creating a ContentInstance `<cin>` within `/sdv-cse/AE_CabinNode_Car01/cnt_raw_telemetry`.
6. **Subscription Dispatch:** The IN-CSE triggers subscription `sub_bridge_consumer`, issuing an asynchronous notification to the Bridge AE.
7. **Health Classification & Commitment:** The Bridge AE evaluates telemetry latency ($\tau_{\text{age}}$) and cross-validation differential ($\Delta T$), appends categorical health metadata, and writes the structured record into InfluxDB 2.x.
8. **Real-Time Visualization:** Grafana evaluates Flux queries against InfluxDB, updating operational cockpit panels.

#### 4.2 Downlink Actuation Pipeline
9. **Rule Evaluation & Triggering:** Grafana evaluates closed-loop constraints:
   $$\text{TriggerCondition}: \left( \text{CO}_2 > 800\text{ ppm} \right) \lor \left( T_{\text{cabin}} > 24.0^\circ\text{C} \right)$$
10. **Command Instantiation:** Upon condition fulfillment (or manual human operator override), an HTTP POST generates an actuation `<cin>` in `/sdv-cse/AE_CabinNode_Car01/cnt_actuator_commands`.
11. **Subscription Event:** The oneM2M IN-CSE notifies subscription `sub_downlink_dispatcher`.
12. **Egress Dispatch & Actuation:** Node-RED dispatches an MQTT packet to `sdv/vehicle_01/control/cmd`. The ESP32-S3 modulates blower PWM duty cycle to $75\%$ ($1{,}850\text{ RPM}$), measures tachometer pulses, and updates visual status signalling.

---

### 5. Data Health State Machine and "Honest-by-Design" Philosophy
In mission-critical automotive software, common developer anti-patterns involve defaulting missing or timed-out sensor data to zero ($0.0$). In an SDV context, this introduces catastrophic hazards:
* Coercing missing temperature to $0.0^\circ\text{C}$ causes climate automation to engage maximum heating elements, squandering traction battery power.
* Coercing missing $\text{CO}_2$ to $0\text{ ppm}$ causes climate automation to shut off ventilation flappers during lethal cabin hypercapnia.

The Bridge AE continuously evaluates every observation against a four-state deterministic state machine:
$$\Delta T(t) = \left| T_{\text{SCD30}}(t) - T_{\text{DHT22}}(t) \right|$$
$$\tau_{\text{age}}(t) = t_{\text{eval}} - t_{\text{sample}}(t)$$

$$\mathcal{H}(t) = \begin{cases}
\text{FRESH}, & \text{if } \tau_{\text{age}}(t) \le 2.50\text{ s} \land \Delta T(t) \le 1.50^\circ\text{C} \land \mathbf{y}(t) \notin \Omega_{\text{err}} \\
\text{STALE}, & \text{if } 2.50\text{ s} < \tau_{\text{age}}(t) \le 10.00\text{ s} \land \Delta T(t) \le 1.50^\circ\text{C} \\
\text{DEGRADED}, & \text{if } \tau_{\text{age}}(t) \le 10.00\text{ s} \land \Delta T(t) > 1.50^\circ\text{C} \\
\text{FAULT}, & \text{if } \tau_{\text{age}}(t) > 10.00\text{ s} \lor \mathbf{y}(t) \in \Omega_{\text{err}}
\end{cases}$$

Under `FAULT` regimes, observations are persisted as `null` with explicit diagnostic annotations. Closed-loop control routines detect this state and engage a deterministic hardware fail-safe baseline ($50\%$ fixed ventilation) rather than computing on corrupt data.

---

### 6. Security and Public Key Infrastructure (PKI)
* **X.509 Certificate Chain:** Dedicated private Root CA issues intermediary broker and node certificates. Every communicating entity possesses a unique keypair and certificate.
* **mTLS 1.3 Termination:** Cipher suites are strictly constrained to `TLS_AES_256_GCM_SHA384` and `TLS_CHACHA20_POLY1305_SHA256` with ephemeral Elliptic Curve Diffie-Hellman (`ECDHE`) key negotiation.
* **Topic ACL Isolation:** Node credentials are structurally barred from publishing or subscribing to foreign vehicle namespaces.
* **Zero Secrets in Repository Invariant:** Cryptographic keys and InfluxDB tokens are injected at runtime via decoupled environment configuration and excluded from version control.

---

### 7. Empirical Validation and Testing Strategy
Validation is conducted across three rigorous tiers:

| Testing Tier | Scope and Verification Targets | Pass Criteria |
| :--- | :--- | :--- |
| **Tier 1: Unit Verification** | JSON Schema parsing; SCD30 CRC-8 checksum evaluation; oneM2M URI generation; floating-point conversion accuracy. | Zero parsing exceptions; $100\%$ detection of corrupt checksums. |
| **Tier 2: HIL Integration** | End-to-end hardware-in-the-loop propagation latency: $\tau_{\text{prop}} = t_{\text{dashboard}} - t_{\text{sensor}}$; blower PWM duty cycle linearity; FreeRTOS heap memory profiling over 48 hours. | $\tau_{\text{prop}} \le 1{,}200\text{ ms}$; linear RPM response ($0 - 2{,}400\text{ RPM}$); zero heap memory degradation. |
| **Tier 3: Fault Injection** | Network transport blackout; expired / untrusted X.509 client certificate injection; I2C line clamping; rogue client ACL penetration. | Deterministic reconnection within $3.0\text{ s}$; immediate broker TLS drop on bad cert; `DEGRADED`/`FAULT` flag assertion. |

---

### 8. Conclusion and Future Directions
This research demonstrates an operational, standards-compliant cyber-physical architecture for closed-loop cabin environmental monitoring and actuation in Software-Defined Vehicles. By integrating dual-sensor edge acquisition with ETSI oneM2M middleware and time-series analytical sinks, the system ensures data fidelity, acoustic comfort, and active passenger safety. Future work will extend the framework to multi-zone passenger microclimates and incorporate predictive machine learning models for thermal comfort optimization (Predicted Mean Vote / Predicted Percentage of Dissatisfied occupants according to ISO 7730).