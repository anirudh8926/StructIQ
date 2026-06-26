"""
The compliance engine — THE product.

For each member we traverse the joined graph (graph.StructGraph) from the member to its
governing clauses (across every active code), evaluate each clause numerically via the
standards registry, and return a verdict together with the *clause path* that produced it.

The numeric rules themselves live in the per-code modules under standards/ (e.g.
standards/is456.py), never here and never in the API. This module is pure traversal +
verdict assembly, so it is automatically multi-standard.
"""
from __future__ import annotations

from pydantic import BaseModel

from .ontology import Member
from .graph import StructGraph, build_graph
from . import standards
from .standards import CheckResult, PathStep  # shared shapes, defined with the checks

# Re-exported so existing imports (tests) keep working after the registry refactor.
from .standards import parse_rebar_area  # noqa: F401


class ComplianceResult(BaseModel):
    member_id: str
    type: str
    status: str          # "PASS" | "FAIL" | "NOT_CHECKED"
    checks: list[CheckResult]
    clause_path: list[PathStep]
    explanation: str


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
        code = clause_node.data.get("code_name")
        clause_id = clause_node.data["clause_id"]
        fn = standards.check_for(code, clause_id)
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
        for ref in graph.references(clause_node.node_id):
            path.append(PathStep(node=ref.node_id, kind="SafetyFactor", detail=ref.label))

    if not checks:
        status = "NOT_CHECKED"
        explanation = f"No applicable clause evaluated for {member.member_id}."
    else:
        failed = [c for c in checks if not c.passed]
        status = "FAIL" if failed else "PASS"
        if failed:
            explanation = (f"{member.member_id} FAILS {failed[0].code_name} "
                           f"{failed[0].clause_id} ({failed[0].title}): {failed[0].detail}")
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
