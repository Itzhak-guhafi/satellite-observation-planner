# Satellite Observation Planner: Project Design & Rules

Home assignment (Full Stack). A local app that selects a valid, priority-favoring subset of satellite
observation opportunities over a fixed 24 h horizon, shows the selection evolving live on a map, and
exports the final plan as `plan.json`.

## Tech stack & versions

| Layer | Technology | Version |
|---|---|---|
| Runtime (backend) | Python | 3.13 |
| API | FastAPI + Uvicorn | 0.162 / 0.54 |
| Tests (backend) | pytest + httpx (FastAPI TestClient) | 9.2 / 0.28 |
| Runtime (frontend) | Node.js (pinned in `.nvmrc`) | 22 LTS |
| UI | React + TypeScript | 19.3 / 7.0 |
| Build / dev server | Vite + @vitejs/plugin-react | 8.3 / 6.2 |
| Map | Leaflet + react-leaflet | 1.9.4 / 5.0 |
| Live progress | Server-Sent Events (native `EventSource`) | n/a |

The exact versions are locked in `backend/requirements.txt` and `frontend/package-lock.json`.

## Repository layout

```
scenario_gen.py, scenario.json   # supplied input; never modified
plan.json                        # exported submission plan
README.md                        # minimal: overview, running, algorithm & trade-offs, limitations
backend/
  planner/                       # pure planning core: no web framework, no I/O except load_scenario
    models.py                    # Target, Opportunity, Scenario, Plan, ProgressSnapshot; load_scenario()
    maneuver.py                  # transition_seconds(prev_id, next_id); unknown IDs raise
    feasibility.py               # is_plan_feasible(plan, scenario); insertion checks (both neighbours)
    objective.py                 # count vector (P1..P5) and lexicographic comparison
    schedule.py                  # mutable, always-feasible search state (checked insert/remove/replace)
    algorithm.py                 # plan_observations(scenario, on_progress, max_passes, max_ejections)
    export.py                    # export_plan(plan, scenario) -> dict
  api/main.py                    # FastAPI app: thin adapter over planner/
  tests/
frontend/
  src/                           # React app: map, legend, side panel, SSE client
```

## Main components

### 1. Planner core (`backend/planner`)
- **Time model:** all instants are integer epoch milliseconds, and transitions are `round(seconds * 1000)`.
  Feasibility compares integers exactly, so an exact fit is feasible.
- **Feasibility rule:** `next.start >= prev.end + transition(prev.target, next.target)`, plus: only supplied
  opportunities with their original times, inside the horizon, each target at most once, chronological order.
  `is_plan_feasible` checks every rule independently of any search or UI state.
- **Objective:** maximise `(P1, P2, P3, P4, P5)` selected-target counts lexicographically. When two count
  vectors are equal, the plan with less total transition time wins.
- **Algorithm:**
  1. *Greedy construction.* Sort targets by the tuple `(priority, opportunity_count, target_id)` and skip
     targets without opportunities. For each target, insert the feasible opportunity that blocks the least.
  2. *Local search.* Accept strictly improving moves only, so the current plan is always the best plan:
     - **Insert-with-ejection:** insert an unselected target by removing a contiguous conflicting block
       (≤ `max_ejections`, default 3), then run a greedy repair.
     - **Relocate:** move a selected target to another of its opportunities to free a slot.
     - The search stops when a full pass brings no improvement, or after `max_passes` (default 50). It reports
       which of the two happened. This is a deterministic accuracy-vs-time trade-off (no wall-clock budget).
  3. *Perturbation is intentionally not implemented.* It is listed in the README as a next step.
- **Progress:** `on_progress(snapshot)` receives an immutable `ProgressSnapshot` (tuple of selected opportunity
  IDs, counts by priority, phase, pass, elapsed time). It is sent on every improvement, plus a periodic heartbeat.

### 2. API (`backend/api/main.py`)

| Method & path | Purpose |
|---|---|
| `GET /api/scenario` | Targets and opportunities for the map |
| `GET /api/plan/stream` | SSE stream. Planning starts when the client connects, so every event is live. The stream sends `progress` events, then `done` (the exported plan) or `failed` |

The planner runs in a worker thread and hands snapshots to the event loop with `loop.call_soon_threadsafe`.
When snapshots pile up, the stream batches them and sends only the newest. The UI builds `plan.json` from
the `done` payload, so the download is exactly the plan shown on the map. The Vite dev server proxies `/api`
to the backend.

### 3. Frontend (`frontend/src`)
- Leaflet map with one `CircleMarker` per target. The colour shows priority (P1 to P5). Selected targets are
  filled, unselected ones hollow, and targets with no opportunity grey. Includes a legend.
- Side panel: Start button, status (idle / running / completed), counts P1–P5 (selected out of total),
  elapsed time, a Download `plan.json` button (enabled only once the run is completed), and a short schedule list.
- **The map stays interactive while SSE runs:** `MapContainer` is created once, `fitBounds` runs only on
  first load, snapshots never move the view, and markers are memoised. A "Fit to targets" button restores
  the full view.

### 4. `plan.json` structure
```json
{
  "scenario_id": "...", "satellite_id": "...",
  "horizon": {"start_utc": "...", "end_utc": "..."},
  "summary": {"selected_count": 0,
              "counts_by_priority": {"P1": 0, "P2": 0, "P3": 0, "P4": 0, "P5": 0},
              "computation_duration_seconds": 0.0, "algorithm": "...",
              "stop_reason": "converged | max_passes", "improvement_passes": 0},
  "schedule": [{"sequence": 1, "opportunity_id": "...", "target_id": "...", "priority": 1,
                "latitude": 0.0, "longitude": 0.0, "start_utc": "...", "end_utc": "...",
                "transition_from_previous_seconds": null}]
}
```
An empty plan exports `schedule: []` with zero counts.

### 5. Tests (`backend/tests`)
The suite covers: a maneuver-infeasible pair that does not overlap in time; an exact-fit feasible transition;
unknown target IDs; the horizon; duplicate-target prevention; a higher priority winning a conflict; a
triangle-inequality violation on removal; empty-plan export; a full scenario run that is feasible and never
regresses across snapshots; and the API flow.

## Rules

1. **Clean code.** Use small functions with one responsibility and descriptive names. Prefer pure functions,
   with no hidden state or side effects.
2. **No unnecessary code.** Build only what the assignment or this document requires (YAGNI). Leave out
   speculative abstractions, unused parameters, dead code, commented-out code and debug prints.
3. **Minimal dependencies.** Add a library only when it clearly beats a few lines of our own code.
4. **Layer boundaries.** `planner/` has no dependency on FastAPI or the UI. `api/` is a thin adapter.
   Business rules live in one place only.
5. **Correctness first.** Use the supplied transition table as the only maneuver model. Never derive
   maneuvers from distance. A missing or unknown ID is an error, never zero. Always re-check both neighbours
   after an insert or a removal, because the triangle inequality is not guaranteed.
6. **Determinism.** The same input gives the same plan. Use explicit sort keys, iteration limits instead of
   time limits, and no unseeded randomness.
7. **Types.** Python uses type hints and `@dataclass(frozen=True)` for values that must not change. TypeScript
   runs in `strict` mode with no `any`.
8. **Comments explain *why*, not *what*.** Docstrings go on the public functions (`transition_seconds`,
   `is_plan_feasible`, `plan_observations`, `export_plan`).
9. **Tests accompany logic.** Every scheduling rule and every planner behaviour gets a focused test.
   `pytest` must pass before any commit.
10. **Supplied files are read-only.** Do not edit `scenario_gen.py` or `scenario.json`.
11. **Keep the docs minimal.** The README has exactly 4 sections: overview, running (with tech and versions),
    algorithm & architecture with trade-offs and scaling, and limitations & next steps.
12. **Language.** Code, identifiers, comments and the README are written in English.
