# 08. Hardware-to-Software Integration Specification (H2SIS)

## Software-Defined Vehicle (SDV) Cyber-Physical Cabin Environmental Monitoring and Closed-Loop HVAC Regulation System

---

## Document Control & Attribution

| Attribute | Specification Detail |
| :--- | :--- |
| **Document Designation** | Hardware-to-Software Integration Specification (H2SIS) |
| **Project Title** | Cyber-Physical Cabin Environmental Monitoring & Closed-Loop HVAC Regulation in Software-Defined Vehicles |
| **Researcher & Architecture** | **Isiaka Mosudi** (Middleware & Distributed Systems Architecture) |
| **Research Team** | **Isiaka Mosudi**, Ashok Ramalingam, Pooja Janwalkar, AnnaMaria Moçi, Julia Philip |
| **GitHub Repository** | [https://github.com/imosudi/HVAC-iot-monitoring](https://github.com/imosudi/HVAC-iot-monitoring) |
| **Status & Compliance** | Released / Verified (FreeRTOS, ESP-IDF, POSIX Serial) |

---

## 1. FreeRTOS Real-Time Firmware Task Scheduling & Core Pinning
The ESP32-S3 firmware partitions real-time execution across its dual Xtensa LX7 processor cores using the FreeRTOS real-time kernel:

| Task Designation | Core Affinity | Priority | Periodicity | Stack Allocation | Functional Scope |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `sensor_acquisition_task` | Core 1 | 4 | $2000\text{ ms}$ | $4096\text{ bytes}$ | Samples SCD30 ($\text{I}^2\text{C}$) and DHT22 (1-Wire); validates inter-sensor delta. |
| `actuator_control_task` | Core 1 | 4 | $100\text{ ms}$ | $2048\text{ bytes}$ | Modulates LEDC PWM; reads PCNT tachometer counter; checks motor stall. |
| `network_telemetry_task` | Core 0 | 5 | Event-driven | $8192\text{ bytes}$ | Serialises JSON frames; pushes UART telemetry; receives downlink directives. |
| `watchdog_task` | Core 0 | 6 | $1000\text{ ms}$ | $2048\text{ bytes}$ | Services FreeRTOS Task Watchdog Timer (TWDT); monitors task liveliness. |

---

## 2. Low-Level Bus Drivers & Synchronisation (I2C, 1-Wire, LEDC, PCNT)
1. **$\text{I}^2\text{C}$ Driver:** Initialised via ESP-IDF `i2c_driver_install()` on `I2C_NUM_0` at $100\text{ kHz}$ Standard Mode. Communication with SCD30 utilises a FreeRTOS mutex to guarantee atomic bus access.
2. **Bit-Banged 1-Wire Driver:** DHT22 protocol execution requires microsecond timing accuracy. Firmware wraps 1-wire pin reads/writes in FreeRTOS critical sections (`portENTER_CRITICAL`) to prevent preemption during the $80\,\mu\text{s}$ sensor response sequence.
3. **Hardware LEDC Driver:** Configured in `LEDC_HIGH_SPEED_MODE` using `LEDC_TIMER_0` configured for 10-bit duty resolution ($1024$ steps) and $25{,}000\text{ Hz}$ carrier frequency.
4. **Hardware PCNT Driver:** Configured on `PCNT_UNIT_0` with an input glitch filter ($1\,\mu\text{s}$ filter width) on `GPIO 19`. Every $1000\text{ ms}$, the actuator task queries the accumulator, computes RPM, and resets the counter.

---

## 3. Micro-ECU to Edge Gateway UART Serial Framing Protocol
- **Physical Demarcation:** UART link via USB bridge or GPIO header (`GPIO 43` TXD, `GPIO 44` RXD).
- **Baud Configuration:** $115{,}200\text{ baud}$, 8 data bits, no parity, 1 stop bit (`115200 8N1`).
- **Framing Convention:** Stream frames are formatted as valid UTF-8 JSON objects terminated by an ASCII newline character (`\n` / `0x0A`).
- **Buffer Overflow Protection:** The gateway serial reader implements a circular ring buffer ($64\text{ KB}$) with non-blocking readline polling to prevent buffer overrun during multi-task scheduling spikes.

---

## 4. Actuator Command Protocol & Downlink Deserialisation
When receiving commands over UART, the Micro-ECU expects line-delimited ASCII directive strings:
```text
CMD:PWM=<duty_percent>,MODE=<AUTOMATIC|MANUAL_OVERRIDE|FAILSAFE>\n
```
**Parsing & Response:**
1. Upon reception, the Micro-ECU validates $0 \le \text{duty\_percent} \le 100$.
2. Firmware ramps LEDC PWM to the target setpoint.
3. Micro-ECU replies with an acknowledgment frame:
   ```text
   ACK:PWM=60,RPM=1800,STATUS=OK\n
   ```

---

## 5. Watchdog Integration, Autonomous Edge Fallback, and Failsafe Safeguards
1. **Task Watchdog Timer (TWDT):** A hardware WDT is primed with a $5.0\text{ s}$ timeout. If `sensor_acquisition_task` or `actuator_control_task` hang due to hardware lockup, the chip automatically resets.
2. **Serial Heartbeat Watchdog:** If no downlink command or heartbeat is received from the edge gateway for $> 15.0\text{ s}$ while in automatic mode, the Micro-ECU assumes backhaul severance and triggers **Autonomous Edge Fallback**:
   - The Micro-ECU activates an internal FreeRTOS fallback heuristic.
   - It directly monitors SCD30 $\text{CO}_2$ and dynamically adjusts PWM purge fan duty cycle without external compute dependency.
   - The WS2812B LED pulses Amber to indicate autonomous fallback mode.
