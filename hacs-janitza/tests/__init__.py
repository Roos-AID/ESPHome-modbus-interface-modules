"""Tests for the Janitza integration."""

import math
import struct

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from modbus_connection.mock import MockModbusUnit

from custom_components.janitza.const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    MODEL_UMG508,
    TYPE_SERIAL,
    TYPE_TCP,
)

MOCK_SERIAL = "7012345"
MOCK_OTHER_SERIAL = "7099999"
MOCK_TITLE = "UMG 96RM"
MOCK_SOFTWARE_RELEASE = 104

MOCK_TCP_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
}

MOCK_ENTRY_DATA = {CONF_TYPE: TYPE_TCP, **MOCK_TCP_INPUT}

MOCK_SERIAL_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: DEFAULT_BAUDRATE,
    CONF_UNIT_ID: 1,
}
MOCK_SERIAL_ENTRY_DATA = {CONF_TYPE: TYPE_SERIAL, **MOCK_SERIAL_INPUT}

# A UMG 508 has no serial number to read: it is known by its link.
MOCK_508_TITLE = "UMG 508"
MOCK_508_TCP_INPUT = {
    CONF_HOST: "192.168.1.60",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
}
MOCK_508_ENTRY_DATA = {
    CONF_TYPE: TYPE_TCP,
    CONF_MODEL: MODEL_UMG508,
    **MOCK_508_TCP_INPUT,
}
MOCK_508_IDENTIFIER = "umg508_192.168.1.60:502_1"
MOCK_508_SERIAL_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: DEFAULT_BAUDRATE,
    CONF_UNIT_ID: 3,
}
MOCK_508_SERIAL_ENTRY_DATA = {
    CONF_TYPE: TYPE_SERIAL,
    CONF_MODEL: MODEL_UMG508,
    **MOCK_508_SERIAL_INPUT,
}
MOCK_508_SERIAL_IDENTIFIER = "umg508_/dev/ttyUSB0_3"

ACTIVE_POWER_TOTAL_REGISTER = 19026
ENERGY_CONSUMED_TOTAL_REGISTER = 19068
TRANSFORMERS_REGISTER = 10

# A three-phase installation drawing about 1.5 kW.
MEASUREMENTS: dict[int, float] = {
    19000: 230.1,
    19002: 231.2,
    19004: 229.8,
    19006: 399.5,
    19008: 400.1,
    19010: 398.7,
    19012: 3.25,
    19014: 4.5,
    19016: 2.0,
    19018: 2.1,
    19020: 700.0,
    19022: 1000.0,
    19024: -150.0,
    19026: 1550.0,
    19028: 748.0,
    19030: 1040.0,
    19032: 460.0,
    19034: 2248.0,
    19036: 120.0,
    19038: -80.0,
    19040: 30.0,
    19042: 70.0,
    19044: 0.98,
    19046: 0.96,
    19048: -0.33,
    19050: 49.98,
    19052: 1.0,
    19054: 1_000_000.0,
    19056: 2_000_000.0,
    19058: -500_000.0,
    19060: 2_500_000.0,
    19062: 1_200_000.0,
    19064: 2_100_000.0,
    19066: 300_000.0,
    19068: 3_600_000.0,
    19070: 200_000.0,
    19072: 100_000.0,
    19074: 800_000.0,
    19076: 1_100_000.0,
    19078: 1_300_000.0,
    19080: 2_200_000.0,
    19082: 500_000.0,
    19084: 4_000_000.0,
    19086: 100_000.0,
    19088: 150_000.0,
    19090: 50_000.0,
    19092: 300_000.0,
    19094: 110_000.0,
    19096: 170_000.0,
    19098: 70_000.0,
    19100: 350_000.0,
    19102: 10_000.0,
    19104: 20_000.0,
    19106: 20_000.0,
    19108: 50_000.0,
    19110: 2.1,
    19112: 2.3,
    19114: 1.9,
    19116: 12.5,
    19118: 8.0,
    19120: 30.0,
}

TRANSFORMERS: dict[int, float] = {
    10: 100.0,
    12: 5.0,
    14: 400.0,
    16: 400.0,
    18: 100.0,
    20: 5.0,
    22: 400.0,
    24: 400.0,
    26: 100.0,
    28: 5.0,
    30: 400.0,
    32: 400.0,
}


def float_words(value: float) -> list[int]:
    """Pack a float into its two registers, most significant word first."""
    hi, lo = struct.unpack(">HH", struct.pack(">f", value))
    return [hi, lo]


def seed_meter(unit: MockModbusUnit, serial: str = MOCK_SERIAL) -> None:
    """Seed a whole UMG 96RM: identity, measurements and transformer ratios."""
    number = int(serial)
    unit.holding[750] = MOCK_SOFTWARE_RELEASE
    unit.holding[754] = [(number >> 16) & 0xFFFF, number & 0xFFFF]
    unit.holding[756] = [0, 1234]
    unit.holding[761] = 0  # no module fitted
    for address in range(19000, 19122, 2):
        unit.holding[address] = float_words(MEASUREMENTS.get(address, math.nan))
    for address, value in TRANSFORMERS.items():
        unit.holding[address] = float_words(value)


MOCK_508_RELEASE = "2.103"
UMG508_TARIFF_REGISTER = 13949
UMG508_TRANSFORMERS_REGISTER = 14176

# Both tariffs together: more than tariff 1 alone (19068).
UMG508_TARIFF_ENERGY: dict[int, float] = {
    13995: 4_100_000.0,
    14007: 1_100_000.0,
}
UMG508_TRANSFORMERS: dict[int, float] = {
    **dict.fromkeys((14176, 14178, 14180), 150.0),
    **dict.fromkeys((14184, 14186, 14188), 5.0),
    **dict.fromkeys((14192, 14194, 14196, 14200, 14202, 14204), 400.0),
}


def seed_umg508(unit: MockModbusUnit) -> None:
    """Seed a UMG 508: measurements, tariff energy, ratios and firmware."""
    for address in range(19000, 19122, 2):
        unit.holding[address] = float_words(MEASUREMENTS.get(address, math.nan))
    unit.holding[13949] = [2, 2]
    for address in range(13951, 14009, 2):
        unit.holding[address] = float_words(UMG508_TARIFF_ENERGY.get(address, math.nan))
    for address in range(14176, 14208, 2):
        unit.holding[address] = float_words(UMG508_TRANSFORMERS.get(address, math.nan))
    data = MOCK_508_RELEASE.encode().ljust(16, b"\0")
    unit.holding[17435] = [
        int.from_bytes(data[i : i + 2], "big") for i in range(0, 16, 2)
    ]
