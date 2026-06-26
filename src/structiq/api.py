"""
Thin FastAPI layer. It ONLY exposes the engine — no design rules live here.

Endpoints:
  POST /upload     IFC file -> parsed members table (also stored as current model)
  POST /check      run compliance over the current model -> verdicts + clause paths
  GET  /model      the 3D-view contract: members w/ geometry + status + clause_path
  GET  /baseline   flat-RAG answer for the side-by-side contrast
  GET  /health     liveness
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import baseline
from .compliance import ComplianceResult, check_all
from .ifc_ingest import parse_ifc, parse_ifc_bytes
from .ontology import Member

app = FastAPI(title="StructIQ", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# In-memory "current model" — fine for a single-user demo.
_STATE: dict = {"members": [], "results": {}, "source": None}


def _set_members(members: list[Member], source: str) -> None:
    _STATE["members"] = members
    _STATE["source"] = source
    _STATE["results"] = {}  # invalidate until /check runs


def _member_view(m: Member) -> dict:
    res: Optional[ComplianceResult] = _STATE["results"].get(m.member_id)
    return {
        "id": m.member_id,
        "type": m.type,
        "start": m.start_xyz,
        "end": m.end_xyz,
        "width_mm": m.width_mm,
        "depth_mm": m.depth_mm,
        "concrete": m.concrete,
        "rebar": m.rebar,
        "status": res.status if res else "UNCHECKED",
        "explanation": res.explanation if res else None,
        "clause_path": [s.model_dump() for s in res.clause_path] if res else [],
        "checks": [c.model_dump() for c in res.checks] if res else [],
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True, "members": len(_STATE["members"]), "source": _STATE["source"]}


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        members = parse_ifc_bytes(data)
    except Exception as exc:
        raise HTTPException(400, f"could not parse IFC: {exc}")
    if not members:
        raise HTTPException(400, "no structural members with Pset_StructIQ found")
    _set_members(members, file.filename or "uploaded.ifc")
    return {"source": _STATE["source"],
            "members": [_member_view(m) for m in members]}


@app.post("/check")
def check() -> dict:
    members: list[Member] = _STATE["members"]
    if not members:
        raise HTTPException(400, "no model loaded — POST /upload first")
    results = check_all(members)
    _STATE["results"] = {r.member_id: r for r in results}
    return model()


@app.get("/model")
def model() -> dict:
    members: list[Member] = _STATE["members"]
    views = [_member_view(m) for m in members]
    passed = sum(v["status"] == "PASS" for v in views)
    failed = sum(v["status"] == "FAIL" for v in views)
    return {"source": _STATE["source"], "members": views,
            "summary": {"pass": passed, "fail": failed, "total": len(views)}}


@app.get("/baseline")
def baseline_query(q: str) -> dict:
    return baseline.query(q)


# Optionally load a default model on startup so GET /model works before any upload.
def _maybe_load_default() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.join(here, "..", "..", "data", "ifc", "frame_flawed.ifc")
    if os.path.exists(default):
        try:
            _set_members(parse_ifc(default), "frame_flawed.ifc (default)")
        except Exception:
            pass


_maybe_load_default()

# Serve the built frontend if present (frontend/dist). Mounted last so /api routes win.
_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
