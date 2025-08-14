# COA tool — drop-in
# Tries to use a common @tool decorator (LangChain). If unavailable, falls back to a no-op.
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import json, hashlib, math

try:
    from langchain.tools import tool  # common in agent stacks
except Exception:  # fallback: no-op decorator
    def tool(*args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _hash(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _toposort(tasks: List[Dict[str, Any]]) -> List[str]:
    indeg: Dict[str, int] = {}
    g: Dict[str, List[str]] = {}
    for t in tasks:
        tid = t["id"]
        indeg[tid] = indeg.get(tid, 0)
    for t in tasks:
        for d in t.get("dependencies", []) or []:
            g.setdefault(d, []).append(t["id"])
            indeg[t["id"]] = indeg.get(t["id"], 0) + 1
    q = [t["id"] for t in tasks if indeg.get(t["id"], 0) == 0]
    out: List[str] = []
    while q:
        v = q.pop(0)
        out.append(v)
        for nxt in g.get(v, []):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    # If cycle, just return declared order
    return out if len(out) == len(tasks) else [t["id"] for t in tasks]


def _parse_iso(s: Optional[str], default_ts_ms: int) -> int:
    if not s:
        return default_ts_ms
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return default_ts_ms


def _schedule(tasks: List[Dict[str, Any]], now_iso: str) -> List[Dict[str, str]]:
    order = _toposort(tasks)
    tmap = {t["id"]: t for t in tasks}
    now_ms = _parse_iso(now_iso, int(datetime.now(timezone.utc).timestamp() * 1000))
    result: Dict[str, Dict[str, int]] = {}
    for tid in order:
        t = tmap[tid]
        deps_end = max([result[d]["end"] for d in (t.get("dependencies") or [])], default=now_ms)
        win_start = _parse_iso((t.get("window") or {}).get("start"), now_ms)
        start = max(deps_end, win_start)
        dur_h = float(t.get("duration_hours") or 1.0)
        end = start + int(dur_h * 3600_000)
        result[tid] = {"start": start, "end": end}
    def _fmt(ms: int) -> str:
        return datetime.fromtimestamp(ms/1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return [{"id": tid, "est": _fmt(result[tid]["start"]), "eet": _fmt(result[tid]["end"])} for tid in order]


def _score(tasks: List[Dict[str, Any]], weights: Dict[str, float]) -> Dict[str, float]:
    total_hours = sum(float(t.get("duration_hours") or 1.0) for t in tasks)
    risk_count  = sum(len(t.get("risks") or []) for t in tasks)
    resource_sum = 0
    dep_sum = 0
    for t in tasks:
        dep_sum += len(t.get("dependencies") or [])
        resources = t.get("resources") or {}
        if isinstance(resources, dict):
            resource_sum += sum((resources.get(k) or 0) for k in resources.keys())

    # crude normalization bounds (tune as needed)
    speed       = _clamp01(1.0 - total_hours/72.0)
    safety      = _clamp01(1.0 - risk_count/12.0)
    sustainment = _clamp01(1.0 - resource_sum/30.0)
    cost        = _clamp01(1.0 - resource_sum/30.0)
    simplicity  = _clamp01(1.0 - dep_sum/20.0)

    composite = _clamp01(
        speed      * float(weights.get("speed", 0.35)) +
        safety     * float(weights.get("safety", 0.25)) +
        sustainment* float(weights.get("sustainment", 0.15)) +
        cost       * float(weights.get("cost", 0.10)) +
        simplicity * float(weights.get("simplicity", 0.15))
    )
    return {"speed": speed, "safety": safety, "sustainment": sustainment, "cost": cost, "simplicity": simplicity, "composite": composite}


def _fasdc(tasks: List[Dict[str, Any]], mission: Dict[str, Any]) -> Dict[str, bool]:
    has_tasks = len(tasks) > 0
    acyclic = len(_toposort(tasks)) == len(tasks)
    return {
        "feasible": has_tasks,
        "acceptable": True,                # wire to policy/ROE checks in your stack
        "suitable": bool(mission.get("intent")),
        "distinguishable": True,           # single COA per call
        "complete": has_tasks and all(("duration_hours" in t) for t in tasks) and acyclic
    }


@tool("COA_generator")
def COA_generator(
    mission: Dict[str, Any],
    environment: Optional[Dict[str, Any]] = None,
    assets: Optional[List[Dict[str, Any]]] = None,
    threats: Optional[List[Dict[str, Any]]] = None,
    hard_constraints: Optional[List[Dict[str, Any]]] = None,
    soft_constraints: Optional[List[Dict[str, Any]]] = None,
    objectives: Optional[Dict[str, float]] = None,
    seed_tasks: Optional[List[Dict[str, Any]]] = None,
    now_iso: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a Course of Action (COA) given mission/context/constraints.

    Args (JSON-serializable):
      mission: {
        "id": str, "intent": str, "end_state"?: str, "time_available_hours"?: float,
        "ccirs"?: [str], "assumptions"?: [str]
      }
      environment?: {
        "ao_name"?: str, "weather"?: str, "terrain"?: str,
        "key_facilities"?: [{"name": str, "location"?: [lon, lat]}],
        "no_go_zones"?: [{"name": str, "polygon"?: [[lon,lat], ...], "reason"?: str}],
        "routes"?: [{"name": str, "legs": [[lon,lat], ...], "mode"?: "ground"|"air"|"sea"}]
      }
      assets?: [{"id": str, "label": str, "count": int, ...}]
      threats?: [{"name": str, "type"?: str, "risk_level"?: "L"|"M"|"H"}]
      hard_constraints?: [{"id": str, "description": str}]
      soft_constraints?: [{"id": str, "description": str, "weight": float, "target": "min"|"max", "metric": str}]
      objectives?: {"speed": float, "safety": float, "sustainment": float, "cost": float, "simplicity": float}
      seed_tasks?: [
        {
          "id": str, "label": str, "owner"?: str,
          "location"?: {"geo"?: [lon,lat], "area"?: str},
          "window"?: {"start"?: ISO8601, "end"?: ISO8601},
          "duration_hours"?: float,
          "dependencies"?: [task_id],
          "resources"?: {asset_id: int},
          "controls"?: {"safety_zones"?: [str], "comms"?: str},
          "risks"?: [{"desc": str, "likelihood": "L"|"M"|"H", "impact": "L"|"M"|"H"}]
        }, ...
      ]
      now_iso?: ISO8601 string (defaults to current UTC time)

    Returns:
      dict with keys:
        mission_id, commander_intent, assumptions, tasks, sync_points, routes,
        decision_points, branches, metrics, fasdc, violations, risk_register, audit, explain
    """
    if not isinstance(mission, dict) or "id" not in mission or "intent" not in mission:
        raise ValueError("mission must include 'id' and 'intent'")

    now_iso = now_iso or _iso_now()
    weights = objectives or {"speed": 0.35, "safety": 0.25, "sustainment": 0.15, "cost": 0.10, "simplicity": 0.15}

    # 1) Seed/synthesize tasks
    tasks: List[Dict[str, Any]]
    if seed_tasks and len(seed_tasks) > 0:
        # Ensure every task has an id and duration
        tasks = []
        for i, t in enumerate(seed_tasks):
            t = dict(t)  # shallow copy
            t.setdefault("id", f"T{i+1}")
            t.setdefault("duration_hours", 1.0)
            t.setdefault("dependencies", t.get("dependencies") or [])
            tasks.append(t)
    else:
        # Safe default (disaster-relief flavored)
        tasks = [
            {
                "id": "T1",
                "label": "Open Primary Route",
                "owner": "Engineer Team 2",
                "location": {"area": "Route Alpha km 0–12"},
                "window": {"start": now_iso},
                "duration_hours": 4,
                "dependencies": [],
                "resources": {},
                "controls": {"comms": "VHF-1"},
                "risks": [{"desc": "Aftershock", "likelihood": "M", "impact": "H"}],
            },
            {
                "id": "T2",
                "label": "Establish Forward Aid Point",
                "owner": "Med Team 1",
                "location": {"area": "Sector A (Clinic Site)"},
                "window": {"start": now_iso},
                "duration_hours": 3,
                "dependencies": ["T1"],
                "resources": {},
                "controls": {"comms": "SAT-1"},
                "risks": [{"desc": "Supply delay", "likelihood": "M", "impact": "M"}],
            },
            {
                "id": "T3",
                "label": "Deliver Critical Supplies",
                "owner": "Log Cell",
                "location": {"area": "Sector A/B"},
                "window": {"start": now_iso},
                "duration_hours": 6,
                "dependencies": ["T1", "T2"],
                "resources": {},
                "controls": {"comms": "VHF-1"},
                "risks": [{"desc": "Road closure", "likelihood": "L", "impact": "H"}],
            },
        ]

    # 2) Minimal hard-constraint screening
    violations: List[str] = []
    for hc in (hard_constraints or []):
        desc = str(hc.get("description", "")).lower()
        if "no-go" in desc or "no go" in desc:
            bad = [t["id"] for t in tasks if "no-go" in str((t.get("location") or {}).get("area", "")).lower()]
            if bad:
                violations.append(f'Hard constraint "{hc.get("id","HC")}" breached by tasks: {", ".join(bad)}')

    # 3) Schedule & sync points
    timeline = _schedule(tasks, now_iso)
    t_by_id = {t["id"]: t for t in timeline}
    sync_points = []
    if "T2" in t_by_id:
        sync_points.append({"time": t_by_id["T2"]["est"], "purpose": "Medical site ready", "depends_on": ["T2"]})
    if "T3" in t_by_id:
        sync_points.append({"time": t_by_id["T3"]["eet"], "purpose": "Initial relief complete", "depends_on": ["T3"]})

    # 4) Decision points & branches (basic examples)
    decision_points = []
    if "T1" in t_by_id:
        decision_points.append({
            "id": "DP1",
            "when": t_by_id["T1"]["eet"],
            "trigger": "Route Alpha blocked > 3h",
            "action": "Re-route via Bravo; reassign Engineer Team 3"
        })
    branches = [
        {"trigger": "Route Alpha blocked > 3h", "changes": ["Use Route Bravo", "Reassign Team 3 to T1"]},
        {"trigger": "Airfield slot denied", "changes": ["Delay T3 by 2h", "Pull stocks from Depot South"]}
    ]

    # 5) Metrics & FASDC
    metrics = _score(tasks, weights)
    fasdc = _fasdc(tasks, mission)

    # 6) Risk register (merge threats + per-task risks)
    risk_register: List[Dict[str, Any]] = []
    for th in (threats or []):
        risk_register.append({
            "risk": f'{th.get("type","Threat")}: {th.get("name","Unknown")}',
            "likelihood": th.get("risk_level", "M"),
            "impact": "H",
            "mitigation": "Avoid hot areas; deconflict timing; reserve QRF"
        })
    for t in tasks:
        for r in (t.get("risks") or []):
            risk_register.append({
                "risk": f'{r.get("desc","Risk")} @ {t["id"]}',
                "likelihood": r.get("likelihood", "M"),
                "impact": r.get("impact", "M"),
                "mitigation": "Add branch plan; pre-position spares/fuel"
            })

    # 7) Routes (pass-through or defaults)
    routes = (environment or {}).get("routes") or [
        {"name": "Route Alpha", "legs": [[-72.13, 18.45], [-72.08, 18.50]], "mode": "ground"},
        {"name": "Route Bravo", "legs": [[-72.13, 18.45], [-72.04, 18.52]], "mode": "ground"},
    ]

    # 8) Compose COA
    coa: Dict[str, Any] = {
        "mission_id": mission["id"],
        "commander_intent": mission["intent"],
        "assumptions": mission.get("assumptions") or ["Road X may reopen within H+12"],
        "tasks": tasks,
        "sync_points": sync_points,
        "routes": routes,
        "decision_points": decision_points,
        "branches": branches,
        "metrics": metrics,
        "fasdc": fasdc,
        "violations": violations,
        "risk_register": risk_register,
        "audit": {
            "generated_at": _iso_now(),
            "inputs_hash": _hash({
                "mission": mission, "environment": environment, "assets": assets,
                "threats": threats, "hard_constraints": hard_constraints,
                "soft_constraints": soft_constraints, "objectives": objectives,
                "seed_tasks": seed_tasks, "now_iso": now_iso
            }),
            "notes": "Prototype generator; validate with human review."
        },
        "explain": "COA prioritizes opening Route Alpha to enable medical setup and supply push; branches cover route denial and slotting issues."
    }
    return coa
