# === COA tool with human brief rendering / LLM handoff ===
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json, hashlib

try:
    from langchain.tools import tool
except Exception:
    def tool(*args, **kwargs):
        def _decorator(fn): return fn
        return _decorator

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def _clamp01(x: float) -> float: return max(0.0, min(1.0, x))
def _hash(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",",":"))
    return hashlib.sha256(s.encode()).hexdigest()[:16]

def _parse_iso(s: Optional[str], default_ms: int) -> int:
    if not s: return default_ms
    try: return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()*1000)
    except Exception: return default_ms

def _toposort(tasks: List[Dict[str, Any]]) -> List[str]:
    indeg, g = {}, {}
    for t in tasks: indeg.setdefault(t["id"], 0)
    for t in tasks:
        for d in (t.get("dependencies") or []):
            g.setdefault(d, []).append(t["id"])
            indeg[t["id"]] = indeg.get(t["id"], 0) + 1
    q = [t["id"] for t in tasks if indeg.get(t["id"],0)==0]
    out=[]
    while q:
        v=q.pop(0); out.append(v)
        for nxt in g.get(v, []):
            indeg[nxt]-=1
            if indeg[nxt]==0: q.append(nxt)
    return out if len(out)==len(tasks) else [t["id"] for t in tasks]

def _schedule(tasks: List[Dict[str, Any]], now_iso: str) -> List[Dict[str,str]]:
    order = _toposort(tasks)
    tmap = {t["id"]: t for t in tasks}
    now_ms = _parse_iso(now_iso, int(datetime.now(timezone.utc).timestamp()*1000))
    times: Dict[str, Dict[str,int]] = {}
    for tid in order:
        t = tmap[tid]
        deps_end = max([times[d]["end"] for d in (t.get("dependencies") or [])], default=now_ms)
        win_start = _parse_iso((t.get("window") or {}).get("start"), now_ms)
        start = max(deps_end, win_start)
        dur_ms = int(float(t.get("duration_hours") or 1.0) * 3600_000)
        times[tid] = {"start": start, "end": start + dur_ms}
    fmt = lambda ms: datetime.fromtimestamp(ms/1000, tz=timezone.utc).isoformat().replace("+00:00","Z")
    return [{"id": tid, "est": fmt(times[tid]["start"]), "eet": fmt(times[tid]["end"])} for tid in order]

def _score(tasks: List[Dict[str, Any]], w: Dict[str,float]) -> Dict[str,float]:
    total_h = sum(float(t.get("duration_hours") or 1.0) for t in tasks)
    risk_ct = sum(len(t.get("risks") or []) for t in tasks)
    res_sum = sum(sum((t.get("resources") or {}).values()) for t in tasks)
    dep_sum = sum(len(t.get("dependencies") or []) for t in tasks)
    speed = _clamp01(1 - total_h/72); safety = _clamp01(1 - risk_ct/12)
    sustain = _clamp01(1 - res_sum/30); cost = _clamp01(1 - res_sum/30)
    simplicity = _clamp01(1 - dep_sum/20)
    comp = _clamp01(speed*w.get("speed",.35)+safety*w.get("safety",.25)+sustain*w.get("sustainment",.15)+
                    cost*w.get("cost",.10)+simplicity*w.get("simplicity",.15))
    return {"speed":speed,"safety":safety,"sustainment":sustain,"cost":cost,"simplicity":simplicity,"composite":comp}

def _fasdc(tasks: List[Dict[str, Any]], mission: Dict[str, Any]) -> Dict[str,bool]:
    has = bool(tasks); acyclic = len(_toposort(tasks))==len(tasks)
    return {"feasible":has, "acceptable":True, "suitable":bool(mission.get("intent")),
            "distinguishable":True, "complete": has and acyclic and all("duration_hours" in t for t in tasks)}

def _render_markdown_brief(coa: Dict[str, Any], timeline: List[Dict[str,str]]) -> str:
    # 4–5 compact paragraphs, markdown, from the COA JSON
    def get(id_: str, key: str) -> Optional[str]:
        for t in timeline:
            if t["id"]==id_: return t.get(key)
        return None

    # Paragraph 1 — Situation & Mission
    p1 = (
        f"**Situation & Mission.** {coa.get('commander_intent','').strip()} "
        f"Assumptions: {', '.join(coa.get('assumptions') or []) or '—'}. "
        f"Routes available: {', '.join([r.get('name','?') for r in (coa.get('routes') or [])]) or '—'}. "
        f"FASDC: "
        f"{'Pass' if all(coa.get('fasdc',{}).values()) else 'Check'}."
    )

    # Paragraph 2 — Concept of Operations
    p2 = (
        "**Concept of Operations.** "
        "Execute a phased corridor opening → medical setup → initial relief push, "
        "with air medevac on standby. Control measures and comms per plan; respect no-go/air corridors. "
        "Primary route is the designated ground corridor; alternate is the branch route if triggered."
    )

    # Paragraph 3 — Tasks & Timeline (compressed)
    task_lines=[]
    for t in coa.get("tasks", []):
        est = get(t["id"], "est"); eet = get(t["id"], "eet")
        line = (f"{t['id']} **{t.get('label','Task')}** ({t.get('owner','—')}), "
                f"win { (t.get('window') or {}).get('start','') or est }"
                f"{'→'+eet if eet else ''}, ~{t.get('duration_hours',1)}h; "
                f"deps: {', '.join(t.get('dependencies') or []) or '—'}; "
                f"risk: {', '.join(r.get('desc','') for r in (t.get('risks') or [])) or '—'}.")
        task_lines.append(line)
    p3 = "**Tasks & Timeline.** " + " ".join(task_lines) if task_lines else "**Tasks & Timeline.** —"

    # Paragraph 4 — Sync / Decisions / Branches
    sp = ", ".join([f"{s.get('purpose','SP')} @ {s.get('time','')}" for s in (coa.get('sync_points') or [])]) or "—"
    dp = "; ".join([f"{d.get('id','DP')}: trigger \"{d.get('trigger','')}\" → {d.get('action','')}"
                    for d in (coa.get('decision_points') or [])]) or "—"
    br = "; ".join([f"\"{b.get('trigger','')}\" → {', '.join(b.get('changes') or [])}" for b in (coa.get('branches') or [])]) or "—"
    p4 = f"**Synchronization, Decisions & Branches.** SPs: {sp}. DPs: {dp}. Branches: {br}."

    # Paragraph 5 — Sustainment / Comms / Risk / Score
    top_risks = ", ".join([rr.get("risk","") for rr in (coa.get("risk_register") or [])][:3]) or "—"
    m = coa.get("metrics", {})
    p5 = (f"**Sustainment, Comms & Assessment.** Maintain resupply and medevac coverage during convoy windows; "
          f"primary nets as specified in controls. Risk highlights: {top_risks}. "
          f"Score — speed {m.get('speed','–'):.2f}, safety {m.get('safety','–'):.2f}, sustain {m.get('sustainment','–'):.2f}, "
          f"cost {m.get('cost','–'):.2f}, simplicity {m.get('simplicity','–'):.2f} → **composite {m.get('composite','–'):.2f}**. "
          f"Violations: {', '.join(coa.get('violations') or []) or 'none'}."
    )
    return "\n\n".join([p1,p2,p3,p4,p5])

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
    now_iso: Optional[str] = None,
    output: str = "json"  # "json" | "markdown" | "both" | "llm_prompt"
) -> Dict[str, Any] | str:
    """
    Generate a COA. 'output' controls what you get back:
      - "json": COA JSON (machine-readable)
      - "markdown": 4–5 paragraph work-order brief (markdown)
      - "both": {"coa": <json>, "brief_md": <markdown>}
      - "llm_prompt": {"coa": <json>, "render_prompt": <string for your LLM>}
    """
    if not isinstance(mission, dict) or "id" not in mission or "intent" not in mission:
        raise ValueError("mission must include 'id' and 'intent'")
    now_iso = now_iso or _iso_now()
    weights = objectives or {"speed": .35, "safety": .25, "sustainment": .15, "cost": .10, "simplicity": .15}

    # --- Seed/sanitize tasks (same as before; omitted here for brevity if you already have it) ---
    if seed_tasks:
        tasks = []
        for i,t in enumerate(seed_tasks):
            t = dict(t); t.setdefault("id", f"T{i+1}"); t.setdefault("duration_hours", 1.0)
            t.setdefault("dependencies", t.get("dependencies") or [])
            tasks.append(t)
    else:
        tasks = [
            {"id":"T1","label":"Open Primary Route","owner":"Engineer Team 2",
             "location":{"area":"Route Alpha km 0–12"},"window":{"start":now_iso},"duration_hours":4,
             "dependencies":[],"resources":{},"controls":{"comms":"VHF-1"},
             "risks":[{"desc":"Aftershock","likelihood":"M","impact":"H"}]},
            {"id":"T2","label":"Establish Forward Aid Point","owner":"Med Team 1",
             "location":{"area":"Sector A (Clinic Site)"},"window":{"start":now_iso},"duration_hours":3,
             "dependencies":["T1"],"resources":{},"controls":{"comms":"SAT-1"},
             "risks":[{"desc":"Supply delay","likelihood":"M","impact":"M"}]},
            {"id":"T3","label":"Deliver Critical Supplies","owner":"Log Cell",
             "location":{"area":"Sector A/B"},"window":{"start":now_iso},"duration_hours":6,
             "dependencies":["T1","T2"],"resources":{},"controls":{"comms":"VHF-1"},
             "risks":[{"desc":"Road closure","likelihood":"L","impact":"H"}]}
        ]

    # --- Minimal constraint screen (example) ---
    violations=[]
    for hc in (hard_constraints or []):
        desc=str(hc.get("description","")).lower()
        if "no-go" in desc or "no go" in desc:
            bad=[t["id"] for t in tasks if "no-go" in str((t.get("location") or {}).get("area","")).lower()]
            if bad: violations.append(f'Hard constraint "{hc.get("id","HC")}" breached by tasks: {", ".join(bad)}')

    # --- Build COA JSON ---
    timeline = _schedule(tasks, now_iso)
    t_times = {t["id"]: t for t in timeline}
    sync_points=[]
    if "T2" in t_times: sync_points.append({"time": t_times["T2"]["est"], "purpose": "Medical site ready", "depends_on":["T2"]})
    if "T3" in t_times: sync_points.append({"time": t_times["T3"]["eet"], "purpose": "Initial relief complete", "depends_on":["T3"]})
    decision_points=[]
    if "T1" in t_times:
        decision_points.append({"id":"DP1","when":t_times["T1"]["eet"],"trigger":"Route Alpha blocked > 3h",
                                "action":"Re-route via Bravo; reassign Engineer Team 3"})
    branches=[
        {"trigger":"Route Alpha blocked > 3h","changes":["Use Route Bravo","Reassign Team 3 to T1"]},
        {"trigger":"Airfield slot denied","changes":["Delay T3 by 2h","Pull stocks from Depot South"]}
    ]
    routes = (environment or {}).get("routes") or [
        {"name":"Route Alpha","legs":[[-72.13,18.45],[-72.08,18.50]],"mode":"ground"},
        {"name":"Route Bravo","legs":[[-72.13,18.45],[-72.04,18.52]],"mode":"ground"}
    ]
    risk_register = [
        *([{"risk": f'{th.get("type","Threat")}: {th.get("name","")}',
            "likelihood": th.get("risk_level","M"), "impact":"H",
            "mitigation":"Avoid hot areas; deconflict timing; reserve QRF"}] for th in (threats or [])),
    ]
    # Flatten nested list if threats existed
    risk_register = [item for sub in risk_register for item in (sub if isinstance(sub, list) else [sub])]
    for t in tasks:
        for r in (t.get("risks") or []):
            risk_register.append({"risk": f'{r.get("desc","Risk")} @ {t["id"]}',
                                  "likelihood": r.get("likelihood","M"), "impact": r.get("impact","M"),
                                  "mitigation":"Add branch plan; pre-position spares/fuel"})

    coa = {
        "mission_id": mission["id"],
        "commander_intent": mission["intent"],
        "assumptions": mission.get("assumptions") or ["Road X may reopen within H+12"],
        "tasks": tasks,
        "sync_points": sync_points,
        "routes": routes,
        "decision_points": decision_points,
        "branches": branches,
        "metrics": _score(tasks, weights),
        "fasdc": _fasdc(tasks, mission),
        "violations": violations,
        "risk_register": risk_register,
        "audit": {"generated_at": _iso_now(),
                  "inputs_hash": _hash({"mission":mission,"environment":environment,"assets":assets,
                                        "threats":threats,"hard_constraints":hard_constraints,
                                        "soft_constraints":soft_constraints,"objectives":objectives,
                                        "seed_tasks":seed_tasks,"now_iso":now_iso})},
        "explain": "COA opens corridor, sets medical capability, then pushes relief; branches cover route denial/slot loss."
    }

    # --- Output selection ---
    if output == "json":
        return coa
    elif output == "markdown":
        return _render_markdown_brief(coa, timeline)
    elif output == "both":
        return {"coa": coa, "brief_md": _render_markdown_brief(coa, timeline)}
    elif output == "llm_prompt":
        prompt = (
            "Write a concise 4–5 paragraph WORK ORDER (markdown) covering: "
            "1) Situation & Mission, 2) Concept of Operations, 3) Tasks & Timeline (IDs, owners, windows, duration, deps, top risks), "
            "4) Synchronization/Decision Points/Branches, 5) Sustainment/Comms/Risk highlights & Score. "
            "Use bold section headers. Keep it tight and actionable. "
            "Here is the COA JSON:\n\n```json\n" + json.dumps(coa, indent=2) + "\n```"
        )
        return {"coa": coa, "render_prompt": prompt}
    else:
        raise ValueError("output must be one of: 'json', 'markdown', 'both', 'llm_prompt'")
