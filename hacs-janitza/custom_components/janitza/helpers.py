"""Helpers for the Janitza integration."""

from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from modbus_connection import ModbusSerialParams, ModbusTcpParams

from .const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    CONF_UNIT_ID,
    DEFAULT_MODEL,
    MODEL_UMG508,
    TYPE_SERIAL,
)
from .janitza_modbus import JanitzaDevice, JanitzaMeter, Umg508

if TYPE_CHECKING:
    from collections.abc import Mapping

    from modbus_connection import ModbusUnit


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE], baudrate=data[CONF_BAUDRATE]
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def model_of(data: Mapping[str, Any]) -> str:
    """Return the meter model an entry names; entries from before models are 96RMs."""
    return str(data.get(CONF_MODEL, DEFAULT_MODEL))


def create_device(
    data: Mapping[str, Any], unit: ModbusUnit, identifier: str
) -> JanitzaDevice:
    """Build the library device for an entry, under the identifier it is kept by."""
    if model_of(data) == MODEL_UMG508:
        return Umg508(unit, serial_number=identifier)
    return JanitzaMeter(unit, serial_number=identifier)


def link_identifier(data: Mapping[str, Any]) -> str:
    """
    Name a meter that reports no serial number by where it is reached.

    The UMG 508 serves none in the registers this integration reads, so what
    tells two of them apart is the host and port, or the serial port, and the
    Modbus unit id.
    """
    if data[CONF_TYPE] == TYPE_SERIAL:
        place = data[CONF_DEVICE]
    else:
        place = f"{data[CONF_HOST]}:{data[CONF_PORT]}"
    return f"{model_of(data)}_{place}_{data[CONF_UNIT_ID]}"
