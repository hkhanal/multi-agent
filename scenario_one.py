from opord_tool import generate_opord

payload = {
  "header": {
    "classification": "UNCLASSIFIED",
    "opord_number": "25-ISLAND-ISR",
    "code_name": "SEAHAWK",
    "issuing_hq": "Blue JTF (Island AO)"
  },
  "situation": {
    "area_of_operations": "Island archipelago, EEZ approaches, and adjacent air/sea lanes",
    "enemy": {
      "description": "Red Navy DDGs operating in a screen around the eastern straits; suspected strike loadout; EMCON varying; UAV counter-ISR observed.",
      "most_likely_coa": "Maintain patrols in the straits, periodic emissions for nav/air ops, screen logistics.",
      "most_dangerous_coa": "Coordinated salvo on Blue ports/airfields; aggressive counter-ISR.",
      "named_areas_of_interest": ["NAI-1 Eastern Strait", "NAI-2 Outer Shelf", "NAI-3 Northern Approach"]
    },
    "friendly": {
      "higher_hq_mission": "CJTF secures the archipelago and deters naval strike.",
      "adjacent_units": ["Blue Air Wing", "Blue Surface Group", "Island Defense Bde"],
      "attachments_detachments": ["SOF Recce Team (1x)", "P-8 det", "MQ-9 det", "Coastal Radar Tp"]
    },
    "terrain_weather": {
      "terrain_key_points": ["Deep-water straits", "Choke points near reefs", "Limited land ISR vantage"],
      "weather_impacts": ["Sea state 3–4 evenings", "Cloud bases 1–2k ft AM, improving PM"],
      "references": ["Annex B (Intelligence)", "Annex L (Information Collection)"]
    },
    "civil_considerations": ["Commercial shipping lane Bravo", "Ferry routes", "Fishing zones"]
  },
  "mission": {
    "sentence": "Blue JTF executes integrated ISR across air, surface, and land to locate hostile Red DDGs and assess missile-launch operations in the Island AO NLT D+2 to enable deterrence options."
  },
  "execution": {
    "commander_intent": {
      "purpose": "Generate a time-sensitive targeting-quality picture of Red DDG locations/intent.",
      "key_tasks": [
        "Detect, fix, and maintain track on DDGs in NAIs",
        "Identify missile-launch indications and EMCON shifts",
        "Fuse air/surface/land sensors; cross-cue within 5 minutes",
        "Report CCIRs immediately; provide hourly ISR roll-ups"
      ],
      "end_state": "Red DDGs located with confidence ≥0.8; launch indications assessed; CJTF holds options."
    },
    "concept": {
      "maneuver": "Air (P-8/MQ-9) wide-area search; Surface (patrol craft/coastal radar) fixation and identification; Land SOF recce and EW for confirmation; cross-cue among domains; maintain covert posture until directed.",
      "fires": "No deliberate fires; defensive ROE; DECONFLICTION with surface patrols.",
      "intelligence": {
        "purpose": "Prioritize detection/fix of DDGs and confirm missile-launch preparations.",
        "priority_effort": ["Locate DDGs", "Assess VLS deck activity", "Monitor EMCON transitions"],
        "named_areas_of_interest": ["NAI-1 Eastern Strait", "NAI-2 Outer Shelf"],
        "collection_assets": ["P-8 (ISAR/ESM)", "MQ-9 (EO/IR/SAR)", "Coastal Radar", "SOF Shore Recce", "EW team"],
        "cueing_cross_cueing": ["Coastal Radar cues P-8 ISAR", "P-8 ESM cues MQ-9 SAR", "SOF recce confirms visually"],
        "assessment_measures": ["Track continuity ≥ 80%", "ID confidence ≥ 0.8", "Cross-cue latency ≤ 5 min"]
      },
      "cyber_space_electromagnetic": "Passive ESM collection; maintain OPSEC; respond to jamming per Annex S (if tasked).",
      "airspace_control_measures": ["MRR-1 Coastal", "ROZ-ISR Alpha/B bravo (MQ-9)", "ATC coordination w/ Wing"],
      "control_measures": ["PL BLUE-1 (shoreline)", "ISR BOXES A/B/C", "No-fly over ferries"]
    },
    "tasks_to_subordinate": [
      {"unit": "Blue Air Wing (P-8/MQ-9)", "task": "Search NAIs; maintain tracks; cross-cue; push ISR roll-ups hourly.", "purpose": "Wide-area detection and fix."},
      {"unit": "Blue Surface Group", "task": "Patrol straits; fix/ID radar contacts; relay to Air/Land; maintain emission control.", "purpose": "Surface fixation & positive ID."},
      {"unit": "SOF Recce Team", "task": "Shore-based observation on NAI-1/3; confirm visual ID; report launch indicators.", "purpose": "Close confirmation."},
      {"unit": "Island Defense Bde (EW/Radar)", "task": "Operate coastal radar/EW; generate alerts; cue P-8/MQ-9.", "purpose": "Persistent domain awareness."}
    ],
    "coordinating_instructions": {
      "ccirs": ["PIR-1: Confirmed DDG location; PIR-2: Missile-launch indications; FFIR: Sensor degradation >20%"],
      "risk_reduction": ["Avoid fratricide with ferries/shipping via AIS correlation", "EMCON policies per Annex C"],
      "roE_remarks": "Defensive ROE; no engagement authorized without CJTF release.",
      "timeline": ["H+0 task org ready", "H+2 first NAI sweep", "H+6 consolidated ISR picture", "Every 60 min: roll-up"],
      "sync_rules": ["Convoy/Surface patrol step-off after Air on-station; Phase II when ≥2 DDGs fixed"]
    }
  },
  "sustainment": {
    "logistics": "P-8/MQ-9 fuel/crew cycles via Island Airbase; surface craft refuel at Pier East.",
    "supply": "Batteries/sensor spares at FOB North; JP-8 allotment 60k liters D+0–D+2.",
    "maintenance": "On-call avionics; prop maintenance window 0200–0500L.",
    "medical": "Role 1 at airbase; MEDEVAC via RW standby.",
    "contracting": "Port services MOU; fuel contract #A12-445."
  },
    "mission": {
        "id": "ISL-ISR-01",
        "intent": "Execute integrated ISR across sea, air, and land to locate hostile Red Navy DDGs and assess missile-launch operations within 24 hours.",
        "end_state": "DDG locations fixed, launch readiness assessed, and continuous ISR track established for targeting/decision.",
        "time_available_hours": 24,
        "ccirs": [
            "Positive ID (PID) of any Red DDG within 200 nm of Island X",
            "Indications of VLS hatch activity or pre-launch EMCON changes",
            "SAM/AAA emissions affecting ISR flight paths"
        ],
        "assumptions": [
            "Civil ATC corridors remain open for deconfliction",
            "Coastal radar sites have power and SAT backhaul",
            "Red surface action group (SAG) operates in 120–180 nm arc NE of Island X"
        ]
    },
    "environment": {
        "ao_name": "Island X Archipelago",
        "weather": "Broken 25–30kft; surface winds 12–18kts ESE; sea state 3–4.",
        "terrain": "Volcanic island chain with 600–900m peaks; cluttered littoral AIS picture.",
        "key_facilities": [
            {"name": "Blue AFB (Runway 09/27)", "location": [139.450, 15.210]},
            {"name": "Coastal Radar Site North", "location": [139.520, 15.360]},
            {"name": "Harbor East (Patrol Boats)", "location": [139.610, 15.170]}
        ],
        "no_go_zones": [
            {"name": "Red AD Bubble (SAM MEZ) – Sector NE", "reason": "High-risk SAM", "polygon": [
                [140.10,15.70],[140.30,15.50],[140.10,15.30],[139.90,15.50],[140.10,15.70]
            ]}
        ],
        "routes": [
            # Air ISR corridor & marshal
            {"name": "Air ISR Corridor A", "mode": "air", "legs": [[139.40,15.20],[139.90,15.50],[140.00,15.20]]},
            {"name": "Air Marshal Box Bravo", "mode": "air", "legs": [[139.50,15.35],[139.70,15.35],[139.70,15.15],[139.50,15.15]]},
            # Surface picket line
            {"name": "Surface Picket Line North", "mode": "sea", "legs": [[139.65,15.25],[139.85,15.35],[140.05,15.45]]},
            # Land coastal radar patrol road
            {"name": "Coastal Road North", "mode": "ground", "legs": [[139.48,15.34],[139.55,15.36],[139.60,15.37]]}
        ]
    },
    "assets": [
        {"id": "P8A",  "label": "P-8A Poseidon",   "count": 1, "speed_kph": 800, "range_km": 2200, "comms": ["SAT-1","UHF-1"], "capabilities": ["maritime-ISR","ESM","AIS"]},
        {"id": "MQ9",  "label": "MQ-9 (EO/IR/SAR)", "count": 2, "speed_kph": 300, "range_km": 1500, "comms": ["SAT-1"], "capabilities": ["EOIR","SAR","GMTI"]},
        {"id": "PB",   "label": "Patrol Boats",     "count": 3, "speed_kph": 65,  "range_km": 300,  "comms": ["VHF-1"], "capabilities": ["surface-ISR","ESM"]},
        {"id": "CRN",  "label": "Coastal Radar North Teams", "count": 2, "comms": ["LAN-1","SAT-1"], "capabilities": ["coastal-radar","ESM"]},
        {"id": "EW1",  "label": "EW/ESM Van",       "count": 1, "comms": ["SAT-1"], "capabilities": ["ESM","SIGINT"]}
    ],
    "threats": [
        {"name": "Red DDG SAG (2–3 units)", "type": "Surface Combatants", "risk_level": "M"},
        {"name": "Red Long-range SAM (NE sector)", "type": "Air Defense", "risk_level": "H"},
        {"name": "GPS jamming bursts", "type": "EW", "risk_level": "M"}
    ],
    "hard_constraints": [
        {"id": "HC-1", "description": "No penetration of Red SAM MEZ without approval"},
        {"id": "HC-2", "description": "Deconflict with civil ATC corridors and reserved airspace"},
        {"id": "HC-3", "description": "Respect territorial waters of neutral states"}
    ],
    "soft_constraints": [
        {"id": "SC-1", "description": "Maximize on-station persistence over NE sector", "weight": 0.2, "target": "max", "metric": "on_station_hours"},
        {"id": "SC-2", "description": "Minimize EM signature near MEZ", "weight": 0.15, "target": "min", "metric": "emissions_near_mez"}
    ],
    "objectives": { "speed": 0.30, "safety": 0.30, "sustainment": 0.15, "cost": 0.10, "simplicity": 0.15 },

    # Tasks: phased, multi-domain ISR (air–sea–land), aligned to find/fix track on DDGs
    "seed_tasks": [
        {
            "id": "T1",
            "label": "Spin-up Coastal Radar & EW Sites",
            "owner": "CRN + EW1",
            "location": {"area": "Island X North Ridge / EW Site"},
            "window": {"start": "2025-10-16T14:00:00Z"},
            "duration_hours": 2.0,
            "dependencies": [],
            "resources": {"CRN": 2, "EW1": 1},
            "controls": {"comms": "SAT-1"},
            "risks": [{"desc": "Power instability", "likelihood": "M", "impact": "M"}]
        },
        {
            "id": "T2",
            "label": "Launch P-8A Maritime ISR (AIS/ESM/SAR) to NE sector",
            "owner": "P8A Crew",
            "location": {"area": "Air ISR Corridor A / Marshal Box Bravo"},
            "window": {"start": "2025-10-16T15:00:00Z"},
            "duration_hours": 6.0,
            "dependencies": ["T1"],
            "resources": {"P8A": 1},
            "controls": {"comms": "SAT-1"},
            "risks": [{"desc": "SAM threat in MEZ edge", "likelihood": "M", "impact": "H"}]
        },
        {
            "id": "T3",
            "label": "Stage MQ-9 #1 on NE box (EO/IR/SAR) – persistence",
            "owner": "MQ9 Det 1",
            "location": {"area": "Air ISR Corridor A"},
            "window": {"start": "2025-10-16T15:30:00Z"},
            "duration_hours": 8.0,
            "dependencies": ["T1"],
            "resources": {"MQ9": 1},
            "controls": {"comms": "SAT-1"},
            "risks": [{"desc": "GPS jamming bursts", "likelihood": "M", "impact": "M"}]
        },
        {
            "id": "T4",
            "label": "Surface picket line deploy (ESM/visual) along northern arc",
            "owner": "Patrol Boat Flotilla",
            "location": {"area": "Surface Picket Line North"},
            "window": {"start": "2025-10-16T15:00:00Z"},
            "duration_hours": 7.0,
            "dependencies": ["T1"],
            "resources": {"PB": 3},
            "controls": {"comms": "VHF-1"},
            "risks": [{"desc": "Sea state 4 slows transit", "likelihood": "M", "impact": "L"}]
        },
        {
            "id": "T5",
            "label": "Handoff tracks to MQ-9 #2 for persistent fix/ID",
            "owner": "MQ9 Det 1",
            "location": {"area": "NE Sector Box"},
            "window": {"start": "2025-10-16T18:00:00Z"},
            "duration_hours": 8.0,
            "dependencies": ["T2","T3","T4"],
            "resources": {"MQ9": 1},
            "controls": {"comms": "SAT-1"},
            "risks": [{"desc": "Cloud tops obscure EO", "likelihood": "L", "impact": "M"}]
        },
        {
            "id": "T6",
            "label": "Multi-INT correlation & missile-launch readiness assessment",
            "owner": "ISR Cell (All-Source)",
            "location": {"area": "Blue AFB – ISR Cell"},
            "window": {"start": "2025-10-16T20:00:00Z"},
            "duration_hours": 3.0,
            "dependencies": ["T5"],
            "resources": {},
            "controls": {"comms": "LAN-1"},
            "risks": [{"desc": "Data latency in SAT backhaul", "likelihood": "M", "impact": "M"}]
        }
    ],

    # Declarative sync points tied to tasks/timeline
    "sync_rules": [
        {"purpose": "ISR Net Up (All Sensors)", "on": ["T1"], "when": "eet"},
        {"purpose": "Air-Sea-Land Track Fusion Start", "on": ["T2","T3","T4"], "when": "est"},
        {"purpose": "Persistent Fix/ID in NE Sector", "on": ["T5"], "when": "est"},
        {"purpose": "Launch Readiness Assessment", "on": ["T6"], "when": "eet"}
    ],

    # Optional: anchor time
    "now_iso": "2025-10-16T13:45:00Z",

    # What to get back
    "output": "both"  # returns {"coa": <json>, "brief_md": <markdown>}
}
