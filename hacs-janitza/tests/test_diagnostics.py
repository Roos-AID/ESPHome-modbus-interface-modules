"""Tests for the Janitza diagnostics."""

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from . import TRANSFORMERS_REGISTER


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag == snapshot


async def test_diagnostics_redacts_what_identifies_the_meter(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test the serial and production numbers are redacted, decoded and raw."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["serial_number"] == "**REDACTED**"
    assert diag["identity"]["production_number"] == "**REDACTED**"
    holding = diag["raw"]["holding"]
    for address in range(754, 758):
        assert str(address) not in holding


@pytest.mark.parametrize(
    ("error", "error_name"),
    [
        pytest.param(ModbusTimeoutError("silent"), "ModbusTimeoutError", id="timeout"),
        pytest.param(
            ModbusConnectionError("gone"), "ModbusConnectionError", id="link_lost"
        ),
    ],
)
async def test_diagnostics_meter_unreachable(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
    error: ModbusError,
    error_name: str,
) -> None:
    """Test diagnostics still download when the meter stops answering."""
    unit = mock_connection.for_unit(1)
    unit.fail_requests(error)
    unit.read_events.clear()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["read_error"] == error_name
    assert diag["raw"] is None
    assert len(unit.read_events) == 1


async def test_diagnostics_before_the_settings_answered(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test a settings poll that never answered shows as no report at all."""
    unit = mock_connection.for_unit(1)
    unit.fail_read(TRANSFORMERS_REGISTER, IllegalDataAddressError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert diag["settings"] is None
    assert diag["readings"] == {"updated": ["measurements"], "failed": {}}
    assert diag["read_error"] == "IllegalDataAddressError"
