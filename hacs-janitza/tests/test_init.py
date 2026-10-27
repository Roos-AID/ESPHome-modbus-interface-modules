"""Tests for the Janitza integration setup and unload."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusSerialParams,
    ModbusTcpParams,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.janitza.const import (
    DOMAIN,
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)

from . import (
    ACTIVE_POWER_TOTAL_REGISTER,
    MOCK_ENTRY_DATA,
    MOCK_SERIAL,
    MOCK_SERIAL_ENTRY_DATA,
    MOCK_SOFTWARE_RELEASE,
    MOCK_TITLE,
    TRANSFORMERS_REGISTER,
)

POWER_ENTITY = "sensor.umg_96rm_active_power"
CT_ENTITY = "sensor.umg_96rm_ct_primary_l1"


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the entry sets up, reads the meter, and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert hass.states.get(POWER_ENTITY).state == "1550.0"

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("data", "expected_params"),
    [
        pytest.param(
            MOCK_ENTRY_DATA,
            ModbusTcpParams(host="192.168.1.100", port=502),
            id="tcp",
        ),
        pytest.param(
            MOCK_SERIAL_ENTRY_DATA,
            ModbusSerialParams(device="/dev/ttyUSB0", baudrate=115200),
            id="serial",
        ),
    ],
)
async def test_setup_asks_modbus_for_the_unit(
    hass: HomeAssistant,
    mock_get_unit: MagicMock,
    data: dict,
    expected_params: ModbusSerialParams | ModbusTcpParams,
) -> None:
    """Test the entry's link settings become the unit it asks modbus for."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_SERIAL, data=data, title=MOCK_TITLE
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_get_unit.assert_called_once_with(hass, entry, expected_params, 1)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ModbusTimeoutError("silent"), id="timeout"),
        pytest.param(ModbusConnectionError("gone"), id="link_lost"),
        pytest.param(IllegalDataAddressError(), id="refused"),
    ],
)
async def test_setup_retries_when_the_meter_does_not_answer(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    error: Exception,
) -> None:
    """Test setup waits to retry while nothing answers."""
    mock_connection.for_unit(1).fail_requests(error)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the meter is registered with what its identity says."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), init_integration.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Janitza"
    assert device.model == "UMG 96RM"
    assert device.serial_number == MOCK_SERIAL
    assert device.sw_version == str(MOCK_SOFTWARE_RELEASE)


async def test_device_info_without_identity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test a meter refusing its identity still sets up, without a version."""
    mock_connection.for_unit(1).fail_read(750, IllegalDataAddressError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version is None


async def test_a_failed_settings_poll_keeps_the_readings(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test the transformer block failing does not hold up setup or readings."""
    mock_connection.for_unit(1).fail_read(
        TRANSFORMERS_REGISTER, IllegalDataAddressError()
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(POWER_ENTITY).state == "1550.0"


async def test_readings_recover_after_a_dropped_link(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test entities go unavailable while the link is down and come back."""
    unit = mock_connection.for_unit(1)
    unit.fail_requests(ModbusConnectionError("gone"))
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(POWER_ENTITY).state == STATE_UNAVAILABLE
    # The entry is not reloaded: the next poll reconnects by itself.
    assert init_integration.state is ConfigEntryState.LOADED

    unit.fail_requests(None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(POWER_ENTITY).state == "1550.0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_refused_block_marks_only_its_own_entities_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test each block's entities follow their own poll."""
    unit = mock_connection.for_unit(1)
    assert hass.states.get(CT_ENTITY).state == "100.0"

    unit.fail_read(TRANSFORMERS_REGISTER, IllegalDataAddressError())
    freezer.tick(timedelta(seconds=SETTINGS_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CT_ENTITY).state == STATE_UNAVAILABLE
    assert hass.states.get(POWER_ENTITY).state == "1550.0"

    unit.fail_read(TRANSFORMERS_REGISTER, None)
    unit.fail_read(ACTIVE_POWER_TOTAL_REGISTER, IllegalDataAddressError())
    freezer.tick(timedelta(seconds=SETTINGS_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CT_ENTITY).state == "100.0"
    assert hass.states.get(POWER_ENTITY).state == STATE_UNAVAILABLE
