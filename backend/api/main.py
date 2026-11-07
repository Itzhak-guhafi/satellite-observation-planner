"""HTTP adapter over the planner: scenario data for the map and a live SSE planning stream."""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from planner.algorithm import plan_observations
from planner.export import export_plan
from planner.models import PRIORITIES, ProgressSnapshot, Scenario, load_scenario

DEFAULT_SCENARIO = Path(__file__).resolve().parents[2] / "scenario.json"
DONE_POLL_SECONDS = 0.1  # how often to re-check whether planning finished while no snapshot arrives

app = FastAPI(title="Satellite Observation Planner")


@lru_cache(maxsize=1)
def get_scenario() -> Scenario:
    return load_scenario(os.environ.get("SCENARIO_PATH", DEFAULT_SCENARIO))


@app.get("/api/scenario")
def scenario_overview() -> dict[str, Any]:
    scenario = get_scenario()
    return {
        "scenario_id": scenario.scenario_id,
        "satellite_id": scenario.satellite_id,
        "horizon": {"start_utc": scenario.horizon_start_utc, "end_utc": scenario.horizon_end_utc},
        "targets": [{**vars(t), "opportunity_count": len(scenario.opportunities_by_target[t.target_id])}
                    for t in scenario.targets.values()],
        "opportunities": [{"opportunity_id": o.opportunity_id, "target_id": o.target_id,
                           "start_utc": o.start_utc, "end_utc": o.end_utc}
                          for o in scenario.opportunities.values()],
    }


@app.get("/api/plan/stream")
async def plan_stream() -> StreamingResponse:
    """Planning starts when the client connects, so every progress event is live (never a replay)."""
    return StreamingResponse(_planning_events(get_scenario()), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _planning_events(scenario: Scenario) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[ProgressSnapshot] = asyncio.Queue()

    def on_progress(snapshot: ProgressSnapshot) -> None:  # runs in the worker thread
        loop.call_soon_threadsafe(queue.put_nowait, snapshot)

    planning = loop.run_in_executor(None, plan_observations, scenario, on_progress)
    while not planning.done() or not queue.empty():
        try:
            latest = await asyncio.wait_for(queue.get(), timeout=DONE_POLL_SECONDS)
        except TimeoutError:
            continue
        # Batch a backlog: if the client is slower than the planner, only the newest snapshot matters.
        while not queue.empty():
            latest = queue.get_nowait()
        yield _sse("progress", _snapshot_payload(latest))

    try:
        plan = await planning
    except Exception as error:  # surface planner failures to the UI instead of a silently closed stream
        yield _sse("failed", {"message": str(error)})
        return
    yield _sse("done", export_plan(plan, scenario))


def _snapshot_payload(snapshot: ProgressSnapshot) -> dict[str, Any]:
    return {
        "opportunity_ids": list(snapshot.opportunity_ids),
        "counts_by_priority": {f"P{p}": snapshot.counts[p - 1] for p in PRIORITIES},
        "phase": snapshot.phase,
        "passes": snapshot.passes,
        "elapsed_seconds": round(snapshot.elapsed_seconds, 4),
    }


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
