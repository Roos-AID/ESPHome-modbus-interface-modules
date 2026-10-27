"""Tests for the Janitza sensor platform."""

import math
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.janitza.const import SCAN_INTERVAL
from custom_components.janitza.janitza_modbus import JanitzaMeter, Umg508
from custom_components.janitza.sensor import SENSOR_DESCRIPTIONS

from . import ENERGY_CONSUMED_TOTAL_REGISTER, float_words

CONSUMED_ENTITY = "sensor.umg_96rm_energy_consumed"
ROTATION_ENTITY = "sensor.umg_96rm_phase_rotation"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test all entities match their snapshot."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.janitza.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


def test_sensor_descriptions_read_real_fields() -> None:
    """Guards SENSOR_DESCRIPTIONS against a component/key transcription slip."""
    unit = MockModbusConnection().for_unit(1)
    meters = (JanitzaMeter(unit, serial_number="1"), Umg508(unit, serial_number="1"))
    keys = [description.key for description in SENSOR_DESCRIPTIONS]
    assert len(keys) == len(set(keys))
    for description in SENSOR_DESCRIPTIONS:
        components = [
            component
            for meter in meters
            if (component := getattr(meter, description.component, None)) is not None
        ]
        assert components, f"unknown component {description.component!r}"
        assert all(hasattr(c, description.key) for c in components), (
            f"{description.component}.{description.key} does not exist"
        )


async def test_rotation_field_reports_its_option(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the enum sensor reports the option slug, not the raw code."""
    assert hass.states.get(ROTATION_ENTITY).state == "right"


async def test_total_restores_its_last_value(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test an energy counter keeps its restored value until the meter answers."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(CONSUMED_ENTITY, "3500.0"),
                {"native_value": 3_500_000.0, "native_unit_of_measurement": "Wh"},
            )
        ],
    )
    # The counter reads NaN: the meter has no value for it yet.
    mock_connection.for_unit(1).holding[ENERGY_CONSUMED_TOTAL_REGISTER] = float_words(
        math.nan
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(CONSUMED_ENTITY).state == "3500.0"


async def test_total_ignores_a_restored_non_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test a restored state that is not a number is not taken over."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(CONSUMED_ENTITY, "unknown"),
                {"native_value": None, "native_unit_of_measurement": "Wh"},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(CONSUMED_ENTITY).state == "3600.0"


async def test_total_holds_its_value_through_a_nan(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a counter reading NaN keeps the last value it had."""
    mock_connection.for_unit(1).holding[ENERGY_CONSUMED_TOTAL_REGISTER] = float_words(
        math.nan
    )
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CONSUMED_ENTITY).state == "3600.0"


async def test_entities_go_unavailable_with_their_block(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a refused measurement block takes its entities offline."""
    mock_connection.for_unit(1).fail_read(
        ENERGY_CONSUMED_TOTAL_REGISTER, IllegalDataAddressError()
    )
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CONSUMED_ENTITY).state == STATE_UNAVAILABLE


def test_totals_are_the_counters() -> None:
    """Test every energy counter is a total, and nothing else is."""
    for description in SENSOR_DESCRIPTIONS:
        is_total = description.state_class in (
            SensorStateClass.TOTAL,
            SensorStateClass.TOTAL_INCREASING,
        )
        assert is_total == (
            description.component in {"energy", "tariff_energy"}
            and description.key != "active_tariff"
        ), description.key
