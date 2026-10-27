"""Sub-systems only the UMG 508 serves, beyond the shared measurement block.

The addresses are those of Janitza's UMG 509-PRO Modbus address list, whose
"Energy" and "Other values" sections the UMG 508 shares. They are read as
blocks of their own, so a meter that refuses one loses only that block.
"""

from __future__ import annotations

from modbus_connection.model import integer, string

from .model import JanitzaComponent, measured


class TariffEnergy(JanitzaComponent):
    """Active energy over every tariff, and the tariff now running, 13949-14008.

    The "frequently required readings" carry consumed energy for tariff 1 only
    (19068). These counters add up all tariffs, so they keep counting when the
    meter switches to tariff 2.
    """

    register_ranges = ((13949, 14008),)

    active_tariff = integer(13949, signed=True)
    """The tariff real and apparent energy are counted under now (1 or 2)."""
    active_energy_consumed_all_tariffs = measured(13995, unit="Wh")
    """Consumed active energy L1..L3, every tariff."""
    active_energy_delivered_all_tariffs = measured(14007, unit="Wh")
    """Delivered active energy L1..L3, every tariff."""


class Umg508Transformers(JanitzaComponent):
    """Primary and secondary ratings of each phase's CT and VT, 14176-14207.

    The same names as the UMG 96RM's ``Transformers``, laid out by kind
    rather than by phase: all CT primaries, then all CT secondaries, and so
    on, each for L1 to L4. L4 is not read.
    """

    register_ranges = ((14176, 14207),)

    ct_primary_l1 = measured(14176, unit="A")
    ct_primary_l2 = measured(14178, unit="A")
    ct_primary_l3 = measured(14180, unit="A")
    ct_secondary_l1 = measured(14184, unit="A")
    ct_secondary_l2 = measured(14186, unit="A")
    ct_secondary_l3 = measured(14188, unit="A")
    vt_primary_l1 = measured(14192, unit="V")
    vt_primary_l2 = measured(14194, unit="V")
    vt_primary_l3 = measured(14196, unit="V")
    vt_secondary_l1 = measured(14200, unit="V")
    vt_secondary_l2 = measured(14202, unit="V")
    vt_secondary_l3 = measured(14204, unit="V")


class Firmware(JanitzaComponent):
    """The firmware release, as the text the meter reports, 17435-17442."""

    register_ranges = ((17435, 17442),)

    release = string(17435, 8)
    """Sixteen characters, null-padded."""
