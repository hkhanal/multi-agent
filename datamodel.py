# pydantic_models_coa.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator

# ---------- Small enums / literals ----------

RiskLevel = Literal["L", "M", "H"]
RouteMode = Literal["ground", "air", "sea"]
TargetSense = Literal["min", "max"]

# ---------- Primitive types with validation ----------

class LatLng(BaseModel):
    """Geo coordinate as [lon, lat] with validation."""
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)

    @classmethod
    def from_pair(cls, pair: Tuple[float, float] | List[float]) -> "LatLng":
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("LatLng must be a 2-element [lon, lat] pair")
        return cls(lon=float(pair[0]), lat=float(pair[1]))

class TimeWindow(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None

    @model_validator(mode="after")
    def _validate_bounds(self):
        if self.start and self.end and self.end <= self.start:
            raise ValueError("TimeWindow.end must be after start")
        return self

# ---------- Mission / environment ----------

class Mission(BaseModel):
    id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    end_state: Optional[str] = None
    time_available_hours: Optional[float] = Field(None, gt=0)
    ccirs: Optional[List[str]] = None
    assumptions: Optional[List[str]] = None

class Facility(BaseModel):
    name: str
    location: Optional[LatLng] = None

    @field_validator("location", mode="before")
    @classmethod
    def _coerce_latlng(cls, v):
        if v is None or isinstance(v, LatLng):
            return v
        return LatLng.from_pair(v)

class NoGoZone(BaseModel):
    name: str
    reason: Optional[str] = None
    polygon: Optional[List[LatLng]] = None

    @field_validator("polygon", mode="before")
    @classmethod
    def _coerce_poly(cls, v):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("polygon must be a list of [lon, lat]")
        return [LatLng.from_pair(p) if not isinstance(p, LatLng) else p for p in v]

    @model_validator(mode="after")
    def _validate_poly(self):
        if self.polygon is not None and len(self.polygon) < 3:
            raise ValueError("polygon must have at least 3 points (triangle or more)")
        return self

class Route(BaseModel):
    name: str
    legs: List[LatLng] = Field(min_length=2)
    mode: RouteMode = "ground"

    @field_validator("legs", mode="before")
    @classmethod
    def _coerce_legs(cls, v):
        if not isinstance(v, list):
            raise ValueError("legs must be a list of [lon, lat]")
        return [LatLng.from_pair(p) if not isinstance(p, LatLng) else p for p in v]

class Environment(BaseModel):
    ao_name: Optional[str] = None
    weather: Optional[str] = None
    terrain: Optional[str] = None
    key_facilities: Optional[List[Facility]] = None
    no_go_zones: Optional[List[NoGoZone]] = None
    routes: Optional[List[Route]] = None

# ---------- Assets / threats / constraints ----------

class Asset(BaseModel):
    id: str
    label: str
    count: int = Field(ge=1)
    speed_kph: Optional[float] = Field(None, gt=0)
    range_km: Optional[float] = Field(None, gt=0)
    fuel_l: Optional[float] = Field(None, ge=0)
    burn_l_per_km: Optional[float] = Field(None, ge=0)
    comms: Optional[List[str]] = None
    capabilities: Optional[List[str]] = None

class Threat(BaseModel):
    name: str
    type: Optional[str] = None
    risk_level: RiskLevel = "M"
    areas: Optional[List[str]] = None

class HardConstraint(BaseModel):
    id: str
    description: str

class SoftConstraint(BaseModel):
    id: str
    description: str
    weight: float = Field(ge=0, le=1)
    target: TargetSense
    metric: str

class ObjectiveWeights(BaseModel):
    speed: float = Field(ge=0, le=1)
    safety: float = Field(ge=0, le=1)
    sustainment: float = Field(ge=0, le=1)
    cost: float = Field(ge=0, le=1)
    simplicity: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _sum_to_one(self):
        s = self.speed + self.safety + self.sustainment + self.cost + self.simplicity
        if not (0.95 <= s <= 1.05):
            raise ValueError(f"Objective weights should sum to ~1.0 (0.95–1.05 allowed). Current sum={s:.3f}")
        return self

# ---------- Tasks & supporting ----------

class RiskItem(BaseModel):
    desc: str
    likelihood: RiskLevel = "M"
    impact: RiskLevel = "M"

class Controls(BaseModel):
    safety_zones: Optional[List[str]] = None
    comms: Optional[str] = None

class Location(BaseModel):
    geo: Optional[LatLng] = None
    area: Optional[str] = None

    @field_validator("geo", mode="before")
    @classmethod
    def _coerce_geo(cls, v):
        if v is None or isinstance(v, LatLng):
            return v
        return LatLng.from_pair(v)

class Task(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    owner: Optional[str] = None
    location: Optional[Location] = None
    window: Optional[TimeWindow] = None
    duration_hours: float = Field(gt=0)
    dependencies: Optional[List[str]] = Field(default_factory=list)
    resources: Optional[Dict[str, int]] = None  # asset_id -> count
    controls: Optional[Controls] = None
    risks: Optional[List[RiskItem]] = None

    @field_validator("resources")
    @classmethod
    def _nonneg_resource_counts(cls, v):
        if v is None:
            return v
        for k, val in v.items():
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"resources['{k}'] must be a non-negative integer")
        return v

# ---------- INPUT to generator ----------

class COARequest(BaseModel):
    mission: Mission
    environment: Optional[Environment] = None
    assets: Optional[List[Asset]] = None
    threats: Optional[List[Threat]] = None
    hard_constraints: Optional[List[HardConstraint]] = None
    soft_constraints: Optional[List[SoftConstraint]] = None
    objectives: Optional[ObjectiveWeights] = None
    seed_tasks: Optional[List[Task]] = None
    now_iso: Optional[datetime] = None

    @model_validator(mode="after")
    def _cross_validate_tasks(self):
        # If seed_tasks are provided, check IDs unique, deps valid, and DAG (no cycles)
        tasks = self.seed_tasks or []
        if not tasks:
            return self

        ids = [t.id for t in tasks]
        if len(ids) != len(set(ids)):
            dupes = {i for i in ids if ids.count(i) > 1}
            raise ValueError(f"Task IDs must be unique; duplicates: {sorted(dupes)}")

        idset = set(ids)
        for t in tasks:
            for d in (t.dependencies or []):
                if d not in idset:
                    raise ValueError(f"Task '{t.id}' depends on unknown task '{d}'")

        # Cycle check (Kahn)
        indeg = {tid: 0 for tid in idset}
        graph: Dict[str, List[str]] = {tid: [] for tid in idset}
        for t in tasks:
            for d in (t.dependencies or []):
                graph[d].append(t.id)
                indeg[t.id] += 1

        q = [tid for tid, deg in indeg.items() if deg == 0]
        visited = 0
        while q:
            v = q.pop(0)
            visited += 1
            for nxt in graph[v]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    q.append(nxt)
        if visited != len(idset):
            raise ValueError("Task dependency graph contains a cycle")

        return self

# ---------- OUTPUT from generator ----------

class SyncPoint(BaseModel):
    time: Optional[datetime] = None
    purpose: str
    depends_on: Optional[List[str]] = None

class DecisionPoint(BaseModel):
    id: str
    when: Optional[datetime] = None
    trigger: str
    action: str

class Branch(BaseModel):
    trigger: str
    changes: List[str] = Field(min_length=1)

class Metrics(BaseModel):
    speed: float = Field(ge=0.0, le=1.0)
    safety: float = Field(ge=0.0, le=1.0)
    sustainment: float = Field(ge=0.0, le=1.0)
    cost: float = Field(ge=0.0, le=1.0)
    simplicity: float = Field(ge=0.0, le=1.0)
    composite: float = Field(ge=0.0, le=1.0)

class FASDC(BaseModel):
    feasible: bool
    acceptable: bool
    suitable: bool
    distinguishable: bool
    complete: bool

class RiskRegisterEntry(BaseModel):
    risk: str
    likelihood: RiskLevel = "M"
    impact: RiskLevel = "M"
    mitigation: Optional[str] = None
    owner: Optional[str] = None

class Audit(BaseModel):
    generated_at: datetime
    inputs_hash: str = Field(min_length=6)
    notes: Optional[str] = None

class COAResponse(BaseModel):
    mission_id: str
    commander_intent: str
    assumptions: List[str] = Field(default_factory=list)
    tasks: List[Task] = Field(min_length=1)
    sync_points: List[SyncPoint] = Field(default_factory=list)
    routes: List[Route] = Field(default_factory=list)
    decision_points: List[DecisionPoint] = Field(default_factory=list)
    branches: List[Branch] = Field(default_factory=list)
    metrics: Metrics
    fasdc: FASDC
    violations: List[str] = Field(default_factory=list)
    risk_register: List[RiskRegisterEntry] = Field(default_factory=list)
    audit: Audit
    explain: str

    @model_validator(mode="after")
    def _validate_internal_consistency(self):
        # task IDs unique
        ids = [t.id for t in self.tasks]
        if len(ids) != len(set(ids)):
            dupes = {i for i in ids if ids.count(i) > 1}
            raise ValueError(f"tasks contain duplicate IDs: {sorted(dupes)}")
        idset = set(ids)

        # deps only reference known tasks
        for t in self.tasks:
            for d in (t.dependencies or []):
                if d not in idset:
                    raise ValueError(f"Task '{t.id}' depends on unknown task '{d}' (in response)")

        # DAG test
        indeg = {tid: 0 for tid in idset}
        graph: Dict[str, List[str]] = {tid: [] for tid in idset}
        for t in self.tasks:
            for d in (t.dependencies or []):
                graph[d].append(t.id)
                indeg[t.id] += 1
        q = [tid for tid, deg in indeg.items() if deg == 0]
        visited = 0
        while q:
            v = q.pop(0)
            visited += 1
            for nxt in graph[v]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    q.append(nxt)
        if visited != len(idset):
            raise ValueError("tasks form a cyclic dependency graph")

        # decision/sync refer to valid tasks if they list depends_on
        for sp in self.sync_points:
            for dep in (sp.depends_on or []):
                if dep not in idset:
                    raise ValueError(f"SyncPoint depends_on unknown task '{dep}'")

        return self
