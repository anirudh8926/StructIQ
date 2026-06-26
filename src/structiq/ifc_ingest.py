"""
Parse an IFC model into Member nodes for the design graph.

We deliberately read everything from the explicit `Pset_StructIQ` property set written
by scripts/make_demo_ifc.py. No IFC geometry tessellation — coordinates come straight
from the Pset. This keeps ingestion fast and failure-proof for the demo.
"""
from __future__ import annotations

from typing import Optional

import ifcopenshell
import ifcopenshell.util.element as element

from .ontology import Member

PSET = "Pset_StructIQ"


def _num(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _member_from_product(product) -> Optional[Member]:
    psets = element.get_psets(product)
    p = psets.get(PSET)
    if not p:
        return None

    start = [_num(p.get("StartX")), _num(p.get("StartY")), _num(p.get("StartZ"))]
    end = [_num(p.get("EndX")), _num(p.get("EndY")), _num(p.get("EndZ"))]
    start = start if all(c is not None for c in start) else None
    end = end if all(c is not None for c in end) else None

    return Member(
        member_id=p.get("MemberId") or product.Name or product.GlobalId,
        type=p.get("MemberType") or ("beam" if product.is_a("IfcBeam") else "column"),
        width_mm=_num(p.get("Width")),
        depth_mm=_num(p.get("Depth")),
        span_m=_num(p.get("Span")),
        support_conditions=p.get("Support"),
        concrete=p.get("Concrete"),
        rebar=p.get("Rebar"),
        start_xyz=start,
        end_xyz=end,
    )


def parse_ifc(path: str) -> list[Member]:
    """Return all structural members (beams + columns) found in the IFC file."""
    model = ifcopenshell.open(path)
    members: list[Member] = []
    for product in model.by_type("IfcBeam") + model.by_type("IfcColumn"):
        m = _member_from_product(product)
        if m is not None:
            members.append(m)
    members.sort(key=lambda m: m.member_id)
    return members


def parse_ifc_bytes(data: bytes) -> list[Member]:
    """Same as parse_ifc but from raw bytes (used by the /upload endpoint)."""
    model = ifcopenshell.file.from_string(data.decode("utf-8", errors="replace"))
    members: list[Member] = []
    for product in model.by_type("IfcBeam") + model.by_type("IfcColumn"):
        m = _member_from_product(product)
        if m is not None:
            members.append(m)
    members.sort(key=lambda m: m.member_id)
    return members
