"""
The verdict tests — the demo's core promise:
clean B3 passes Cl 26.5.1.1; flawed B3 fails it, with a clause path.
"""
import os

import pytest

from structiq.compliance import check_all, parse_rebar_area
from structiq.ifc_ingest import parse_ifc

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "ifc")


def _by_id(results):
    return {r.member_id: r for r in results}


def test_rebar_area():
    assert parse_rebar_area("4-T16") == pytest.approx(804.2, abs=1.0)
    assert parse_rebar_area("2-T10") == pytest.approx(157.1, abs=1.0)


def test_clean_frame_all_pass():
    results = _by_id(check_all(parse_ifc(os.path.join(DATA, "frame_clean.ifc"))))
    assert results["B3"].status == "PASS"
    assert all(r.status in ("PASS", "NOT_CHECKED") for r in results.values())


def test_flawed_frame_b3_fails_with_clause_path():
    results = _by_id(check_all(parse_ifc(os.path.join(DATA, "frame_flawed.ifc"))))
    b3 = results["B3"]
    assert b3.status == "FAIL"
    # the failing clause is the minimum-tension-steel clause
    assert any(c.clause_id == "26.5.1.1" and not c.passed for c in b3.checks)
    # the clause path is populated and ends in a verdict
    kinds = [s.kind for s in b3.clause_path]
    assert kinds[0] == "Member" and kinds[-1] == "Verdict"
    assert any(s.kind == "DesignCode" for s in b3.clause_path)
    # the other beams still pass
    assert results["B1"].status == "PASS"
    assert results["B2"].status == "PASS"
