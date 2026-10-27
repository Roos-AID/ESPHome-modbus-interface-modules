"""Coded values the meter reports, as enums."""

from __future__ import annotations

from enum import IntEnum


class RotationField(IntEnum):
    """The direction the three phases rotate in, address 19052."""

    LEFT = -1
    NONE = 0
    RIGHT = 1


class ModuleType(IntEnum):
    """The extension module fitted to the meter, address 761."""

    NONE = 0
    PROFIBUS = 1
    CBM = 2
    ETHERNET = 3
