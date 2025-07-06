import re, json
from typing import Dict, Any

def safe_json_merge(resp: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the first JSON object from `resp`, parse it, and merge into `state`.
    If parsing fails, stash an error message in state without raising.
    """
    # 1️⃣ Remove common code-fence wrappers (```json ... ``` or ``` ... ```)
    cleaned = re.sub(r"```(?:json)?|```", "", resp, flags=re.IGNORECASE).strip()

    # 2️⃣ Grab the first {...} with a simple greedy regex
    m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not m:
        state["error"] = "No JSON object found in LLM output."
        return state

    try:
        payload = json.loads(m.group())
    except json.JSONDecodeError as err:
        state["error"] = f"JSON decoding failed: {err}"
        return state

    # 3️⃣ Merge cleanly (later keys overwrite earlier ones)
    return {**state, **payload}