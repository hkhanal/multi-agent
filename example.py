"""
c2_mission_clarifier.py
Standalone demo – validates C2 mission requests, asks only for
missing data, and accepts single-sentence orders like:
  need recconaissance 38s dc 123 456, start 2 Jul 25 0800 Z prio high-prio dur 24
"""

from __future__ import annotations
import re, json, difflib
from datetime import datetime
from typing import Dict, Any, List

# ---------------------------------------------------------------------------
# Optional: dateutil gives very robust free-text parsing of dates.
# ---------------------------------------------------------------------------
try:
    import dateutil.parser as du  # type: ignore
except ModuleNotFoundError:  # graceful degradation if not installed
    du = None  # pyright: ignore

# ─────────────────────────────────────────────────────────────────────────────
# 1. Mission schema + canned questions
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
    "area_of_operations": (
        "Please specify the area of operations (MGRS grid, lat/lon box, or description)."
    ),
    "start_time": "When should the mission start? (ISO date-time, e.g. 2025-07-02T08:00Z)",
    "duration_hours": "How many hours should the mission last?",
    "priority": "What is the priority? (low / medium / high)",
}

# JSON-Schema validator -------------------------------------------------------
from jsonschema import Draft7Validator  # type: ignore
_validator = Draft7Validator(MISSION_REQUEST_SCHEMA)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Helper utilities
# ─────────────────────────────────────────────────────────────────────────────

def _closest(word: str | None, vocab: List[str]) -> str | None:
    """Return the closest entry from *vocab* using difflib."""
    if not word:
        return None
    matches = difflib.get_close_matches(word.lower(), vocab, n=1, cutoff=0.6)
    return matches[0] if matches else None

# Regex patterns --------------------------------------------------------------
_COORD_RE = re.compile(r"\b(\d{1,2}[A-HJ-NP-Z]\s*[A-Z]{2}\s*\d{1,5}\s*\d{1,5})\b", re.I)
_TIME_RE = re.compile(
    r"\bstart(?:s|ing)?\s*([0-9]{1,2}\s+[A-Za-z]{3}\s+[0-9]{2,4}\s+[0-9]{3,4}\s*Z)\b",
    re.I,
)
_DUR_RE = re.compile(r"\bdur(?:ation)?\s*(\d{1,3})\b", re.I)
_PRIO_RE = re.compile(r"\bprio\s*([a-z\-]+)\b", re.I)
_TYPE_RE = re.compile(
    r"\b(recon(?:naissance)?|strike|escort|resupply|evac(?:uation)?|cas|close\s+air\s+support)\b",
    re.I,
)


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract mission fields from a single commander sentence."""
    out: Dict[str, Any] = {}

    if m := _TYPE_RE.search(text):
        out["mission_type"] = _closest(m.group(1), _ALLOWED_MISSION_TYPES)

    if m := _COORD_RE.search(text):
        out["area_of_operations"] = re.sub(r"\s+", " ", m.group(1).upper())

    if m := _TIME_RE.search(text):
        ts = m.group(1)
        if du is not None:
            try:
                dt = du.parse(ts, dayfirst=True, fuzzy=True)
                out["start_time"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, OverflowError):
                pass
        else:
            out["start_time"] = ts

    if m := _DUR_RE.search(text):
        out["duration_hours"] = int(m.group(1))

    if m := _PRIO_RE.search(text):
        out["priority"] = _closest(m.group(1), _ALLOWED_PRIORITIES)

    return out


# Normalisation --------------------------------------------------------------

def normalize_request(req: Dict[str, Any]) -> Dict[str, Any]:
    out = req.copy()

    # Strip whitespace and punctuation
    for k, v in list(out.items()):
        if isinstance(v, str):
            out[k] = v.strip(" ,.;")

    # Fix common misspelling
    if out.get("mission_type", "").startswith("recon"):
        out["mission_type"] = "reconnaissance"

    # Normalise priority variants ("high-prio" → "high")
    if pr := out.get("priority"):
        out["priority"] = pr.replace("-", " ").split()[0]

    # Ensure duration is an int
    if "duration_hours" in out:
        try:
            out["duration_hours"] = int(out["duration_hours"])
        except (ValueError, TypeError):
            out.pop("duration_hours", None)

    # Standardise ISO date-time when possible
    st = out.get("start_time")
    if st and du is not None and isinstance(st, str):
        try:
            out["start_time"] = du.parse(st).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

    return out


# JSON‑Schema helpers ---------------------------------------------------------

def _first_problem_field(errors) -> str | None:
    """Return the *property name* that the first validation error refers to."""
    for err in errors:
        # Missing required property → pull the property name from the message
        if err.validator == "required":
            # jsonschema puts the name in err.message and in params
            if hasattr(err, "params") and "property" in err.params:
                return err.params["property"]
            m = re.search(r"'(.*?)' is a required property", err.message)
            if m:
                return m.group(1)
            continue

        # For other validators, the last item in schema_path is the field
        if err.schema_path:
            tail = err.schema_path[-1]
            if tail != "required":
                return tail
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Clarifier state machine
# ─────────────────────────────────────────────────────────────────────────────

def mission_clarifier(state: Dict[str, Any]) -> Dict[str, Any]:
    """Update the clarifier state with the user's latest message."""

    user_msg = state.get("raw_input", "")
    draft = state.get("mission_request", {}).copy()

    # a. Update draft with anything we can parse
    if user_msg:
        draft.update(_extract_json(user_msg))
    draft = normalize_request(draft)
    state["mission_request"] = draft

    # b. Validate against schema
    errors = list(_validator.iter_errors(draft))
    if not errors:
        state.update(
            assistant_message=json.dumps(draft, indent=2),
            requires_user=False,
        )
        return state  # ✅ done

    # c. Ask for the *first* missing or invalid field
    missing = _first_problem_field(errors) or "unknown"
    if missing == state.get("last_question") and len(errors) > 1:
        missing = _first_problem_field(errors[1:]) or missing

    state.update(
        assistant_message=QUESTION_BANK.get(
            missing, f"Could you provide a valid value for '{missing}'?"
        ),
        requires_user=True,
        last_question=missing,
    )
    return state


# ─────────────────────────────────────────────────────────────────────────────
# 4. Minimal REPL demo
# ─────────────────────────────────────────────────────────────────────────────

def _demo() -> None:  # pragma: no cover
    state: Dict[str, Any] = {"mission_request": {}, "requires_user": True}
    print("── C2 Mission Clarifier Demo ──")
    while True:
        if state.get("assistant_message"):
            print(f"Clarifier ▶ {state['assistant_message']}")
        if not state.get("requires_user"):
            print("★ Final MissionRequest JSON:")
            print(state["assistant_message"])
            break
        cmd = input("Commander ▶ ")
        state.update(raw_input=cmd)
        state = mission_clarifier(state)


if __name__ == "__main__":
    _demo()

