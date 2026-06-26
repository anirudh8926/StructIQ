"""
Day-1 hand inspection: print the standards graph and the joined design+standards graph
for a demo IFC so we can eyeball that the spine is correct before trusting it.

Run:  python scripts/inspect_graph.py [path-to.ifc]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from structiq.graph import build_graph          # noqa: E402
from structiq.ifc_ingest import parse_ifc        # noqa: E402


def main() -> None:
    default = os.path.join(os.path.dirname(__file__), "..", "data", "ifc", "frame_flawed.ifc")
    path = sys.argv[1] if len(sys.argv) > 1 else default
    members = parse_ifc(path)
    g = build_graph(members)

    print(f"\n== Standards + design graph for {os.path.basename(path)} ==")
    print(f"nodes: {len(g.nodes)}   edges: {len(g.edges)}\n")

    for kind in ("Material", "DesignCode", "SafetyFactor", "Member"):
        ns = [n for n in g.nodes.values() if n.kind == kind]
        print(f"-- {kind} ({len(ns)}) --")
        for n in ns:
            print(f"   {n.node_id:24} {n.label}")
        print()

    print("-- traversal: each member -> governing clauses --")
    for m in members:
        clauses = g.governing_clauses(m.member_id)
        print(f"   {m.member_id}: " + ", ".join(c.data["clause_id"] for c in clauses))


if __name__ == "__main__":
    main()
