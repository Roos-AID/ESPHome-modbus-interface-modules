"""Base entity for Janitza power analysers."""

from dataclasses import dataclass
from typing import override

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import JanitzaDataUpdateCoordinator, JanitzaRuntimeData


@dataclass(frozen=True, kw_only=True)
class JanitzaEntityDescription(EntityDescription):
    """Describe a Janitza entity."""

    component: str  # attribute name on the device, e.g. 'voltage', 'energy'


class JanitzaEntity(CoordinatorEntity[JanitzaDataUpdateCoordinator]):
    """Defines a base Janitza entity."""

    _attr_has_entity_name = True
    entity_description: JanitzaEntityDescription

    def __init__(
        self,
        runtime_data: JanitzaRuntimeData,
        entity_description: JanitzaEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data.coordinator_for(entity_description.component))
        self.entity_description = entity_description
        serial = self.coordinator.device.serial_number
        self._attr_unique_id = f"{serial}_{entity_description.key}"
        self._attr_device_info = self.coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not super().available or self.coordinator.data is None:
            return False
        report_name = self.coordinator.device.report_name(
            self.entity_description.component
        )
        return report_name not in self.coordinator.data.failed
