"""
C2 Mission Clarifier — FINAL
===========================
Fully‑working demo that:
* Parses commander orders with OpenAI function‑calling (if key present) or
  regex fallback.
* Cross‑checks LLM output to prevent hallucinated fields (e.g. default “1 h”).
* Incrementally asks only for missing information.
* Logs every exchange (UTC) and stores the completed request.
* Includes a minimal REPL (`python c2_mission_clarifier.py`).
"""

from __future__ import annotations
import os, re, json, difflib, datetime as dt
from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Optional dependencies
# ─────────────────────────────────────────────────────────────────────────────
try:
    import dateutil.parser as du  # robust date parsing
except ModuleNotFoundError:  # pragma: no cover
    du = None  # type: ignore

try:
    from openai import OpenAI, APIError  # type: ignore
    _openai_client: Optional[OpenAI] = OpenAI()
except ModuleNotFoundError:  # pragma: no cover
    _openai_client = None

# ─────────────────────────────────────────────────────────────────────────────
# Config / constants
# ─────────────────────────────────────────────────────────────────────────────
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = (
    "You are a mission‑parsing assistant. Extract as many of the following "
    "fields as possible from the commander’s message and return them as JSON "
    "arguments to the `MissionRequest` function. Use ISO‑8601 UTC for times, "
    "integers for duration_hours, and exact enums for mission_type and priority. "
    "If a field is missing, omit it. Do NOT hallucinate values or ask follow‑up "
    "questions — the dialogue manager will handle clarification."
)

# ─────────────────────────────────────────────────────────────────────────────
# Schema & questions
# ─────────────────────────────────────────────────────────────────────────────
_ALLOWED_MISSION_TYPES = [
    "reconnaissance", "strike", "escort", "resupply",
    "evacuation", "close air support",
]
_ALLOWED_PRIORITIES = ["low", "medium", "high"]

MISSION_REQUEST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "mission_type": {"enum": _ALLOWED_MISSION_TYPES},
        "area_of_operations": {"type": "string"},
        "start_time": {"type": "string", "format": "date-time"},
        "duration_hours": {"type": "integer", "minimum": 1},
        "priority": {"enum": _ALLOWED_PRIORITIES},
    },
    "required": [
        "mission_type", "area_of_operations", "start_time",
        "duration_hours", "priority",
    ],
    "additionalProperties": False,
}

QUESTION_BANK = {
    "mission_type": "What type of mission do you need (e.g. reconnaissance, strike)?",
    "area_of_operations": "Please specify the area of operations (MGRS grid, lat/lon box, or description).",
    "start_time": "When should the mission start? (ISO date‑time, e.g. 2025‑07‑02T08:00Z)",
    "duration_hours": "How many hours should the mission last?",
    "priority": "What is the priority? (low / medium / high)",
}

from jsonschema import Draft7Validator  # type: ignore
_validator = Draft7Validator(MISSION_REQUEST_SCHEMA)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
_HISTORY_CAP = 100

def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def _log(state: Dict[str, Any], role: str, content: str) -> None:
    hist: List[Dict[str, str]] = state.setdefault("history", [])
    hist.append({"time": _utcnow(), "role": role, "content": content})
    if len(hist) > _HISTORY_CAP:
        del hist[: len(hist) - _HISTORY_CAP]

def _closest(word: Optional[str], vocab: List[str]) -> Optional[str]:
    if not word:
        return None
    match = difflib.get_close_matches(word.lower(), vocab, n=1, cutoff=0.6)
    return match[0] if match else None

# Regex patterns -------------------------------------------------------------
_COORD_RE = re.compile(r"\b(\d{1,2}[A-HJ-NP-Z]\s*[A-Z]{2}\s*\d{1,5}\s*\d{1,5})\b", re.I)
_TIME_RE = re.compile(r"\bstart(?:s|ing)?\s*([0-9]{1,2}\s+[A-Za-z]{3}\s+[0-9]{2,4}\s+[0-9]{3,4}\s*Z)\b", re.I)
_DUR_RE = re.compile(r"\b(?:dur(?:ation)?\s*)?(\d{1,3})(?:\s*h(?:ours?)?)?\b", re.I)
_PRIO_RE = re.compile(r"\bprio\s*([a-z\-]+)\b", re.I)
_TYPE_RE = re.compile(r"\b(recon(?:naissance)?|recconaissance|strike|escort|resupply|evac(?:uation)?|cas|close\s+air\s+support)\b", re.I)

_FIELD_REGEX = {
    "mission_type": _TYPE_RE,
    "area_of_operations": _COORD_RE,
    "start_time": _TIME_RE,
    "duration_hours": _DUR_RE,
    "priority": _PRIO_RE,
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. Extractor (LLM + regex fallback + cross‑check)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> Dict[str, Any]:
    """Try OpenAI function‑calling; otherwise regex. Remove any field not
    explicitly present in *text* to stop hallucinations."""

    if _openai_client and os.getenv("OPENAI_API_KEY"):
        try:
            resp = _openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                functions=[{
                    "name": "MissionRequest",
                    "description": "Populate as many fields as possible",
                    "parameters": MISSION_REQUEST_SCHEMA,
                }],
                function_call={"name": "MissionRequest"},
            )
            cand: Dict[str, Any] = json.loads(resp.choices[0].message.function_call.arguments or "{}")  # type: ignore[attr-defined]
            # Cross‑check
            for k, regex in _FIELD_REGEX.items():
                if k in cand and not regex.search(text):
                    cand.pop(k)
            return cand
        except (APIError, json.JSONDecodeError):
            pass  # fall through

    # Pure regex path --------------------------------------------------------
    out: Dict[str, Any] = {}
    if m := _TYPE_RE.search(text):
        out["mission_type"] = _closest(m.group(1), _ALLOWED_MISSION_TYPES)
    if m := _COORD_RE.search(text):
        out["area_of_operations"] = re.sub(r"\s+", " ", m.group(1).upper())
    if m := _TIME_RE.search(text):
        raw = m.group(1)
        if du:
            try:
                out["start_time"] = du.parse(raw, dayfirst=True, fuzzy=True).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                out["start_time"] = raw
        else:
            out["start_time"] = raw
    if m := _DUR_RE.search(text):
        out["duration_hours"] = int(m.group(1))
    if m := _PRIO_RE.search(text):
        out["priority"] = _closest(m.group(1), _ALLOWED_PRIORITIES)
    return out

# ─────────────────────────────────────────────────────────────────────────────
# 2. Normaliser & validator helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(req: Dict[str, Any]) -> Dict[str, Any]:
    out = req.copy()
    for k, v in list(out.items()):
        if isinstance(v, str):
            out[k] = v.strip(" ,.;")
    # fixes
    if out.get("mission_type", "").startswith("recon"):
        out["mission_type"] = "reconnaissance"
    if pr := out.get("priority"):
        out["priority"] = pr.replace("-", " ").split()[0]
    if "duration_hours" in out:
        try:
            out["duration_hours"] = int(out["duration_hours"])
        except Exception:
            out.pop("duration_hours", None)
    st = out.get("start_time")
    if st and du and isinstance(st, str):
        try:
            out["start_time"] = du.parse(st).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    return out


def _first_problem(errors) -> Optional[str]:
    for err in errors:
        if err.validator == "required":
            prop = getattr(err, "params", {}).get("property") if hasattr(err, "params") else None
            if prop:
                return prop
            m = re.search(r"'(.*?)'", err.message)
            if m:
                return m.group(1)
        elif err.schema_path and err.schema_path[-1] != "required":
            return str(err.schema_path[-1])
    return None

# ─────────────────────────────────────────────────────────────────────────────
# 3. Clarifier state machine
# ─────────────────────────────────────────────────────────────────────────────

def mission_clarifier(state: Dict[str, Any]) -> Dict[str, Any]:
    """Single‑turn update: parse, validate, ask follow‑ups, and log."""

    user_msg = state.get("raw_input", "")
    if user_msg:
        _log(state, "user", user_msg)

    draft = state.get("mission_request", {}).copy()
    if user_msg:
        draft.update(_extract_json(user_msg))
    draft = _normalise(draft)
    state["mission_request"] = draft

    errors = list(_validator.iter_errors(draft))
    if not errors:
        assistant_msg = json.dumps(draft, indent=2)
        state.update(
            completed_request=draft,
            assistant_message=assistant_msg,
            requires_user=False,
        )
        _log(state, "assistant", assistant_msg)
        return state

    missing = _first_problem(errors) or "unknown"
    if missing == state.get("last_question") and len(errors) > 1:
        missing = _first_problem(errors[1:]) or missing

    assistant_msg = QUESTION_BANK.get(missing, f"Could you provide a valid value for '{missing}'?")
    state.update(
        assistant_message=assistant_msg,
        requires_user=True,
        last_question=missing,
    )
    _log(state, "assistant", assistant_msg)
    return state

# ─────────────────────────────────────────────────────────────────────────────
# 4. REPL demo
# ─────────────────────────────────────────────────────────────────────────────

def _demo() -> None:  # pragma: no cover
    print("── C2 Mission Clarifier Demo ──")
    state: Dict[str, Any] = {
        "mission_request": {},
        "requires_user": True,
    }

    while True:
        if state.get("assistant_message"):
            print(f"Clarifier ▶ {state['assistant_message']}")
        if not state.get("requires_user"):
            print("★ Final MissionRequest JSON saved in state['completed_request']")
            break
        try:
            cmd = input("Commander ▶ ")
        except (EOFError, KeyboardInterrupt):
            print("Exiting.")
            break
        state.update(raw_input=cmd)
        state = mission_clarifier(state)


if __name__ == "__main__":
    _demo()
