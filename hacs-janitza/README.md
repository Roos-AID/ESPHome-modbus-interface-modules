# Janitza for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

A Home Assistant integration for the **Janitza UMG 96RM** and **UMG 508**
power analysers, read over Modbus: voltages, currents, power, power factor, frequency, harmonic
distortion and the meter's energy counters, ready for the energy dashboard.

This is the community test release of an integration intended for Home
Assistant Core. It runs on Home Assistant's own Modbus connection layer, so
the meter can share a gateway or RS-485 bus with other Modbus integrations
without them competing for it.

## Supported devices

- UMG 96RM, UMG 96RM-P and UMG 96RM-CBM, over RS-485 (Modbus RTU)
- UMG 96RM-EL and UMG 96RM-E, over Ethernet (Modbus TCP)
- UMG 508, over its own Ethernet port (Modbus TCP, recommended) or RS-485
  (Modbus RTU)

## Requirements

Home Assistant 2026.10.0 or later. Nothing to install besides the
integration: it uses the Modbus libraries Home Assistant already ships.

## Installation

### HACS

1. In HACS, open the menu in the top right and choose **Custom repositories**.
2. Add `https://github.com/OWNER/hacs-janitza` with type **Integration**.
3. Search for **Janitza**, download it, and restart Home Assistant.

### Manually

Copy `custom_components/janitza` into the `custom_components` folder of your
Home Assistant configuration and restart.

## Configuration

Go to **Settings** > **Devices & services** > **Add integration** and pick
**Janitza**. Pick the model (**UMG 96RM** or **UMG 508**), then how the meter
is reached:

- **Network (Modbus TCP)**: host, port (502) and Modbus unit ID. For a UMG
  508 or an Ethernet UMG 96RM directly, or an RS-485 model behind a Modbus
  TCP gateway.
- **Serial port (Modbus RTU)**: serial port, baud rate and Modbus unit ID.
  Covers USB adapters and serial ports shared over the network by a serial
  proxy, such as an ESPHome device.

The UMG 96RM leaves the factory at device address 1 (parameter 000) and
115200 baud (parameter 001), with 8 data bits, no parity and one stop bit. The
integration reads its serial number to identify it.

### UMG 508

- Over Ethernet the UMG 508 answers Modbus TCP on port 502 itself. The
  **Modbus unit ID** is the device address set for its RS-485 interface
  (default 1), also when you reach it over the network.
- On its RS-485 line it uses 8 data bits, no parity and 2 stop bits; set the
  baud rate to what the meter is configured for.
- The UMG 508 does not report a serial number in the registers this
  integration reads, so it is identified by its link: host and port (or serial
  port) plus unit ID. Moving the meter to another IP address with
  **Reconfigure** keeps its entities and history; adding it again as a new
  entry does not.
- Beyond the shared measurements, the UMG 508 also gets **Energy consumed
  (all tariffs)** and **Energy delivered (all tariffs)**, an **Active tariff**
  sensor (diagnostic, disabled by default), its CT and VT ratios, and its
  firmware release on the device page. These come from the UMG 509-PRO
  address list (registers 13949-14008, 14176-14207 and 17435), which the
  UMG 508 is expected to share. Each is read as a block of its own: if the
  meter refuses one, only those sensors go unavailable.

The connection details of either model can be changed later with
**Reconfigure**.

## Entities

Both models get the same measurement sensors, named after the entry (for
example `sensor.umg_508_active_power`).

Enabled by default: voltage L1-N/L2-N/L3-N, current L1/L2/L3, active power
per phase and total, frequency, energy consumed, energy delivered, net
energy, and phase rotation.

Disabled by default, and can be enabled from the device page: line-to-line
voltages, neutral current, apparent and reactive power, power factor,
per-phase energy, apparent and reactive energy, THD of voltage and current,
and the configured CT and VT ratios.

For the energy dashboard use **Energy consumed** as grid consumption and
**Energy delivered** as return to grid. Active power is positive while
consuming and negative while delivering, as the current transformers are
wired. **Energy consumed** is the counter from the "frequently required
readings" (register 19068), which Janitza labels as tariff 1 only. On a UMG
508, use **Energy consumed (all tariffs)** and **Energy delivered (all
tariffs)** in the energy dashboard instead: they keep counting when the meter
switches to tariff 2.

Measurements refresh every 10 seconds (two Modbus requests), the UMG 96RM's
transformer ratios every 5 minutes. The integration is read-only.

## Reporting a problem

Enable debug logging for `custom_components.janitza` and `modbus_connection`,
and attach the integration's diagnostics download to the issue: it holds every
register the integration reads, undecoded, with the serial number left out.

## How this repository is built

The register map lives in a separate device library,
[janitza-modbus](https://github.com/OWNER/janitza-modbus), which has no
Home Assistant dependency. Until it is published on PyPI, a copy of it is
vendored in `custom_components/janitza/janitza_modbus`, imported relatively,
so the integration installs without any extra requirement. Do not edit that
copy; refresh it from a library checkout instead:

```bash
scripts/vendor ../janitza-modbus
```

Once the library is on PyPI, the vendored copy can be dropped in favour of a
`janitza-modbus==x.y.z` requirement in `manifest.json`, and the imports go
back to `from janitza_modbus import ...` — which is exactly the Core version
of this integration.

File | Purpose
-- | --
`custom_components/janitza/` | The integration
`custom_components/janitza/janitza_modbus/` | The vendored device library (see `VENDORED.md`)
`tests/` | Tests, run with `pytest-homeassistant-custom-component`
`.devcontainer.json` | Development container for Visual Studio Code
`.github/workflows/` | Lint (ruff), Test (pytest), Validate (hassfest and HACS)
`.github/renovate.json`, `.github/_dependabot.yml` | Dependency updates (Renovate on, Dependabot off)
`scripts/setup`, `scripts/develop`, `scripts/lint` | Install, run Home Assistant with the integration, lint
`scripts/vendor` | Refresh the vendored library

## Development

```bash
scripts/setup                                 # install Home Assistant and lint tools
python3 -m pip install -r requirements_test.txt
python3 -m pytest                             # run the tests
scripts/lint                                  # ruff format and fix
scripts/develop                               # start Home Assistant on :8123
```

## License

Apache-2.0, like the vendored library.
