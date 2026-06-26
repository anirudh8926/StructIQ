"""
StructIQ ontology — the 6 entities every other module hangs off.

These are intentionally minimal for the hackathon. Add fields only when a
compliance check or a demo question actually needs them. Resist scope creep.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class Material(BaseModel):
    name: str = Field(..., description="e.g. 'M25', 'Fe415'")
    grade: Optional[str] = None
    yield_strength: Optional[float] = Field(None, description="MPa, for steel")
    char_strength: Optional[float] = Field(None, description="MPa, fck for concrete")
    use_conditions: Optional[str] = None


class Member(BaseModel):
    member_id: str = Field(..., description="e.g. 'B1', 'C2' — matches IFC Name/Tag")
    type: str = Field(..., description="'beam' | 'column' | 'slab'")
    width_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    span_m: Optional[float] = None
    support_conditions: Optional[str] = None
    concrete: Optional[str] = Field(None, description="Material.name of concrete")
    rebar: Optional[str] = Field(None, description="e.g. '4-T16'")
    # Geometry for the 3D view. Read directly from Pset_StructIQ — no IFC geometry math.
    start_xyz: Optional[list[float]] = Field(None, description="[x, y, z] in metres")
    end_xyz: Optional[list[float]] = Field(None, description="[x, y, z] in metres")


class LoadCase(BaseModel):
    load_type: str = Field(..., description="'dead' | 'live' | 'wind' | 'UDL'")
    magnitude: float = Field(..., description="kN or kN/m")
    combination: Optional[str] = None


class DesignCode(BaseModel):
    code_name: str = Field(..., description="e.g. 'IS 456:2000'")
    clause_id: str = Field(..., description="e.g. '26.5.1.1'")
    title: Optional[str] = None
    formula: Optional[str] = None
    applicability: Optional[str] = Field(None, description="when this clause governs")


class SafetyFactor(BaseModel):
    value: float
    condition: str = Field(..., description="e.g. 'ULS, concrete'")
    referenced_by: Optional[str] = Field(None, description="DesignCode.clause_id")


class Connection(BaseModel):
    member_a: str
    member_b: str
    relationship_type: str = Field(..., description="e.g. 'beam-column joint'")
