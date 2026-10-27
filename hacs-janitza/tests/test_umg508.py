"""Tests for a UMG 508: model choice, link-derived identity and its sensors."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from modbus_connection import (
    IllegalDataAddressError,
    ModbusSerialParams,
    ModbusTcpParams,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from custom_components.janitza.config_flow import STEP_RECONFIGURE_TCP
from custom_components.janitza.const import (
    CONF_MODEL,
    DOMAIN,
    MODEL_UMG508,
    TYPE_SERIAL,
    TYPE_TCP,
)

from . import (
    MOCK_508_ENTRY_DATA,
    MOCK_508_IDENTIFIER,
    MOCK_508_RELEASE,
    MOCK_508_SERIAL_ENTRY_DATA,
    MOCK_508_SERIAL_IDENTIFIER,
    MOCK_508_SERIAL_INPUT,
    MOCK_508_TCP_INPUT,
    MOCK_508_TITLE,
    UMG508_TARIFF_REGISTER,
    seed_umg508,
)

POWER_ENTITY = "sensor.umg_508_active_power"
CONSUMED_ENTITY = "sensor.umg_508_energy_consumed"
DELIVERED_ENTITY = "sensor.umg_508_energy_delivered"
ALL_TARIFFS_CONSUMED_ENTITY = "sensor.umg_508_energy_consumed_all_tariffs"
ALL_TARIFFS_DELIVERED_ENTITY = "sensor.umg_508_energy_delivered_all_tariffs"
CT_ENTITY = "sensor.umg_508_ct_primary_l1"


def _patch_temporary_unit(connection: MockModbusConnection):  # noqa: ANN202
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


async def _start_508_flow(hass: HomeAssistant, connection_type: str) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "umg_508"}
    )
    assert result["step_id"] == "connection"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": connection_type}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == connection_type
    return result["flow_id"]


@pytest.mark.parametrize(
    ("connection_type", "user_input", "unit_id", "expected_data", "expected_id"),
    [
        pytest.param(
            TYPE_TCP,
            MOCK_508_TCP_INPUT,
            1,
            MOCK_508_ENTRY_DATA,
            MOCK_508_IDENTIFIER,
            id="tcp",
        ),
        pytest.param(
            TYPE_SERIAL,
            MOCK_508_SERIAL_INPUT,
            3,
            MOCK_508_SERIAL_ENTRY_DATA,
            MOCK_508_SERIAL_IDENTIFIER,
            id="serial",
        ),
    ],
)
async def test_flow_creates_a_508_entry(  # noqa: PLR0917 - parametrized
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    connection_type: str,
    user_input: dict,
    unit_id: int,
    expected_data: dict,
    expected_id: str,
) -> None:
    """Test a UMG 508 is probed on its measurement block and named by its link."""
    connection = MockModbusConnection()
    seed_umg508(connection.for_unit(unit_id))
    flow_id = await _start_508_flow(hass, connection_type)

    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_508_TITLE
    assert result["data"] == expected_data
    assert result["result"].unique_id == expected_id
    # The probe reads the measurement block, never the 96RM identity registers.
    addresses = {event.address for event in connection.for_unit(unit_id).read_events}
    assert addresses == {19000, 19054}


async def test_flow_rejects_a_device_refusing_the_block(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a device answering but refusing the block is not taken for a 508."""
    connection = MockModbusConnection()
    unit = connection.for_unit(1)
    seed_umg508(unit)
    unit.fail_read(19000, IllegalDataAddressError())
    unit.fail_read(19054, IllegalDataAddressError())
    flow_id = await _start_508_flow(hass, TYPE_TCP)

    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_configure(
            flow_id, MOCK_508_TCP_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unrecognized_umg508"}


async def test_flow_aborts_on_the_same_link(hass: HomeAssistant) -> None:
    """Test a second entry for the same host, port and unit is refused."""
    MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_508_IDENTIFIER, data=MOCK_508_ENTRY_DATA
    ).add_to_hass(hass)
    connection = MockModbusConnection()
    seed_umg508(connection.for_unit(1))
    flow_id = await _start_508_flow(hass, TYPE_TCP)

    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_configure(
            flow_id, MOCK_508_TCP_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_a_508_to_a_new_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a new address is accepted and the entry keeps its unique ID."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_508_IDENTIFIER, data=MOCK_508_ENTRY_DATA
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == STEP_RECONFIGURE_TCP

    connection = MockModbusConnection()
    seed_umg508(connection.for_unit(1))
    new_input = {**MOCK_508_TCP_INPUT, CONF_HOST: "192.168.1.61"}
    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_TYPE: TYPE_TCP, CONF_MODEL: MODEL_UMG508, **new_input}
    assert entry.unique_id == MOCK_508_IDENTIFIER


async def test_508_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration_508: MockConfigEntry,
) -> None:
    """Test a UMG 508 sets up with its own blocks and no serial number."""
    assert init_integration_508.state is ConfigEntryState.LOADED
    assert init_integration_508.runtime_data.settings is not None
    assert hass.states.get(POWER_ENTITY).state == "1550.0"
    assert hass.states.get(CONSUMED_ENTITY).state == "3600.0"
    assert hass.states.get(DELIVERED_ENTITY).state == "1100.0"
    assert hass.states.get(ALL_TARIFFS_CONSUMED_ENTITY).state == "4100.0"
    assert hass.states.get(ALL_TARIFFS_DELIVERED_ENTITY).state == "1100.0"

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_508_IDENTIFIER), init_integration_508.entry_id
    )
    assert device is not None
    assert device.model == "UMG 508"
    assert device.manufacturer == "Janitza"
    assert device.serial_number is None
    assert device.sw_version == MOCK_508_RELEASE

    await hass.config_entries.async_unload(init_integration_508.entry_id)
    assert init_integration_508.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_508_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_508: MockConfigEntry,
    mock_get_unit_508: MagicMock,
) -> None:
    """Test a UMG 508 gets the shared sensors, its own and its CT/VT ratios."""
    mock_config_entry_508.add_to_hass(hass)
    with patch("custom_components.janitza.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry_508.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_508.entry_id
    )
    keys = {
        entry.unique_id.removeprefix(f"{MOCK_508_IDENTIFIER}_") for entry in entries
    }
    assert sum(key.startswith(("ct_", "vt_")) for key in keys) == 12
    assert "active_energy_consumed_all_tariffs" in keys
    assert "active_tariff" in keys
    assert len(entries) == 76
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_508.entry_id
    )


async def test_508_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration_508: MockConfigEntry,
) -> None:
    """Test diagnostics for a model without identity or settings."""
    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration_508
    )
    assert diag["model"] == "UMG 508"
    assert diag["identity"] is None
    assert diag["software_release"] == MOCK_508_RELEASE
    assert diag["settings"] == {"updated": ["transformers"], "failed": {}}
    assert diag["readings"] == {
        "updated": ["measurements", "tariff_energy"],
        "failed": {},
    }
    holding = diag["raw"]["holding"]
    for address in ("13949", "14176", "17435", "19000"):
        assert address in holding


async def test_508_refused_tariff_block(
    hass: HomeAssistant,
    mock_connection_508: MockModbusConnection,
    mock_config_entry_508: MockConfigEntry,
    mock_get_unit_508: MagicMock,
) -> None:
    """Test a 508 refusing the tariff block loses only those sensors."""
    mock_connection_508.for_unit(1).fail_read(
        UMG508_TARIFF_REGISTER, IllegalDataAddressError()
    )
    mock_config_entry_508.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_508.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_508.state is ConfigEntryState.LOADED
    assert hass.states.get(POWER_ENTITY).state == "1550.0"
    assert hass.states.get(ALL_TARIFFS_CONSUMED_ENTITY).state == "unavailable"
