# 07. Environmental & Enclosure Specification (EES)

## Software-Defined Vehicle (SDV) Cyber-Physical Cabin Environmental Monitoring and Closed-Loop HVAC Regulation System

---

## Document Control & Attribution

| Attribute | Specification Detail |
| :--- | :--- |
| **Document Designation** | Environmental & Enclosure Specification (EES) |
| **Project Title** | Cyber-Physical Cabin Environmental Monitoring & Closed-Loop HVAC Regulation in Software-Defined Vehicles |
| **Researcher & Architecture** | **Isiaka Mosudi** (Middleware & Distributed Systems Architecture) |
| **Research Team** | **Isiaka Mosudi**, Ashok Ramalingam, Pooja Janwalkar, AnnaMaria Moçi, Julia Philip |
| **GitHub Repository** | [https://github.com/imosudi/HVAC-iot-monitoring](https://github.com/imosudi/HVAC-iot-monitoring) |
| **Status & Compliance** | Released / Verified (IEC 60529 IP52, UL94 V-0) |

---

## 1. Automotive Cabin Psychrometric Operating Envelope
Automotive passenger compartments represent non-adiabatic environments subject to extreme solar thermal loading, rapid temperature swings, and severe humidity differentials:
- **Operating Temperature:** $-40.0^\circ\text{C}$ to $+70.0^\circ\text{C}$ (conforming to automotive cabin electronic interior standards).
- **Storage / Soak Temperature:** $-40.0^\circ\text{C}$ to $+85.0^\circ\text{C}$.
- **Relative Humidity:** $0\%\text{--}95\%$ non-condensing (up to $100\%$ condensing with active defrost mitigation).
- **Barometric Pressure:** $70\text{ kPa}$ to $110\text{ kPa}$ (barometric pressure compensation supported by Sensirion SCD30).

---

## 2. Ingress Protection Rating & Mechanical Enclosure Design
- **Ingress Protection Rating:** **IP52** compliance according to IEC 60529:
  - First Digit (5): Dust protected — ingress of dust is not entirely prevented, but dust cannot enter in sufficient quantity to interfere with satisfactory operation.
  - Second Digit (2): Protected against vertically falling water drops when enclosure is tilted up to $15^\circ$ from its normal position.
- **Enclosure Material:** Injection-molded automotive-grade Polycarbonate / Acrylonitrile Butadiene Styrene (PC-ABS) blend with **UL94 V-0** flammability rating.
- **Sensor Aspiration Chamber:** The enclosure incorporates a custom **dual-baffle labyrinthine sampling port**. This geometry allows unimpeded natural atmospheric diffusion to the SCD30 optical NDIR cavity while preventing direct solar radiant glare ($>1{,}000\text{ W/m}^2$) from entering the optical chamber and shielding internal electronics from direct liquid droplet splashing.

---

## 3. Thermal Dissipation, Heat Sinking, and Gateway Thermal Management
- **Micro-ECU Dissipation:** The ESP32-S3 module generates $<0.4\text{ W}$ typical power dissipation, cooled entirely through natural ambient convection and PCB copper ground planes.
- **Vehicular Gateway Dissipation:** The Raspberry Pi 5 gateway operates up to $12\text{ W}$ peak load. An integrated aluminum heat spreader and a software-controlled PWM cooling fan are incorporated, tripping automatically when the Broadcom BCM2712 SoC temperature exceeds $65.0^\circ\text{C}$.

---

## 4. Acoustic Mitigation & Noise Enclosure Standards
Automotive acoustic comfort mandates that cabin climate systems introduce minimal audible noise into passenger compartments:
- **Ultrasonic Carrier Locking:** By locking the blower LEDC modulation frequency to **$25{,}000\text{ Hz}$**, all motor winding electromagnetic vibrations are shifted into the ultrasonic range, avoiding acoustic whine.
- **Ambient Acoustic Footprint:** Total radiated acoustic sound pressure is verified at **$<25\text{ dBA}$** at a distance of $0.5\text{ m}$ in quiet ambient conditions.
- **Vibration Isolation:** The fan and circuit assemblies are mounted using silicone elastomeric anti-vibration grommets (Shore hardness 40A) to prevent mechanical vibration transmission into the vehicle dashboard chassis.
