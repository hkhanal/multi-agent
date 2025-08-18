from pprint import pprint
# If you imported the tool directly as a function:
# from my_tools.coa import COA_generator
# If you’re using LangChain’s @tool decorator, you can also call: COA_generator.invoke(args)

args = {
    "mission": {
        "id": "RSP-25-08",
        "intent": "Restore medical access in Sectors A and B within 48 hours with minimal civilian risk.",
        "end_state": "Two triage points operational; 24h resupply corridor established.",
        "time_available_hours": 48,
        "ccirs": ["Status of Route Alpha", "Forward fuel < 30%", "Medevac availability"],
        "assumptions": [
            "Secondary road Bravo may reopen by H+12",
            "Intermittent thunderstorms after 1800L",
            "Commercial power unavailable in Sector B for 24–48h"
        ],
    },
    "environment": {
        "ao_name": "Region X",
        "weather": "TSRA after 1800L; winds 15G25",
        "terrain": "Coastal, low-lying; two choke points on Route Alpha",
        "key_facilities": [
            {"name": "Main Hospital", "location": [-72.112, 18.505]},
            {"name": "Depot South",  "location": [-72.145, 18.462]},
            {"name": "Airstrip East","location": [-72.070, 18.520]}
        ],
        "no_go_zones": [
            {"name": "Flooded Lowland", "reason": "Impassable", "polygon": [
                [-72.120,18.490], [-72.118,18.482], [-72.110,18.481], [-72.107,18.488], [-72.120,18.490]
            ]}
        ],
        "routes": [
            {"name": "Route Alpha", "mode": "ground", "legs": [
                [-72.150,18.450], [-72.135,18.470], [-72.120,18.490], [-72.105,18.505]
            ]},
            {"name": "Route Bravo", "mode": "ground", "legs": [
                [-72.150,18.450], [-72.140,18.465], [-72.130,18.485], [-72.110,18.510]
            ]},
            {"name": "Heli Corridor 1", "mode": "air", "legs": [
                [-72.160,18.440], [-72.100,18.520]
            ]}
        ]
    },
    "assets": [
        {"id": "eng2", "label": "Engineer Team 2", "count": 1, "capabilities": ["engineer"], "comms": ["VHF-1"]},
        {"id": "med1", "label": "Medical Team 1", "count": 1, "capabilities": ["med"], "comms": ["SAT-1"]},
        {"id": "log1", "label": "Logistics Cell", "count": 1, "capabilities": ["lift"], "fuel_l": 2000},
        {"id": "rw1",  "label": "Rotary Wing A", "count": 1, "capabilities": ["medevac","sling"], "range_km": 350}
    ],
    "threats": [
        {"name": "Aftershocks", "type": "Natural", "risk_level": "M"},
        {"name": "Road washout at km 9", "type": "Terrain", "risk_level": "M"}
    ],
    "hard_constraints": [
        {"id": "HC-1", "description": "No entry into Flooded Lowland no-go polygon"},
        {"id": "HC-2", "description": "Respect air corridor altitude blocks and slot times"}
    ],
    "soft_constraints": [
        {"id": "SC-1", "description": "Minimize night driving on unlit segments", "weight": 0.2, "target": "min", "metric": "night_hours"},
        {"id": "SC-2", "description": "Prefer Bravo for heavy loads once reopened", "weight": 0.1, "target": "max", "metric": "use_bravo"}
    ],
    "objectives": {  # weights must sum ~1.0 (not strictly required; code normalizes by your values)
        "speed": 0.35, "safety": 0.25, "sustainment": 0.15, "cost": 0.10, "simplicity": 0.15
    },
    # Provide your own tasks to fully control the plan; otherwise the tool seeds a simple 3-task flow
    "seed_tasks": [
        {
            "id": "T1",
            "label": "Clear debris on Route Alpha (km 0–12)",
            "owner": "Engineer Team 2",
            "location": {"area": "Route Alpha km 0–12"},
            "window": {"start": "2025-08-17T12:30:00Z"},
            "duration_hours": 4,
            "dependencies": [],
            "resources": {"eng2": 1},
            "controls": {"safety_zones": ["SZ-3"], "comms": "VHF-1"},
            "risks": [{"desc": "Aftershock delays", "likelihood": "M", "impact": "H"}]
        },
        {
            "id": "T2",
            "label": "Establish Forward Aid Point (Sector A Clinic)",
            "owner": "Medical Team 1",
            "location": {"area": "Sector A Clinic Site"},
            "window": {"start": "2025-08-17T12:30:00Z"},
            "duration_hours": 3,
            "dependencies": ["T1"],
            "resources": {"med1": 1},
            "controls": {"comms": "SAT-1"},
            "risks": [{"desc": "Supply kit late arrival", "likelihood": "M", "impact": "M"}]
        },
        {
            "id": "T3",
            "label": "Ground convoy: Depot South → Sector A/B",
            "owner": "Logistics Cell",
            "location": {"area": "Route Alpha / Sectors A-B"},
            "window": {"start": "2025-08-17T15:30:00Z"},
            "duration_hours": 6,
            "dependencies": ["T1", "T2"],
            "resources": {"log1": 1},
            "controls": {"comms": "VHF-1"},
            "risks": [{"desc": "Route washout at km 9", "likelihood": "L", "impact": "H"}]
        },
        {
            "id": "T4",
            "label": "Medevac standby (RW)",
            "owner": "Rotary Wing A",
            "location": {"area": "Airstrip East"},
            "window": {"start": "2025-08-17T14:00:00Z"},
            "duration_hours": 8,
            "dependencies": ["T2"],
            "resources": {"rw1": 1},
            "controls": {"comms": "AIR-1"},
            "risks": [{"desc": "Afternoon CB tops/TSRA", "likelihood": "M", "impact": "M"}]
        }
    ],
    "now_iso": "2025-08-17T12:00:00Z"
}

# --- Call styles ---
# 1) If you imported it as a normal function (fallback decorator):
# result = COA_generator(**args)

# 2) If you're using LangChain's @tool (Runnable):
# result = COA_generator.invoke(args)

# 3) Some LangChain versions use .run for str input; prefer .invoke for dicts.

result = COA_generator(**args)  # adjust to your integration
pprint(result, width=110)
