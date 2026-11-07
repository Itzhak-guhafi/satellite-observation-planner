"""Mutable search state: a chronologically sorted, always-feasible sequence of observations."""

from bisect import bisect_left

from planner.feasibility import transition_fits, within_horizon
from planner.models import Opportunity, Scenario
from planner.objective import ObjectiveKey, objective_key


class Schedule:
    """Every mutation keeps the sequence feasible, so neighbours are checked on both sides."""

    def __init__(self, scenario: Scenario, items: list[Opportunity] | None = None) -> None:
        self.scenario = scenario
        self.items: list[Opportunity] = list(items or [])
        self.target_ids: set[str] = {o.target_id for o in self.items}

    def copy(self) -> "Schedule":
        return Schedule(self.scenario, self.items)

    def key(self) -> ObjectiveKey:
        return objective_key(self.items, self.scenario)

    def opportunity_ids(self) -> tuple[str, ...]:
        return tuple(o.opportunity_id for o in self.items)

    def insertion_index(self, opp: Opportunity) -> int:
        return bisect_left(self.items, opp.start_ms, key=lambda o: o.start_ms)

    def fits_between(self, left: int, right: int, opp: Opportunity) -> bool:
        """`opp` fits after items[left - 1] and before items[right] (other items ignored)."""
        if opp.target_id in self.target_ids or not within_horizon(self.scenario, opp):
            return False
        if left > 0 and not transition_fits(self.scenario, self.items[left - 1], opp):
            return False
        return right >= len(self.items) or transition_fits(self.scenario, opp, self.items[right])

    def can_insert(self, opp: Opportunity) -> bool:
        index = self.insertion_index(opp)
        return self.fits_between(index, index, opp)

    def can_remove(self, index: int) -> bool:
        """Removal creates a new neighbouring pair; the table does not guarantee the triangle inequality."""
        if index == 0 or index == len(self.items) - 1:
            return True
        return transition_fits(self.scenario, self.items[index - 1], self.items[index + 1])

    def insert(self, opp: Opportunity) -> None:
        index = self.insertion_index(opp)
        self.replace_range(index, index, opp)

    def remove(self, index: int) -> Opportunity:
        if not self.can_remove(index):
            raise ValueError(f"removing {self.items[index].opportunity_id} breaks its neighbours' transition")
        removed = self.items.pop(index)
        self.target_ids.discard(removed.target_id)
        return removed

    def replace_range(self, left: int, right: int, opp: Opportunity) -> list[Opportunity]:
        """Replace items[left:right] with `opp`, checking the transitions on both sides."""
        if not self.fits_between(left, right, opp):
            raise ValueError(f"{opp.opportunity_id} does not fit")
        removed = self.items[left:right]
        self.items[left:right] = [opp]
        self.target_ids.difference_update(o.target_id for o in removed)
        self.target_ids.add(opp.target_id)
        return removed
