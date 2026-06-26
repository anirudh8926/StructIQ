"""
The standards graph — IS 456:2000.

Per CLAUDE.md: a small correct graph beats a large noisy one. The reliable spine is a
hand-curated seed of demo-critical nodes (defined here). PDF auto-extraction with
pdfplumber/Cognee is *optional enrichment* layered on top (see `enrich_from_pdf`), never
the thing the demo depends on.
"""
from __future__ import annotations

import os
from typing import Optional

from .ontology import DesignCode, Material, SafetyFactor

CODE = "IS 456:2000"


# --- Curated seed: the demo-critical clauses, materials, and factors -----------------

SEED_MATERIALS: list[Material] = [
    Material(name="M25", grade="M25", char_strength=25.0, use_conditions="concrete, fck"),
    Material(name="Fe415", grade="Fe415", yield_strength=415.0, use_conditions="steel, fy"),
    Material(name="Fe500", grade="Fe500", yield_strength=500.0, use_conditions="steel, fy"),
]

SEED_CLAUSES: list[DesignCode] = [
    DesignCode(
        code_name=CODE, clause_id="26.5.1.1", title="Minimum tension reinforcement (beams)",
        formula="As_min = 0.85 * b * d / fy",
        applicability="minimum area of tension steel in beams",
    ),
    DesignCode(
        code_name=CODE, clause_id="26.5.1.2", title="Maximum tension reinforcement (beams)",
        formula="As_max = 0.04 * b * D",
        applicability="maximum area of tension steel in beams",
    ),
    DesignCode(
        code_name=CODE, clause_id="26.5.3.1", title="Minimum longitudinal steel (columns)",
        formula="As_min = 0.008 * Ag",
        applicability="minimum longitudinal steel in columns",
    ),
    DesignCode(
        code_name=CODE, clause_id="40.1", title="Nominal shear stress",
        formula="tau_v = Vu / (b * d)",
        applicability="shear in beams",
    ),
]

SEED_FACTORS: list[SafetyFactor] = [
    SafetyFactor(value=1.5, condition="ULS, concrete (gamma_m)", referenced_by="26.5.1.1"),
    SafetyFactor(value=1.15, condition="ULS, steel (gamma_m)", referenced_by="26.5.1.1"),
]


def seed() -> dict:
    """Return the curated standards graph payload as plain dicts."""
    return {
        "materials": [m.model_dump() for m in SEED_MATERIALS],
        "clauses": [c.model_dump() for c in SEED_CLAUSES],
        "factors": [f.model_dump() for f in SEED_FACTORS],
    }


def clause(clause_id: str) -> Optional[DesignCode]:
    for c in SEED_CLAUSES:
        if c.clause_id == clause_id:
            return c
    return None


def steel_grade_fy(name: Optional[str]) -> float:
    """Yield strength for a steel grade name; defaults to Fe415."""
    for m in SEED_MATERIALS:
        if name and m.name == name and m.yield_strength:
            return m.yield_strength
    return 415.0


# --- Optional enrichment from the real PDF (not required for the demo) ---------------

def enrich_from_pdf(pdf_path: str, max_pages: int = 20) -> list[str]:
    """Best-effort text/table extraction with pdfplumber. Returns text chunks.

    Used by the flat-RAG baseline and (optionally) Cognee. Never on the demo's critical
    path — if the PDF is missing we just return an empty list.
    """
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
