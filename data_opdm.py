# opord_models.py
from __future__ import annotations
from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

Classification = Literal["UNCLASSIFIED", "FOUO", "CUI", "CONFIDENTIAL", "SECRET", "TOP SECRET"]
SyncWhen = Literal["est", "eet", "mid"]

class Header(BaseModel):
    classification: Classification = "UNCLASSIFIED"
    opord_number: str = Field(..., min_length=1, description="e.g., OPORD 21-01")
    code_name: Optional[str] = Field(None, description="(optional) operation code name")
    issuing_hq: str = Field(..., min_length=1, description="Issuing headquarters")
    dtg: datetime = Field(default_factory=datetime.utcnow)

class EnemySituation(BaseModel):
    description: str
    most_likely_coa: Optional[str] = None
    most_dangerous_coa: Optional[str] = None
    named_areas_of_interest: Optional[List[str]] = None

class FriendlySituation(BaseModel):
    higher_hq_mission: Optional[str] = None
    adjacent_units: Optional[List[str]] = None
    attachments_detachments: Optional[List[str]] = None

class TerrainWeather(BaseModel):
    terrain_key_points: Optional[List[str]] = None
    weather_impacts: Optional[List[str]] = None
    references: Optional[List[str]] = None  # e.g., "Annex B (Intelligence)"

class Situation(BaseModel):
    area_of_operations: Optional[str] = "Island archipelago AO"
    enemy: EnemySituation
    friendly: FriendlySituation
    terrain_weather: Optional[TerrainWeather] = None
    civil_considerations: Optional[List[str]] = None  # e.g., shipping lanes, fisheries, ports, airways

class Mission(BaseModel):
    sentence: str  # one clear task & purpose line (FM 6-0 Figure C-2)

class Intent(BaseModel):
    purpose: str
    key_tasks: List[str]
    end_state: str

class ISRScheme(BaseModel):
    purpose: str
    priority_effort: List[str]  # e.g., "Locate Red DDGs", "Assess missile-launch indications"
    named_areas_of_interest: Optional[List[str]] = None
    collection_assets: Optional[List[str]] = None  # MQ-9, P-8, surface radar, EW, SOF recon, etc.
    cueing_cross_cueing: Optional[List[str]] = None
    assessment_measures: Optional[List[str]] = None  # MOEs/MOPs

class ConceptOfOperations(BaseModel):
    maneuver: str  # narrative “how” across air/surface/land for ISR
    fires: Optional[str] = None  # if any supporting fires/DE/conflict; can be "N/A" here
    intelligence: Optional[ISRScheme] = None  # Scheme of Intelligence / Information Collection (Annex L)
    cyber_space_electromagnetic: Optional[str] = None
    airspace_control_measures: Optional[List[str]] = None
    control_measures: Optional[List[str]] = None  # phase lines, areas, corridors, MRRs, etc.

class TaskToSubordinateUnit(BaseModel):
    unit: str
    task: str
    purpose: Optional[str] = None
    coordinating_instructions: Optional[List[str]] = None

class CoordinatingInstructions(BaseModel):
    ccirs: Optional[List[str]] = None  # PIRs/FFIRs/EEFI as applicable
    risk_reduction: Optional[List[str]] = None
    roE_remarks: Optional[str] = None
    timeline: Optional[List[str]] = None  # key times (SPs, phase changes, checks)
    sync_rules: Optional[List[str]] = None  # free text (you can drive sync points via your other tool)

class Execution(BaseModel):
    commander_intent: Intent
    concept: ConceptOfOperations
    tasks_to_subordinate: List[TaskToSubordinateUnit]
    coordinating_instructions: Optional[CoordinatingInstructions] = None

class Sustainment(BaseModel):
    logistics: Optional[str] = None
    medical: Optional[str] = None
    maintenance: Optional[str] = None
    supply: Optional[str] = None
    contracting: Optional[str] = None

class CommandSignal(BaseModel):
    command_posts: Optional[List[str]] = None  # location/time of opening/closing (FM 6-0 Fig C-2)
    succession_of_command: Optional[str] = None
    signal: Optional[List[str]] = None  # primary/alt comms, data links, crypto fill windows
    reporting: Optional[List[str]] = None  # SITREPs, ISR roll-ups, SPOTREPs cadence

class AttachmentsReferences(BaseModel):
    annexes: Optional[List[str]] = None  # e.g., Annex B (Intelligence), Annex L (Information Collection), Annex R (Reports)
    distribution: Optional[List[str]] = None

class OPORDRequest(BaseModel):
    header: Header
    situation: Situation
    mission: Mission
    execution: Execution
    sustainment: Optional[Sustainment] = None
    command_signal: Optional[CommandSignal] = None
    attachments_refs: Optional[AttachmentsReferences] = None

    @model_validator(mode="after")
    def _check_core(self):
        # Ensure execution has at least one subordinate task
        if not self.execution.tasks_to_subordinate:
            raise ValueError("At least one task to a subordinate unit is required.")
        return self

class OPORDResponse(BaseModel):
    markdown: str  # rendered five-paragraph OPORD text
