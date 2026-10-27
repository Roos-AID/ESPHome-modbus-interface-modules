"""Voltages, currents, power, frequency and harmonics, 19000-19053 and 19110-19121.

Every value in the block is an IEEE-754 float over two registers, most
significant word first, in the unit the meter measures it in.
"""

from __future__ import annotations

from .enums import RotationField
from .model import MEASUREMENT_RANGES, JanitzaComponent, measured


class Voltage(JanitzaComponent):
    """Phase-to-neutral and phase-to-phase voltages."""

    register_ranges = MEASUREMENT_RANGES

    voltage_l1_n = measured(19000, unit="V")
    voltage_l2_n = measured(19002, unit="V")
    voltage_l3_n = measured(19004, unit="V")
    voltage_l1_l2 = measured(19006, unit="V")
    voltage_l2_l3 = measured(19008, unit="V")
    voltage_l3_l1 = measured(19010, unit="V")


class Current(JanitzaComponent):
    """Phase currents and the neutral current."""

    register_ranges = MEASUREMENT_RANGES

    current_l1 = measured(19012, unit="A")
    current_l2 = measured(19014, unit="A")
    current_l3 = measured(19016, unit="A")
    current_n = measured(19018, unit="A")
    """Vector sum of the three phase currents."""


class Power(JanitzaComponent):
    """Active, apparent and reactive power, and the power factor per phase.

    Active power is signed: positive while consuming, negative while
    delivering, as the current transformers are wired.
    """

    register_ranges = MEASUREMENT_RANGES

    active_power_l1 = measured(19020, unit="W")
    active_power_l2 = measured(19022, unit="W")
    active_power_l3 = measured(19024, unit="W")
    active_power_total = measured(19026, unit="W")
    apparent_power_l1 = measured(19028, unit="VA")
    apparent_power_l2 = measured(19030, unit="VA")
    apparent_power_l3 = measured(19032, unit="VA")
    apparent_power_total = measured(19034, unit="VA")
    reactive_power_l1 = measured(19036, unit="var")
    """Reactive power of the fundamental."""
    reactive_power_l2 = measured(19038, unit="var")
    """Reactive power of the fundamental."""
    reactive_power_l3 = measured(19040, unit="var")
    """Reactive power of the fundamental."""
    reactive_power_total = measured(19042, unit="var")
    """Reactive power of the fundamental."""
    cos_phi_l1 = measured(19044)
    """Power factor of the fundamental."""
    cos_phi_l2 = measured(19046)
    """Power factor of the fundamental."""
    cos_phi_l3 = measured(19048)
    """Power factor of the fundamental."""


class Grid(JanitzaComponent):
    """Grid frequency and phase rotation."""

    register_ranges = MEASUREMENT_RANGES

    frequency = measured(19050, unit="Hz")
    rotation_field_code = measured(19052)
    """The rotation as the meter sends it: 1.0, 0.0 or -1.0."""

    @property
    def rotation_field(self) -> RotationField | None:
        """The direction the phases rotate in; ``None`` before the first read."""
        code = self.rotation_field_code
        if code is None:
            return None
        try:
            return RotationField(round(code))
        except ValueError:
            return None


class Harmonics(JanitzaComponent):
    """Total harmonic distortion of voltage and current."""

    register_ranges = MEASUREMENT_RANGES

    thd_voltage_l1 = measured(19110, unit="%")
    thd_voltage_l2 = measured(19112, unit="%")
    thd_voltage_l3 = measured(19114, unit="%")
    thd_current_l1 = measured(19116, unit="%")
    thd_current_l2 = measured(19118, unit="%")
    thd_current_l3 = measured(19120, unit="%")
