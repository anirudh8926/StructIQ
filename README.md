# StructIQ

Graph-native structural-engineering compliance, grounded in IS 456. Two graphs — a
**standards graph** (IS 456 clauses) and a **design graph** (members parsed from an IFC
model) — are joined, and a compliance check *traverses* from a real member to its
governing clause and returns a verdict **with the clause path**. See [CLAUDE.md](CLAUDE.md)
for the full design.

The headline demo is two IFC files with identical geometry that differ in exactly one
property: `frame_clean.ifc` (all compliant) vs `frame_flawed.ifc` (beam B3 under-reinforced,
fails IS 456 Cl 26.5.1.1). Upload clean → all green; upload flawed → B3 turns red, with the
clause path that explains why.

## Layout
- `src/structiq/` — backend (ontology, graph join, IS 456 standards, IFC ingest,
  compliance engine, FastAPI). Rules live in `compliance.py`, never in the API.
- `scripts/make_demo_ifc.py` — generates both demo IFCs from one frame definition.
- `scripts/inspect_graph.py` — prints the joined graph for hand inspection.
- `frontend/` — Vite + React + react-three-fiber 3D viewer.
- `data/ifc/` — generated demo models. `data/standards/` — drop `IS456.pdf` here (optional).
- `tests/` — compliance verdict tests.

## Run

```bash
# 1. Python deps
pip install -r requirements.txt

# 2. Generate the two demo IFCs
python scripts/make_demo_ifc.py

# 3. Backend API on :8000
PYTHONPATH=src python -m uvicorn structiq.api:app --port 8000     # bash
#   (PowerShell)  $env:PYTHONPATH="src"; python -m uvicorn structiq.api:app --port 8000

# 4. Frontend dev server on :5173 (proxies /model etc. to :8000)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Upload a file from `data/ifc/`, click **Check against IS 456**,
then click any member to see its clause path. (For a single-origin build, run
`npm run build` in `frontend/` and the FastAPI app serves `frontend/dist` at
http://localhost:8000.)

## Tests
```bash
pytest          # clean B3 passes; flawed B3 fails Cl 26.5.1.1 with a clause path
```

## Notes
- The 3D geometry comes from an explicit `Pset_StructIQ` property set on each member — no
  IFC geometry tessellation.
- Cognee (graph memory) and ChromaDB (flat-RAG baseline) are optional enrichment. The demo
  runs fully on a deterministic in-memory graph; if those packages or an LLM key are
  absent, the core IFC → graph → compliance → verdict path still works.
