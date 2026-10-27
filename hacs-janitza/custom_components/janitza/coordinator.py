"""Data update coordinator for Janitza power analysers."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError
from propcache.api import cached_property

from .const import ATTR_MANUFACTURER, DOMAIN
from .janitza_modbus import JanitzaDevice, UpdateReport

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import timedelta

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class JanitzaDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Run one of the meter's update methods on its own interval."""

    config_entry: JanitzaConfigEntry
    device: JanitzaDevice

    def __init__(
        self,
        hass: HomeAssistant,
        entry: JanitzaConfigEntry,
        device: JanitzaDevice,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=interval,
        )
        self.device = device
        self._poll = poll

    @cached_property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        info = dr.DeviceInfo(
            identifiers={(DOMAIN, self.device.serial_number)},
            manufacturer=ATTR_MANUFACTURER,
            model=self.device.model_name,
        )
        # A stand-in identifier is not a serial number; only a real one is shown.
        if self.device.has_serial_number:
            info["serial_number"] = self.device.serial_number
        if (release := self.device.software_release) is not None:
            info["sw_version"] = str(release)
        return info

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self._poll()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup(
                "all components failed to refresh", list(report.failed.values())
            )
        return report


@dataclass
class JanitzaRuntimeData:
    """Class to hold runtime data."""

    readings: JanitzaDataUpdateCoordinator
    settings: JanitzaDataUpdateCoordinator | None

    def coordinator_for(self, component: str) -> JanitzaDataUpdateCoordinator:
        """Which coordinator owns a given component's data."""
        device = self.readings.device
        if device.report_name(component) in device.readings_components:
            return self.readings
        assert self.settings is not None  # noqa: S101 - only models with settings
        return self.settings


type JanitzaConfigEntry = ConfigEntry[JanitzaRuntimeData]
