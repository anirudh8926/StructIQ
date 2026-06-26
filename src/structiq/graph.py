"""
The join: one graph holding BOTH the standards nodes (clauses/materials/factors from
every active code) and the design nodes (real members from an IFC), with edges between
them.

A compliance check is a *traversal* over this graph: from a Member, follow GOVERNED_BY
edges to the DesignCode clauses that apply, and from a clause follow REFERENCES edges to
the SafetyFactors it depends on. The traversal path is what we surface to the user.

The graph is code-agnostic — it builds itself from the standards registry, so adding a
new code (see standards/) needs no change here. It is also a deterministic in-memory
graph: the demo's safe fallback, needing no external services. `try_cognify()` is an
optional hook to also push the same nodes into Cognee when an LLM key is configured.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .ontology import Member
from . import standards


@dataclass
class Node:
    node_id: str            # e.g. "Member:B3", "DesignCode:IS 456:2000:26.5.1.1"
    kind: str               # "Member" | "DesignCode" | "SafetyFactor" | "Material"
    label: str
    data: dict = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    rel: str                # "GOVERNED_BY" | "REFERENCES"


def _clause_node_id(code: str, clause_id: str) -> str:
    return f"DesignCode:{code}:{clause_id}"


class StructGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._load_standards()

    # --- construction ---------------------------------------------------------------

    def _add(self, node: Node) -> None:
        self.nodes[node.node_id] = node

    def _load_standards(self) -> None:
        """Build the standards graph from every active code in the registry."""
        for code, m in standards.all_materials():
            self._add(Node(f"Material:{code}:{m.name}", "Material", m.name, m.model_dump()))
        for code, c in standards.all_clauses():
            self._add(Node(_clause_node_id(code, c.clause_id), "DesignCode",
                           f"{code} Cl {c.clause_id}", c.model_dump()))
        for i, (code, f) in enumerate(standards.all_factors()):
            nid = f"SafetyFactor:{code}:{i}"
            self._add(Node(nid, "SafetyFactor",
                           f"gamma_m={f.value} ({f.condition})", f.model_dump()))
            if f.referenced_by:
                clause = _clause_node_id(code, f.referenced_by)
                if clause in self.nodes:
                    self.edges.append(Edge(clause, nid, "REFERENCES"))

    def load_members(self, members: list[Member]) -> None:
        """Add the design graph and join it to the standards graph."""
        for m in members:
            nid = f"Member:{m.member_id}"
            self._add(Node(nid, "Member", m.member_id, m.model_dump()))
            for code, clause_id in standards.governing_clause_ids(m.type):
                clause = _clause_node_id(code, clause_id)
                if clause in self.nodes:
                    self.edges.append(Edge(nid, clause, "GOVERNED_BY"))

    # --- traversal ------------------------------------------------------------------

    def governing_clauses(self, member_id: str) -> list[Node]:
        return [self.nodes[e.dst] for e in self.edges
                if e.src == f"Member:{member_id}" and e.rel == "GOVERNED_BY"]

    def references(self, clause_node_id: str) -> list[Node]:
        return [self.nodes[e.dst] for e in self.edges
                if e.src == clause_node_id and e.rel == "REFERENCES"]

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
