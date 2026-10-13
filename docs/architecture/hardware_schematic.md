# Hardware Wiring and Circuit Schematic Specification

## Embedded Sensor and Actuator Interfacing for ESP32-S3 Cabin Node

**Document Version:** 1.0.0  
**Hardware Lead:** Ashok Ramalingam  
**Target Platform:** Espressif ESP32-S3-WROOM-1 (N16R8 Dual-Core SoC)  

---

### 1. Master Pinout and Peripheral Assignment

| Peripheral | Component | Pin Identifier | Electrical Logic | Pull-Up / Protection | Functional Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **I2C_NUM_0 SDA** | Sensirion SCD30 | **GPIO 8** | 3.3 V CMOS | 4.7 kΩ to 3.3 V | Bidirectional serial data line |
| **I2C_NUM_0 SCL** | Sensirion SCD30 | **GPIO 9** | 3.3 V CMOS | 4.7 kΩ to 3.3 V | Serial clock line (400 kHz Fast-Mode) |
| **GPIO Bit-Bang** | DHT22 (AM2302) | **GPIO 4** | 3.3 V CMOS | 10 kΩ to 3.3 V | Single-wire bidirectional bus |
| **LEDC Timer 0** | Blue LED Actuator (Purge / Cooling) | **GPIO 18** | 3.3 V PWM | 150 Ω series resistor | Primary purge actuator; brightness emulates blower speed (0 to 100% duty) |
| **GPIO Output** | Red LED Actuator (Heating) | **GPIO 17** | 3.3 V Digital | 330 Ω series resistor | Thermal heating actuator; engages when cabin temperature falls below 19.0 °C |
| **GPIO Output** | Green LED Actuator (Eco Ventilation) | **GPIO 16** | 3.3 V Digital | 330 Ω series resistor | Nominal air-quality actuator; active under baseline CO₂ (< 800 ppm) equilibrium |
| **GPIO Output** | Amber LED Actuator (Alert / Dehumidification) | **GPIO 15** | 3.3 V Digital | 330 Ω series resistor | Dehumidification / caution actuator; active under elevated humidity (> 65%) |
| **PCNT Unit 0** | Bench Feedback Tachometer | **GPIO 19** | 3.3 V Digital | 4.7 kΩ pull-up to 3.3 V | Pulse counter input for bench rotation verification (2 pulses/rev) |
| **RMT / GPIO** | WS2812B RGB LED | **GPIO 38** | 3.3 V RZ | 330 Ω series damping | Addressable node optical health and network status annunciator |

---

### 2. Circuit Subsystem Topologies

#### 2.1 Environmental Transducer Bus
```text
  3.3V Rail ────────────┬─────────────┬─────────────┬─────────────┐
                        │             │             │             │
                      [4.7k]        [4.7k]        [10k]           │
                        │             │             │             │
  GPIO 8  (SDA) ────────┴─────────────┼─────────────┼──────[SCD30: Pin 4 (SDA)]
  GPIO 9  (SCL) ──────────────────────┴─────────────┼──────[SCD30: Pin 3 (SCL)]
  GPIO 4  (DHT) ────────────────────────────────────┴──────[DHT22: Pin 2 (DATA)]
  GND Rail  ───────────────────────────────────────────────[Common Ground]
```

* Both the SCD30 and DHT22 are powered from the regulated 3.3 V rail.
* The 4.7 kΩ pull-up resistors on the I²C bus preserve signal rise times under 300 ns, conforming to Fast-Mode specifications.
* The SCD30 measurement cycle requires a 2-second default interval; clock stretching by the sensor is handled with a 50 ms timeout in firmware.

#### 2.2 Coloured LED Actuator Array (Physical Device Emulation)

In place of high-current vehicular blower motors, stepper flappers, and PTC heating elements, the MVP bench implementation uses discrete coloured LEDs as the physical actuators. This preserves the cyber-physical control semantics without high-voltage power hazards or acoustic disturbance:

```text
  GPIO 18 (LEDC PWM) ───────[150 Ohm]───────[ >| Blue LED: Purge / Blower ]───────┐
                                                                                    │
  GPIO 17 (Digital)  ───────[330 Ohm]───────[ >| Red LED: Cabin Heater ]──────────┤
                                                                                    │
  GPIO 16 (Digital)  ───────[330 Ohm]───────[ >| Green LED: Eco Baseline ]─────────┤
                                                                                    │
  GPIO 15 (Digital)  ───────[330 Ohm]───────[ >| Amber LED: Alert / Dehum ]────────┤
                                                                                    │
  GND Rail  ────────────────────────────────────────────────────────────────────────┘
```

* **Blue LED Actuator (Purge Ventilation / Cooling):** Driven via the ESP32-S3 LEDC hardware timer on GPIO 18. Luminous intensity directly visualises the commanded duty cycle percentage (0 to 100%) calculated by the closed-loop rule engine upon carbon dioxide exceedance (> 800 ppm).
* **Red LED Actuator (Cabin Heating):** Driven via GPIO 17. Illuminates when temperature falls below the comfort lower bound (< 19.0 °C), emulating vehicular PTC heater core activation.
* **Green LED Actuator (Eco Ventilation):** Driven via GPIO 16. Illuminates during nominal baseline air quality (CO₂ between 400 and 800 ppm, temperature between 20.0 and 23.5 °C).
* **Amber LED Actuator (Alert / Dehumidification):** Driven via GPIO 15. Engages during high relative humidity (> 65%) or when the Bridge AE flags a `DEGRADED` or `STALE` health status.


#### 2.3 Optical Status Indicator (WS2812B)
```text
  5V VCC Rail ──────────────[WS2812B: Pin 1 (VDD)]
                                  │
  GPIO 38 ──────[330 Ohm]─────────┴─[WS2812B: Pin 4 (DIN)]
                                  │
  GND Rail  ──────────────────────┴─[WS2812B: Pin 3 (GND)]
```
* A 330 Ω series resistor placed adjacent to the data input dampens transmission line reflections.
* A 100 nF ceramic decoupling capacitor is situated directly across VDD and GND pins.

---

### 3. Electrical Characteristics and Power Budget

| Subsystem Rail | Source | Typical Current | Peak Current | Decoupling Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **+3.3 V DC (LED Actuators)** | ESP32-S3 GPIO Pins | 12 mA (Single LED) | 48 mA (All LEDs Active) | Current-limiting resistors (220 Ω / 330 Ω) |
| **+5.0 V DC (Node Power)** | USB-C VBUS / Buck Converter | 120 mA | 350 mA (Wi-Fi burst) | 10 µF tantalum + 100 nF ceramic |
| **+3.3 V DC (Transducers)** | LDO Regulator (AMS1117-3.3) | 65 mA | 120 mA | 22 µF ceramic + 100 nF per IC |

Operating the actuators as coloured LEDs allows the entire cyber-physical node to operate safely from standard 5.0 V USB-C power without external 12.0 V automotive bench power supplies.

---

### 4. Physical Layout and Noise Mitigation Rules

1. **Direct GPIO Drive:** Low-current coloured LEDs eliminate inductive flyback, motor commutation spikes, and electromagnetic interference (EMI).
2. **Current Budget Compliance:** The cumulative current draw of all active LED actuators (maximum 48 mA) remains well within the ESP32-S3 total GPIO source limit of 120 mA.
3. **I2C Bus Clearance:** Sensor routing traces on GPIO 8 and GPIO 9 are routed cleanly with short ground return paths, preserving I²C Fast-Mode clock fidelity.
4. **Deterministic Optical Feedback:** Every closed-loop command dispatched by oneM2M produces an immediate visual change in LED luminous intensity or colour channel.

