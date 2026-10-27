"""Integrate Janitza power analysers (UMG 96RM, UMG 508) into Home Assistant."""

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform

from .const import CONF_UNIT_ID, SCAN_INTERVAL, SETTINGS_SCAN_INTERVAL
from .coordinator import (
    JanitzaConfigEntry,
    JanitzaDataUpdateCoordinator,
    JanitzaRuntimeData,
)
from .helpers import create_device, create_modbus_params

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: JanitzaConfigEntry) -> bool:
    """Set up Janitza from a config entry."""
    serial = entry.unique_id
    assert serial is not None  # noqa: S101 - a config flow entry always has one

    unit = async_get_unit(
        hass,
        entry,
        create_modbus_params(entry.data),
        entry.data[CONF_UNIT_ID],
    )
    device = create_device(entry.data, unit, serial)

    readings = JanitzaDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_readings,
        timedelta(seconds=SCAN_INTERVAL),
    )
    # A model with nothing configurable to read has no settings to poll.
    settings = (
        JanitzaDataUpdateCoordinator(
            hass,
            entry,
            device,
            device.async_update_settings,
            timedelta(seconds=SETTINGS_SCAN_INTERVAL),
        )
        if device.settings_components
        else None
    )
    await readings.async_config_entry_first_refresh()
    if settings is not None:
        await settings.async_refresh()
    # Not tied to a coordinator: identity never changes once read.
    await device.async_read_identity()

    entry.runtime_data = JanitzaRuntimeData(readings, settings)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JanitzaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
