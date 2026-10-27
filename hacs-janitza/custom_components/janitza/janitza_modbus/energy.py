"""Energy counters, 19054-19109.

The meter counts in Wh, VAh and varh, as IEEE-754 floats. Each counter
exists per phase and summed over the three.
"""

from __future__ import annotations

from .model import MEASUREMENT_RANGES, JanitzaComponent, measured


class Energy(JanitzaComponent):
    """Active, apparent and reactive energy counters."""

    register_ranges = MEASUREMENT_RANGES

    active_energy_l1 = measured(19054, unit="Wh")
    """Net active energy: consumed less delivered."""
    active_energy_l2 = measured(19056, unit="Wh")
    """Net active energy: consumed less delivered."""
    active_energy_l3 = measured(19058, unit="Wh")
    """Net active energy: consumed less delivered."""
    active_energy_total = measured(19060, unit="Wh")
    """Net active energy: consumed less delivered."""

    active_energy_consumed_l1 = measured(19062, unit="Wh")
    active_energy_consumed_l2 = measured(19064, unit="Wh")
    active_energy_consumed_l3 = measured(19066, unit="Wh")
    active_energy_consumed_total = measured(19068, unit="Wh")

    active_energy_delivered_l1 = measured(19070, unit="Wh")
    active_energy_delivered_l2 = measured(19072, unit="Wh")
    active_energy_delivered_l3 = measured(19074, unit="Wh")
    active_energy_delivered_total = measured(19076, unit="Wh")

    apparent_energy_l1 = measured(19078, unit="VAh")
    apparent_energy_l2 = measured(19080, unit="VAh")
    apparent_energy_l3 = measured(19082, unit="VAh")
    apparent_energy_total = measured(19084, unit="VAh")

    reactive_energy_l1 = measured(19086, unit="varh")
    reactive_energy_l2 = measured(19088, unit="varh")
    reactive_energy_l3 = measured(19090, unit="varh")
    reactive_energy_total = measured(19092, unit="varh")

    reactive_energy_inductive_l1 = measured(19094, unit="varh")
    reactive_energy_inductive_l2 = measured(19096, unit="varh")
    reactive_energy_inductive_l3 = measured(19098, unit="varh")
    reactive_energy_inductive_total = measured(19100, unit="varh")

    reactive_energy_capacitive_l1 = measured(19102, unit="varh")
    reactive_energy_capacitive_l2 = measured(19104, unit="varh")
    reactive_energy_capacitive_l3 = measured(19106, unit="varh")
    reactive_energy_capacitive_total = measured(19108, unit="varh")
