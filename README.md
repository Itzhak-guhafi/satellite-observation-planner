# Priority-Based Satellite Observation Planner

## 1. Overview

A local web app that picks a valid subset of the precomputed observation opportunities in `scenario.json`
(200 targets, 266 opportunities, 24 h horizon). It favours higher priorities lexicographically,
`(P1, P2, P3, P4, P5)`. A map shows the selection changing while the planner runs, and the final plan can be
downloaded as `plan.json`.

On the supplied scenario, the plan selects 63 observations, `(13, 19, 15, 8, 8)`, in about 70 ms. All 13
schedulable P1 targets are included. The committed [`plan.json`](plan.json) is that plan.

## 2. Running

| | Technology |
|---|---|
| Backend | Python 3.13, FastAPI 0.162, Uvicorn 0.54, pytest 9.2 |
| Frontend | Node 22 LTS (`.nvmrc`), React 19.3, TypeScript 7.0, Vite 8.3, Leaflet 1.9.4 + react-leaflet 5.0 |
| Live progress | Server-Sent Events |

```bash
# Backend (terminal 1)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --port 8000

# Frontend (terminal 2)
cd frontend
nvm use && npm install
npm run dev            # open http://localhost:5173 and click Start

# Tests (any new terminal: activate the venv first)
cd backend && source .venv/bin/activate
pytest
```

pytest, uvicorn and the backend dependencies are installed only inside `backend/.venv`. Run
`source .venv/bin/activate` from `backend/` in every new terminal, or you will get `command not found`.

`plan.json` contains the scenario, satellite and horizon, a `summary` (counts P1–P5 including zeros,
computation duration, stop reason) and a chronological `schedule`. Each schedule entry lists the opportunity
and target IDs, priority, coordinates, the original start/end times, and the transition from the previous entry.
To regenerate it, click Start in the UI, then Download plan.json.

```json
{
  "scenario_id": "demo-001",
  "satellite_id": "sat-01",
  "horizon": {"start_utc": "2026-11-02T00:00:00Z", "end_utc": "2026-11-03T00:00:00Z"},
  "summary": {
    "selected_count": 63,
    "counts_by_priority": {"P1": 13, "P2": 19, "P3": 15, "P4": 8, "P5": 8},
    "computation_duration_seconds": 0.0723,
    "algorithm": "greedy construction + local search (insert-with-ejection, relocate)",
    "stop_reason": "converged",
    "improvement_passes": 3
  },
  "schedule": [
    {"sequence": 1, "opportunity_id": "T104-01", "target_id": "T104", "priority": 3,
     "latitude": 33.0756, "longitude": 130.691,
     "start_utc": "2026-11-02T00:54:15Z", "end_utc": "2026-11-02T00:54:25Z",
     "transition_from_previous_seconds": null},
    {"sequence": 2, "opportunity_id": "T106-01", "target_id": "T106", "priority": 1,
     "latitude": 35.175, "longitude": 130.6562,
     "start_utc": "2026-11-02T00:55:15Z", "end_utc": "2026-11-02T00:55:25Z",
     "transition_from_previous_seconds": 24.6}
  ]
}
```

The example shows the first two of 63 entries. An empty plan has `"schedule": []` and all counts at 0.

## 3. Algorithm & Architecture

**Feasibility.** Times are converted to integer milliseconds, so `next.start >= prev.end + transition` is an
exact comparison and an exact fit is feasible. `is_plan_feasible` checks every rule on its own. During the
search, every insert, removal or replacement re-checks the transitions on both sides, because removing an
observation creates a new neighbouring pair and the table does not guarantee the triangle inequality.

**1. Greedy construction.** Targets are sorted by the tuple `(priority, number of opportunities, target_id)`:
highest priority first, then scarcest first, with a deterministic tie-break. Each target gets the feasible
opportunity that blocks the fewest remaining opportunities.

**2. Local search.** Only strictly improving moves are accepted, so the current plan is always the best plan
found so far. That makes every progress snapshot and the final export valid and never worse than an earlier one.
- *Insert-with-ejection:* adds targets that greedy construction left out, typically a higher-priority target
  blocked by lower-priority ones already in the plan. To make room, up to `max_ejections` adjacent
  observations can be removed, and the freed gap is then re-filled greedily. Each resulting plan is compared
  with the current one. Only a strict improvement is kept (a higher count vector, or the same counts with less
  maneuver time), and it is applied immediately and shown live on the map.
- *Relocate:* moves a target that is already in the plan to another of its opportunities, so the slot it frees
  can be used by targets that did not fit there. The move is tried only if the new slot is already free and
  the old neighbours still fit together without it. The freed slot is then re-filled greedily. A relocation
  can improve the plan in two ways: it can add observations in the freed slot, or keep the same counts and
  shorten the plan's total maneuver time. As with insertion, only a strict improvement is kept, and it is
  applied immediately and shown live on the map.

**Trade-off: accuracy vs. computation time.**

The local search is capped at `max_passes = 50` passes (each pass runs both moves), and insert-with-ejection
at `max_ejections = 3` ejections per move. The search only accepts strict improvements, so it always ends,
but without a cap it could run for a very long time on large inputs. The cap is a speed-vs-accuracy choice: higher values may find better plans, lower
values give faster runs. It counts iterations rather than seconds, so the same input gives the same plan on
every machine. On this scenario the search converges after 3 passes, well under the cap, and improves the
greedy plan from `(13, 17, 14, 8, 7)` to `(13, 19, 15, 8, 8)`.

Greedy construction is O(n²) for n opportunities. I kept it simple on purpose: at this assignment's scale
(266 opportunities) the cost is negligible, and simpler code is easier to verify. For larger inputs, or
where higher accuracy is needed, the two improvements in section 4 (Limitations & Next steps) should be
implemented: one for speed and one for accuracy.

**Scaling to more targets.**
- *Computation:* local search dominates the cost. It is already bounded by `max_passes` and `max_ejections`
  (see *Trade-off: accuracy vs. computation time* above). Greedy construction can be sped up as described
  under *Speed* in section 4.
- *Memory:* the transition table grows with the square of the number of targets. The same idea as *Speed*
  in section 4 applies: only targets whose opportunities are close in time ever need a transition, so a
  sparse table would be enough.
- *UI:* with thousands of markers, switch Leaflet from SVG to its Canvas renderer. All markers are then
  drawn on a single canvas instead of one DOM element each, which keeps pan and zoom smooth.

**Architecture.**
- `backend/planner/` is a pure planning core with no web dependencies.
- `backend/api/` is a thin FastAPI adapter. `GET /api/plan/stream` starts the planner in a worker thread
  when the client connects and streams `progress` snapshots over SSE, so the progress is live, not a replay.
  When snapshots pile up they are batched, and only the newest is sent. The stream ends with `done`
  (the exported plan).
- `frontend/` is React + Leaflet. The map is created once and never re-centred by updates, so you can pan
  and zoom freely during a run. Markers are memoised. The download button saves the `done` payload, so the
  file is exactly the plan on the map.

**No duplicated state.** Each piece of data is stored once, so copies cannot drift apart:
- `Schedule` keeps only its chronological `items`. The insertion point is found with
  `bisect_left(items, start, key=...)` (Python 3.10+), not with a parallel list of start times that every
  mutation would have to keep in sync. This also makes each candidate copy in the local search cheaper.
- `Scenario` keeps only the transition table in integer milliseconds, which is what the planner uses. The raw
  table in seconds is used during loading (conversion and a completeness check) and is then released. The
  table is N², so storing it twice would double the largest memory cost.

## 4. Limitations & Next steps

- The plan is not proven optimal. The search stops when no single insertion or relocation improves it, but a
  better plan may still exist that needs a larger change, or a step that first makes the plan worse.
- A planning run takes about 70 ms, so the live map changes only briefly. No artificial delay was added.
- Re-filling is first-fit, and the greedy "least-blocking" choice counts pairwise conflicts only.
- **Next:**
  - Perturbation (iterated local search) to escape local optima. It removes a random segment of the best
    schedule, runs the local search again, and keeps the result only if it beats the best schedule so far.
  - Two greedy-construction improvements:
    - *Speed.* To find the opportunity that blocks the fewest others, the greedy step currently checks the
      opportunities of all unselected targets, which is O(n²) for n opportunities. The improvement is to
      check only opportunities close in time to the one being inserted, since only those can conflict with
      it. This gives the same choice in about O(n log n), as long as each range holds only a few opportunities.
    - *Accuracy.* The greedy step counts blocked opportunities without regard to their priority, so
      blocking a P2 and blocking a P5 weigh the same. Taking the priority of the blocked opportunities
      into account would make that choice deliberate instead of arbitrary. This changes results, so it
      should be measured on the scenario first.
  - A Stop control and a timeline view.

**Time spent:** about 6–8 hours.
