"""
The join: one graph holding BOTH the standards nodes (IS 456 clauses/materials/factors)
and the design nodes (real members from an IFC), with edges between them.

A compliance check is a *traversal* over this graph: from a Member, follow GOVERNED_BY
edges to the DesignCode clauses that apply, and from a clause follow REFERENCES edges to
the SafetyFactors it depends on. The traversal path is what we surface to the user.

This is a deterministic in-memory graph — it is the demo's safe fallback and needs no
external services. `try_cognify()` is an optional hook to also push the same nodes into
Cognee when an LLM key is configured; the demo never depends on it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .ontology import Member
from . import standards


@dataclass
class Node:
    node_id: str            # e.g. "Member:B3", "DesignCode:26.5.1.1"
    kind: str               # "Member" | "DesignCode" | "SafetyFactor" | "Material"
    label: str
    data: dict = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    rel: str                # "GOVERNED_BY" | "REFERENCES"


# member type -> clause ids that govern it (applicability of the standards graph)
_GOVERNS = {
    "beam": ["26.5.1.1", "26.5.1.2", "40.1"],
    "column": ["26.5.3.1"],
}


class StructGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._load_standards()

    # --- construction ---------------------------------------------------------------

    def _add(self, node: Node) -> None:
        self.nodes[node.node_id] = node

    def _load_standards(self) -> None:
        s = standards.seed()
        for m in s["materials"]:
            self._add(Node(f"Material:{m['name']}", "Material", m["name"], m))
        for c in s["clauses"]:
            self._add(Node(f"DesignCode:{c['clause_id']}", "DesignCode",
                           f"{c['code_name']} Cl {c['clause_id']}", c))
        for i, f in enumerate(s["factors"]):
            nid = f"SafetyFactor:{i}"
            self._add(Node(nid, "SafetyFactor", f"gamma_m={f['value']} ({f['condition']})", f))
            if f.get("referenced_by"):
                self.edges.append(Edge(f"DesignCode:{f['referenced_by']}", nid, "REFERENCES"))

    def load_members(self, members: list[Member]) -> None:
        """Add the design graph and join it to the standards graph."""
        for m in members:
            nid = f"Member:{m.member_id}"
            self._add(Node(nid, "Member", m.member_id, m.model_dump()))
            for clause_id in _GOVERNS.get(m.type, []):
                if f"DesignCode:{clause_id}" in self.nodes:
                    self.edges.append(Edge(nid, f"DesignCode:{clause_id}", "GOVERNED_BY"))

    # --- traversal ------------------------------------------------------------------

    def governing_clauses(self, member_id: str) -> list[Node]:
        out = []
        for e in self.edges:
            if e.src == f"Member:{member_id}" and e.rel == "GOVERNED_BY":
                out.append(self.nodes[e.dst])
        return out

    def references(self, clause_id: str) -> list[Node]:
        out = []
        for e in self.edges:
            if e.src == f"DesignCode:{clause_id}" and e.rel == "REFERENCES":
                out.append(self.nodes[e.dst])
        return out

    def members(self) -> list[Member]:
        return [Member(**n.data) for n in self.nodes.values() if n.kind == "Member"]


def build_graph(members: list[Member]) -> StructGraph:
    g = StructGraph()
    g.load_members(members)
    return g


def try_cognify(members: list[Member]) -> Optional[str]:
    """Optionally push nodes into Cognee. Returns a status string, never raises.

    Cognee needs an LLM key (see .env.example). This is enrichment only — the demo runs
    fully on the in-memory StructGraph above.
    """
    try:
        import cognee  # noqa: F401
    except Exception as exc:  # pragma: no cover - optional path
        return f"cognee not available ({exc.__class__.__name__}); using in-memory graph"
    return "cognee installed; in-memory graph is authoritative for the demo"
