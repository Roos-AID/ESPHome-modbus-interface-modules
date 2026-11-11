# ESPHome Modbus Interface Modules

ESPHome configurations that connect Modbus RS-485 devices to **Home Assistant**.

All configurations run on the **ESP32-C6 WiFi/Zigbee to RS-485 bridge** from Elecram:
<https://elecram.com/products/esp32-c6-wifi-zigbee-to-rs485-bridge>

All of these modules are used in production on my own Home Assistant dashboards.

## Contents

| File | Device | Modbus role | Status |
|------|--------|-------------|--------|
| [abb-b23-kwhmeters-mk.yaml](YAML%20files/abb-b23-kwhmeters-mk.yaml) | 2× ABB B23 kWh meter | Client (reads meters) | Production |
| [ha-sdm630server.yaml](YAML%20files/ha-sdm630server.yaml) | Eastron SDM630 emulator for Eplucon / Ecoforest heat pump | Server (acts as a meter) | Production |
| [varmevt180ww.yaml](YAML%20files/varmevt180ww.yaml) | Varme / Vesttherm heat pump boiler (VT180WW) | Client (reads and writes) | Work in progress |
| [modbus-serialproxy.yaml](YAML%20files/modbus-serialproxy.yaml) | Any Modbus device (e.g. Janitza) | Transparent serial proxy | Production |

---

## Hardware

The bridge uses an ESP32-C6 with a COSMAX13487EESA (MAX13487E-compatible) half-duplex RS-485 transceiver with automatic direction control.

| ESP32-C6 pin | Transceiver pin | Function |
|--------------|-----------------|----------|
| GPIO4 | nSHDN | Shutdown. High = normal operation, low = shutdown |
| GPIO5 | nEN (RE) | Receiver output enable. Used as UART `flow_control_pin` |
| GPIO6 | RO | Receiver output → UART RX |
| GPIO7 | DI | Driver input → UART TX |
| GPIO19 | — | Status LED (heartbeat) |

## Common features

Every configuration includes:

- ESP32-C6, ESP-IDF framework, 4 MB flash
- Encrypted Home Assistant API and OTA updates
- WiFi with fallback hotspot and captive portal
- Local web server (v3)
- Heartbeat LED: short blink every 3 seconds
- Restart button
- Diagnostic text sensors: IP address, SSID, MAC address, config version and ESPHome version
- Most configs: a **"_Logging UART raw byte"** switch to show raw RS-485 traffic in the ESPHome log on demand

Entities whose name starts with an underscore (`_`) are diagnostic/maintenance entities.

## Getting started

1. Create a `secrets.yaml` in your ESPHome config folder:

   ```yaml
   wifi_ssid: "your-ssid"
   wifi_password: "your-wifi-password"
   api_key: "your-32-byte-base64-api-key"
   ota_pw: "your-ota-password"   # only used by abb-b23-kwhmeters-mk.yaml
   ```

2. Copy the YAML file you need into ESPHome.
3. Check the `substitutions:` block at the top of the file (device name, Modbus address, baud rate, Home Assistant entity IDs).
4. Flash the bridge via USB the first time; after that, updates can be done over the air.

### About log levels

`logger: level:` sets the **compile-time maximum** log level. The logging switches can only change the level at runtime up to that maximum. If it is set to `INFO`, debug messages are removed at compile time and no switch can bring them back. Use `VERBOSE` or `DEBUG` while troubleshooting, then set it back to `INFO` to save flash and CPU.

---

## 1. ABB B23 kWh meters

**File:** `abb-b23-kwhmeters-mk.yaml`

Reads the most important registers from **two ABB B23 kWh meters** on the same RS-485 bus. Each meter is polled by two controllers with different intervals: fast values every 20 s, energy counters every 120 s.

> **Note:** requires ESPHome 2026.9.0 or later, because two Modbus devices are polled on the same bus.

**Bus settings:** 19200 baud, 8N1

| Meter | Modbus address | Entity prefix |
|-------|----------------|---------------|
| Main meter | 1 | `Hoofd` |
| Backup meter | 2 | `Bkup` |

**Sensors per meter** (holding registers):

| Measurement | Register | Unit | Interval |
|-------------|----------|------|----------|
| Active import total | 0x5000 | kWh | 120 s |
| Active import L1 / L2 / L3 | 0x5460 / 0x5464 / 0x5468 | kWh | 120 s |
| Voltage L1 / L2 / L3 | 0x5B00 / 0x5B02 / 0x5B04 | V | 20 s |
| Voltage L1-L2 / L3-L2 / L1-L3 | 0x5B06 / 0x5B08 / 0x5B0A | V | 20 s |
| Current L1 / L2 / L3 | 0x5B0C / 0x5B0E / 0x5B10 | A | 20 s |
| Active power total | 0x5B14 | W | 20 s |
| Active power L1 / L2 / L3 | 0x5B16 / 0x5B18 / 0x5B1A | W | 20 s |
| Power factor | 0x5B3A | — | 20 s |

Neutral current (0x5B12) and DMTME current registers are included but commented out.

---

## 2. Eastron SDM630 emulator (Modbus server)

**File:** `ha-sdm630server.yaml`

The bridge acts as a **Modbus RTU server (slave)** and answers register requests as if it were a real Eastron SDM630 three-phase meter. The values come from your **P1 smart meter sensors in Home Assistant**, not from its own measurements.

It is used as the SDM630 kWh meter for an **Eplucon / Ecoforest heat pump**. This heat pump needs live energy and power data from the main utility meter to optimise its energy use. It can also be adapted for inverters or EV chargers that expect an SDM630.

**Bus settings (Eplucon Th-touch):** address 5, 19200 baud, 8N2

### Registers used by Eplucon

Eplucon only reads four values:

| Register | Meaning |
|----------|---------|
| 0x0034 | Total system power (W). **Inverted for Eplucon:** positive = export, negative = import |
| 0x0046 | Grid frequency (Hz) |
| 0x0048 | Total import energy (kWh) |
| 0x004A | Total export energy (kWh) |

### All emulated registers (input registers, FP32)

| Register | Value | Source |
|----------|-------|--------|
| 0x0000–0x0004 | Voltage L1–L3 | P1 meter |
| 0x0006–0x000A | Current L1–L3 | P1 meter |
| 0x000C–0x0010 | Active power L1–L3 (consumption − production) | P1 meter |
| 0x0012–0x0016 | Apparent power L1–L3 | \|P\| (power factor assumed 1) |
| 0x0018–0x001C | "Net power" L1–L3 | Same as active power (verified against a real SDM630) |
| 0x001E–0x0022 | Direction L1–L3 | +1 = import, −1 = export |
| 0x002A | Average phase voltage | Calculated |
| 0x002E | Average current | Calculated |
| 0x0030 | Sum of phase currents | Calculated |
| 0x0034 | Total active power | P1 meter (inverted, see above) |
| 0x0038 | Total apparent power | \|P total\| |
| 0x003C | Total reactive power | Fixed 0 |
| 0x003E | Total direction | +1 / −1 |
| 0x0046 | Frequency | Fixed 50.0 Hz |
| 0x0048 / 0x004A | Total import / export energy | Sum of tariff T1 + T2 |
| 0x00C8–0x00CC | Line-to-line voltages | Calculated with 120° phase shift |
| 0x0156 | Total energy (import + export) | Calculated |

### Before flashing

1. Change the `ha_*` entity IDs in `substitutions:` to the entity IDs of **your** P1 meter integration (default: `sensor.p1ultra_*`). Find them in Home Assistant under *Settings → Devices & services → Entities*.
2. Set `modbus_address`, `baudrate` and `stopbits` to what your heat pump, inverter or charger expects.
3. Per-phase voltage and current are only available on DSMR 5.0+ meters. If your meter does not provide them, replace those sensors with fixed or calculated values (e.g. 230 V and current = power / 230).

### Limitations

- A P1 telegram has no frequency, reactive power or power factor. These registers use fixed or approximated values.
- Line-to-line voltages are calculated, not measured.
- This is an emulation for monitoring and load management, **not** a certified (MID) meter. Do not use it for billing.

### Diagnostics

Two switches make the bus traffic visible in the ESPHome log:

- **_Logging Modbus server** – shows which registers are being requested
- **_Logging UART raw byte** – shows the raw bytes on the RS-485 bus

---

## 3. Varme / Vesttherm heat pump boiler

**File:** `varmevt180ww.yaml`

Reads and controls a **Varme VT180WW** heat pump boiler. Probably also works with VT100WW, VT100C, VT180C, VT3120 and similar models.

> **Status:** work in progress. Some registers are not working yet and are commented out.

**Bus settings:** address 1, 19200 baud, 8E1, polled every 60 s

**Temperatures** (input registers):

| Entity | Register |
|--------|----------|
| Evaporator temperature (T1) | 7 |
| Boiler temperature (T2) | 8 |

**Status** (binary sensors): pressure switch, PV input, compressor, electric element, boiler function, solenoid valve, condenser, fan, status and alarm.

**Settings** (holding registers, writable):

| Entity | Register | Range |
|--------|----------|-------|
| Target temperature | 4 | 5–62 °C |
| T minimum | 5 | 5–62 °C |
| T2 minimum | 6 | 5–62 °C |
| Operating mode | 12 | Off / Heat pump only / Element only / Heat pump + element / Boiler / Heat pump + boiler |
| Legionella protection | 13 | Off / 60 °C / 65 °C |
| PV mode | 17 | Off / Heat pump only / Element only / Heat pump + element |
| PV temperature heat pump | 18 | 5–62 °C |
| PV temperature element | 19 | 5–62 °C |
| Boost (switch) | 22 | On / Off |
| T maximum | 28 | 5–65 °C |

---

## 4. Modbus serial proxy

**File:** `modbus-serialproxy.yaml`

A generic **serial proxy**: the RS-485 port is exposed to Home Assistant through the ESPHome API. A Home Assistant integration (for example the Janitza integration from HACS) talks Modbus RTU itself; the bridge only forwards the bytes.

- Default settings: 19200 baud, 8E1. These only apply until Home Assistant connects; the integration then sets baud rate, parity and stop bits itself (Janitza: 8N1 + configured baud rate).
- GPIO5 is used for half-duplex direction control, so the bridge's own transmitted bytes are not echoed back to Home Assistant.
- WiFi power saving is disabled to keep latency low on every Modbus request.
- RX buffer is 512 bytes (largest Janitza response is 141 bytes).

---

## License

MIT – see [LICENSE.txt](LICENSE.txt).
