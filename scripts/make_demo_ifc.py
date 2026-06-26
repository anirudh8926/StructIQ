"""
Generate the two demo IFC files from ONE frame definition.

    data/ifc/frame_clean.ifc   -> fully compliant
    data/ifc/frame_flawed.ifc  -> identical geometry, ONE planted violation (B3 rebar)

The whole point of having a single generator is that the two files are guaranteed to
differ in exactly one property (B3's rebar), so the clean-vs-flawed demo is honest.

Geometry + section + rebar are written into an explicit property set `Pset_StructIQ`
on every member. The parser (ifc_ingest.py) reads that Pset directly — we never do
IFC geometry math. Coordinates are in metres.

Run:  python scripts/make_demo_ifc.py
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import ifcopenshell
import ifcopenshell.api.root
import ifcopenshell.api.unit
import ifcopenshell.api.context
import ifcopenshell.api.aggregate
import ifcopenshell.api.spatial
import ifcopenshell.api.pset

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "data", "ifc")

# Column height and storey level
H = 3.0  # m

# Plan corners (x, y) for the four columns
C1, C2, C3, C4 = (0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)


@dataclass
class MemberDef:
    member_id: str
    ifc_class: str          # "IfcColumn" | "IfcBeam"
    start: tuple            # (x, y, z) metres
    end: tuple
    width_mm: float
    depth_mm: float
    concrete: str
    rebar: str
    span_m: float
    support: str


def frame(flaw: bool) -> list[MemberDef]:
    """One frame. `flaw` flips only B3's rebar."""
    # Columns: 300x300, vertical from z=0 to z=H
    cols = [
        MemberDef(f"C{i+1}", "IfcColumn", (x, y, 0.0), (x, y, H),
                  300, 300, "M25", "8-T16", H, "fixed-base")
        for i, (x, y) in enumerate([C1, C2, C3, C4])
    ]

    def beam(mid, a, b, rebar, span):
        return MemberDef(mid, "IfcBeam", (a[0], a[1], H), (b[0], b[1], H),
                         230, 450, "M25", rebar, span, "simply-supported")

    # B3 is the planted-violation candidate. 4-T16 passes Cl 26.5.1.1; 2-T10 fails it.
    b3_rebar = "2-T10" if flaw else "4-T16"
    beams = [
        beam("B1", C1, C2, "4-T16", 6.0),
        beam("B2", C2, C3, "4-T16", 4.0),
        beam("B3", C4, C3, b3_rebar, 6.0),
    ]
    return cols + beams


def build(flaw: bool, path: str) -> None:
    model = ifcopenshell.file(schema="IFC4")

    project = ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="StructIQ Demo")
    ifcopenshell.api.unit.assign_unit(model)
    ctx = ifcopenshell.api.context.add_context(model, context_type="Model")

    site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuilding", name="Building")
    storey = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuildingStorey", name="Level 1")
    ifcopenshell.api.aggregate.assign_object(model, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(model, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(model, products=[storey], relating_object=building)

    for m in frame(flaw):
        product = ifcopenshell.api.root.create_entity(model, ifc_class=m.ifc_class, name=m.member_id)
        ifcopenshell.api.spatial.assign_container(model, products=[product], relating_structure=storey)
        pset = ifcopenshell.api.pset.add_pset(model, product=product, name="Pset_StructIQ")
        ifcopenshell.api.pset.edit_pset(model, pset=pset, properties={
            "MemberId": m.member_id,
            "MemberType": "beam" if m.ifc_class == "IfcBeam" else "column",
            "StartX": m.start[0], "StartY": m.start[1], "StartZ": m.start[2],
            "EndX": m.end[0], "EndY": m.end[1], "EndZ": m.end[2],
            "Width": m.width_mm, "Depth": m.depth_mm,
            "Concrete": m.concrete, "Rebar": m.rebar,
            "Span": m.span_m, "Support": m.support,
        })

    os.makedirs(os.path.dirname(path), exist_ok=True)
    model.write(path)
    print(f"wrote {os.path.relpath(path)}  (flaw={flaw})")


def main() -> None:
    build(flaw=False, path=os.path.join(OUT_DIR, "frame_clean.ifc"))
    build(flaw=True, path=os.path.join(OUT_DIR, "frame_flawed.ifc"))


if __name__ == "__main__":
    main()
