from conftest import make_scenario

from planner.algorithm import plan_observations
from planner.feasibility import is_plan_feasible
from planner.models import Plan
from planner.objective import priority_counts
from planner.schedule import Schedule


def counts(plan: Plan, scenario) -> tuple[int, ...]:
    return priority_counts([scenario.opportunities[i] for i in plan.opportunity_ids], scenario)


def test_duplicate_target_is_rejected_by_feasibility():
    scenario = make_scenario({"A": 1}, [("A-01", "A", 0, 10), ("A-02", "A", 1000, 1010)])
    assert not is_plan_feasible(Plan(("A-01", "A-02")), scenario)


def test_planner_observes_a_target_at_most_once():
    scenario = make_scenario({"A": 1, "B": 3},
                             [("A-01", "A", 0, 10), ("A-02", "A", 1000, 1010), ("B-01", "B", 500, 510)])
    plan = plan_observations(scenario)
    assert sorted(plan.opportunity_ids) == ["A-01", "B-01"]
    assert is_plan_feasible(plan, scenario)


def test_higher_priority_wins_a_conflict_against_many_lower_priority_targets():
    # One P1 overlaps three mutually compatible P5 observations: (1,0,0,0,0) outranks (0,0,0,0,3).
    scenario = make_scenario(
        {"HIGH": 1, "L1": 5, "L2": 5, "L3": 5},
        [("HIGH-01", "HIGH", 38, 100), ("L1-01", "L1", 25, 35), ("L2-01", "L2", 45, 60), ("L3-01", "L3", 70, 85)],
    )
    assert is_plan_feasible(Plan(("L1-01", "L2-01", "L3-01")), scenario)
    plan = plan_observations(scenario)
    assert plan.opportunity_ids == ("HIGH-01",)
    assert counts(plan, scenario) == (1, 0, 0, 0, 0)


def test_maneuver_conflict_favours_the_higher_priority_target():
    # Non-overlapping, but A -> B needs 15 s and the gap is 10 s: only one can be taken.
    scenario = make_scenario({"A": 2, "B": 1}, [("A-01", "A", 0, 10), ("B-01", "B", 20, 30)], {("A", "B"): 15.0})
    assert plan_observations(scenario).opportunity_ids == ("B-01",)


def test_local_search_improves_on_greedy():
    # Greedy places P1 target A at its earlier opportunity, which blocks the only P2 opportunity.
    # Insert-with-ejection removes A-01, adds C-01, and the repair step re-adds A at A-02.
    scenario = make_scenario(
        {"A": 1, "C": 2, "D": 5},
        [("A-01", "A", 0, 30), ("A-02", "A", 1000, 1030), ("C-01", "C", 10, 20), ("D-01", "D", 1010, 1020)],
    )
    greedy = plan_observations(scenario, max_passes=0)
    improved = plan_observations(scenario)
    assert counts(greedy, scenario) == (1, 0, 0, 0, 1)
    assert counts(improved, scenario) == (1, 1, 0, 0, 0)
    assert improved.stop_reason == "converged"


def test_removal_rechecks_the_new_neighbour_pair():
    # X -> Y -> Z fits (10 s + 10 s), but X -> Z needs 90 s: removing Y must be refused.
    scenario = make_scenario(
        {"X": 3, "Y": 5, "Z": 3},
        [("X-01", "X", 0, 10), ("Y-01", "Y", 20, 30), ("Z-01", "Z", 40, 50)],
        {("X", "Y"): 10.0, ("Y", "Z"): 10.0, ("X", "Z"): 90.0},
    )
    assert is_plan_feasible(Plan(("X-01", "Y-01", "Z-01")), scenario)
    assert not is_plan_feasible(Plan(("X-01", "Z-01")), scenario)
    schedule = Schedule(scenario, [scenario.opportunities[i] for i in ("X-01", "Y-01", "Z-01")])
    assert not schedule.can_remove(1)


def test_target_without_opportunities_is_never_selected():
    scenario = make_scenario({"A": 1, "B": 1}, [("A-01", "A", 0, 10)])
    assert plan_observations(scenario).opportunity_ids == ("A-01",)


def test_empty_scenario_gives_empty_plan():
    plan = plan_observations(make_scenario({"A": 1}, []))
    assert plan.opportunity_ids == ()
