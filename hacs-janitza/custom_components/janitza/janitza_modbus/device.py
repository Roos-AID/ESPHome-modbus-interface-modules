"""The top-level objects for the Janitza power analysers: UMG 96RM and UMG 508."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, ClassVar, Self

from modbus_connection import ModbusError
from modbus_connection.model import ComponentGroup, Device, Raw

from .energy import Energy
from .identity import PRODUCTION_NUMBER_REGISTERS, SERIAL_NUMBER_REGISTERS, Identity
from .measurements import Current, Grid, Harmonics, Power, Voltage
from .model import UpdateReport
from .transformers import Transformers
from .umg508 import Firmware, TariffEnergy, Umg508Transformers

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

_LOGGER = logging.getLogger(__name__)

# The sub-systems tiling the 19000-19121 block. Reading one apart would
# cost a request and isolate nothing: a meter serving one serves them all.
# So they are pooled into one group, polled and reported as "measurements".
MEASUREMENT_COMPONENTS = ("voltage", "current", "power", "grid", "energy", "harmonics")
MEASUREMENTS = "measurements"

# Attribute names of what each update method reads.
READINGS_COMPONENTS = (MEASUREMENTS,)
SETTINGS_COMPONENTS = ("transformers",)

_IDENTITY_ATTEMPTS = 3


class JanitzaDevice(Device):
    """What the Janitza power analysers share: the 19000-19121 measurement block.

    Every UMG in the family serves the "frequently required readings" at the
    same addresses, in the same units. A subclass adds what only its model
    has: the UMG 96RM its identity and transformer ratios, the UMG 508 nothing
    beyond the measurements.

    Read-only. The caller owns the connection; this only reads registers.
    """

    model_name: ClassVar[str]
    """The model as the manufacturer names it, for a device registry."""
    has_serial_number: ClassVar[bool]
    """Whether ``serial_number`` is the meter's own, as opposed to a stand-in."""
    readings_components: ClassVar[tuple[str, ...]] = READINGS_COMPONENTS
    """What ``async_update_readings()`` polls, by report name."""
    settings_components: ClassVar[tuple[str, ...]] = ()
    """What ``async_update_settings()`` polls, by report name."""

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        serial_number: str,
        timeout: float | None = None,
    ) -> None:
        super().__init__(unit)
        unit.require_timeout(timeout)
        self.serial_number = serial_number

        self.voltage = Voltage(unit)
        self.current = Current(unit)
        self.power = Power(unit)
        self.grid = Grid(unit)
        self.energy = Energy(unit)
        self.harmonics = Harmonics(unit)

        self.measurements = ComponentGroup(
            unit, [getattr(self, name) for name in MEASUREMENT_COMPONENTS]
        )

    @property
    def software_release(self) -> int | str | None:
        """The firmware release the meter reports, where it reports one."""
        return None

    @property
    def unrecognized(self) -> bool:
        """Whether the device answered without anything to tell it by."""
        return False

    @staticmethod
    def report_name(component: str) -> str:
        """The name an ``UpdateReport`` lists a component under.

        The measurement components are read as one pool, so a report names
        the pool rather than any of its members.
        """
        if component in MEASUREMENT_COMPONENTS:
            return MEASUREMENTS
        return component

    async def async_read_identity(self) -> bool:
        """Read what identifies the meter, where it serves any.

        Returns whether it read. A model with no identity registers has
        nothing to read, which is not a failure.
        """
        return True

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the meter measures."""
        return await self.async_poll(self.readings_components)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh what the meter has been configured with."""
        return await self.async_poll(self.settings_components)

    async def async_update(self) -> UpdateReport:
        """Refresh the measurements and the settings, in one merged report."""
        report = await self.async_poll(self.readings_components)
        return await self.async_poll(self.settings_components, report)

    async def _async_setup(self) -> None:
        """Nothing to settle: every model serves one fixed register map."""
        _LOGGER.debug(
            "%s %s; polling: %s",
            self.model_name,
            self.serial_number,
            ", ".join((*self.readings_components, *self.settings_components)),
        )

    async def async_read_raw(
        self,
        names: Iterable[str] | None = None,
        *,
        redact_serial: bool = False,
    ) -> Raw:
        """Every register this meter reads, undecoded, for diagnostics.

        Nothing notifies here: a diagnostics download is not a poll.
        ``redact_serial`` leaves the serial and production numbers out, for
        a dump that will be posted publicly.
        """
        if names is None:
            names = (*self.readings_components, *self.settings_components)
        return await super().async_read_raw(names)


class JanitzaMeter(JanitzaDevice):
    """A UMG 96RM reached through a ``ModbusUnit``.

    Read-only. The caller owns the connection; this only reads registers.
    """

    model_name = "UMG 96RM"
    has_serial_number = True
    settings_components = SETTINGS_COMPONENTS

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        serial_number: str,
        timeout: float | None = None,
    ) -> None:
        super().__init__(unit, serial_number=serial_number, timeout=timeout)
        self.identity = Identity(unit)
        self.transformers = Transformers(unit)

    @classmethod
    async def async_detect(
        cls, unit: ModbusUnit, *, timeout: float | None = None
    ) -> Self:
        """Build a meter for a caller that does not know its serial number."""
        unit.require_timeout(timeout)
        identity = Identity(unit)
        await identity.async_update(notify=False)
        serial = identity.serial_number
        device = cls(
            unit,
            serial_number="" if serial is None else str(serial),
            timeout=timeout,
        )
        device.identity = identity
        _LOGGER.debug(
            "Meter %s runs software release %s with module %s",
            device.serial_number,
            identity.software_release,
            identity.module.name.lower() if identity.module is not None else None,
        )
        return device

    @property
    def software_release(self) -> int | str | None:
        """The firmware release, once the identity has been read."""
        return self.identity.software_release

    @property
    def unrecognized(self) -> bool:
        """Whether the meter answered without a serial number to tell it by."""
        return self.serial_number in ("", "0")

    async def async_read_identity(self) -> bool:
        """Read the identity, with a few tries against a transient blip.

        Returns whether it read. A meter that keeps refusing gets a warning
        instead of an error: nothing a poll reads depends on it.
        """
        for attempt in range(_IDENTITY_ATTEMPTS):
            try:
                await self.identity.async_update()
            except ModbusError as err:
                if attempt == _IDENTITY_ATTEMPTS - 1:
                    _LOGGER.warning(
                        "Meter %s: could not read identity: %s",
                        self.serial_number,
                        err,
                    )
            else:
                return True
        return False

    async def async_read_raw(
        self,
        names: Iterable[str] | None = None,
        *,
        redact_serial: bool = False,
    ) -> Raw:
        """Every register this meter reads, undecoded, for diagnostics.

        Nothing notifies here: a diagnostics download is not a poll.
        ``redact_serial`` leaves the serial and production numbers out, for
        a dump that will be posted publicly.
        """
        if names is None:
            names = ("identity", *READINGS_COMPONENTS, *SETTINGS_COMPONENTS)
        raw = await super().async_read_raw(names)
        if redact_serial and (holding := raw.get("holding")) is not None:
            for address in (*SERIAL_NUMBER_REGISTERS, *PRODUCTION_NUMBER_REGISTERS):
                holding.pop(address, None)
        return raw


# What a UMG 508 polls beyond the shared block, by attribute name.
UMG508_READINGS_COMPONENTS = (MEASUREMENTS, "tariff_energy")
UMG508_SETTINGS_COMPONENTS = ("transformers",)


class Umg508(JanitzaDevice):
    """A UMG 508 reached through a ``ModbusUnit``, over Ethernet or RS-485.

    The UMG 508 serves the same "frequently required readings" block as the
    UMG 96RM, so it reads the same measurements. Beyond that it reads the
    active energy over every tariff (``tariff_energy``), its transformer
    ratios (``transformers``) and its firmware release (``firmware``), each
    as a block of its own.

    It reports no serial number, so the caller names the meter:
    ``serial_number`` is whatever stable identifier the caller keeps it under
    (the Home Assistant integration uses its link and unit id), not a number
    read from the meter.
    """

    model_name = "UMG 508"
    has_serial_number = False
    readings_components = UMG508_READINGS_COMPONENTS
    settings_components = UMG508_SETTINGS_COMPONENTS

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        serial_number: str = "",
        timeout: float | None = None,
    ) -> None:
        super().__init__(unit, serial_number=serial_number, timeout=timeout)
        self.tariff_energy = TariffEnergy(unit)
        self.transformers = Umg508Transformers(unit)
        self.firmware = Firmware(unit)
        self._answered = True

    @classmethod
    async def async_detect(
        cls,
        unit: ModbusUnit,
        *,
        serial_number: str = "",
        timeout: float | None = None,
    ) -> Self:
        """Build a meter after proving it serves the measurement block.

        A dead link or a silent meter raises, as it does from any poll. A
        device that answers but refuses the block is ``unrecognized``: it is
        not a UMG 508, or not one this library can read.
        """
        device = cls(unit, serial_number=serial_number, timeout=timeout)
        report = await device.async_poll((MEASUREMENTS,))
        device._answered = MEASUREMENTS in report.updated
        if not device._answered:
            _LOGGER.debug(
                "UMG 508 probe: the measurement block was refused: %s",
                report.failed,
            )
        return device

    @property
    def unrecognized(self) -> bool:
        """Whether the device refused the measurement block when detected."""
        return not self._answered

    @property
    def software_release(self) -> str | None:
        """The firmware release, once it has been read; ``None`` if blank."""
        return self.firmware.release or None

    async def async_read_identity(self) -> bool:
        """Read the firmware release, with a few tries against a blip.

        Returns whether it read. A meter that keeps refusing gets a warning
        instead of an error: nothing a poll reads depends on it.
        """
        for attempt in range(_IDENTITY_ATTEMPTS):
            try:
                await self.firmware.async_update()
            except ModbusError as err:
                if attempt == _IDENTITY_ATTEMPTS - 1:
                    _LOGGER.warning(
                        "UMG 508 %s: could not read the firmware release: %s",
                        self.serial_number,
                        err,
                    )
            else:
                return True
        return False

    async def async_read_raw(
        self,
        names: Iterable[str] | None = None,
        *,
        redact_serial: bool = False,
    ) -> Raw:
        """Every register this meter reads, undecoded, for diagnostics."""
        if names is None:
            names = ("firmware", *self.readings_components, *self.settings_components)
        return await super().async_read_raw(names, redact_serial=redact_serial)
