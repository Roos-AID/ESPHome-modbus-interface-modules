"""The component base every sub-system of the UMG 96RM builds on."""

from __future__ import annotations

import struct
from typing import Any

from modbus_connection.model import Component, FloatField, UpdateReport

__all__ = [
    "MEASUREMENT_RANGES",
    "JanitzaComponent",
    "MeasuredFloat",
    "UpdateReport",
    "measured",
    "shortest_float32",
]

# The "frequently required readings" block, 19000-19121, as the two runs
# the meter is read in: the instantaneous values up to the rotation field,
# then the energy counters and harmonics. Both fit one request on their
# own; reading them apart keeps each request well inside what a meter, or
# a gateway in front of it, is known to take.
MEASUREMENT_RANGES: tuple[tuple[int, int], ...] = (
    (19000, 19053),
    (19054, 19121),
)


class JanitzaComponent(Component):
    """A sub-system of the UMG 96RM register map."""

    # The meter answers FC03 and FC04 alike; FC03 is what it documents.
    register_space = "holding"
    max_span = 125  # the Modbus per-request ceiling


def shortest_float32(value: float) -> float:
    """The shortest decimal that encodes to the same float32 as ``value``.

    A float32 holds about seven significant digits, so 230.1 V arrives as
    230.10000610351562 once widened to a Python float. This hands back the
    230.1 the meter meant, without dropping a digit the float32 does carry.
    """
    packed = struct.pack(">f", value)
    for digits in range(6, 10):
        candidate = float(f"{value:.{digits}g}")
        if struct.pack(">f", candidate) == packed:
            return candidate
    return value


class MeasuredFloat(FloatField):
    """A float32 decoded to the shortest decimal naming the same float32."""

    def decode(self, words: list[int], scale_exponent: int | None = None) -> Any:
        """Decode the float, then drop the noise float32-to-float adds."""
        value = super().decode(words, scale_exponent)
        if value is None:
            return None
        return shortest_float32(value)


def measured(address: int, *, unit: str | None = None) -> MeasuredFloat:
    """A float32 measurement over two registers, high word first."""
    return MeasuredFloat(address, count=2, unit=unit)
