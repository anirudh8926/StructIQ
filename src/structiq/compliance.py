"""
The compliance engine — THE product.

Rules live here, never in the API layer. For each member we traverse the joined graph
(graph.StructGraph) from the member to its governing IS 456 clauses, evaluate each clause
numerically, and return a verdict together with the *clause path* that produced it.

The clause path is the differentiator: an auditable Member -> DesignCode -> verdict
trail, not a similarity score.
"""
from __future__ import annotations

import math
import re
from typing import Callable, Optional

from pydantic import BaseModel

from .ontology import Member
from .graph import StructGraph, build_graph
from . import standards

COVER_MM = 35.0  # nominal cover + half-bar, kept simple for the demo


# --- result shapes -------------------------------------------------------------------

class PathStep(BaseModel):
    node: str            # node id, e.g. "DesignCode:26.5.1.1"
    kind: str            # "Member" | "DesignCode" | "SafetyFactor" | "Verdict"
    detail: str          # human-readable explanation of this hop


class CheckResult(BaseModel):
    clause_id: str
    title: str
    passed: bool
    detail: str
    computed: dict


class ComplianceResult(BaseModel):
    member_id: str
    type: str
    status: str          # "PASS" | "FAIL" | "NOT_CHECKED"
    checks: list[CheckResult]
    clause_path: list[PathStep]
    explanation: str


# --- helpers -------------------------------------------------------------------------

def parse_rebar_area(rebar: Optional[str]) -> Optional[float]:
    """'4-T16' -> total steel area in mm^2 = 4 * pi/4 * 16^2."""
    if not rebar:
        return None
    m = re.match(r"\s*(\d+)\s*[-xX]?\s*[TtØ#]?\s*(\d+(?:\.\d+)?)", rebar)
    if not m:
        return None
    n, dia = int(m.group(1)), float(m.group(2))
    return n * math.pi / 4.0 * dia * dia


# --- clause checks (registry keyed by clause id) -------------------------------------

def _check_min_tension_steel(member: Member) -> Optional[CheckResult]:
    """IS 456 Cl 26.5.1.1 — As_min = 0.85 * b * d / fy."""
    if member.type != "beam" or not member.width_mm or not member.depth_mm:
        return None
    fy = standards.steel_grade_fy("Fe415")
    b = member.width_mm
    d = member.depth_mm - COVER_MM
    as_min = 0.85 * b * d / fy
    as_prov = parse_rebar_area(member.rebar)
    if as_prov is None:
        return None
    passed = as_prov >= as_min
    detail = (f"As_prov={as_prov:.0f} mm² {'≥' if passed else '<'} "
              f"As_min={as_min:.0f} mm² (0.85·{b:.0f}·{d:.0f}/{fy:.0f})")
    return CheckResult(clause_id="26.5.1.1", title="Minimum tension reinforcement",
                       passed=passed, detail=detail,
                       computed={"As_provided_mm2": round(as_prov, 1),
                                 "As_min_mm2": round(as_min, 1),
                                 "rebar": member.rebar})


def _check_max_tension_steel(member: Member) -> Optional[CheckResult]:
    """IS 456 Cl 26.5.1.2 — As_max = 0.04 * b * D."""
    if member.type != "beam" or not member.width_mm or not member.depth_mm:
        return None
    as_max = 0.04 * member.width_mm * member.depth_mm
    as_prov = parse_rebar_area(member.rebar)
    if as_prov is None:
        return None
    passed = as_prov <= as_max
    detail = (f"As_prov={as_prov:.0f} mm² {'≤' if passed else '>'} "
              f"As_max={as_max:.0f} mm² (0.04·{member.width_mm:.0f}·{member.depth_mm:.0f})")
    return CheckResult(clause_id="26.5.1.2", title="Maximum tension reinforcement",
                       passed=passed, detail=detail,
                       computed={"As_provided_mm2": round(as_prov, 1),
                                 "As_max_mm2": round(as_max, 1)})


def _check_min_column_steel(member: Member) -> Optional[CheckResult]:
    """IS 456 Cl 26.5.3.1 — As_min = 0.008 * Ag (gross area)."""
    if member.type != "column" or not member.width_mm or not member.depth_mm:
        return None
    ag = member.width_mm * member.depth_mm
    as_min = 0.008 * ag
    as_prov = parse_rebar_area(member.rebar)
    if as_prov is None:
        return None
    passed = as_prov >= as_min
    detail = (f"As_prov={as_prov:.0f} mm² {'≥' if passed else '<'} "
              f"As_min={as_min:.0f} mm² (0.008·{ag:.0f})")
    return CheckResult(clause_id="26.5.3.1", title="Minimum longitudinal steel (column)",
                       passed=passed, detail=detail,
                       computed={"As_provided_mm2": round(as_prov, 1),
                                 "As_min_mm2": round(as_min, 1)})


# clause id -> check function
CHECKS: dict[str, Callable[[Member], Optional[CheckResult]]] = {
    "26.5.1.1": _check_min_tension_steel,
    "26.5.1.2": _check_max_tension_steel,
    "26.5.3.1": _check_min_column_steel,
}


# --- the traversal -------------------------------------------------------------------

def check_member(graph: StructGraph, member: Member) -> ComplianceResult:
    path: list[PathStep] = [
        PathStep(node=f"Member:{member.member_id}", kind="Member",
                 detail=f"{member.type} {member.member_id}: "
                        f"{member.width_mm:.0f}×{member.depth_mm:.0f}, {member.rebar}"
                        if member.width_mm and member.depth_mm
                        else f"{member.type} {member.member_id}")
    ]
    checks: list[CheckResult] = []

    for clause_node in graph.governing_clauses(member.member_id):
        clause_id = clause_node.data["clause_id"]
        fn = CHECKS.get(clause_id)
        if fn is None:
            continue
        result = fn(member)
        if result is None:
            continue
        checks.append(result)
        path.append(PathStep(
            node=clause_node.node_id, kind="DesignCode",
            detail=f"{clause_node.label} — {clause_node.data.get('title', '')}: {result.detail}",
        ))
        # one more hop: the safety factor(s) this clause references
        for ref in graph.references(clause_id):
            path.append(PathStep(node=ref.node_id, kind="SafetyFactor", detail=ref.label))

    if not checks:
        status = "NOT_CHECKED"
        explanation = f"No applicable IS 456 clause evaluated for {member.member_id}."
    else:
        failed = [c for c in checks if not c.passed]
        status = "FAIL" if failed else "PASS"
        if failed:
            explanation = (f"{member.member_id} FAILS {failed[0].clause_id} "
                           f"({failed[0].title}): {failed[0].detail}")
        else:
            explanation = (f"{member.member_id} satisfies "
                           f"{', '.join(c.clause_id for c in checks)}.")

    path.append(PathStep(node=f"Verdict:{member.member_id}", kind="Verdict",
                         detail=f"{status} — {explanation}"))
    return ComplianceResult(member_id=member.member_id, type=member.type, status=status,
                            checks=checks, clause_path=path, explanation=explanation)


def check_all(members: list[Member]) -> list[ComplianceResult]:
    graph = build_graph(members)
    return [check_member(graph, m) for m in members]
