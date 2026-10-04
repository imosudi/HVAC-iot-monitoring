# MVP Test Verification Plan and Execution Report

## Software-Defined Vehicle (SDV) Automotive IoT HVAC Monitoring

**Milestone:** MVP Release 1.0 Acceptance Verification  
**Academic Affiliation:** University of Applied Sciences Technikum Wien (FH Technikum Wien)  
**Authors:** Ashok Ramalingam, Isiaka Mosudi, Pooja Janwalkar  

---

### 1. Verification Strategy and Quality Gates

The verification process validates the closed-loop cyber-physical pipeline across three testing tiers, ensuring compliance with automotive reliability and data integrity standards:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        THREE-TIER TESTING PYRAMID                      │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 3: Adversarial Fault Injection & HIL Verification                │
│  • Broker blackouts, transducer detachment, latency injection          │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 2: Pipeline Integration & Latency Benchmarking                   │
│  • End-to-end telemetry propagation, oneM2M subscription notification  │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 1: Unit Testing & Contract Verification                          │
│  • JSON Schema 2020-12 validation, four-state health machine logic     │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 2. Test Execution Matrix and Traceability

| Test ID | Tier | Target Component | Description | Expected Outcome | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **UT-01** | Tier 1 | JSON Schema | Valid telemetry frame passes schema validation | Validation succeeds with zero errors | **PASSED** |
| **UT-02** | Tier 1 | JSON Schema | Invalid vehicle ID format (`car-01`) is rejected | `ValidationError` raised | **PASSED** |
| **UT-03** | Tier 1 | JSON Schema | Non-25 kHz motor carrier frequency is rejected | `ValidationError` raised | **PASSED** |
| **UT-04** | Tier 1 | JSON Schema | Actuator command target PWM > 100% rejected | `ValidationError` raised | **PASSED** |
| **UT-05** | Tier 1 | Health Engine | Nominal reading ($\tau_{\mathrm{age}} \le 2.5\,\mathrm{s}$, $\Delta T \le 1.5\,^\circ\mathrm{C}$) | State `FRESH` | **PASSED** |
| **UT-06** | Tier 1 | Health Engine | Stale reading ($2.5\,\mathrm{s} < \tau_{\mathrm{age}} \le 10.0\,\mathrm{s}$) | State `STALE` | **PASSED** |
| **UT-07** | Tier 1 | Health Engine | Transducer discrepancy ($\Delta T > 1.5\,^\circ\mathrm{C}$) | State `DEGRADED` | **PASSED** |
| **UT-08** | Tier 1 | Health Engine | Extreme latency ($\tau_{\mathrm{age}} > 10.0\,\mathrm{s}$) or null readings | State `FAULT` | **PASSED** |
| **IT-01** | Tier 2 | Pipeline E2E | Ingress telemetry converts into InfluxDB line-protocol | Clean point formatted and queued | **PASSED** |
| **IT-02** | Tier 2 | Closed-Loop | CO₂ exceedance (> 800 ppm) produces 75% purge directive | Downlink command generated and schema validated | **PASSED** |
| **FI-01** | Tier 3 | Fault Injector | Simulated backdated timestamp (stale trigger) | Bridge AE flags record as `STALE` | **VERIFIED** |
| **FI-02** | Tier 3 | Fault Injector | SCD30 (21.0 °C) vs DHT22 (24.2 °C) divergence | Bridge AE flags record as `DEGRADED` | **VERIFIED** |
| **FI-03** | Tier 3 | Fault Injector | Transducer detachment (null payload) | Bridge AE asserts `FAULT`, omits null fields | **VERIFIED** |
| **FI-04** | Tier 3 | Fault Injector | Commanded 75% PWM but 0 RPM tachometer feedback | Motor stall flagged in telemetry stream | **VERIFIED** |
| **FI-05** | Tier 3 | Ingress IPE | Corrupt JSON text rejected at boundary | Node-RED drops frame without crash | **VERIFIED** |

---

### 3. Automated Test Execution Commands

#### 3.1 Executing Tier 1 and Tier 2 Automated Tests
```bash
# Run the complete pytest suite with verbose reporting
pytest -v
```

#### 3.2 Executing Tier 3 Fault Injection Suite
```bash
# Start the MEC container mesh
./deploy/deploy_gateway.sh

# Run fault injection scenarios against the edge broker
./scripts/testing/inject_faults.py --host localhost --port 1883 --vehicle-id vehicle_01
```

#### 3.3 Continuous Telemetry Simulation
```bash
# Simulate normal operation telemetry at 1.0 Hz
./scripts/testing/simulate_telemetry.py --host localhost --port 1883 --mode normal

# Simulate CO2 exceedance condition to test closed-loop ventilation
./scripts/testing/simulate_telemetry.py --host localhost --port 1883 --mode co2_spike
```

---

### 4. Performance Benchmarks and Latency Targets

* **Propagation Latency ($\tau_{\mathrm{prop}}$):** Target $\le 1{,}200\,\mathrm{ms}$. Measured average over 1,000 frames: $340\,\mathrm{ms}$ from ESP32-S3 sensor acquisition to Grafana cockpit display.
* **LEDC Carrier Accuracy:** Target $25.0\,\mathrm{kHz} \pm 1\%$. Measured: $25.002\,\mathrm{kHz}$ on digital oscilloscope.
* **Fail-Safe Transition Time:** Transducer disconnection triggers baseline 50% PWM engagement within $1{,}500\,\mathrm{ms}$.
