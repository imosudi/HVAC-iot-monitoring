# LED Actuator Circuit and Hardware Interfacing Specification

## Cyber-Physical Actuator Emulation for the Software-Defined Vehicle (SDV) MVP

**Document Version:** 1.0.0  
**Target Platform:** Espressif ESP32-S3-WROOM-1 (N16R8 Dual-Core SoC)  
**Lead Hardware Engineer:** Ashok Ramalingam  
**Academic Affiliation:** University of Applied Sciences Technikum Wien (FH Technikum Wien)  

---

### 1. Actuator Emulation Strategy Overview

In production Software-Defined Vehicles, the climate control pipeline modulates high-power physical subsystems: brushless DC (BLDC) centrifugal blower motors, positive temperature coefficient (PTC) heating elements, air-mixing stepper flappers, and refrigerant solenoid valves.

For the benchtop Minimum Viable Product (MVP), physical devices are emulated using an array of discrete coloured light-emitting diodes (LEDs). This approach eliminates:
* High-voltage automotive power supplies (+12.0 V to +48.0 V DC) and high current demands (> 15 A).
* Acoustic interference and stator coil whine on the development bench.
* Inductive flyback transients and thermal dissipation hazards.

Simultaneously, the physical cybernetic interface remains completely authentic: the ESP32-S3 microcontroller modulates physical output pins via hardware pulse-width modulation (LEDC) and digital logic, producing verifiable optical changes in response to closed-loop oneM2M directives.

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           LED ACTUATOR INTERFACE TOPOLOGY                       │
└─────────────────────────────────────────────────────────────────────────────────┘
  ESP32-S3 GPIO Outputs                   Current Limiter       Emulated Subsystem
 ┌──────────────────────┐
 │ GPIO 18 (LEDC PWM)   ├───[ 150 Ω Resistor ]───[ >| Blue LED ]    (Purge Blower / AC)
 │ GPIO 17 (Digital DO) ├───[ 330 Ω Resistor ]───[ >| Red LED ]     (PTC Cabin Heater)
 │ GPIO 16 (Digital DO) ├───[ 330 Ω Resistor ]───[ >| Green LED ]   (Eco Ventilation)
 │ GPIO 15 (Digital DO) ├───[ 330 Ω Resistor ]───[ >| Amber LED ]   (Alert / Dehumidifier)
 │                      │
 │ GPIO 38 (RMT Serial) ├───[ 330 Ω Damping ]────[ WS2812B RGB ]    (Node Health Annunc.)
 └──────────────────────┘                                 │
  Common Ground Rail ─────────────────────────────────────┴─────────────────────────
```

---

### 2. LED Component Electrical Specifications

Standard 5 mm diffused indicator LEDs are employed across four distinct optical channels, complemented by an onboard addressable WS2812B RGB LED for system lifecycle signalling:

| Actuator Function | Lens Colour | Dominant Wavelength ($\lambda$) | Forward Voltage ($V_f$) | Max Current ($I_{\max}$) | Nominal Testbench Current ($I_f$) | Semiconductor Material |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Purge / Cooling** | **Blue** | $465\,\mathrm{nm} - 470\,\mathrm{nm}$ | $3.00\,\mathrm{V}$ | $20\,\mathrm{mA}$ | $2.00\,\mathrm{mA}$ | Indium Gallium Nitride (InGaN) |
| **Cabin Heating** | **Red** | $620\,\mathrm{nm} - 630\,\mathrm{nm}$ | $1.90\,\mathrm{V}$ | $20\,\mathrm{mA}$ | $4.24\,\mathrm{mA}$ | Aluminium Gallium Indium Phosphide (AlGaInP) |
| **Eco Ventilation** | **Green** | $520\,\mathrm{nm} - 530\,\mathrm{nm}$ | $2.10\,\mathrm{V}$ | $20\,\mathrm{mA}$ | $3.64\,\mathrm{mA}$ | Gallium Phosphide (GaP) |
| **Alert / Dehumidify**| **Amber / Yellow**| $585\,\mathrm{nm} - 595\,\mathrm{nm}$ | $2.00\,\mathrm{V}$ | $20\,\mathrm{mA}$ | $3.94\,\mathrm{mA}$ | Gallium Arsenide Phosphide (GaAsP) |
| **Node Annunciator** | **RGB (WS2812B)** | Multi-channel ($R, G, B$) | $5.00\,\mathrm{V}$ ($V_{\mathrm{DD}}$) | $60\,\mathrm{mA}$ (full white) | $18.0\,\mathrm{mA}$ (typical) | Integrated Controller + RGB Die |

---

### 3. Current-Limiting Resistor Derivations and Power Ratings

The ESP32-S3 output pads supply a nominal logic high level $V_{\mathrm{OH}} = 3.30\,\mathrm{V}$. To protect the microcontroller output transistors and maintain LED longevity, series current-limiting resistors ($R$) are inserted into each anode path:

#### 3.1 Mathematical Derivation (Ohm's Law)
$$R_{\mathrm{calc}} = \frac{V_{\mathrm{OH}} - V_f}{I_f}$$

#### 3.2 Power Dissipation Derivation (Joule's Law)
$$P_{\mathrm{resistor}} = I_f^2 \times R = (V_{\mathrm{OH}} - V_f) \times I_f$$

#### 3.3 Design Calculations per Channel:
1. **Blue LED Actuator (GPIO 18):**
   * $V_{\mathrm{OH}} - V_f = 3.30\,\mathrm{V} - 3.00\,\mathrm{V} = 0.30\,\mathrm{V}$
   * Selected Standard Resistor: **$150\,\Omega$** (E24 series, 5% tolerance)
   * Resulting Current: $I_f = \frac{0.30\,\mathrm{V}}{150\,\Omega} = 2.00\,\mathrm{mA}$
   * Power Dissipation: $P = (0.30\,\mathrm{V}) \times (0.002\,\mathrm{A}) = 0.60\,\mathrm{mW}$ (Exceedingly safe for 250 mW 1/4 W resistors)
   * *Note on InGaN Efficacy:* Modern InGaN blue dies emit substantial luminous flux even at 2.0 mA, preventing blinding glares during bench testing.

2. **Red LED Actuator (GPIO 17):**
   * $V_{\mathrm{OH}} - V_f = 3.30\,\mathrm{V} - 1.90\,\mathrm{V} = 1.40\,\mathrm{V}$
   * Selected Standard Resistor: **$330\,\Omega$** (E24 series, 5% tolerance)
   * Resulting Current: $I_f = \frac{1.40\,\mathrm{V}}{330\,\Omega} = 4.24\,\mathrm{mA}$
   * Power Dissipation: $P = (1.40\,\mathrm{V}) \times (0.00424\,\mathrm{A}) = 5.94\,\mathrm{mW}$ (Safe for 1/4 W rating)

3. **Green LED Actuator (GPIO 16):**
   * $V_{\mathrm{OH}} - V_f = 3.30\,\mathrm{V} - 2.10\,\mathrm{V} = 1.20\,\mathrm{V}$
   * Selected Standard Resistor: **$330\,\Omega$** (E24 series, 5% tolerance)
   * Resulting Current: $I_f = \frac{1.20\,\mathrm{V}}{330\,\Omega} = 3.64\,\mathrm{mA}$
   * Power Dissipation: $P = (1.20\,\mathrm{V}) \times (0.00364\,\mathrm{A}) = 4.37\,\mathrm{mW}$ (Safe for 1/4 W rating)

4. **Amber LED Actuator (GPIO 15):**
   * $V_{\mathrm{OH}} - V_f = 3.30\,\mathrm{V} - 2.00\,\mathrm{V} = 1.30\,\mathrm{V}$
   * Selected Standard Resistor: **$330\,\Omega$** (E24 series, 5% tolerance)
   * Resulting Current: $I_f = \frac{1.30\,\mathrm{V}}{330\,\Omega} = 3.94\,\mathrm{mA}$
   * Power Dissipation: $P = (1.30\,\mathrm{V}) \times (0.00394\,\mathrm{A}) = 5.12\,\mathrm{mW}$ (Safe for 1/4 W rating)

5. **WS2812B RGB Damping Resistor (GPIO 38):**
   * Selected Resistor: **$330\,\Omega$** series resistor positioned adjacent to the DIN pin to eliminate transmission line ringing and suppress high-frequency reflection spikes.

---

### 4. Microcontroller Pinout and Electrical Isolation Analysis

#### 4.1 Master Interfacing Pin Table

| Pin Identifier | Function / Channel | Mode / Drive Type | Current-Limiting Resistor | Destination Pin | Forward Current |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GPIO 18** | Blue Purge LED | LEDC Timer 0 (25 kHz PWM) | **$150\,\Omega$, 1/4 W, 5%** | Blue LED Anode (Long Lead) | $2.00\,\mathrm{mA}$ |
| **GPIO 17** | Red Heating LED | Digital Push-Pull Output | **$330\,\Omega$, 1/4 W, 5%** | Red LED Anode (Long Lead) | $4.24\,\mathrm{mA}$ |
| **GPIO 16** | Green Eco LED | Digital Push-Pull Output | **$330\,\Omega$, 1/4 W, 5%** | Green LED Anode (Long Lead) | $3.64\,\mathrm{mA}$ |
| **GPIO 15** | Amber Alert LED | Digital Push-Pull Output | **$330\,\Omega$, 1/4 W, 5%** | Amber LED Anode (Long Lead) | $3.94\,\mathrm{mA}$ |
| **GPIO 19** | Bench Tachometer Feedback | PCNT Unit 0 Pulse Accumulator | $4.7\,\mathrm{k}\Omega$ Pull-up to 3.3 V | Hall Output / Function Gen | Negligible |
| **GPIO 38** | WS2812B RGB Status | RMT Peripheral / Serial RZ | **$330\,\Omega$, 1/4 W, 5%** | WS2812B DIN Pin | Negligible logic drive |
| **GND** | Circuit Return | System Reference (0.0 V) | Direct Bus Tie | All LED Cathodes (Flat Edge) | $13.82\,\mathrm{mA}$ (All On) |

#### 4.2 Strapping Pin and Octal PSRAM Isolation Verification
The ESP32-S3 microcontroller possesses several hardware-sensitive bootstrap and memory bus pins that must remain unencumbered:
* **Bootstrap Pins (GPIO 0, 3, 45, 46):** None of these pins are utilised for LED actuation, guaranteeing unhindered system booting and firmware reflashing.
* **Octal Flash / PSRAM Lines (GPIO 26 to 37):** Entirely avoided. The N16R8 variant routes high-speed PSRAM lines internally across these pins.
* **Native USB Lines (GPIO 19, 20):** GPIO 19 is reserved for pulse counter input only when using the external USB-UART bridge (CP2102/CH343). GPIO 15, 16, 17, and 18 are isolated general-purpose I/O pads free of internal bus contention.

#### 4.3 Total Current Budget Assessment
* Cumulative current when all four coloured LED actuators illuminate simultaneously:
  $$I_{\mathrm{total\_actuators}} = 2.00\,\mathrm{mA} + 4.24\,\mathrm{mA} + 3.64\,\mathrm{mA} + 3.94\,\mathrm{mA} = 13.82\,\mathrm{mA}$$
* The ESP32-S3 maximum source current rating is $40\,\mathrm{mA}$ per individual pad and $120\,\mathrm{mA}$ cumulatively across the package.
* Safety margin: Operating at $13.82\,\mathrm{mA}$ represents just **11.5%** of the rated package limit, ensuring cool silicon junction temperatures ($T_J < 45\,^\circ\mathrm{C}$) and zero voltage droop on internal power rails.

---

### 5. Physical Wiring and Breadboard Assembly Guide

```text
  [ ESP32-S3 Node ]                    [ Resistors ]             [ Coloured LEDs ]
 ┌─────────────────┐
 │ GPIO 18 (Pin 18)│───────────────[ 150 Ω Resistor ]───────(A)[ Blue LED  ](K)───┐
 │ GPIO 17 (Pin 17)│───────────────[ 330 Ω Resistor ]───────(A)[ Red LED   ](K)───┤
 │ GPIO 16 (Pin 16)│───────────────[ 330 Ω Resistor ]───────(A)[ Green LED ](K)───┤
 │ GPIO 15 (Pin 15)│───────────────[ 330 Ω Resistor ]───────(A)[ Amber LED ](K)───┤
 │                 │                                                              │
 │ GND     (Pin G) ───────────────────────────────────────────────────────────────┴───(Common GND)
 └─────────────────┘
```

#### Step-by-Step Connection Instructions:
1. **Blue Purge LED (GPIO 18):**
   * Connect a jumper wire from ESP32-S3 **GPIO 18** to a vacant breadboard row.
   * Insert one terminal of a **$150\,\Omega$** resistor (Brown-Green-Brown-Gold) into this row.
   * Insert the opposite resistor terminal into a separate row, connecting to the **Anode** (longer lead) of the **Blue LED**.
   * Insert the **Cathode** (shorter lead, flat side of casing) into the common breadboard **Ground Rail**.
2. **Red Heating LED (GPIO 17):**
   * Connect a jumper wire from ESP32-S3 **GPIO 17** to a vacant breadboard row.
   * Insert one terminal of a **$330\,\Omega$** resistor (Orange-Orange-Brown-Gold) into this row.
   * Connect the opposite resistor terminal to the **Anode** of the **Red LED**.
   * Connect the **Cathode** of the Red LED to the common **Ground Rail**.
3. **Green Eco LED (GPIO 16):**
   * Connect a jumper wire from ESP32-S3 **GPIO 16** to a vacant breadboard row.
   * Insert one terminal of a **$330\,\Omega$** resistor into this row.
   * Connect the opposite resistor terminal to the **Anode** of the **Green LED**.
   * Connect the **Cathode** of the Green LED to the common **Ground Rail**.
4. **Amber Alert LED (GPIO 15):**
   * Connect a jumper wire from ESP32-S3 **GPIO 15** to a vacant breadboard row.
   * Insert one terminal of a **$330\,\Omega$** resistor into this row.
   * Connect the opposite resistor terminal to the **Anode** of the **Amber LED**.
   * Connect the **Cathode** of the Amber LED to the common **Ground Rail**.
5. **Ground Rail Return:**
   * Tie the breadboard Ground Rail directly to an ESP32-S3 **GND** pin.

---

### 6. Closed-Loop Actuator Behaviour and Optical Truth Table

The firmware translates environmental readings and oneM2M closed-loop directives into unambiguous optical feedback:

| Operational State | Environmental Condition | Blue LED (GPIO 18) | Red LED (GPIO 17) | Green LED (GPIO 16) | Amber LED (GPIO 15) | WS2812B (GPIO 38) | Physical HVAC Analogue |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline Eco** | CO₂ $\le 800\,\mathrm{ppm}$, $20.0 \le T \le 23.5\,^\circ\mathrm{C}$ | Off / Low ($20\%$) | **Off** | **ON (Solid)** | **Off** | Green (Solid) | Blower low speed; fresh air intake closed. |
| **Moderate Purge** | $800 < \mathrm{CO_2} \le 1{,}200\,\mathrm{ppm}$ | **PWM $75\%$ (Bright)** | **Off** | **Off** | **Off** | Amber (Solid) | Blower 75% speed; cabin fresh air induction. |
| **Critical Purge** | $\mathrm{CO_2} > 1{,}200\,\mathrm{ppm}$ | **PWM $100\%$ (Max)** | **Off** | **Off** | **Off** | Red (Flashing) | Blower 100% emergency evacuation flush. |
| **Thermal Heating** | $T_{\mathrm{cabin}} < 19.0\,^\circ\mathrm{C}$ | Off | **ON (Solid)** | **Off** | **Off** | Green (Solid) | Auxiliary PTC heating element energised. |
| **Dehumidification**| Relative Humidity $> 65\%$ | Off / Low | **Off** | **Off** | **ON (Solid)** | Amber (Solid) | A/C evaporator dehumidification active. |
| **Sensor Fault** | SCD30 detached / I²C bus timeout | **PWM $50\%$ (Fail-safe)**| **Off** | **Off** | **ON (Flashing)** | Red (Solid) | Deterministic 50% baseline ventilation fallback. |
| **Manual Override** | oneM2M Operator `<cin>` directive | **PWM Commanded** | Reflects Cmd | Reflects Cmd | Reflects Cmd | Blue (Solid) | Dashboard direct driver override. |
