"""
IS 456:2000 — Plain and Reinforced Concrete, Code of Practice.

The reference standard for StructIQ. This module is a template for any future code: define
the curated nodes, the applicability map, and the numeric checks, then `register` it.
"""
from __future__ import annotations

from typing import Optional

from ..ontology import DesignCode, Material, Member, SafetyFactor
from .base import COVER_MM, CheckResult, Standard, parse_rebar_area, register, steel_grade_fy

CODE = "IS 456:2000"


# --- numeric checks ------------------------------------------------------------------

def _min_tension_steel(member: Member) -> Optional[CheckResult]:
    """Cl 26.5.1.1 — As_min = 0.85 * b * d / fy."""
    if member.type != "beam" or not member.width_mm or not member.depth_mm:
        return None
    as_prov = parse_rebar_area(member.rebar)
    if as_prov is None:
        return None
    fy = steel_grade_fy("Fe415")
    b, d = member.width_mm, member.depth_mm - COVER_MM
    as_min = 0.85 * b * d / fy
    passed = as_prov >= as_min
    detail = (f"As_prov={as_prov:.0f} mm² {'≥' if passed else '<'} "
              f"As_min={as_min:.0f} mm² (0.85·{b:.0f}·{d:.0f}/{fy:.0f})")
    return CheckResult(code_name=CODE, clause_id="26.5.1.1",
                       title="Minimum tension reinforcement", passed=passed, detail=detail,
                       computed={"As_provided_mm2": round(as_prov, 1),
                                 "As_min_mm2": round(as_min, 1), "rebar": member.rebar})


def _max_tension_steel(member: Member) -> Optional[CheckResult]:
    """Cl 26.5.1.2 — As_max = 0.04 * b * D."""
    if member.type != "beam" or not member.width_mm or not member.depth_mm:
        return None
    as_prov = parse_rebar_area(member.rebar)
    if as_prov is None:
        return None
    as_max = 0.04 * member.width_mm * member.depth_mm
    passed = as_prov <= as_max
    detail = (f"As_prov={as_prov:.0f} mm² {'≤' if passed else '>'} "
              f"As_max={as_max:.0f} mm² (0.04·{member.width_mm:.0f}·{member.depth_mm:.0f})")
    return CheckResult(code_name=CODE, clause_id="26.5.1.2",
                       title="Maximum tension reinforcement", passed=passed, detail=detail,
                       computed={"As_provided_mm2": round(as_prov, 1),
                                 "As_max_mm2": round(as_max, 1)})


def _min_column_steel(member: Member) -> Optional[CheckResult]:
    """Cl 26.5.3.1 — As_min = 0.008 * Ag (gross area)."""
    if member.type != "column" or not member.width_mm or not member.depth_mm:
        return None
    as_prov = parse_rebar_area(member.rebar)
    if as_prov is None:
        return None
    ag = member.width_mm * member.depth_mm
    as_min = 0.008 * ag
    passed = as_prov >= as_min
    detail = (f"As_prov={as_prov:.0f} mm² {'≥' if passed else '<'} "
              f"As_min={as_min:.0f} mm² (0.008·{ag:.0f})")
    return CheckResult(code_name=CODE, clause_id="26.5.3.1",
                       title="Minimum longitudinal steel (column)", passed=passed, detail=detail,
                       computed={"As_provided_mm2": round(as_prov, 1),
                                 "As_min_mm2": round(as_min, 1)})


# --- the standard --------------------------------------------------------------------

IS456 = Standard(
    code_name=CODE,
    materials=[
        Material(name="M25", grade="M25", char_strength=25.0, use_conditions="concrete, fck"),
        Material(name="Fe415", grade="Fe415", yield_strength=415.0, use_conditions="steel, fy"),
        Material(name="Fe500", grade="Fe500", yield_strength=500.0, use_conditions="steel, fy"),
    ],
    clauses=[
        DesignCode(code_name=CODE, clause_id="26.5.1.1",
                   title="Minimum tension reinforcement (beams)",
                   formula="As_min = 0.85 * b * d / fy",
                   applicability="minimum area of tension steel in beams"),
        DesignCode(code_name=CODE, clause_id="26.5.1.2",
                   title="Maximum tension reinforcement (beams)",
                   formula="As_max = 0.04 * b * D",
                   applicability="maximum area of tension steel in beams"),
        DesignCode(code_name=CODE, clause_id="26.5.3.1",
                   title="Minimum longitudinal steel (columns)",
                   formula="As_min = 0.008 * Ag",
                   applicability="minimum longitudinal steel in columns"),
        DesignCode(code_name=CODE, clause_id="40.1", title="Nominal shear stress",
                   formula="tau_v = Vu / (b * d)", applicability="shear in beams"),
    ],
    factors=[
        SafetyFactor(value=1.5, condition="ULS, concrete (gamma_m)", referenced_by="26.5.1.1"),
        SafetyFactor(value=1.15, condition="ULS, steel (gamma_m)", referenced_by="26.5.1.1"),
    ],
    governs={
        "beam": ["26.5.1.1", "26.5.1.2", "40.1"],
        "column": ["26.5.3.1"],
    },
    checks={
        "26.5.1.1": _min_tension_steel,
        "26.5.1.2": _max_tension_steel,
        "26.5.3.1": _min_column_steel,
    },
)

register(IS456)
