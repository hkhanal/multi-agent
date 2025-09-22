# JSON schemas & examples — Receipt of Mission tools (Extractor, Time Allocator, WARNO, Staff Checklist)

# 1) Tool 1 — Order Ingest & Extractor

##**Purpose:** ingest a raw WARNORD/OPORD (text or OCR from PDF) and produce a normalized `PlanningPacket` partial (the receipt-of-mission fields needed to begin MDMP).

### Input (to extractor)

input_tool1_schema = {
  "type": "object",
  "required": ["source_id","raw_text","format","ingest_meta"],
  "properties": {
    "source_id": {"type":"string", "description":"unique id for traceability (e.g., file name/hash)"},
    "raw_text": {"type":"string", "description":"full textual content of WARNORD/OPORD (OCR or pasted text)"},
    "format": {"type":"string","enum":["warnord","opord","fragord","email","pdf_text"], "default":"warnord"},
    "ingest_meta": {
      "type":"object",
      "properties":{
        "received_time_utc":{"type":"string","format":"date-time"},
        "sender":{"type":"string"},
        "classification":{"type":"string"}
      }
    }
  }
}

output_tool1_schema = {
  "type":"object",
  "required":["planning_id","mission_context","ingest_meta"],
  "properties":{
    "planning_id":{"type":"string"},
    "ingest_meta":{
      "type":"object",
      "properties":{
        "source_id":{"type":"string"},
        "received_time_utc":{"type":"string","format":"date-time"},
        "extractor_version":{"type":"string"}
      }
    },
    "mission_context":{
      "type":"object",
      "required":["higher_hq_mission","higher_hq_intent","specified_tasks","approx_time_available"],
      "properties":{
        "higher_hq_mission":{"type":"string"},
        "higher_hq_intent":{"type":"string"},
        "specified_tasks":{"type":"array","items":{"type":"string"}},
        "implied_tasks":{"type":"array","items":{"type":"string"}},
        "constraints":{"type":"array","items":{"type":"string"}},
        "restraints":{"type":"array","items":{"type":"string"}},
        "assumptions":{"type":"array","items":{"type":"string"}},
        "ccir":{
          "type":"object",
          "properties":{
            "pir":{"type":"array","items":{"type":"string"}},
            "ffir":{"type":"array","items":{"type":"string"}},
            "eefi":{"type":"array","items":{"type":"string"}}
          }
        },
        "approx_time_available":{"type":"string", "description":"time until H or execution deadline, e.g. '48h' or '2025-09-25T08:00:00Z'"},
        "echelon":{"type":"string", "description":"receiving HQ echelon (company/bn/bde/div)"},
        "operational_type":{"type":"string","enum":["offense","defense","stability","humanitarian","other"]}
      }
    }
  }
}


example_output_tool1 = {
  "planning_id": "plan-20250925-0001",
  "ingest_meta": {
    "source_id": "warnord_redacted_20250925.txt",
    "received_time_utc": "2025-09-25T02:30:00Z",
    "extractor_version": "v0.1"
  },
  "mission_context": {
    "higher_hq_mission": "Seize OBJ RED to secure crossing over River X NLT 2025-09-26 1200Z.",
    "higher_hq_intent": "Control crossing to enable follow-on brigade movement and prevent enemy counterattacks.",
    "specified_tasks": ["Secure assembly area by H-24", "establish route security on MSR-1"],
    "implied_tasks": ["recon to identify crossing sites", "prepare bridge or escort engineers"],
    "constraints": ["No offensive fires within SECTOR ALPHA prior to H+2 (fire control)"],
    "restraints": ["Do not strike civil infrastructure unless hostile forces are present"],
    "assumptions": ["Bridges over River X are intact unless reported otherwise"],
    "ccir": {
      "pir": ["Enemy armor concentration location north of OBJ RED"],
      "ffir": ["Status of bridging assets"],
      "eefi": ["Exact location of division logistics hub"]
    },
    "approx_time_available": "34h",
    "echelon": "battalion",
    "operational_type": "offense"
  }
}




# 2) Tool 2 — Time Allocator (1/3–2/3 rule + milestones)


### Input

input_tool2_schema = {
  "type":"object",
  "required":["planning_id","approx_time_available","commander_guidance"],
  "properties":{
    "planning_id":{"type":"string"},
    "approx_time_available":{"type":"string", "description":"duration or absolute deadline"},
    "commander_guidance":{"type":"object",
      "properties":{
        "desired_h_time": {"type":"string","description":"H time in ISO format, optional"},
        "time_allocation_ratio":{"type":"number","minimum":0,"maximum":1, "default":0.333}
      }
    },
    "constraints": {"type":"array","items":{"type":"string"}}
  }
}
### Output (timeline)

output_tool2_schema = {
  "type":"object",
  "required":["planning_id","total_time_seconds","hq_planning_seconds","subordinate_planning_seconds","milestones"],
  "properties":{
    "planning_id":{"type":"string"},
    "total_time_seconds":{"type":"integer"},
    "hq_planning_seconds":{"type":"integer"},
    "subordinate_planning_seconds":{"type":"integer"},
    "milestones":{
      "type":"array",
      "items":{
        "type":"object",
        "required":["name","deadline_utc","notes"],
        "properties":{
          "name":{"type":"string"},
          "deadline_utc":{"type":"string","format":"date-time"},
          "notes":{"type":"string"}
        }
      }
    },
    "allocation_notes":{"type":"string"}
  }
}

#### Example output

example_output_tool2 = {
  "planning_id":"plan-20250925-0001",
  "total_time_seconds":122400,
  "hq_planning_seconds":40800,
  "subordinate_planning_seconds":81600,
  "milestones":[
    {"name":"HQ: Complete Mission Analysis & WARNO", "deadline_utc":"2025-09-25T14:30:00Z", "notes":"HQ uses 1/3 time for MDMP; issue WARNORD ASAP"},
    {"name":"HQ: COA development complete", "deadline_utc":"2025-09-25T19:30:00Z", "notes":"COA drafts for staff review"},
    {"name":"Subordinates: OPORD production & rehearsal window start", "deadline_utc":"2025-09-25T20:00:00Z", "notes":"2/3 time allocated to subordinate planning"}
  ],
  "allocation_notes":"1/3-2/3 rule applied to total_time 34h; commander can override ratio"
}

# 3) Tool 3 — Initial WARNO Draft Generator


input_tool3_schema = {
  "type":"object",
  "required":["planning_id","mission_context","timeline"],
  "properties":{
    "planning_id":{"type":"string"},
    "mission_context":{"$ref":"#/definitions/mission_context_snippet"},
    "timeline":{"$ref":"#/definitions/timeline_snippet"},
    "audience":{"type":"array","items":{"type":"string"},"description":"units to receive the WARNORD"},
    "author_meta":{"type":"object","properties":{"drafted_by":{"type":"string"},"draft_time":{"type":"string","format":"date-time"}}}
  },
  "definitions":{
    "mission_context_snippet":{
      "type":"object",
      "properties":{
        "higher_hq_mission":{"type":"string"},
        "higher_hq_intent":{"type":"string"},
        "specified_tasks":{"type":"array","items":{"type":"string"}},
        "constraints":{"type":"array","items":{"type":"string"}},
        "ccir":{"type":"object"}
      }
    },
    "timeline_snippet":{
      "type":"object",
      "properties":{
        "hq_planning_deadline":{"type":"string","format":"date-time"},
        "h_time":{"type":"string","format":"date-time"}
      }
    }
  }
}
### Output (WARNO)

output_tool3_schema = {
  "type":"object",
  "required":["worno_id","planning_id","warno_text","fields","requires_command_review"],
  "properties":{
    "worno_id":{"type":"string"},
    "planning_id":{"type":"string"},
    "warno_text":{"type":"string"},
    "fields":{
      "type":"object",
      "properties":{
        "situation":{"type":"string"},
        "mission":{"type":"string"},
        "general_instructions":{"type":"string"},
        "special_instructions":{"type":"string"},
        "ccir_highlights":{"type":"array","items":{"type":"string"}}
      }
    },
    "requires_command_review":{"type":"boolean"}
  }
}

example_output_tool3 = {
  "worno_id":"warn-20250925-0001",
  "planning_id":"plan-20250925-0001",
  "warno_text":"WARNO: 1. Situation: Enemy armored screen N of River X. 2. Mission: 2nd Bn seizes OBJ RED NLT 26 Sep 1200Z. 3. Instructions: Prepare bridging, recon of crossing sites, establish MSR security. ...",
  "fields":{
    "situation":"Enemy forces defending river line; limited ISR in sector.",
    "mission":"Seize OBJ RED to secure crossing NLT 26 Sep 1200Z.",
    "general_instructions":"H-hour planned 26 Sep 1200Z. Units prepare for river crossing; prioritize bridging and engineer assets.",
    "special_instructions":"No fires within SECTOR ALPHA before H+2. Report any changes to commander immediately.",
    "ccir_highlights":["PIR: enemy armor concentration location north of OBJ RED", "FFIR: bridging company status"]
  },
  "requires_command_review": True


}


# 4) Tool 4 — Staff Readiness Checklist Builder
input_tool4_schema = {
  "type":"object",
  "required":["planning_id","mission_context"],
  "properties":{
    "planning_id":{"type":"string"},
    "mission_context":{"type":"object"},
    "available_assets":{"type":"object","properties":{"engineer_assets":{"type":"array","items":{"type":"string"}},"logistics_asset_status":{"type":"string"}}}
  }
}

### Output (Checklist package)

output_tool4_schema = {
  "type":"object",
  "required":["planning_id","generated_at_utc","checklists"],
  "properties":{
    "planning_id":{"type":"string"},
    "generated_at_utc":{"type":"string","format":"date-time"},
    "checklists":{
      "type":"array",
      "items":{
        "type":"object",
        "required":["section","items"],
        "properties":{
          "section":{"type":"string"},
          "priority":{"type":"integer","minimum":1,"maximum":5},
          "items":{"type":"array","items":{"type":"object","properties":{"task":"string","notes":"string","done":"boolean"}}}
        }
      }
    },
    "notes":{"type":"string"}
  }
}

#### Example output

example_output_tool4 = {
  "planning_id":"plan-20250925-0001",
  "generated_at_utc":"2025-09-25T02:45:00Z",
  "checklists":[
    {"section":"S2 (Intelligence)","priority":1,"items":[
      {"task":"Produce initial SITEMP and MLCOA/MDCOA sketch","notes":"Use latest ISR; if none, mark NAIs for collection","done":false},
      {"task":"Refine PIRs into SIRs and indicate collection assets","notes":"Coordinate with collection manager","done":false}
    ]},
    {"section":"S3 (Operations)","priority":1,"items":[
      {"task":"Prepare COA development meeting slot & map overlays","notes":"Reserve map room and whiteboards","done":false},
      {"task":"Confirm availability of engineer bridging assets","notes":"Check with S4","done":false}
    ]},
    {"section":"S4 (Logistics)","priority":2,"items":[
      {"task":"Confirm fuel and ammo levels for main effort units","notes":"Report estimate in 2 hours","done":false}
    ]}
  ],
  "notes":"Prioritize S2/S3/S4 actions for next 4 hours."
}
