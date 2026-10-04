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
| **LEDC Timer 0** | Blower MOSFET Gate | **GPIO 18** | 3.3 V PWM | 100 Ω gate, 10 kΩ pull-down | 25.0 kHz ultrasonic motor PWM |
| **PCNT Unit 0** | Hall Tachometer | **GPIO 19** | 3.3 V Digital | 4.7 kΩ to 3.3 V | Open-collector pulse accumulation |
| **RMT / GPIO** | WS2812B RGB LED | **GPIO 38** | 3.3 V RZ | 330 Ω series damping | Addressable optical status annunciator |

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

#### 2.2 Supersonic PWM Blower Drive and Motor Protection
```text
  12V Motor Rail ───────────────────────┬────────────────────────┐
                                        │                        │
                                      [===] 100uF 25V         ┌──┴──┐
                                     Electro Cap              │  M  │ Blower Motor
                                        │                     └──┬──┘
                                        │         1N5819         │
                                        ├───────────|<───────────┤ (Flyback Diode)
                                        │                        │
                                        │                     ┌──┴──┐
                                        │                     │  D  │ IRLZ44N
  GPIO 18 ──────[100 Ohm]───────────────┼─────────────────────┤G    │ Logic-Level
                                        │                     │  S  │ N-Ch MOSFET
                                      [10k]                   └──┬──┘
                                    Pull-down                    │
  GND Rail  ────────────────────────────┴────────────────────────┴─────────
```

* **Carrier Frequency:** Modulated at 25.0 kHz using the LEDC hardware timer. This eliminates audible motor hum within the cabin.
* **MOSFET Selection:** Logic-level N-channel MOSFET (such as IRLZ44N or AO3400A) ensures saturation at 3.3 V gate voltages ($V_{\mathrm{GS(th)}} \le 2.0\,\mathrm{V}$).
* **Gate Protection:** A 100 Ω series resistor limits inrush charging current to the gate capacitance, protecting the ESP32-S3 GPIO driver. A 10 kΩ pull-down resistor prevents floating gate conditions during microcontroller boot and reset cycles.
* **Inductive Clamp:** A fast-recovery Schottky diode (1N5819 or SS34) across motor terminals dissipates inductive flyback spikes generated during PWM off-periods.

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

| Rail Voltage | Source | Typical Current | Peak Inrush Current | Decoupling Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **+12.0 V DC** | Automotive Battery / Bench Supply | 450 mA (100% PWM) | 1.80 A (Motor stall) | 100 µF 25 V electrolytic capacitor |
| **+5.0 V DC** | Buck Converter / USB-C VBUS | 120 mA | 350 mA (Wi-Fi burst) | 10 µF tantalum + 100 nF ceramic |
| **+3.3 V DC** | LDO Regulator (AMS1117-3.3) | 80 mA | 160 mA | 22 µF ceramic + 100 nF per IC |

---

### 4. Physical Layout and Noise Mitigation Rules

1. **Ground Plane Separation:** Star grounding separates high-current motor return paths from sensitive transducer analogue references.
2. **I2C Routing:** SDA and SCL traces are kept below 100 mm in total length and routed away from the 25 kHz high-power motor switching node.
3. **Fail-Safe Biasing:** In the event of firmware crash or brownout, the 10 kΩ gate pull-down resistor forces the blower into an immediate off-state until the FreeRTOS watchdog triggers a system reset.
