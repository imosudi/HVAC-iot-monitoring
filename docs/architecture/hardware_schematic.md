# Hardware Wiring and Circuit Schematic Specification

## Embedded Sensor and Actuator Interfacing for ESP32-S3 Cabin Node

**Document Version:** 2.0.0  
**Target Platform:** Espressif ESP32-S3-WROOM-1 (N16R8 Dual-Core SoC)  
**Academic Affiliation:** University of Applied Sciences Technikum Wien (FH Technikum Wien)  
**Standardisation Compliance:** ETSI TS 118 101 / oneM2M Release 4  

---

### 1. Executive Overview and Visual Circuit Schematic

This document provides the definitive hardware electrical specification, circuit schematics, bill of materials (BOM), and netlist for the cyber-physical cabin sensing and actuation node of the Software-Defined Vehicle (SDV) IoT HVAC monitoring platform.

The edge cabin node is engineered around the **Espressif ESP32-S3-WROOM-1** System-on-Chip (SoC), interfacing a dual-transducer environmental acquisition suite (Sensirion SCD30 photoacoustic NDIR CO₂ sensor and DHT22 capacitive relative humidity / temperature sensor) alongside a 4-channel discrete coloured LED actuator matrix, a high-speed addressable optical annunciator (WS2812B), and a bench rotor feedback tachometer.

The complete publication-grade vector schematic is illustrated below:

![SDV Master Hardware Circuit Schematic](../assets/circuit_schematic.svg)

```text
+---------------------------------------------------------------------------------------------------------+
|                                  SDV CABIN NODE HARDWARE ARCHITECTURE                                   |
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|   +-------------------+       +-----------------------+       +-------------------------------------+   |
|   |  Power Regulation |       |  ESP32-S3 Dual-Core   |       |  Coloured LED Actuator Matrix       |   |
|   |  USB-C 5.0V VBUS  | ====> |  Xtensa LX7 @ 240 MHz | ====> |  - Ch 1: Blue LED (Purge PWM 25kHz) |   |
|   |  AMS1117-3.3 LDO  |       |  Core 0: mbedTLS/WiFi |       |  - Ch 2: Red LED (Cabin Heater DO)  |   |
|   +-------------------+       |  Core 1: Sensor & PWM |       |  - Ch 3: Green LED (Eco Vent DO)    |   |
|                               +-----------------------+       |  - Ch 4: Amber LED (Alert/Dehum DO) |   |
|                                     ▲           ▲             +-------------------------------------+   |
|                                     │           │                                                       |
|                                     │           │             +-------------------------------------+   |
|   +--------------------+            │           +===========> |  WS2812B Smart RGB Annunciator      |   |
|   | Sensirion SCD30    | <==========+                         |  - GPIO 38 RMT Single-Wire RZ       |   |
|   | Dual-Beam NDIR CO₂ | (I²C Fast-Mode 400 kHz)              +-------------------------------------+   |
|   +--------------------+            │                                                                   |
|                                     │                         +-------------------------------------+   |
|   +--------------------+            │                         |  Bench Feedback Tachometer          |   |
|   | DHT22 (AM2302)     | <==========+                         |  - GPIO 19 PCNT Pulse Accumulator   |   |
|   | Capacitive T & RH  | (1-Wire Bidirectional Bus)           +-------------------------------------+   |
|   +--------------------+                                                                                |
+---------------------------------------------------------------------------------------------------------+
```

---

### 2. Master Pinout and Peripheral Assignment Matrix

The physical pin and peripheral mapping ensures conflict-free operation across the ESP32-S3 hardware timers, pulse counters, remote control (RMT) bitstream generators, and serial communication engines.

| Peripheral ID | Component / Signal | Physical GPIO | Logic Level | Drive Mode / Pull-Up | Forward Current / Rating | Default Boot State | Functional Specification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **I2C_NUM_0 SDA** | Sensirion SCD30 Data | **GPIO 8** | 3.3 V CMOS | Open-Drain, Ext. 4.7 kΩ to 3.3V | $I_{\text{sink}} \approx 0.70\text{ mA}$ | High-Z (Pulled High) | I²C Serial Data (Fast-Mode 400 kHz) |
| **I2C_NUM_0 SCL** | Sensirion SCD30 Clock | **GPIO 9** | 3.3 V CMOS | Open-Drain, Ext. 4.7 kΩ to 3.3V | $I_{\text{sink}} \approx 0.70\text{ mA}$ | High-Z (Pulled High) | I²C Serial Clock (400 kHz, 50 ms timeout) |
| **GPIO Bit-Bang** | DHT22 / AM2302 Data | **GPIO 4** | 3.3 V CMOS | Bidirectional, Ext. 10.0 kΩ to 3.3V| $I_{\text{sink}} \approx 0.33\text{ mA}$ | High-Z (Pulled High) | Single-wire handshaking & 40-bit frame ingest |
| **LEDC Timer 0** | Blue LED (Purge / Blower) | **GPIO 18** | 3.3 V PWM | Push-Pull, 150 Ω series resistor | $I_f = 2.00\text{ mA}$ ($V_f = 3.00\text{ V}$) | Low (0% Duty) | Ultrasonic 25.0 kHz carrier, 10-bit duty |
| **GPIO Output** | Red LED (PTC Heater) | **GPIO 17** | 3.3 V DO | Push-Pull, 330 Ω series resistor | $I_f = 4.24\text{ mA}$ ($V_f = 1.90\text{ V}$) | Low (De-energised) | Cabin heating actuation ($T < 19.0\,^\circ\text{C}$) |
| **GPIO Output** | Green LED (Eco Vent) | **GPIO 16** | 3.3 V DO | Push-Pull, 330 Ω series resistor | $I_f = 3.64\text{ mA}$ ($V_f = 2.10\text{ V}$) | Low (De-energised) | Equilibrium recirculation ($400 \le \text{CO}_2 \le 800$) |
| **GPIO Output** | Amber LED (Alert / Dehum)| **GPIO 15** | 3.3 V DO | Push-Pull, 330 Ω series resistor | $I_f = 3.94\text{ mA}$ ($V_f = 2.00\text{ V}$) | Low (De-energised) | Dehumidification ($\varphi > 65\%$) & degraded health |
| **PCNT Unit 0** | Bench Feedback Tachometer | **GPIO 19** | 3.3 V Digital | Input, Ext. 4.7 kΩ to 3.3V | High Impedance ($< 1\,\mu\text{A}$) | Pulled High | Rotor edge counting (2 pulses/rev) |
| **RMT Transmit**| WS2812B RGB Smart LED | **GPIO 38** | 3.3 V RZ | Push-Pull, 330 Ω series damping | Logic Level ($< 1\,\mu\text{A}$) | Low | 800 kHz RZ bitstream for node lifecycle optical state |
| **Power Rail** | AMS1117-3.3 Output | **3V3 Pin** | +3.3 V DC | Regulated Output, Low-Z | $I_{\max} = 800\text{ mA}$ | Active (+3.30 V) | Primary microcontroller and sensor rail |
| **Power Rail** | USB-C VBUS | **5V Pin** | +5.0 V DC | Raw Ingress Supply | $I_{\max} = 500\text{ mA}$ (USB 2.0) | Active (+5.00 V) | VBUS supply for LDO and WS2812B VDD |
| **Ground Rail** | System Return Ground | **GND Pin** | 0.0 V DC | Common Ground Return | Continuous Return | Common Ground (0V) | Star-connected ground plane |

---

### 3. Circuit Subsystem Schematics and Topologies

#### 3.1 Subsystem 1: Power Regulation and Decoupling Network

The cabin node is powered from standard USB-C 5.0 V VBUS. An onboard **AMS1117-3.3** Low-Dropout (LDO) regulator steps down the input voltage to a stable +3.30 V DC system rail with ripple voltage bounded below 20 mV peak-to-peak.

```text
  USB-C Connector (J1)
  ┌─────────────────┐
  │ Pin A4/B4, A9/B9│───[ NET_VBUS: +5.0V ]────────┬──────────────────────┬─────────────┐
  │ (VBUS)          │                              │                      │             │
  │ Pin A1/B1, A12  │───[ NET_GND: 0.0V ]──┐     [C1: 10µF]             [C2: 100nF]   [WS2812B: VDD]
  │ (GND)           │                      │      (Tantalum)             (Ceramic)      (Subsystem 5)
  └─────────────────┘                      │       │                      │             │
                                           │       ▼                      ▼             │
                                           │      GND                    GND            │
                                           │                                            │
                                           │       AMS1117-3.3 LDO (U1)                 │
                                           │     ┌──────────────────────┐               │
                                           ├────>│ VIN (Pin 3)          │               │
                                           │     │                      │               │
                                           │     │ VOUT (Pin 2 / Tab)   ├──[ NET_3V3 ]──┤
                                           │     │                      │       │       │
                                           │     │ GND/ADJ (Pin 1)      │       │       │
                                           │     └──────────┬───────────┘       │       │
                                           │                │                   │       │
                                           ▼                ▼                   │       │
                                          GND              GND                  │       │
                                                                                │       │
                                                 ┌──────────────────────────────┴───┐   │
                                                 │                                  │   │
                                               [C3: 22µF]                         [C4: 100nF]
                                               (Ceramic)                          (Ceramic)
                                                 │                                  │
                                                 ▼                                  ▼
                                                GND                                GND
```

##### Thermal Dissipation Derivation (Joule's Law)
Under nominal operating load ($I_{\text{load}} \approx 165\text{ mA}$):
$$P_D = (V_{\text{in}} - V_{\text{out}}) \times I_{\text{load}} = (5.00\,\text{V} - 3.30\,\text{V}) \times 0.165\,\text{A} = 1.70\,\text{V} \times 0.165\,\text{A} = 0.2805\,\text{W} \approx 281\,\text{mW}$$

With an SOT-223 package junction-to-ambient thermal resistance $\theta_{JA} = 90\,^\circ\text{C/W}$ and ambient testbench temperature $T_A = 25.0\,^\circ\text{C}$:
$$T_J = T_A + (P_D \times \theta_{JA}) = 25.0\,^\circ\text{C} + (0.2805\,\text{W} \times 90\,^\circ\text{C/W}) = 25.0\,^\circ\text{C} + 25.2\,^\circ\text{C} = 50.2\,^\circ\text{C}$$
The junction temperature $T_J = 50.2\,^\circ\text{C}$ remains comfortably below the manufacturer thermal shutdown threshold ($125\,^\circ\text{C}$), ensuring continuous thermal stability without external heatsinks.

---

#### 3.2 Subsystem 2: Sensirion SCD30 Dual-Beam NDIR CO₂ Sensor Bus

The Sensirion SCD30 module operates in I²C slave mode at factory address `0x61`. Both serial clock (`SCL`) and serial data (`SDA`) lines are pulled up to the +3.3 V rail via discrete precision 4.7 kΩ resistors.

```text
  NET_3V3 Rail ───────────────────────────┬───────────────────────┬─────────────────────────┐
                                          │                       │                         │
                                      [R1: 4.7kΩ]             [R2: 4.7kΩ]                   │
                                      (Pull-Up SCL)           (Pull-Up SDA)                 │
                                          │                       │                         │
  ESP32-S3 GPIO 9 (I2C0_SCL) ─────────────┴───────────────────────┼─────────────[SCD30: Pin 3 (TX/SCL)]
                                                                  │
  ESP32-S3 GPIO 8 (I2C0_SDA) ─────────────────────────────────────┴─────────────[SCD30: Pin 4 (RX/SDA)]
                                                                                [SCD30: Pin 1 (VDD)] ───┘
  NET_GND Rail ─────────────────────────────────────────────────────────────────[SCD30: Pin 2 (GND)]
```

##### I²C Bus Rise-Time Calculation (Conformity with I²C Fast-Mode Specification)
In accordance with the NXP I²C-bus specification (UM10204, Section 7.1), the maximum permissible rise time $t_r$ for Fast-Mode (400 kHz) is $300\,\text{ns}$. With pull-up resistor $R_p = 4.7\,\text{k}\Omega$ and total bus capacitance $C_b \approx 50\,\text{pF}$ (transducer input pin capacitance + breadboard parasitic capacitance):

$$t_r = 0.8473 \times R_p \times C_b = 0.8473 \times (4.7 \times 10^3\,\Omega) \times (50 \times 10^{-12}\,\text{F}) \approx 199.1\,\text{ns}$$

Since $199.1\,\text{ns} \le 300\,\text{ns}$, the selected $4.7\,\text{k}\Omega$ pull-up values provide steep rise slopes, robust noise immunity against capacitive crosstalk, and preserve I²C clock edge integrity. Clock stretching by the SCD30 optical sensor is handled in the ESP-IDF driver with a 50 ms timeout parameter.

---

#### 3.3 Subsystem 3: DHT22 Cabin Temperature and Relative Humidity Sensor

The DHT22 (AM2302) serves as a secondary, physically distinct environmental cross-validation transducer. It employs a proprietary single-wire bidirectional asynchronous protocol.

```text
  NET_3V3 Rail ───────────────────────────────────────────┬─────────────────────[DHT22: Pin 1 (VCC)]
                                                          │
                                                     [R3: 10.0kΩ]
                                                     (Pull-Up DATA)
                                                          │
  ESP32-S3 GPIO 4 (1-Wire DATA) ──────────────────────────┴─────────────────────[DHT22: Pin 2 (DATA)]
                                                                                [DHT22: Pin 3 (NC)]
  NET_GND Rail ─────────────────────────────────────────────────────────────────[DHT22: Pin 4 (GND)]
```

* The line is held in an idle high state by pull-up resistor $R_3 = 10.0\,\text{k}\Omega$.
* Communication begins when the ESP32-S3 pulls GPIO 4 low for $\ge 1.0\,\text{ms}$, followed by a high release for $20\,\mu\text{s} - 40\,\mu\text{s}$, after which the sensor responds with a 40-bit transmission frame consisting of 16-bit relative humidity, 16-bit temperature, and an 8-bit parity checksum.
* Firmware executes non-blocking sampling at 2.0-second intervals on Core 1 to prevent transducer self-heating.

---

#### 3.4 Subsystem 4: 4-Channel Coloured LED Physical Actuator Matrix

The physical mechanical actuators of an automotive HVAC system (centrifugal blower motor, positive temperature coefficient heating elements, fresh-air intake flaps, and dehumidification compressors) are emulated using four discrete 5 mm diffused light-emitting diodes:

```text
  ESP32-S3 Outputs                         Current Limiter             Emulated Actuator
 ┌──────────────────────┐
 │ GPIO 18 (LEDC PWM)   ├───[ NET_ACT_BLUE ]───[ R5: 150 Ω ]───[ >| D1: Blue LED ]──────┐
 │                      │                                                                 │
 │ GPIO 17 (Digital DO) ├───[ NET_ACT_RED ]────[ R6: 330 Ω ]───[ >| D2: Red LED ]───────┤
 │                      │                                                                 │
 │ GPIO 16 (Digital DO) ├───[ NET_ACT_GREEN ]──[ R7: 330 Ω ]───[ >| D3: Green LED ]─────┤
 │                      │                                                                 │
 │ GPIO 15 (Digital DO) ├───[ NET_ACT_AMBER ]──[ R8: 330 Ω ]───[ >| D4: Amber LED ]─────┤
 └──────────────────────┘                                                                 │
  Common Return Ground Bus (NET_GND) ─────────────────────────────────────────────────────┘
```

##### Electrical Calculations per Actuator Channel

| Actuator Function | Optical Colour | Dominant $\lambda$ | Forward Voltage ($V_f$) | Limiting Resistor ($R$) | Resistor Dissipation ($P$) | Forward Current ($I_f$) | Microcontroller Output Pad |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Purge Ventilation** | **Blue** | $468\,\text{nm}$ | $3.00\,\text{V}$ | $150\,\Omega$ | $0.60\,\text{mW}$ | $2.00\,\text{mA}$ | GPIO 18 (LEDC Timer 0, 25 kHz) |
| **Cabin Heating** | **Red** | $625\,\text{nm}$ | $1.90\,\text{V}$ | $330\,\Omega$ | $5.94\,\text{mW}$ | $4.24\,\text{mA}$ | GPIO 17 (Digital DO) |
| **Eco Ventilation** | **Green** | $525\,\text{nm}$ | $2.10\,\text{V}$ | $330\,\Omega$ | $4.37\,\text{mW}$ | $3.64\,\text{mA}$ | GPIO 16 (Digital DO) |
| **Alert / Dehumidify**| **Amber** | $590\,\text{nm}$ | $2.00\,\text{V}$ | $330\,\Omega$ | $5.12\,\text{mW}$ | $3.94\,\text{mA}$ | GPIO 15 (Digital DO) |

##### Mathematical Derivations
* **Channel 1 (Blue LED - Purge Blower Emulation):**
  $$I_f = \frac{V_{\text{OH}} - V_f}{R_5} = \frac{3.30\,\text{V} - 3.00\,\text{V}}{150\,\Omega} = \frac{0.30\,\text{V}}{150\,\Omega} = 2.00\,\text{mA}$$
  $$P_{R5} = (V_{\text{OH}} - V_f) \times I_f = 0.30\,\text{V} \times 0.002\,\text{A} = 0.60\,\text{mW}$$
  The Blue LED brightness scales linearly with commanded blower duty cycle (0 to 1,023 setpoint register values) driven by LEDC Timer 0 at an ultrasonic $25.0\,\text{kHz}$ carrier frequency.

* **Channel 2 (Red LED - PTC Heater Emulation):**
  $$I_f = \frac{3.30\,\text{V} - 1.90\,\text{V}}{330\,\Omega} = \frac{1.40\,\text{V}}{330\,\Omega} \approx 4.24\,\text{mA}$$
  $$P_{R6} = 1.40\,\text{V} \times 0.00424\,\text{A} \approx 5.94\,\text{mW}$$

* **Channel 3 (Green LED - Eco Air Quality Equilibrium):**
  $$I_f = \frac{3.30\,\text{V} - 2.10\,\text{V}}{330\,\Omega} = \frac{1.20\,\text{V}}{330\,\Omega} \approx 3.64\,\text{mA}$$
  $$P_{R7} = 1.20\,\text{V} \times 0.00364\,\text{A} \approx 4.37\,\text{mW}$$

* **Channel 4 (Amber LED - Alert / Dehumidification):**
  $$I_f = \frac{3.30\,\text{V} - 2.00\,\text{V}}{330\,\Omega} = \frac{1.30\,\text{V}}{330\,\Omega} \approx 3.94\,\text{mA}$$
  $$P_{R8} = 1.30\,\text{V} \times 0.00394\,\text{A} \approx 5.12\,\text{mW}$$

* **Cumulative GPIO Current Consumption:**
  $$I_{\text{total\_actuators}} = 2.00\,\text{mA} + 4.24\,\text{mA} + 3.64\,\text{mA} + 3.94\,\text{mA} = 13.82\,\text{mA}$$
  The total draw of $13.82\,\text{mA}$ with all four channels concurrently active represents only $11.5\%$ of the ESP32-S3 maximum package source budget of $120\,\text{mA}$, ensuring absolute electrical safety and low thermal dissipation.

---

#### 3.5 Subsystem 5: WS2812B Smart RGB Optical Annunciator

A single-wire addressable WS2812B RGB LED on GPIO 38 provides instantaneous, human-visible optical annunciation of the cabin node lifecycle, cryptographic connectivity, and data-health classification state.

```text
  NET_VBUS (+5.0V) ───────────────────────┬─────────────────────────────[WS2812B: Pin 1 (VDD)]
                                          │
                                     [C5: 100nF]
                                      (Decoupling)
                                          │
  NET_GND ────────────────────────────────┴──────────┬──────────────────[WS2812B: Pin 3 (GND)]
                                                     │
  ESP32-S3 GPIO 38 (RMT) ─────[ R9: 330 Ω ]──────────┼──────────────────[WS2812B: Pin 4 (DIN)]
                              (Series Damping)       │
                                                     │                  [WS2812B: Pin 2 (DOUT)] ── (NC)
```

* **Damping Resistor ($R_9 = 330\,\Omega$):** Positioned within 10 mm of the WS2812B `DIN` pin, this resistor dampens transmission-line high-frequency reflection ringing caused by the fast edges ($t_r < 10\,\text{ns}$) of the $800\,\text{kHz}$ RMT bitstream.
* **Bypass Capacitor ($C_5 = 100\,\text{nF}$):** A low-ESR ceramic capacitor is positioned directly across pins 1 and 3 of the WS2812B to absorb switching transients from the integrated constant-current driver PWM circuits.

##### Optical State Signalling Mapping

| Optical Display Colour | RGB Code | Associated System State | oneM2M Semantic / Telemetry Condition |
| :--- | :--- | :--- | :--- |
| **Flashing Cyan** | `(0, 180, 255)` | Booting / Wi-Fi Handshake | Initialising network layer, establishing TLS 1.3 socket |
| **Solid Green** | `(0, 255, 0)` | Operational / FRESH | Telemetry streaming, broker connected, sensor delta within bounds |
| **Solid Amber** | `(255, 160, 0)` | Degraded / STALE | $\tau_{\text{age}} > 2.5\,\text{s}$ or cross-transducer differential $\Delta T > 1.5\,^\circ\text{C}$ |
| **Solid Red** | `(255, 0, 0)` | Hardware Fault / Disconnected | Transducer CRC failure, I²C bus timeout, or MQTT socket termination |
| **Pulsing Blue** | `(0, 100, 255)` | Active Purge Actuation | Downlink actuation active: Blue blower operating at commanded duty |
| **Magenta / Purple** | `(200, 0, 255)` | Downlink Override | Emergency fail-safe override dispatched by Node-RED IPE |

---

#### 3.6 Subsystem 6: Bench Tachometer Rotor Pulse Feedback

For testbench verification of blower motor rotation dynamics without an active high-power mechanical rotor, a 3-pin connector header `J2` interfaces an optical interrupter or Hall-effect pulse generator.

```text
  NET_3V3 Rail ───────────────────────────┬─────────────────────────────[J2: Pin 1 (+3.3V Power)]
                                          │
                                     [R4: 4.7kΩ]
                                     (Pull-Up Pulse)
                                          │
  ESP32-S3 GPIO 19 (PCNT Unit 0) ─────────┴─────────────────────────────[J2: Pin 2 (Tacho Pulse)]
                                                                        [J2: Pin 3 (GND Return)] ───┐
  NET_GND Rail ─────────────────────────────────────────────────────────────────────────────────────┘
```

* **Pulse Capture:** Connected to ESP32-S3 hardware **PCNT Unit 0**, capturing rising edges without CPU cycle consumption.
* **Angular Velocity Derivation:**
  $$\omega_{\text{rotor}} = \left( \frac{\Delta \text{Pulses}}{P \times \Delta t} \right) \times 60 \quad [\text{RPM}]$$
  where $P = 2$ pulses per mechanical revolution and integration window $\Delta t = 1.0\,\text{s}$.

---

### 4. Master Circuit Netlist Table

The netlist below establishes all electrical connections across the node subsystems:

| Net Name | Operating Voltage | Driver / Source Pin | Receiver / Destination Pin(s) | Pull-Up / Series Element | Functional Specification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `NET_VBUS` | +5.00 V DC | USB-C Connector (J1: A4/B4, A9/B9) | AMS1117-3.3 (U1: Pin 3), WS2812B (U5: Pin 1) | C1 (10 µF Tant), C2 (100 nF Cer) | Main raw DC supply rail |
| `NET_3V3` | +3.30 V DC | AMS1117-3.3 (U1: Pin 2 / Tab) | ESP32-S3 (U2: Pin 2), SCD30 (U3: Pin 1), DHT22 (U4: Pin 1), J2 (Pin 1), R1, R2, R3, R4 | C3 (22 µF Cer), C4 (100 nF Cer) | Regulated system power rail |
| `NET_GND` | 0.00 V DC | Common Ground Point | J1 (GND), U1 (Pin 1), U2 (Pin 1), U3 (Pin 2), U4 (Pin 4), U5 (Pin 3), J2 (Pin 3), D1-D4 (Cathodes) | Direct plane return | Common reference potential |
| `NET_I2C0_SDA`| 3.3 V Logic | ESP32-S3 (GPIO 8) | Sensirion SCD30 (U3: Pin 4) | R2 (4.7 kΩ pull-up to 3V3) | Bidirectional I²C serial data |
| `NET_I2C0_SCL`| 3.3 V Logic | ESP32-S3 (GPIO 9) | Sensirion SCD30 (U3: Pin 3) | R1 (4.7 kΩ pull-up to 3V3) | Synchronous I²C serial clock |
| `NET_DHT_DATA`| 3.3 V Logic | ESP32-S3 (GPIO 4) | DHT22 / AM2302 (U4: Pin 2) | R3 (10.0 kΩ pull-up to 3V3) | Bidirectional 1-Wire data bus |
| `NET_ACT_BLUE`| 3.3 V PWM | ESP32-S3 (GPIO 18) | Blue LED Actuator (D1: Anode) | R5 (150 Ω series resistor) | 25 kHz PWM purge blower drive |
| `NET_ACT_RED` | 3.3 V Logic | ESP32-S3 (GPIO 17) | Red LED Actuator (D2: Anode) | R6 (330 Ω series resistor) | PTC cabin heater activation |
| `NET_ACT_GRN` | 3.3 V Logic | ESP32-S3 (GPIO 16) | Green LED Actuator (D3: Anode) | R7 (330 Ω series resistor) | Eco ventilation activation |
| `NET_ACT_AMB` | 3.3 V Logic | ESP32-S3 (GPIO 15) | Amber LED Actuator (D4: Anode) | R8 (330 Ω series resistor) | Dehumidification / alert signal |
| `NET_TACHO` | 3.3 V Pulses | Bench Sensor Header (J2: Pin 2) | ESP32-S3 (GPIO 19) | R4 (4.7 kΩ pull-up to 3V3) | Hardware pulse accumulator input |
| `NET_RGB_DATA`| 3.3 V RZ | ESP32-S3 (GPIO 38) | WS2812B Smart LED (U5: Pin 4) | R9 (330 Ω series damping) | High-speed optical state bitstream |

---

### 5. Comprehensive Bill of Materials (BOM)

| Designator | Qty | Component Description | Value / Model | Manufacturer / Part Number | Package / Footprint | Mounting | Tolerance / Rating |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **U1** | 1 | Linear Voltage Regulator | AMS1117-3.3 | Advanced Monolithic Systems | SOT-223 / TO-252 | SMT / Through-Hole | 3.30 V $\pm 1.5\%$, 800 mA |
| **U2** | 1 | Microcontroller Dual-Core SoC | ESP32-S3-WROOM-1 | Espressif Systems (N16R8) | SMD Module 18x25.5 mm | SMT / DevKit Header | 240 MHz, 16MB Flash, 8MB PSRAM |
| **U3** | 1 | NDIR Optical CO₂ + T/RH Sensor | Sensirion SCD30 | Sensirion AG / 1-101625-01 | Shielded Sensor Box | Through-Hole Header | 400 - 10,000 ppm $\pm(30\text{ppm} + 3\%)$ |
| **U4** | 1 | Capacitive T & RH Sensor | DHT22 / AM2302 | Aosong Electronics | 4-Pin Single Row | Through-Hole | $\pm 0.5\,^\circ\text{C}$, $\pm 2\% - 5\%\,\text{RH}$ |
| **U5** | 1 | Addressable RGB Smart LED | WS2812B | Worldsemi Co. | SMD 5050 Top View | SMT / Breakout | 24-bit True Colour, 800 kHz RZ |
| **D1** | 1 | Purge Blower Actuator LED | 5 mm Round Diffused | Kingbright L-53GD-BLUE | Radial 5 mm Lead | Through-Hole | $\lambda = 468\,\text{nm}$, $V_f = 3.00\,\text{V}$ |
| **D2** | 1 | Cabin Heater Actuator LED | 5 mm Round Diffused | Kingbright L-53ID-RED | Radial 5 mm Lead | Through-Hole | $\lambda = 625\,\text{nm}$, $V_f = 1.90\,\text{V}$ |
| **D3** | 1 | Eco Ventilation Actuator LED | 5 mm Round Diffused | Kingbright L-53GD-GREEN | Radial 5 mm Lead | Through-Hole | $\lambda = 525\,\text{nm}$, $V_f = 2.10\,\text{V}$ |
| **D4** | 1 | Alert / Dehum Actuator LED | 5 mm Round Diffused | Kingbright L-53YD-YELLOW | Radial 5 mm Lead | Through-Hole | $\lambda = 590\,\text{nm}$, $V_f = 2.00\,\text{V}$ |
| **R1, R2** | 2 | I²C Pull-Up Resistors | 4.7 kΩ | Yageo / RC0805FR-074K7L | Axial 0.25 W / 0805 | Through-Hole / SMT | $\pm 5\%$, 250 mW |
| **R3** | 1 | 1-Wire Bus Pull-Up Resistor | 10.0 kΩ | Yageo / RC0805FR-0710KL | Axial 0.25 W / 0805 | Through-Hole / SMT | $\pm 5\%$, 250 mW |
| **R4** | 1 | Tachometer Pull-Up Resistor | 4.7 kΩ | Yageo / RC0805FR-074K7L | Axial 0.25 W / 0805 | Through-Hole / SMT | $\pm 5\%$, 250 mW |
| **R5** | 1 | Blue LED Limiting Resistor | 150 Ω | Yageo / RC0805FR-07150RL| Axial 0.25 W / 0805 | Through-Hole / SMT | $\pm 5\%$, 250 mW |
| **R6, R7, R8**| 3 | Red, Green, Amber Limiters | 330 Ω | Yageo / RC0805FR-07330RL| Axial 0.25 W / 0805 | Through-Hole / SMT | $\pm 5\%$, 250 mW |
| **R9** | 1 | WS2812B Line Damping Resistor| 330 Ω | Yageo / RC0805FR-07330RL| Axial 0.25 W / 0805 | Through-Hole / SMT | $\pm 5\%$, 250 mW |
| **C1** | 1 | Input Bulk Filter Capacitor | 10 µF | KEMET T491A106K016AT | Molded Tantalum Case A | SMT / Through-Hole | $\pm 10\%$, 16 V, Low ESR |
| **C2** | 1 | High-Frequency Bypass Cap | 100 nF | Murata GRM188R71C104KA | Ceramic Disc / 0603 | Through-Hole / SMT | $\pm 10\%$, 25 V, X7R |
| **C3** | 1 | Output Stabilisation Capacitor | 22 µF | Murata GRM21BR61A226ME | Ceramic 0805 / Radial | SMT / Through-Hole | $\pm 20\%$, 10 V, X5R |
| **C4, C5** | 2 | Local Decoupling Capacitors | 100 nF | Murata GRM188R71C104KA | Ceramic Disc / 0603 | Through-Hole / SMT | $\pm 10\%$, 25 V, X7R |
| **J1** | 1 | Power Ingress Connector | USB-C 16-Pin Receptacle | GCT USB4085-GF-A | USB-C Mid-Mount | SMT / Breadboard | 5.0 V DC, 3.0 A max |
| **J2** | 1 | Tachometer Bench Terminal | 3-Pin 2.54 mm Header | Molex KK 254 (22-28-4033)| Straight Male Pin Header| Through-Hole | 250 V, 4.0 A rating |

---

### 6. Electrical Budget, Power Analysis, and Safety Derivations

The node power budget is calculated under three distinct operational regimes:

| Subsystem Component | Idle State ($I_{\text{idle}}$) | Nominal Operating ($I_{\text{nom}}$) | Peak Wi-Fi Transmission Burst ($I_{\text{peak}}$) | Supply Rail |
| :--- | :--- | :--- | :--- | :--- |
| **ESP32-S3 SoC (Xtensa Dual-Core)** | 45.0 mA | 85.0 mA | 280.0 mA (802.11b TX @ 20 dBm) | +3.3 V DC |
| **Sensirion SCD30 (NDIR Optical)** | 0.5 mA (Sleep) | 19.0 mA (Average continuous) | 75.0 mA (Optical lamp flash) | +3.3 V DC |
| **DHT22 Transducer (AM2302)** | 0.05 mA | 1.5 mA (During sampling) | 2.5 mA | +3.3 V DC |
| **4-Channel LED Actuator Matrix** | 0.0 mA | 5.64 mA (Ch 1 + Ch 3 active) | 13.82 mA (All 4 channels active) | +3.3 V DC |
| **WS2812B RGB Smart Annunciator** | 1.0 mA | 18.0 mA (Single optical colour) | 55.0 mA (Full 100% white test) | +5.0 V DC |
| **I²C and Tacho Pull-Up Resistors** | 0.0 mA | 1.40 mA | 2.10 mA | +3.3 V DC |
| **Cumulative Total Node Current** | **46.55 mA** | **130.54 mA** | **428.42 mA** | **USB-C 5.0 V** |

##### Key Observations on Electrical Margins
1. **USB 2.0 Ingress Limit:** Standard USB 2.0 host ports supply up to $500.0\,\text{mA}$. The peak current consumption ($428.42\,\text{mA}$) occurs during simultaneous Wi-Fi 802.11b transmit bursts, SCD30 infrared lamp pulse, and full-intensity WS2812B illumination, maintaining a $14.3\%$ safety margin below the $500\,\text{mA}$ threshold.
2. **LDO Headroom:** The AMS1117-3.3 regulator provides up to $800\,\text{mA}$ continuous output current. The peak load on the +3.3 V rail is $373.42\,\text{mA}$, utilising only $46.7\%$ of rated regulator capacity.
3. **Microcontroller GPIO Safety:** The total simultaneous current sourced across GPIO pins 15, 16, 17, and 18 is $13.82\,\text{mA}$, which is well below the maximum total chip limit of $120.0\,\text{mA}$.

---

### 7. Noise Mitigation, High-Speed Layout, and Bench Wiring Guidelines

To ensure deterministic timing and avoid transmission anomalies on the bench, the following wiring and PCB design guidelines must be observed:

1. **Decoupling Capacitor Proximity:**
   * Capacitor $C_4$ ($100\,\text{nF}$) must be located within 5.0 mm of the ESP32-S3 `3V3` and `GND` pins with direct, wide traces.
   * Capacitor $C_5$ ($100\,\text{nF}$) must be placed directly across pins 1 and 3 of the WS2812B package to attenuate switching noise.
2. **I²C Trace Routing & Length:**
   * Traces for `NET_I2C0_SDA` and `NET_I2C0_SCL` must not exceed 200 mm in total length when connecting breadboard modules.
   * Ground lines should be routed parallel to clock and data traces to suppress capacitive and inductive crosstalk from the high-frequency $25.0\,\text{kHz}$ LEDC PWM signal on GPIO 18.
3. **Signal Reflection Suppression:**
   * Damping resistor $R_9$ ($330\,\Omega$) must be placed adjacent to GPIO 38 to damp transmission line reflections on the single-wire RZ signal feeding the WS2812B.
4. **Star-Ground Topology:**
   * High-frequency digital return currents from the WS2812B and the LED actuator array must not flow through the analogue sensor ground returns of the SCD30 and DHT22. Connect all ground leads back to a central star ground at the output of the LDO.
5. **Acoustic and Electromagnetic Silence:**
   * Driving discrete LEDs rather than inductive electric motors eliminates magnetic hysteresis hum, motor commutation sparks, and back-EMF voltage spikes.

---

### 8. Verification and Quality Assurance Sign-Off

* **Schematic Vector Asset:** `docs/assets/circuit_schematic.svg` (Validated XML, 1680x1160 px, 100% vector scalability).
* **Electrical Safety Audit:** Passed (Total GPIO source: 13.82 mA / 120 mA limit; LDO thermal dissipation: 0.28 W; peak node current: 428 mA / 500 mA USB limit).
* **Firmware Configuration Parity:** 100% matched with `firmware/esp32s3_cabin_node/main/app_config.h`.
* **Standardisation Compliance:** ETSI TS 118 101, oneM2M Release 4, and Standard British English conventions.
