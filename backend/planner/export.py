"""JSON-serializable plan export."""

from typing import Any

from planner.models import PRIORITIES, Plan, Scenario
from planner.objective import priority_counts

ALGORITHM_NAME = "greedy construction + local search (insert-with-ejection, relocate)"


def export_plan(plan: Plan, scenario: Scenario) -> dict[str, Any]:
    """Build the chronological schedule document saved as plan.json."""
    opportunities = sorted((scenario.opportunities[oid] for oid in plan.opportunity_ids),
                           key=lambda o: (o.start_ms, o.opportunity_id))
    counts = priority_counts(opportunities, scenario)

    schedule = []
    previous = None
    for sequence, opp in enumerate(opportunities, start=1):
        target = scenario.targets[opp.target_id]
        schedule.append({
            "sequence": sequence,
            "opportunity_id": opp.opportunity_id,
            "target_id": target.target_id,
            "priority": target.priority,
            "latitude": target.latitude,
            "longitude": target.longitude,
            "start_utc": opp.start_utc,
            "end_utc": opp.end_utc,
            "transition_from_previous_seconds": (
                None if previous is None
                else scenario.transition_ms(previous.target_id, opp.target_id) / 1000),
        })
        previous = opp

    return {
        "scenario_id": scenario.scenario_id,
        "satellite_id": scenario.satellite_id,
        "horizon": {"start_utc": scenario.horizon_start_utc, "end_utc": scenario.horizon_end_utc},
        "summary": {
            "selected_count": len(schedule),
            "counts_by_priority": {f"P{p}": counts[p - 1] for p in PRIORITIES},
            "computation_duration_seconds": round(plan.computation_seconds, 4),
            "algorithm": ALGORITHM_NAME,
            "stop_reason": plan.stop_reason,
            "improvement_passes": plan.passes,
        },
        "schedule": schedule,
    }
