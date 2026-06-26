"""
StructIQ standards registry.

Import this package to use the engine-facing API (`active`, `all_clauses`,
`governing_clause_ids`, `check_for`, …). Built-in codes register themselves on import.
Add a new code by creating a module like is456.py and importing it below.
"""
from .base import (  # noqa: F401
    COVER_MM,
    Check,
    CheckResult,
    PathStep,
    Standard,
    active,
    all_clauses,
    all_factors,
    all_materials,
    check_for,
    enrich_from_pdf,
    get,
    governing_clause_ids,
    parse_rebar_area,
    register,
    steel_grade_fy,
)
from . import is456  # noqa: F401  (registers IS 456:2000)

__all__ = [
    "COVER_MM", "Check", "CheckResult", "PathStep", "Standard",
    "active", "all_clauses", "all_factors", "all_materials", "check_for",
    "enrich_from_pdf", "get", "governing_clause_ids", "parse_rebar_area",
    "register", "steel_grade_fy",
]
