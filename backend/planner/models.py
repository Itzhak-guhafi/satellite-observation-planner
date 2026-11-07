"""Domain model and scenario loading.

All instants are stored as integer epoch milliseconds so that feasibility checks are exact
integer comparisons (an exact fit must be feasible, with no floating-point tolerance).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from planner.maneuver import TransitionTable, transition_seconds

PRIORITIES = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class Target:
    target_id: str
    latitude: float
    longitude: float
    priority: int


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    target_id: str
    start_utc: str
    end_utc: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True, eq=False)
class Scenario:
    scenario_id: str
    satellite_id: str
    horizon_start_utc: str
    horizon_end_utc: str
    horizon_start_ms: int
    horizon_end_ms: int
    targets: Mapping[str, Target]
    opportunities: Mapping[str, Opportunity]
    opportunities_by_target: Mapping[str, tuple[Opportunity, ...]]
    transition_ms_table: Mapping[str, Mapping[str, int]]

    def transition_ms(self, previous_target_id: str, next_target_id: str) -> int:
        """Maneuver time in integer milliseconds (precomputed from `transition_seconds`)."""
        return self.transition_ms_table[previous_target_id][next_target_id]


@dataclass(frozen=True)
class Plan:
    """Selected opportunity IDs in chronological order, plus run metadata."""

    opportunity_ids: tuple[str, ...]
    computation_seconds: float = 0.0
    stop_reason: str = "not_run"
    passes: int = 0


@dataclass(frozen=True)
class ProgressSnapshot:
    """Immutable view of the best valid plan found so far."""

    opportunity_ids: tuple[str, ...]
    counts: tuple[int, ...]
    phase: str
    passes: int
    elapsed_seconds: float


def parse_utc_ms(value: str) -> int:
    instant = datetime.fromisoformat(value)
    if instant.utcoffset() is None:
        raise ValueError(f"timestamp without timezone: {value!r}")
    return round(instant.timestamp() * 1000)


def parse_scenario(data: Mapping[str, Any]) -> Scenario:
    targets = {t["target_id"]: Target(t["target_id"], float(t["latitude"]), float(t["longitude"]), int(t["priority"]))
               for t in data["targets"]}
    if len(targets) != len(data["targets"]):
        raise ValueError("duplicate target_id")
    for target in targets.values():
        if target.priority not in PRIORITIES:
            raise ValueError(f"{target.target_id}: priority must be 1-5")

    opportunities: dict[str, Opportunity] = {}
    for raw in data["opportunities"]:
        opp = Opportunity(raw["opportunity_id"], raw["target_id"], raw["start_utc"], raw["end_utc"],
                          parse_utc_ms(raw["start_utc"]), parse_utc_ms(raw["end_utc"]))
        if opp.opportunity_id in opportunities:
            raise ValueError(f"duplicate opportunity_id {opp.opportunity_id}")
        if opp.target_id not in targets:
            raise ValueError(f"{opp.opportunity_id}: unknown target {opp.target_id}")
        if opp.end_ms < opp.start_ms:
            raise ValueError(f"{opp.opportunity_id}: ends before it starts")
        opportunities[opp.opportunity_id] = opp

    by_target: dict[str, list[Opportunity]] = {tid: [] for tid in targets}
    for opp in opportunities.values():
        by_target[opp.target_id].append(opp)

    table: TransitionTable = data["transition_seconds"]
    # Converting every ordered pair up front also validates that the table is complete.
    transition_ms_table = {a: {b: round(transition_seconds(table, a, b) * 1000) for b in targets if b != a}
                           for a in targets}

    return Scenario(
        scenario_id=data["scenario_id"],
        satellite_id=data["satellite_id"],
        horizon_start_utc=data["horizon_start_utc"],
        horizon_end_utc=data["horizon_end_utc"],
        horizon_start_ms=parse_utc_ms(data["horizon_start_utc"]),
        horizon_end_ms=parse_utc_ms(data["horizon_end_utc"]),
        targets=targets,
        opportunities=opportunities,
        opportunities_by_target={tid: tuple(sorted(opps, key=lambda o: (o.start_ms, o.opportunity_id)))
                                 for tid, opps in by_target.items()},
        transition_ms_table=transition_ms_table,
    )


def load_scenario(path: str | Path) -> Scenario:
    with open(path, encoding="utf-8") as f:
        return parse_scenario(json.load(f))
