import json

from fastapi.testclient import TestClient

from api.main import app, get_scenario
from planner.feasibility import is_plan_feasible
from planner.models import Plan

client = TestClient(app)


def parse_events(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_scenario_endpoint_lists_targets_and_opportunities():
    body = client.get("/api/scenario").json()
    assert len(body["targets"]) == 200
    assert {"target_id", "latitude", "longitude", "priority", "opportunity_count"} <= body["targets"][0].keys()
    assert body["opportunities"]


def test_stream_sends_progress_then_a_feasible_done_plan():
    events = parse_events(client.get("/api/plan/stream").text)
    names = [name for name, _ in events]
    assert names[-1] == "done" and "progress" in names

    exported = events[-1][1]
    plan = Plan(tuple(entry["opportunity_id"] for entry in exported["schedule"]))
    assert is_plan_feasible(plan, get_scenario())
    assert set(exported["summary"]["counts_by_priority"]) == {"P1", "P2", "P3", "P4", "P5"}
