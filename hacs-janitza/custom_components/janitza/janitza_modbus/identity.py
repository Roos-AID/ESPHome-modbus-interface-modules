"""What identifies the meter: serial number, firmware and fitted module."""

from __future__ import annotations

from modbus_connection.model import enum, integer, uint32

from .enums import ModuleType
from .model import JanitzaComponent

# Addresses of the two identifying numbers, for a dump that will be shared.
SERIAL_NUMBER_REGISTERS = (754, 755)
PRODUCTION_NUMBER_REGISTERS = (756, 757)


class Identity(JanitzaComponent):
    """The meter's serial number, firmware release and module.

    The parameter list documents these four addresses and nothing between
    them, so each is read as a range of its own rather than spanning the
    gaps.
    """

    register_ranges = ((750, 750), (754, 757), (761, 761))

    software_release = integer(750, signed=True)
    serial_number = uint32(754)
    production_number = uint32(756)
    module = enum(761, ModuleType)
