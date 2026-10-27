"""Fixtures for the Janitza integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.janitza.const import DOMAIN

from . import (
    MOCK_508_ENTRY_DATA,
    MOCK_508_IDENTIFIER,
    MOCK_508_TITLE,
    MOCK_ENTRY_DATA,
    MOCK_SERIAL,
    MOCK_TITLE,
    seed_meter,
    seed_umg508,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components in every test."""


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Enable every entity, including the ones disabled by default."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new_callable=PropertyMock,
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.janitza.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> MockModbusConnection:
    """Seed a fake Modbus connection with a UMG 96RM on unit 1."""
    connection = MockModbusConnection()
    seed_meter(connection.for_unit(1))
    return connection


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Janitza config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data=MOCK_ENTRY_DATA,
        title=MOCK_TITLE,
    )


@pytest.fixture
def mock_connection_508() -> MockModbusConnection:
    """Seed a fake Modbus connection with a UMG 508 on unit 1."""
    connection = MockModbusConnection()
    seed_umg508(connection.for_unit(1))
    return connection


@pytest.fixture
def mock_config_entry_508() -> MockConfigEntry:
    """Mock a Janitza config entry for a UMG 508."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_508_IDENTIFIER,
        data=MOCK_508_ENTRY_DATA,
        title=MOCK_508_TITLE,
    )


@pytest.fixture
def mock_get_unit(mock_connection: MockModbusConnection) -> Generator[MagicMock]:
    """Hand out units on the mock connection when the entry sets up."""
    with patch(
        "custom_components.janitza.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ) as mock_get_unit:
        yield mock_get_unit


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> MockConfigEntry:
    """Set up the Janitza integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry


@pytest.fixture
def mock_get_unit_508(
    mock_connection_508: MockModbusConnection,
) -> Generator[MagicMock]:
    """Hand out units on the UMG 508's mock connection when the entry sets up."""
    with patch(
        "custom_components.janitza.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection_508.for_unit(
            unit_id
        ),
    ) as mock_get_unit:
        yield mock_get_unit


@pytest.fixture
async def init_integration_508(
    hass: HomeAssistant,
    mock_config_entry_508: MockConfigEntry,
    mock_get_unit_508: MagicMock,
) -> MockConfigEntry:
    """Set up the Janitza integration for a UMG 508."""
    mock_config_entry_508.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_508.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry_508
