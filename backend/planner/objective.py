"""Plan ranking: lexicographic (P1, ..., P5) selected-target counts, then less total maneuver time."""

from collections.abc import Sequence

from planner.models import PRIORITIES, Opportunity, Scenario

Counts = tuple[int, int, int, int, int]
ObjectiveKey = tuple[Counts, int]


def priority_counts(opportunities: Sequence[Opportunity], scenario: Scenario) -> Counts:
    counts = [0] * len(PRIORITIES)
    for opp in opportunities:
        counts[scenario.targets[opp.target_id].priority - 1] += 1
    return tuple(counts)  # type: ignore[return-value]


def total_transition_ms(opportunities: Sequence[Opportunity], scenario: Scenario) -> int:
    return sum(scenario.transition_ms(a.target_id, b.target_id) for a, b in zip(opportunities, opportunities[1:]))


def objective_key(opportunities: Sequence[Opportunity], scenario: Scenario) -> ObjectiveKey:
    """Higher is better. Python compares tuples element by element, which gives the lexicographic order."""
    return priority_counts(opportunities, scenario), -total_transition_ms(opportunities, scenario)
