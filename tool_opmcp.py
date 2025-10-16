# opord_tool.py
from __future__ import annotations
from typing import Dict, Any
from datetime import datetime
import textwrap

try:
    from langchain.tools import tool
except Exception:
    def tool(*args, **kwargs):
        def _decorator(fn): return fn
        return _decorator

from opord_models import OPORDRequest, OPORDResponse

def _fmt_dtg(dt: datetime) -> str:
    # simple ISO→DTG-ish display; replace with your DTG formatter if desired
    return dt.strftime("%d %b %Y %H%MZ")

def _h(s: str) -> str:
    return s.replace("\n", " ").strip()

def _bullet_list(items):
    return "\n".join(f"- {i}" for i in items) if items else "- N/A"

@tool("generate_opord")
def generate_opord(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a 5-paragraph OPORD (markdown) using FM 6-0 Appendix C format (Figure C-2).
    Args:
      payload: dict shaped as OPORDRequest (see opord_models.OPORDRequest)

    Returns:
      dict: {"markdown": "..."} (OPORDResponse as dict)
    """
    req = OPORDRequest.model_validate(payload)

    h = req.header
    s = req.situation
    e = req.execution
    sus = req.sustainment
    cs = req.command_signal
    at = req.attachments_refs

    # Header line per Figure C-2 structure (simplified, unclassified header)
    top = f"{h.classification}\n\n**OPORD {h.opord_number} ({h.code_name or '—'}) — {h.issuing_hq} — DTG {_fmt_dtg(h.dtg)}**\n\n{h.classification}\n"

    # 1. SITUATION
    terrain = ""
    if s.terrain_weather:
        terrain_lines = []
        if s.terrain_weather.terrain_key_points:
            terrain_lines.append("Terrain: " + "; ".join(s.terrain_weather.terrain_key_points))
        if s.terrain_weather.weather_impacts:
            terrain_lines.append("Weather: " + "; ".join(s.terrain_weather.weather_impacts))
        terrain = "\n" + "\n".join(f"- {x}" for x in terrain_lines)

    civil = ""
    if s.civil_considerations:
        civil = "\n- Civil Considerations: " + "; ".join(s.civil_considerations)

    situation_md = f"""
**1. SITUATION**

- Area of Operations: {_h(s.area_of_operations or '')}{terrain}{civil}
- Enemy Forces: {_h(s.enemy.description)}
  - Most Likely COA: {_h(s.enemy.most_likely_coa or 'N/A')}
  - Most Dangerous COA: {_h(s.enemy.most_dangerous_coa or 'N/A')}
  - NAIs: {", ".join(s.enemy.named_areas_of_interest or []) or 'N/A'}
- Friendly Forces:
  - Higher HQ Mission: {_h(s.friendly.higher_hq_mission or 'N/A')}
  - Adjacent Units: {", ".join(s.friendly.adjacent_units or []) or 'N/A'}
  - Attachments/Detachments: {", ".join(s.friendly.attachments_detachments or []) or 'N/A'}
""".strip()

    # 2. MISSION (one sentence)
    mission_md = f"""
**2. MISSION**

{_h(req.mission.sentence)}
""".strip()

    # 3. EXECUTION
    intent = e.commander_intent
    concept = e.concept

    scheme_intel = ""
    if concept.intelligence:
        i = concept.intelligence
        scheme_intel = f"""
  - **Scheme of Intelligence / Information Collection (Annex L link):**
    - Purpose: {_h(i.purpose)}
    - Priority of Effort: {_bullet_list(i.priority_effort)}
    - NAIs: {", ".join(i.named_areas_of_interest or []) or 'N/A'}
    - Collection Assets: {_bullet_list(i.collection_assets or [])}
    - Cueing/Cross-cueing: {_bullet_list(i.cueing_cross_cueing or [])}
    - Assessment Measures: {_bullet_list(i.assessment_measures or [])}
""".rstrip()

    tasks_md = "\n".join(
        f"- **{t.unit}**: {_h(t.task)}" + (f" — Purpose: {_h(t.purpose)}" if t.purpose else "") +
        (f"\n  - Coord: {_bullet_list(t.coordinating_instructions or [])}" if t.coordinating_instructions else "")
        for t in e.tasks_to_subordinate
    )

    coord = e.coordinating_instructions
    coord_md = ""
    if coord:
        coord_md = f"""
  - Coordinating Instructions:
    - CCIRs: {_bullet_list(coord.ccirs or [])}
    - Risk Reduction: {_bullet_list(coord.risk_reduction or [])}
    - ROE/Remarks: {_h(coord.roE_remarks or 'N/A')}
    - Timeline: {_bullet_list(coord.timeline or [])}
    - Sync Rules: {_bullet_list(coord.sync_rules or [])}
""".rstrip()

    exec_md = f"""
**3. EXECUTION**

a. **Commander’s Intent**
- Purpose: {_h(intent.purpose)}
- Key Tasks:
{_bullet_list(intent.key_tasks)}
- End State: {_h(intent.end_state)}

b. **Concept of Operations**
- Maneuver (Air/Surface/Land ISR): {_h(concept.maneuver)}
- Fires/Effects (if any): {_h(concept.fires or 'N/A')}
- Cyber/Space/EW: {_h(concept.cyber_space_electromagnetic or 'N/A')}
- Airspace Control Measures: {_bullet_list(concept.airspace_control_measures or [])}
- Control Measures: {_bullet_list(concept.control_measures or [])}
{scheme_intel}

c. **Tasks to Subordinate Units**
{tasks_md}

d. **Coordinating Instructions**
{coord_md if coord_md else '- N/A'}
""".strip()

    # 4. SUSTAINMENT
    sus_md = "- N/A"
    if sus:
        parts = []
        if sus.logistics: parts.append(f"- Logistics: {_h(sus.logistics)}")
        if sus.supply: parts.append(f"- Supply: {_h(sus.supply)}")
        if sus.maintenance: parts.append(f"- Maintenance: {_h(sus.maintenance)}")
        if sus.medical: parts.append(f"- Medical: {_h(sus.medical)}")
        if sus.contracting: parts.append(f"- Contracting: {_h(sus.contracting)}")
        sus_md = "\n".join(parts) if parts else "- N/A"

    sustainment_md = f"""
**4. SUSTAINMENT**

{sus_md}
""".strip()

    # 5. COMMAND & SIGNAL
    cs_md = "- N/A"
    if cs:
        parts = []
        if cs.command_posts: parts.append(f"- Command Posts: {_bullet_list(cs.command_posts)}")
        if cs.succession_of_command: parts.append(f"- Succession of Command: {_h(cs.succession_of_command)}")
        if cs.signal: parts.append(f"- Signal: {_bullet_list(cs.signal)}")
        if cs.reporting: parts.append(f"- Reporting: {_bullet_list(cs.reporting)}")
        cs_md = "\n".join(parts) if parts else "- N/A"

    cmdsig_md = f"""
**5. COMMAND AND SIGNAL**

{cs_md}
""".strip()

    # Annexes/Distribution (as per Fig C-2 tables C-2 etc.)
    annex_md = ""
    if at and (at.annexes or at.distribution):
        annex_md = "\n\n**Annexes/References:**\n" + _bullet_list(at.annexes or []) \
                   + ("\n\n**Distribution:**\n" + _bullet_list(at.distribution or []) if at.distribution else "")

    # Compose
    md = "\n\n".join([top, situation_md, mission_md, exec_md, sustainment_md, cmdsig_md]) + annex_md + \
         f"\n\n{h.classification}"

    # Return as OPORDResponse (dict)
    return OPORDResponse(markdown=textwrap.dedent(md).strip()).model_dump()
