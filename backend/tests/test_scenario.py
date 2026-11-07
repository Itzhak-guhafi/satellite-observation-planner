from pathlib import Path

from planner.algorithm import plan_observations
from planner.feasibility import is_plan_feasible
from planner.models import Plan, load_scenario

SCENARIO_PATH = Path(__file__).resolve().parents[2] / "scenario.json"


def test_supplied_scenario_plan_is_feasible_and_progress_never_regresses():
    scenario = load_scenario(SCENARIO_PATH)
    snapshots = []
    plan = plan_observations(scenario, snapshots.append)

    assert is_plan_feasible(plan, scenario)
    assert snapshots and snapshots[-1].opportunity_ids == plan.opportunity_ids
    for earlier, later in zip(snapshots, snapshots[1:]):
        assert later.counts >= earlier.counts
    assert all(is_plan_feasible(Plan(s.opportunity_ids), scenario) for s in snapshots)


def test_planner_is_deterministic():
    scenario = load_scenario(SCENARIO_PATH)
    assert plan_observations(scenario).opportunity_ids == plan_observations(scenario).opportunity_ids
