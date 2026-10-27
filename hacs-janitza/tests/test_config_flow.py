"""Tests for the Janitza config flow."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, _patch, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from modbus_connection import ModbusSerialParams, ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    get_schema_suggested_value,
)

from custom_components.janitza.config_flow import (
    STEP_RECONFIGURE_SERIAL,
    STEP_RECONFIGURE_TCP,
)
from custom_components.janitza.const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    DOMAIN,
    MODEL_UMG96RM,
    MODEL_UMG508,
    TYPE_SERIAL,
    TYPE_TCP,
)

from . import (
    MOCK_ENTRY_DATA,
    MOCK_OTHER_SERIAL,
    MOCK_SERIAL,
    MOCK_SERIAL_ENTRY_DATA,
    MOCK_SERIAL_INPUT,
    MOCK_TCP_INPUT,
    MOCK_TITLE,
    seed_meter,
)


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant,
        params: ModbusSerialParams | ModbusTcpParams,
        unit_id: int,
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "custom_components.janitza.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


class _RaisingTemporaryUnit:
    """Stand in for a temporary-unit context whose __aenter__ raises."""

    def __init__(self, error: Exception) -> None:
        """Initialize with the error to raise on entry."""
        self._error = error

    async def __aenter__(self) -> None:
        raise self._error

    async def __aexit__(self, *args: object) -> None:
        """No cleanup: entry never succeeded."""


async def _start_flow(
    hass: HomeAssistant, connection_type: str, model: str = MODEL_UMG96RM
) -> str:
    """Open the flow, pick a model and a connection type, and return the flow ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["umg_96rm", "umg_508"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "umg_508" if model == MODEL_UMG508 else "umg_96rm"},
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "connection"
    assert result["menu_options"] == [TYPE_TCP, TYPE_SERIAL]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": connection_type}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == connection_type
    assert result["errors"] == {}

    return result["flow_id"]


@pytest.mark.parametrize(
    ("connection_type", "user_input", "expected_params", "expected_data"),
    [
        pytest.param(
            TYPE_TCP,
            {**MOCK_TCP_INPUT, CONF_PORT: 1502},
            ModbusTcpParams(host="192.168.1.100", port=1502),
            {**MOCK_ENTRY_DATA, CONF_MODEL: MODEL_UMG96RM, CONF_PORT: 1502},
            id="tcp",
        ),
        pytest.param(
            TYPE_SERIAL,
            {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200},
            ModbusSerialParams(device="/dev/ttyUSB0", baudrate=19200),
            {**MOCK_SERIAL_ENTRY_DATA, CONF_MODEL: MODEL_UMG96RM, CONF_BAUDRATE: 19200},
            id="serial",
        ),
    ],
)
async def test_user_step_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    connection_type: str,
    user_input: dict[str, Any],
    expected_params: ModbusSerialParams | ModbusTcpParams,
    expected_data: dict[str, Any],
) -> None:
    """Test each connection type probes the meter and creates an entry."""
    mock_conn = MockModbusConnection()
    seed_meter(mock_conn.for_unit(1))
    flow_id = await _start_flow(hass, connection_type)

    with _patch_temporary_unit(mock_conn) as mock_temporary_unit:
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)

    mock_temporary_unit.assert_called_once_with(hass, expected_params, 1)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_TITLE
    assert result["data"] == expected_data
    assert result["result"].unique_id == MOCK_SERIAL
    assert len(mock_setup_entry.mock_calls) == 1
    # The probe must read only the identity, never poll the meter.
    assert {event.address for event in mock_conn.for_unit(1).read_events} == {
        750,
        754,
        761,
    }


def _seed_unreachable(unit: MockModbusUnit) -> None:
    unit.fail_requests(ModbusTimeoutError("stuck"))


def _seed_unrecognized(unit: MockModbusUnit) -> None:
    """No-op: an unseeded meter answers a serial number of 0."""


@pytest.mark.parametrize(
    ("seed", "expected_error", "expected_placeholders"),
    [
        pytest.param(
            _seed_unreachable,
            "cannot_connect",
            {"error": "stuck"},
            id="cannot_connect",
        ),
        pytest.param(
            _seed_unrecognized,
            "unrecognized_meter",
            {},
            id="unrecognized_meter",
        ),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    seed: Callable[[MockModbusUnit], None],
    expected_error: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Test the user step reports the right error and recovers, per failure."""
    mock_conn = MockModbusConnection()
    seed(mock_conn.for_unit(1))
    flow_id = await _start_flow(hass, TYPE_TCP)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == TYPE_TCP
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == expected_placeholders

    working_conn = MockModbusConnection()
    seed_meter(working_conn.for_unit(1))

    with _patch_temporary_unit(working_conn):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_link_settings_conflict(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a shared-connection link-settings clash surfaces its own message."""
    error = HomeAssistantError(
        "Modbus device ('192.168.1.100', 502) is already in use with different "
        "link settings"
    )
    flow_id = await _start_flow(hass, TYPE_TCP)

    with patch(
        "custom_components.janitza.config_flow.async_get_temporary_unit",
        return_value=_RaisingTemporaryUnit(error),
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == {"error": str(error)}

    working_conn = MockModbusConnection()
    seed_meter(working_conn.for_unit(1))

    with _patch_temporary_unit(working_conn):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    """Test aborting when the meter is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_conn = MockModbusConnection()
    seed_meter(mock_conn.for_unit(1))
    flow_id = await _start_flow(hass, TYPE_TCP)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


_NEW_TCP_INPUT = {**MOCK_TCP_INPUT, CONF_HOST: "192.168.1.200"}


async def _start_reconfigure(
    hass: HomeAssistant, entry: MockConfigEntry, step_id: str
) -> ConfigFlowResult:
    """Open the reconfigure flow and return the form for the entry's link."""
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id

    return result


async def test_reconfigure_updates_the_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfigure updates the entry and reloads it."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_TCP)

    mock_conn = MockModbusConnection()
    seed_meter(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_TCP_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_TYPE: TYPE_TCP,
        CONF_MODEL: MODEL_UMG96RM,
        **_NEW_TCP_INPUT,
    }


async def test_reconfigure_offers_the_current_settings(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the link an entry is on comes back prefilled."""
    entry = _serial_entry()
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_SERIAL)

    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_DEVICE)
        == MOCK_SERIAL_INPUT[CONF_DEVICE]
    )

    mock_conn = MockModbusConnection()
    seed_meter(mock_conn.for_unit(1))
    new_input = {**MOCK_SERIAL_INPUT, CONF_DEVICE: "/dev/ttyUSB1"}

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_TYPE: TYPE_SERIAL,
        CONF_MODEL: MODEL_UMG96RM,
        **new_input,
    }


async def test_reconfigure_rejects_a_different_serial(hass: HomeAssistant) -> None:
    """Test reconfigure aborts if the meter's serial doesn't match."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_TCP)

    mock_conn = MockModbusConnection()
    seed_meter(mock_conn.for_unit(1), serial=MOCK_OTHER_SERIAL)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_TCP_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == MOCK_ENTRY_DATA


@pytest.mark.parametrize(
    ("seed", "expected_error", "expected_placeholders"),
    [
        pytest.param(
            _seed_unreachable,
            "cannot_connect",
            {"error": "stuck"},
            id="cannot_connect",
        ),
        pytest.param(
            _seed_unrecognized,
            "unrecognized_meter",
            {},
            id="unrecognized_meter",
        ),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    seed: Callable[[MockModbusUnit], None],
    expected_error: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Test the reconfigure step reports the right error and recovers."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_TCP)

    mock_conn = MockModbusConnection()
    seed(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_TCP_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_RECONFIGURE_TCP
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == expected_placeholders
    assert entry.data == MOCK_ENTRY_DATA
    # The retry starts from what was typed, not from the stored entry.
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == _NEW_TCP_INPUT[CONF_HOST]
    )

    working_conn = MockModbusConnection()
    seed_meter(working_conn.for_unit(1))

    with _patch_temporary_unit(working_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_TCP_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_TYPE: TYPE_TCP,
        CONF_MODEL: MODEL_UMG96RM,
        **_NEW_TCP_INPUT,
    }


def _serial_entry() -> MockConfigEntry:
    """Build a config entry for a meter on a serial port."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data=MOCK_SERIAL_ENTRY_DATA,
        title=MOCK_TITLE,
    )


@pytest.mark.parametrize(
    ("setup_error", "setup_state"),
    [
        pytest.param(None, ConfigEntryState.LOADED, id="loaded"),
        pytest.param(
            ModbusTimeoutError("stuck"),
            ConfigEntryState.SETUP_RETRY,
            id="silent",
        ),
        pytest.param(ValueError("bug"), ConfigEntryState.SETUP_RETRY, id="setup_retry"),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_reconfigure_new_line_settings(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    setup_error: Exception | None,
    setup_state: ConfigEntryState,
) -> None:
    """Test new line settings take the entry off the bus before probing."""
    entry = _serial_entry()
    entry.add_to_hass(hass)
    states: list[ConfigEntryState] = []

    @asynccontextmanager
    async def _probe_watching_the_entry(
        hass: HomeAssistant,
        params: ModbusSerialParams | ModbusTcpParams,
        unit_id: int,
    ) -> AsyncIterator[MockModbusUnit]:
        states.append(entry.state)
        yield mock_connection.for_unit(unit_id)

    mock_connection.for_unit(1).fail_requests(setup_error)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is setup_state
    mock_connection.for_unit(1).fail_requests(None)

    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_SERIAL)
    with patch(
        "custom_components.janitza.config_flow.async_get_temporary_unit",
        side_effect=_probe_watching_the_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
        )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert states == [ConfigEntryState.NOT_LOADED]
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_BAUDRATE] == 19200
    assert entry.unique_id == MOCK_SERIAL
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_get_unit")
async def test_reconfigure_new_line_settings_cannot_connect(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a failed probe puts the entry back on the bus it was taken off."""
    entry = _serial_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError("stuck"))

    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_SERIAL)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
        )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == MOCK_SERIAL_ENTRY_DATA
    assert entry.unique_id == MOCK_SERIAL
    # Back on the bus, where the silent meter leaves setup waiting to retry.
    assert entry.state is ConfigEntryState.SETUP_RETRY

    mock_connection.for_unit(1).fail_requests(None)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
        )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_get_unit")
async def test_reconfigure_new_line_settings_wrong_device(hass: HomeAssistant) -> None:
    """Test a different meter on the new settings restores the entry."""
    entry = _serial_entry()
    entry.add_to_hass(hass)

    other_conn = MockModbusConnection()
    seed_meter(other_conn.for_unit(1), serial=MOCK_OTHER_SERIAL)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_SERIAL)
    with _patch_temporary_unit(other_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
        )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == MOCK_SERIAL_ENTRY_DATA
    assert entry.unique_id == MOCK_SERIAL
    assert entry.state is ConfigEntryState.LOADED
