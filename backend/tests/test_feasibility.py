import pytest
from conftest import at, make_scenario

from planner.feasibility import is_plan_feasible
from planner.maneuver import UnknownTransitionError, transition_seconds
from planner.models import Plan


def spec_example(b_start: int):
    """A ends at 10:00:10 and A -> B takes 15 s (the example from the assignment)."""
    return make_scenario(
        {"A": 2, "B": 1},
        [("A-01", "A", at(10, 0, 0), at(10, 0, 10)), ("B-01", "B", b_start, b_start + 10)],
        {("A", "B"): 15.0},
    )


def test_non_overlapping_but_maneuver_infeasible():
    assert not is_plan_feasible(Plan(("A-01", "B-01")), spec_example(at(10, 0, 20)))


def test_exact_fit_transition_is_feasible():
    assert is_plan_feasible(Plan(("A-01", "B-01")), spec_example(at(10, 0, 25)))


def test_fractional_transitions_are_compared_exactly():
    def plan_with(transition: float) -> bool:
        scenario = make_scenario({"A": 1, "B": 1}, [("A-01", "A", 0, 10), ("B-01", "B", 13, 20)],
                                 {("A", "B"): transition})
        return is_plan_feasible(Plan(("A-01", "B-01")), scenario)

    assert plan_with(2.9) and plan_with(3.0) and not plan_with(3.1)


def test_transition_is_asymmetric():
    scenario = make_scenario({"A": 1, "B": 1}, [("A-01", "A", 0, 10), ("B-01", "B", 20, 30)],
                             {("A", "B"): 15.0, ("B", "A"): 5.0})
    assert scenario.transition_ms("A", "B") == 15_000
    assert scenario.transition_ms("B", "A") == 5_000
    assert not is_plan_feasible(Plan(("A-01", "B-01")), scenario)


def test_unknown_target_is_an_error_not_zero():
    with pytest.raises(UnknownTransitionError):
        transition_seconds({"A": {"B": 15.0}}, "A", "UNKNOWN")
    with pytest.raises(KeyError):
        spec_example(at(10, 0, 25)).transition_ms("A", "UNKNOWN")


def test_incomplete_transition_table_is_rejected():
    from planner.models import parse_scenario
    with pytest.raises(UnknownTransitionError):
        parse_scenario({
            "scenario_id": "x", "satellite_id": "s",
            "horizon_start_utc": "2026-11-02T00:00:00Z", "horizon_end_utc": "2026-11-03T00:00:00Z",
            "targets": [{"target_id": t, "latitude": 0, "longitude": 0, "priority": 1} for t in ("A", "B")],
            "opportunities": [], "transition_seconds": {"A": {"B": 1.0}},
        })


def test_unknown_opportunity_and_order_are_checked():
    scenario = spec_example(at(10, 0, 25))
    assert not is_plan_feasible(Plan(("A-01", "NOPE")), scenario)
    assert not is_plan_feasible(Plan(("B-01", "A-01")), scenario)


def test_observation_must_be_inside_horizon():
    scenario = make_scenario({"A": 1}, [("A-01", "A", 24 * 3600 - 5, 24 * 3600 + 5)])
    assert not is_plan_feasible(Plan(("A-01",)), scenario)


def test_empty_plan_is_feasible():
    assert is_plan_feasible(Plan(()), spec_example(at(10, 0, 25)))
