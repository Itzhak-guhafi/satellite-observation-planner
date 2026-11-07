import json

from conftest import make_scenario

from planner.export import export_plan
from planner.models import Plan


def test_empty_plan_exports_with_zero_counts():
    scenario = make_scenario({"A": 1}, [("A-01", "A", 0, 10)])
    exported = export_plan(Plan(()), scenario)
    assert exported["schedule"] == []
    assert exported["summary"]["counts_by_priority"] == {"P1": 0, "P2": 0, "P3": 0, "P4": 0, "P5": 0}
    json.dumps(exported)


def test_export_is_chronological_with_original_times():
    scenario = make_scenario({"A": 2, "B": 4}, [("A-01", "A", 100, 110), ("B-01", "B", 0, 10)], {("B", "A"): 7.5})
    exported = export_plan(Plan(("B-01", "A-01"), computation_seconds=0.5), scenario)

    assert exported["scenario_id"] == "test"
    assert exported["horizon"] == {"start_utc": "2026-11-02T00:00:00Z", "end_utc": "2026-11-03T00:00:00Z"}
    assert [e["opportunity_id"] for e in exported["schedule"]] == ["B-01", "A-01"]
    first, second = exported["schedule"]
    assert first["start_utc"] == "2026-11-02T00:00:00Z" and first["end_utc"] == "2026-11-02T00:00:10Z"
    assert first["transition_from_previous_seconds"] is None
    assert second["transition_from_previous_seconds"] == 7.5
    assert exported["summary"]["counts_by_priority"] == {"P1": 0, "P2": 1, "P3": 0, "P4": 1, "P5": 0}
    assert exported["summary"]["computation_duration_seconds"] == 0.5
