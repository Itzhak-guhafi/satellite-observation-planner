"""Scheduling rules. This is the single source of truth for what a valid plan is."""

from planner.models import Opportunity, Plan, Scenario


def transition_fits(scenario: Scenario, previous: Opportunity, following: Opportunity) -> bool:
    """`following` may come right after `previous` (an exact fit is feasible)."""
    return following.start_ms >= previous.end_ms + scenario.transition_ms(previous.target_id, following.target_id)


def within_horizon(scenario: Scenario, opp: Opportunity) -> bool:
    return scenario.horizon_start_ms <= opp.start_ms and opp.end_ms <= scenario.horizon_end_ms


def find_violations(plan: Plan, scenario: Scenario) -> list[str]:
    """List every broken rule; an empty list means the plan is feasible."""
    violations: list[str] = []
    known: list[Opportunity] = []
    for opp_id in plan.opportunity_ids:
        opp = scenario.opportunities.get(opp_id)
        if opp is None:
            violations.append(f"unknown opportunity {opp_id}")
        else:
            known.append(opp)

    if len(set(plan.opportunity_ids)) != len(plan.opportunity_ids):
        violations.append("an opportunity is selected more than once")

    seen_targets: set[str] = set()
    for opp in known:
        if not within_horizon(scenario, opp):
            violations.append(f"{opp.opportunity_id} is outside the planning horizon")
        if opp.target_id in seen_targets:
            violations.append(f"target {opp.target_id} is observed more than once")
        seen_targets.add(opp.target_id)

    for previous, following in zip(known, known[1:]):
        if previous.target_id != following.target_id and not transition_fits(scenario, previous, following):
            violations.append(f"{previous.opportunity_id} -> {following.opportunity_id}: "
                              "not chronological or not enough maneuver time")
    return violations


def is_plan_feasible(plan: Plan, scenario: Scenario) -> bool:
    """Check all scheduling rules, independently of planner or UI state."""
    return not find_violations(plan, scenario)
