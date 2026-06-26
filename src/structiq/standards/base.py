"""
Standards registry — the pluggable spine.

Each engineering code (IS 456, ACI 318, …) is a `Standard`: a bundle of curated nodes
(materials, clauses, safety factors), an applicability map (member type -> clause ids),
and the numeric checks (clause id -> callable). Codes register themselves here; the graph
and the compliance engine iterate the registry generically and never name a specific code.

To add a standard: create a module next to is456.py, build a `Standard`, call
`register(std)`, and import it from this package's __init__. Nothing in graph.py or
compliance.py changes.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from pydantic import BaseModel

from ..ontology import DesignCode, Material, Member, SafetyFactor

COVER_MM = 35.0  # nominal cover + half-bar, kept simple for the demo


# --- result shapes (shared by every check) -------------------------------------------

class CheckResult(BaseModel):
    code_name: str
    clause_id: str
    title: str
    passed: bool
    detail: str
    computed: dict


class PathStep(BaseModel):
    node: str            # node id, e.g. "DesignCode:IS 456:2000:26.5.1.1"
    kind: str            # "Member" | "DesignCode" | "SafetyFactor" | "Verdict"
    detail: str          # human-readable explanation of this hop


# A check evaluates one clause for one member; returns None when the clause doesn't apply.
Check = Callable[[Member], Optional[CheckResult]]


@dataclass
class Standard:
    code_name: str                                              # e.g. "IS 456:2000"
    materials: list[Material] = field(default_factory=list)
    clauses: list[DesignCode] = field(default_factory=list)
    factors: list[SafetyFactor] = field(default_factory=list)
    governs: dict[str, list[str]] = field(default_factory=dict)  # member type -> clause ids
    checks: dict[str, Check] = field(default_factory=dict)       # clause id -> check

    def clause(self, clause_id: str) -> Optional[DesignCode]:
        return next((c for c in self.clauses if c.clause_id == clause_id), None)


# --- registry ------------------------------------------------------------------------

_REGISTRY: dict[str, Standard] = {}


def register(std: Standard) -> Standard:
    _REGISTRY[std.code_name] = std
    return std


def get(code_name: str) -> Standard:
    return _REGISTRY[code_name]


def active() -> list[Standard]:
    """Standards used for checking. Defaults to ALL registered codes; the env var
    STRUCTIQ_CODES (comma-separated code names) narrows the set when present."""
    sel = os.environ.get("STRUCTIQ_CODES")
    if not sel:
        return list(_REGISTRY.values())
    wanted = {s.strip() for s in sel.split(",") if s.strip()}
    return [s for s in _REGISTRY.values() if s.code_name in wanted]


# --- aggregation helpers the graph/engine use (code-agnostic) ------------------------

def all_materials() -> list[tuple[str, Material]]:
    return [(s.code_name, m) for s in active() for m in s.materials]


def all_clauses() -> list[tuple[str, DesignCode]]:
    return [(s.code_name, c) for s in active() for c in s.clauses]


def all_factors() -> list[tuple[str, SafetyFactor]]:
    return [(s.code_name, f) for s in active() for f in s.factors]


def governing_clause_ids(member_type: str) -> list[tuple[str, str]]:
    """(code_name, clause_id) pairs that govern this member type, across active codes."""
    return [(s.code_name, cid) for s in active() for cid in s.governs.get(member_type, [])]


def check_for(code_name: str, clause_id: str) -> Optional[Check]:
    s = _REGISTRY.get(code_name)
    return s.checks.get(clause_id) if s else None


def steel_grade_fy(name: Optional[str], default: float = 415.0) -> float:
    """Yield strength for a steel grade name, looked up across active codes."""
    for _, m in all_materials():
        if name and m.name == name and m.yield_strength:
            return m.yield_strength
    return default


# --- shared check primitives ---------------------------------------------------------

def parse_rebar_area(rebar: Optional[str]) -> Optional[float]:
    """'4-T16' -> total steel area in mm^2 = 4 * pi/4 * 16^2."""
    if not rebar:
        return None
    m = re.match(r"\s*(\d+)\s*[-xX]?\s*[TtØ#]?\s*(\d+(?:\.\d+)?)", rebar)
    if not m:
        return None
    n, dia = int(m.group(1)), float(m.group(2))
    return n * math.pi / 4.0 * dia * dia


# --- optional PDF enrichment (per code, never on the demo's critical path) ------------

def enrich_from_pdf(pdf_path: str, max_pages: int = 20) -> list[str]:
    """Best-effort text/table extraction with pdfplumber. Returns text chunks; empty list
    if the PDF is missing. Used by the flat-RAG baseline and (optionally) Cognee."""
    if not pdf_path or not os.path.exists(pdf_path):
        return []
    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            text = page.extract_text() or ""
            for para in text.split("\n\n"):
                para = para.strip()
                if len(para) > 40:
                    chunks.append(para)
    return chunks
