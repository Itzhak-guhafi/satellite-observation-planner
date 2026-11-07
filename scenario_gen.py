"""Deterministic generator for scenario.json (seed fixed)."""
import json, math, random
from datetime import datetime, timedelta, timezone

SEED = 20261101
rng = random.Random(SEED)
H0 = datetime(2026, 11, 2, tzinfo=timezone.utc)
H1 = H0 + timedelta(days=1)
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")

# Regions: (name, lat_c, lon_c, lat_spread, lon_spread, n_targets, pass times in hours UTC)
REGIONS = [
    ("Levant",          32.0,  35.0, 3.0, 2.0, 22, [3.4, 8.9, 15.2, 20.6]),
    ("W_Europe",        48.5,   4.0, 4.0, 5.0, 20, [4.8, 10.1, 16.7]),
    ("E_Mediterranean", 37.5,  25.0, 3.0, 4.0, 16, [5.6, 17.3]),
    ("Gulf",            25.5,  52.0, 3.0, 4.0, 18, [2.1, 7.7, 19.4]),
    ("Horn_of_Africa",  10.0,  45.0, 4.0, 4.0, 12, [6.8, 18.9]),
    ("East_Asia",       35.5, 135.0, 4.0, 5.0, 20, [0.9, 12.6, 13.4]),
    ("South_Asia",      22.0,  78.0, 5.0, 5.0, 16, [1.5, 14.0]),
    ("N_America_East",  40.5, -75.0, 4.0, 5.0, 20, [11.3, 22.8]),
    ("N_America_West",  37.0,-120.0, 4.0, 3.0, 14, [9.6, 21.7]),
    ("South_America",  -23.0, -46.0, 4.0, 4.0, 14, [10.8, 23.3]),
    ("West_Africa",      7.0,   2.0, 3.0, 5.0, 12, [12.1]),
    ("Oceania",        -33.5, 151.0, 3.0, 3.0, 16, []),  # no passes -> unschedulable targets
]
PRIO_WEIGHTS = [(1, 0.10), (2, 0.15), (3, 0.20), (4, 0.25), (5, 0.30)]

def pick_prio():
    r, acc = rng.random(), 0.0
    for p, w in PRIO_WEIGHTS:
        acc += w
        if r < acc: return p
    return 5

targets, region_of = [], {}
n = 0
for name, latc, lonc, dlat, dlon, count, _ in REGIONS:
    for _ in range(count):
        n += 1
        tid = f"T{n:03d}"
        targets.append({"target_id": tid,
                        "latitude": round(latc + rng.uniform(-dlat, dlat), 4),
                        "longitude": round(lonc + rng.uniform(-dlon, dlon), 4),
                        "priority": pick_prio()})
        region_of[tid] = name
tmap = {t["target_id"]: t for t in targets}

# ---- transition table: asymmetric, roughly distance-driven, with triangle-inequality violations
def ang(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a["latitude"], a["longitude"], b["latitude"], b["longitude"]))
    c = math.sin(la1)*math.sin(la2) + math.cos(la1)*math.cos(la2)*math.cos(lo1-lo2)
    return math.degrees(math.acos(max(-1, min(1, c))))

trans = {}
for a in targets:
    row = {}
    for b in targets:
        if a is b: continue
        base = 8.0 + 9.0 * math.sqrt(ang(a, b))
        v = base * rng.uniform(0.85, 1.30)          # asymmetry
        if rng.random() < 0.03: v *= rng.uniform(2.0, 3.5)  # triangle-inequality breakers
        row[b["target_id"]] = round(v, 1)
    trans[a["target_id"]] = row

# ---- opportunities: along-track passes; time offset follows latitude (ascending pass)
opps = []
GROUND_SPEED_DEG_S = 0.063
for name, latc, lonc, dlat, dlon, count, passes in REGIONS:
    members = [t for t in targets if region_of[t["target_id"]] == name]
    for ph in passes:
        pass_start = H0 + timedelta(hours=ph)
        for t in members:
            if rng.random() > 0.55: continue
            along = (t["latitude"] - (latc - dlat)) / GROUND_SPEED_DEG_S
            jitter = rng.uniform(-25, 25)
            start = pass_start + timedelta(seconds=round(along + jitter))
            dur = rng.choice([10, 15, 20, 20, 30, 30, 45, 60])
            opps.append({"target_id": t["target_id"], "start": start, "end": start + timedelta(seconds=dur)})

# ---- engineered cases (documented below)
def add(tid, start, dur):
    opps.append({"target_id": tid, "start": start, "end": start + timedelta(seconds=dur)})

lev = [t for t in targets if region_of[t["target_id"]] == "Levant"]
by_p = lambda p, pool: [t for t in pool if t["priority"] == p]
p1s, low = by_p(1, targets), [t for t in targets if t["priority"] >= 4]
pick = lambda pool, used: next(t for t in pool if t["target_id"] not in used)
used = set()
engineered = []

# Case A: exact-fit transition (integer transition, start == end + transition)
a = pick(low, used); used.add(a["target_id"])
b = pick(by_p(3, targets), used); used.add(b["target_id"])
trans[a["target_id"]][b["target_id"]] = 20.0
s = H0 + timedelta(hours=6, minutes=30); add(a["target_id"], s, 10)
add(b["target_id"], s + timedelta(seconds=10 + 20), 10)
engineered.append(f"exact fit: {a['target_id']} -> {b['target_id']} (transition 20.0 s, gap exactly 20 s)")

# Case B: non-overlapping but maneuver-infeasible (gap 10 s, transition 15 s) - mirrors the spec example
a = pick(by_p(2, targets), used); used.add(a["target_id"])
b = pick(by_p(1, targets), used); used.add(b["target_id"])
trans[a["target_id"]][b["target_id"]] = 15.0
s = H0 + timedelta(hours=7, minutes=10); add(a["target_id"], s, 10)
add(b["target_id"], s + timedelta(seconds=20), 10)
engineered.append(f"maneuver conflict: {a['target_id']} (P2) ends, {b['target_id']} (P1) starts 10 s later; transition 15.0 s")

# Case C: one P1 blocks three lower-priority targets that are mutually compatible
p1 = pick(p1s, used); used.add(p1["target_id"])
s = H0 + timedelta(hours=8, minutes=5)
add(p1["target_id"], s + timedelta(seconds=40), 60)
lows = []
for k in range(3):
    t = pick(low, used); used.add(t["target_id"]); lows.append(t)
    add(t["target_id"], s + timedelta(seconds=k * 45), 15)
for x in lows:
    for y in lows:
        if x is not y: trans[x["target_id"]][y["target_id"]] = 12.0
engineered.append(f"priority conflict: {p1['target_id']} (P1) overlaps {', '.join(t['target_id'] for t in lows)} (P4/P5), which fit together")

# Case D: triangle inequality violation making removal unsafe: X->Y->Z cheap, X->Z expensive
x = pick(by_p(3, targets), used); used.add(x["target_id"])
y = pick(by_p(5, targets), used); used.add(y["target_id"])
z = pick(by_p(3, targets), used); used.add(z["target_id"])
trans[x["target_id"]][y["target_id"]] = 10.0
trans[y["target_id"]][z["target_id"]] = 10.0
trans[x["target_id"]][z["target_id"]] = 90.0
s = H0 + timedelta(hours=13, minutes=50)
add(x["target_id"], s, 10); add(y["target_id"], s + timedelta(seconds=20), 10)
add(z["target_id"], s + timedelta(seconds=40), 10)
engineered.append(f"triangle violation: {x['target_id']}->{y['target_id']}->{z['target_id']} fits (10+10 s), but {x['target_id']}->{z['target_id']} needs 90 s")

# Case E: two P1 targets competing for the same slot (only one can be taken)
a = pick(p1s, used); used.add(a["target_id"]); b = pick(p1s, used); used.add(b["target_id"])
s = H0 + timedelta(hours=16, minutes=20)
add(a["target_id"], s, 30); add(b["target_id"], s + timedelta(seconds=15), 30)
engineered.append(f"P1 vs P1 overlap: {a['target_id']} and {b['target_id']}")

# ---- clamp to horizon, sort, assign IDs
opps = [o for o in opps if o["start"] >= H0 and o["end"] <= H1]
opps.sort(key=lambda o: (o["start"], o["target_id"]))
counter = {}
out_opps = []
for o in opps:
    counter[o["target_id"]] = counter.get(o["target_id"], 0) + 1
    out_opps.append({"opportunity_id": f"{o['target_id']}-{counter[o['target_id']]:02d}",
                     "target_id": o["target_id"], "start_utc": iso(o["start"]), "end_utc": iso(o["end"])})

scenario = {"scenario_id": "demo-001", "satellite_id": "sat-01",
            "horizon_start_utc": iso(H0), "horizon_end_utc": iso(H1),
            "targets": targets, "opportunities": out_opps, "transition_seconds": trans}
with open("scenario.json", "w") as f:
    json.dump(scenario, f, separators=(",", ":"))
with open("engineered_cases.txt", "w") as f:
    f.write("\n".join(engineered) + "\n")
print("\n".join(engineered))

