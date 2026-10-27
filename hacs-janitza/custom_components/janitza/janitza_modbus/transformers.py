"""The current and voltage transformer ratios the meter is configured with."""

from __future__ import annotations

from .model import JanitzaComponent, measured


class Transformers(JanitzaComponent):
    """Primary and secondary ratings of each phase's CT and VT, 10-33.

    These scale every measurement, so they are worth reading back when a
    value looks off by a constant factor. Read-only here: a wrong ratio
    silently rescales every counter the meter keeps from then on.
    """

    register_ranges = ((10, 33),)

    ct_primary_l1 = measured(10, unit="A")
    ct_secondary_l1 = measured(12, unit="A")
    vt_primary_l1 = measured(14, unit="V")
    vt_secondary_l1 = measured(16, unit="V")
    ct_primary_l2 = measured(18, unit="A")
    ct_secondary_l2 = measured(20, unit="A")
    vt_primary_l2 = measured(22, unit="V")
    vt_secondary_l2 = measured(24, unit="V")
    ct_primary_l3 = measured(26, unit="A")
    ct_secondary_l3 = measured(28, unit="A")
    vt_primary_l3 = measured(30, unit="V")
    vt_secondary_l3 = measured(32, unit="V")
