from datetime import datetime, timedelta, timezone

from planner.models import Scenario, parse_scenario

HORIZON_START = datetime(2026, 11, 2, tzinfo=timezone.utc)
DEFAULT_TRANSITION_SECONDS = 5.0


def iso(seconds_from_start: float) -> str:
    return (HORIZON_START + timedelta(seconds=seconds_from_start)).strftime("%Y-%m-%dT%H:%M:%SZ")


def at(hh: int, mm: int, ss: int) -> int:
    return hh * 3600 + mm * 60 + ss


def make_scenario(priorities: dict[str, int],
                  opportunities: list[tuple[str, str, int, int]],
                  transitions: dict[tuple[str, str], float] | None = None) -> Scenario:
    """Small hand-built scenario. Opportunities are (opportunity_id, target_id, start_s, end_s) from the horizon
    start. Every unlisted ordered pair gets DEFAULT_TRANSITION_SECONDS, so the table is complete."""
    transitions = transitions or {}
    return parse_scenario({
        "scenario_id": "test",
        "satellite_id": "sat-test",
        "horizon_start_utc": iso(0),
        "horizon_end_utc": iso(24 * 3600),
        "targets": [{"target_id": t, "latitude": 0.0, "longitude": 0.0, "priority": p} for t, p in priorities.items()],
        "opportunities": [{"opportunity_id": oid, "target_id": t, "start_utc": iso(s), "end_utc": iso(e)}
                          for oid, t, s, e in opportunities],
        "transition_seconds": {a: {b: transitions.get((a, b), DEFAULT_TRANSITION_SECONDS)
                                   for b in priorities if b != a} for a in priorities},
    })
