# coa_tool.py
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import json, hashlib

try:
    from langchain.tools import tool   # optional: only needed if you actually use LangChain
except Exception:
    def tool(*args, **kwargs):
        def _decorator(fn): return fn
        return _decorator

from pydantic_models_coa import (
    COARequest, COAResponse, Mission, Environment, Route, ObjectiveWeights,
    Task, TimeWindow, Location, Controls, RiskRegisterEntry, SyncPoint, DecisionPoint, Branch,
    Metrics, FASDC, Audit
)

# --------- small helpers (pure-python; Pydantic enforces structure) ----------
def _iso_now_dt() -> datetime:
    return datetime.now(timezone.utc)

def _hash(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()[:16]

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def _toposort(tasks: List[Task]) -> List[str]:
    indeg: Dict[str, int] = {}
    g: Dict[str, List[str]] = {}
    for t in tasks:
        indeg.setdefault(t.id, 0)
    for t in tasks:
        for d in (t.dependencies or []):
            g.setdefault(d, []).append(t.id)
            indeg[t.id] = indeg.get(t.id, 0) + 1
    q = [t.id for t in tasks if indeg.get(t.id, 0) == 0]
    out: List[str] = []
    while q:
        v = q.pop(0)
        out.append(v)
        for nxt in g.get(v, []):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    return out if len(out) == len(tasks) else [t.id for t in tasks]

def _schedule(tasks: List[Task], now_dt: datetime) -> Dict[str, Dict[str, datetime]]:
    """
    Very simple forward scheduler:
    - respects dependencies
    - uses window.start if provided, else now
    - end = start + duration_hours
    """
    order = _toposort(tasks)
    t_by_id = {t.id: t for t in tasks}
    result: Dict[str, Dict[str, datetime]] = {}
    for tid in order:
        t = t_by_id[tid]
        deps_end = max([result[d]["end"] for d in (t.dependencies or [])], default=now_dt)
        win_start = (t.window.start if t.window and t.window.start else now_dt)
        start = max(deps_end, win_start)
        end = start + timedelta(hours=float(t.duration_hours))
        result[tid] = {"start": start, "end": end}
    return result

def _score(tasks: List[Task], w: ObjectiveWeights) -> Metrics:
    # Toy normalization just to keep a bounded 0..1 score; replace with your calibrated logic.
    total_h = sum(float(t.duration_hours) for t in tasks)
    risk_ct = sum(len(t.risks or []) for t in tasks)
    res_sum = 0
    dep_sum = 0
    for t in tasks:
        dep_sum += len(t.dependencies or [])
        if t.resources:
            res_sum += sum(max(0, int(v)) for v in t.resources.values())

    speed = _clamp01(1.0 - total_h / 72.0)
    safety = _clamp01(1.0 - risk_ct / 12.0)
    sustainment = _clamp01(1.0 - res_sum / 30.0)
    cost = _clamp01(1.0 - res_sum / 30.0)
    simplicity = _clamp01(1.0 - dep_sum / 20.0)

    composite = _clamp01(
        speed * w.speed
        + safety * w.safety
        + sustainment * w.sustainment
        + cost * w.cost
        + simplicity * w.simplicity
    )
    return Metrics(
        speed=speed, safety=safety, sustainment=sustainment,
        cost=cost, simplicity=simplicity, composite=composite
    )

def _fasdc(tasks: List[Task], mission: Mission) -> FASDC:
    acyclic = len(_toposort(tasks)) == len(tasks)
    has = len(tasks) > 0
    complete = has and acyclic and all(t.duration_hours and t.label for t in tasks)
    return FASDC(
        feasible=has,
        acceptable=True,          # hook your policy/ROE gate here
        suitable=bool(mission.intent),
        distinguishable=True,     # one COA at a time
        complete=complete
    )

def _render_markdown_brief(resp: COAResponse) -> str:
    # 4–5 paragraph work-order brief derived from the validated response
    # Build quick access to task times
    times = {}  # id -> (est, eet)
    for t in resp.tasks:
        times[t.id] = ("", "")
    # derive from sync_points / decision_points if you want exact times;
    # here we’ll just omit exact timestamps unless provided in those fields.

    # P1
    p1 = (
        f"**Situation & Mission.** {resp.commander_intent} "
        f"Assumptions: {', '.join(resp.assumptions) if resp.assumptions else '—'}. "
        f"Routes available: {', '.join(r.name for r in resp.routes) if resp.routes else '—'}. "
        f"FASDC: {'Pass' if all([resp.fasdc.feasible, resp.fasdc.acceptable, resp.fasdc.suitable, resp.fasdc.distinguishable, resp.fasdc.complete]) else 'Check'}."
    )
    # P2
    p2 = (
        "**Concept of Operations.** Corridor opening → medical setup → initial relief push, "
        "with medevac standby and branch routes on triggers; respect control measures and no-go areas."
    )
    # P3
    task_lines = []
    for t in resp.tasks:
        win = (t.window.start.isoformat().replace("+00:00","Z") if (t.window and t.window.start) else "ASAP")
        line = (f"{t.id} **{t.label}** ({t.owner or '—'}), win {win}, ~{t.duration_hours}h; "
                f"deps: {', '.join(t.dependencies or []) or '—'}; "
                f"risk: {', '.join([r.desc for r in (t.risks or [])]) or '—'}.")
        task_lines.append(line)
    p3 = "**Tasks & Timeline.** " + " ".join(task_lines) if task_lines else "**Tasks & Timeline.** —"

    # P4
    sp = ", ".join([f"{s.purpose} @ {(s.time.isoformat().replace('+00:00','Z') if s.time else 'TBD')}" for s in resp.sync_points]) or "—"
    dp = "; ".join([f"{d.id}: trigger \"{d.trigger}\" → {d.action}" for d in resp.decision_points]) or "—"
    br = "; ".join([f"\"{b.trigger}\" → {', '.join(b.changes)}" for b in resp.branches]) or "—"
    p4 = f"**Synchronization, Decisions & Branches.** SPs: {sp}. DPs: {dp}. Branches: {br}."

    # P5
    top_risks = ", ".join([rr.risk for rr in resp.risk_register[:3]]) or "—"
    m = resp.metrics
    p5 = (
        f"**Sustainment, Comms & Assessment.** Maintain resupply/medevac coverage; follow comms per controls. "
        f"Risk highlights: {top_risks}. "
        f"Score — speed {m.speed:.2f}, safety {m.safety:.2f}, sustain {m.sustainment:.2f}, "
        f"cost {m.cost:.2f}, simplicity {m.simplicity:.2f} → **composite {m.composite:.2f}**. "
        f"Violations: {', '.join(resp.violations) or 'none'}."
    )
    return "\n\n".join([p1, p2, p3, p4, p5])

# --------- The tool (Pydantic-in, Pydantic-out; optional markdown) ----------
@tool("COA_generator")
def COA_generator(
    mission: Dict[str, Any],
    environment: Optional[Dict[str, Any]] = None,
    assets: Optional[List[Dict[str, Any]]] = None,
    threats: Optional[List[Dict[str, Any]]] = None,
    hard_constraints: Optional[List[Dict[str, Any]]] = None,
    soft_constraints: Optional[List[Dict[str, Any]]] = None,
    objectives: Optional[Dict[str, Any]] = None,
    seed_tasks: Optional[List[Dict[str, Any]]] = None,
    now_iso: Optional[str] = None,
    output: str = "json"   # "json" | "markdown" | "both"
) -> Dict[str, Any] | str:
    """
    Validates input as COARequest, generates a COA, validates output as COAResponse.
    'output': json (default), markdown (4–5 paras), or both.
    """
    # ---- 1) Validate & coerce INPUT into COARequest ----
    raw_req = {
        "mission": mission,
        "environment": environment,
        "assets": assets,
        "threats": threats,
        "hard_constraints": hard_constraints,
        "soft_constraints": soft_constraints,
        "objectives": objectives,
        "seed_tasks": seed_tasks,
        "now_iso": (datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
                    if now_iso else None),
    }
    req = COARequest.model_validate(raw_req)

    # ---- 2) Build task list (use provided, or seed defaults) ----
    tasks: List[Task]
    if req.seed_tasks:
        tasks = list(req.seed_tasks)
    else:
        now = req.now_iso or _iso_now_dt()
        tasks = [
            Task(
                id="T1", label="Open Primary Route", owner="Engineer Team 2",
                location=Location(area="Route Alpha km 0–12"),
                window=TimeWindow(start=now),
                duration_hours=4, dependencies=[],
                controls=Controls(comms="VHF-1")
            ),
            Task(
                id="T2", label="Establish Forward Aid Point", owner="Med Team 1",
                location=Location(area="Sector A (Clinic Site)"),
                window=TimeWindow(start=now),
                duration_hours=3, dependencies=["T1"],
                controls=Controls(comms="SAT-1")
            ),
            Task(
                id="T3", label="Deliver Critical Supplies", owner="Log Cell",
                location=Location(area="Sector A/B"),
                window=TimeWindow(start=now),
                duration_hours=6, dependencies=["T1", "T2"],
                controls=Controls(comms="VHF-1")
            ),
        ]

    # ---- 3) Minimal constraint checking (example; extend as needed) ----
    violations: List[str] = []
    for hc in (req.hard_constraints or []):
        if "no-go" in hc.description.lower() or "no go" in hc.description.lower():
            bad = [t.id for t in tasks if (t.location and t.location.area and "no-go" in t.location.area.lower())]
            if bad:
                violations.append(f'Hard constraint "{hc.id}" breached by tasks: {", ".join(bad)}')

    # ---- 4) Timeline, SPs, DPs, Branches ----
    now_dt = req.now_iso or _iso_now_dt()
    timeline = _schedule(tasks, now_dt)  # id -> {start, end}

    sync_points: List[SyncPoint] = []
    if "T2" in timeline:
        sync_points.append(SyncPoint(time=timeline["T2"]["start"], purpose="Medical site ready", depends_on=["T2"]))
    if "T3" in timeline:
        sync_points.append(SyncPoint(time=timeline["T3"]["end"], purpose="Initial relief complete", depends_on=["T3"]))

    decision_points: List[DecisionPoint] = []
    if "T1" in timeline:
        decision_points.append(DecisionPoint(
            id="DP1", when=timeline["T1"]["end"],
            trigger="Route Alpha blocked > 3h",
            action="Re-route via Bravo; reassign Engineer Team 3"
        ))

    branches: List[Branch] = [
        Branch(trigger="Route Alpha blocked > 3h", changes=["Use Route Bravo", "Reassign Team 3 to T1"]),
        Branch(trigger="Airfield slot denied", changes=["Delay T3 by 2h", "Pull stocks from Depot South"]),
    ]

    # ---- 5) Routes (from env or defaults) ----
    routes: List[Route] = list(req.environment.routes) if (req.environment and req.environment.routes) else [
        Route(name="Route Alpha", mode="ground", legs=[[-72.13, 18.45], [-72.08, 18.50]]),
        Route(name="Route Bravo", mode="ground", legs=[[-72.13, 18.45], [-72.04, 18.52]]),
    ]

    # ---- 6) Metrics & FASDC ----
    weights = req.objectives or ObjectiveWeights(speed=.35, safety=.25, sustainment=.15, cost=.10, simplicity=.15)
    metrics = _score(tasks, weights)
    fasdc = _fasdc(tasks, req.mission)

    # ---- 7) Risk register (threats + task risks) ----
    risk_register: List[RiskRegisterEntry] = []
    for th in (req.threats or []):
        risk_register.append(RiskRegisterEntry(
            risk=f"{(th.type or 'Threat')}: {th.name}",
            likelihood=th.risk_level, impact="H",
            mitigation="Avoid hot areas; deconflict timing; reserve QRF"
        ))
    for t in tasks:
        for r in (t.risks or []):
            risk_register.append(RiskRegisterEntry(
                risk=f"{r.desc} @ {t.id}", likelihood=r.likelihood, impact=r.impact,
                mitigation="Add branch plan; pre-position spares/fuel"
            ))

    # ---- 8) Compose & VALIDATE OUTPUT (COAResponse) ----
    resp = COAResponse(
        mission_id=req.mission.id,
        commander_intent=req.mission.intent,
        assumptions=req.mission.assumptions or ["Road X may reopen within H+12"],
        tasks=tasks,
        sync_points=sync_points,
        routes=routes,
        decision_points=decision_points,
        branches=branches,
        metrics=metrics,
        fasdc=fasdc,
        violations=violations,
        risk_register=risk_register,
        audit=Audit(generated_at=_iso_now_dt(),
                    inputs_hash=_hash(raw_req),
                    notes="Prototype generator; validate with human review."),
        explain="Open corridor → set medical capability → push relief; branches for route denial and slot loss."
    )
    # If anything is structurally wrong, the COAResponse constructor raises a ValidationError.

    # ---- 9) Return format ----
    if output == "json":
        return json.loads(resp.model_dump_json())
    elif output == "markdown":
        return _render_markdown_brief(resp)
    elif output == "both":
        return {
            "coa": json.loads(resp.model_dump_json()),
            "brief_md": _render_markdown_brief(resp)
        }
    else:
        raise ValueError("output must be one of: 'json' | 'markdown' | 'both'")
