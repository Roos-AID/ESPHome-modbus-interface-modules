"""Diagnostics support for Janitza."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from modbus_connection import ModbusError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import JanitzaConfigEntry
    from .janitza_modbus import UpdateReport

TO_REDACT = {"serial_number", "production_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001 - the platform signature
    entry: JanitzaConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    device = runtime_data.readings.device
    raw = read_error = None
    try:
        raw = await device.async_read_raw(redact_serial=True)
    except ModbusError as err:
        read_error = type(err).__name__

    identity = getattr(device, "identity", None)
    settings = runtime_data.settings
    return async_redact_data(
        {
            "model": device.model_name,
            "serial_number": device.serial_number,
            "software_release": device.software_release,
            "identity": (
                None
                if identity is None
                else {
                    "software_release": identity.software_release,
                    "module": (
                        identity.module.name.lower()
                        if identity.module is not None
                        else None
                    ),
                    "production_number": identity.production_number,
                }
            ),
            "readings": _report(runtime_data.readings.data),
            "settings": _report(None if settings is None else settings.data),
            "read_error": read_error,
            "raw": raw,
        },
        TO_REDACT,
    )


def _report(report: UpdateReport | None) -> dict[str, Any] | None:
    """Render an update report as JSON."""
    if report is None:
        return None
    return {
        "updated": sorted(report.updated),
        "failed": {name: repr(err) for name, err in sorted(report.failed.items())},
    }
