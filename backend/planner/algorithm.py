"""Priority-based planner: greedy construction followed by strictly improving local search.

Every move is accepted only if it improves the objective key, so the current schedule is always
the best valid plan found so far, and that is what progress snapshots and the final plan report.
"""

from collections.abc import Callable, Iterable
from time import perf_counter

from planner.feasibility import transition_fits, within_horizon
from planner.models import Opportunity, Plan, ProgressSnapshot, Scenario, Target
from planner.objective import priority_counts
from planner.schedule import Schedule

ProgressCallback = Callable[[ProgressSnapshot], None]

HEARTBEAT_SECONDS = 0.25


class _Reporter:
    def __init__(self, on_progress: ProgressCallback | None) -> None:
        self.on_progress = on_progress
        self.started = perf_counter()
        self.last_report = self.started

    def elapsed(self) -> float:
        return perf_counter() - self.started

    def report(self, schedule: Schedule, phase: str, passes: int) -> None:
        self.last_report = perf_counter()
        if self.on_progress is not None:
            self.on_progress(ProgressSnapshot(schedule.opportunity_ids(), priority_counts(schedule.items, schedule.scenario),
                                              phase, passes, self.elapsed()))

    def heartbeat(self, schedule: Schedule, phase: str, passes: int) -> None:
        if perf_counter() - self.last_report >= HEARTBEAT_SECONDS:
            self.report(schedule, phase, passes)


def target_order_key(scenario: Scenario) -> Callable[[Target], tuple[int, int, str]]:
    """Higher priority first, then scarcer targets (fewer opportunities), then target_id for determinism."""
    return lambda t: (t.priority, len(scenario.opportunities_by_target[t.target_id]), t.target_id)


def plan_observations(scenario: Scenario, on_progress: ProgressCallback | None = None, *,
                      max_passes: int = 50, max_ejections: int = 3) -> Plan:
    """Return the best valid plan found, calling `on_progress` with immutable snapshots while planning."""
    reporter = _Reporter(on_progress)
    schedule = Schedule(scenario)
    construct_greedy(schedule, reporter)
    schedule, stop_reason, passes = improve(schedule, reporter, max_passes, max_ejections)
    reporter.report(schedule, "completed", passes)
    return Plan(schedule.opportunity_ids(), reporter.elapsed(), stop_reason, passes)


def construct_greedy(schedule: Schedule, reporter: _Reporter) -> None:
    scenario = schedule.scenario
    candidates = sorted((t for t in scenario.targets.values() if scenario.opportunities_by_target[t.target_id]),
                        key=target_order_key(scenario))
    remaining = {t.target_id for t in candidates}
    for target in candidates:
        remaining.discard(target.target_id)
        fitting = [o for o in scenario.opportunities_by_target[target.target_id] if schedule.can_insert(o)]
        if not fitting:
            continue
        chosen = min(fitting, key=lambda o: (blocked_opportunities(scenario, o, remaining), o.start_ms, o.opportunity_id))
        schedule.insert(chosen)
        reporter.report(schedule, "construction", 0)


def blocked_opportunities(scenario: Scenario, opp: Opportunity, target_ids: set[str]) -> int:
    """How many opportunities of the given targets could no longer sit next to `opp`."""
    return sum(1 for tid in target_ids for other in scenario.opportunities_by_target[tid]
               if not pairwise_compatible(scenario, opp, other))


def pairwise_compatible(scenario: Scenario, a: Opportunity, b: Opportunity) -> bool:
    return transition_fits(scenario, a, b) if a.start_ms <= b.start_ms else transition_fits(scenario, b, a)


def improve(schedule: Schedule, reporter: _Reporter, max_passes: int,
            max_ejections: int) -> tuple[Schedule, str, int]:
    """Repeat full improvement passes until one finds nothing, or until `max_passes` (accuracy vs. time)."""
    order = target_order_key(schedule.scenario)
    for pass_number in range(1, max_passes + 1):
        improved = False

        unselected = [t for t in schedule.scenario.targets.values() if t.target_id not in schedule.target_ids]
        for target in sorted(unselected, key=order):
            candidate = best_insertion_with_ejection(schedule, target, max_ejections)
            if candidate is not None:
                schedule, improved = candidate, True
                reporter.report(schedule, "improvement", pass_number)
            reporter.heartbeat(schedule, "improvement", pass_number)

        selected = [schedule.scenario.targets[o.target_id] for o in schedule.items]
        for target in sorted(selected, key=order):
            candidate = best_relocation(schedule, target)
            if candidate is not None:
                schedule, improved = candidate, True
                reporter.report(schedule, "improvement", pass_number)
            reporter.heartbeat(schedule, "improvement", pass_number)

        if not improved:
            return schedule, "converged", pass_number
    return schedule, "max_passes", max_passes


def best_insertion_with_ejection(schedule: Schedule, target: Target, max_ejections: int) -> Schedule | None:
    """Insert `target` by ejecting up to `max_ejections` adjacent observations, then repair the freed gap.

    Returns the best resulting schedule if it beats the current one, otherwise None.
    """
    scenario = schedule.scenario
    best, best_key = None, schedule.key()
    for opp in scenario.opportunities_by_target[target.target_id]:
        if not within_horizon(scenario, opp):
            continue
        index = schedule.insertion_index(opp)
        for ejected_before in range(max_ejections + 1):
            for ejected_after in range(max_ejections + 1 - ejected_before):
                left, right = index - ejected_before, index + ejected_after
                if left < 0 or right > len(schedule.items) or not schedule.fits_between(left, right, opp):
                    continue
                low_ms, high_ms = gap_bounds(schedule, left, right)
                candidate = schedule.copy()
                ejected = candidate.replace_range(left, right, opp)
                repair(candidate, gap_candidates(candidate, low_ms, high_ms, ejected))
                key = candidate.key()
                if key > best_key:
                    best, best_key = candidate, key
    return best


def best_relocation(schedule: Schedule, target: Target) -> Schedule | None:
    """Move a selected target to another of its opportunities, then repair the slot it freed."""
    scenario = schedule.scenario
    index = next(i for i, o in enumerate(schedule.items) if o.target_id == target.target_id)
    if not schedule.can_remove(index):
        return None
    current = schedule.items[index]
    low_ms, high_ms = gap_bounds(schedule, index, index + 1)
    best, best_key = None, schedule.key()
    for alternative in scenario.opportunities_by_target[target.target_id]:
        if alternative == current:
            continue
        candidate = schedule.copy()
        candidate.remove(index)
        if not candidate.can_insert(alternative):
            continue
        candidate.insert(alternative)
        repair(candidate, gap_candidates(candidate, low_ms, high_ms, []))
        key = candidate.key()
        if key > best_key:
            best, best_key = candidate, key
    return best


def gap_bounds(schedule: Schedule, left: int, right: int) -> tuple[int, int]:
    """Time window freed when items[left:right] are removed."""
    scenario = schedule.scenario
    low = schedule.items[left - 1].end_ms if left > 0 else scenario.horizon_start_ms
    high = schedule.items[right].start_ms if right < len(schedule.items) else scenario.horizon_end_ms
    return low, high


def gap_candidates(schedule: Schedule, low_ms: int, high_ms: int,
                   ejected: Iterable[Opportunity]) -> list[Opportunity]:
    """Only these can newly fit: unselected opportunities inside the freed window, and any opportunity
    of an ejected target (which may now fit elsewhere). Everything else has unchanged neighbours."""
    scenario = schedule.scenario
    ejected_targets = {o.target_id for o in ejected}
    return [o for o in scenario.opportunities.values()
            if o.target_id not in schedule.target_ids
            and (o.target_id in ejected_targets or (low_ms <= o.start_ms and o.end_ms <= high_ms))]


def repair(schedule: Schedule, candidates: list[Opportunity]) -> None:
    """Greedy re-fill in the same priority order as construction (first fitting opportunity per target)."""
    order = target_order_key(schedule.scenario)
    targets = schedule.scenario.targets
    for opp in sorted(candidates, key=lambda o: (order(targets[o.target_id]), o.start_ms, o.opportunity_id)):
        if schedule.can_insert(opp):
            schedule.insert(opp)
