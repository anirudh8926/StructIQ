# StructIQ

**Graph-native structural-engineering compliance, grounded in IS 456.**

StructIQ joins two graphs — a **standards graph** (IS 456 clauses, limits, materials) and a
**design graph** (real members parsed from an IFC model) — and answers compliance questions
by *traversing* from a real member to its governing clause, returning a verdict **with the
clause path**. That auditable traversal — not flat semantic search over a PDF — is the
entire product.

The headline demo is two IFC files with identical geometry that differ in exactly one
property: `frame_clean.ifc` (all compliant) vs `frame_flawed.ifc` (beam **B3**
under-reinforced, fails IS 456 Cl 26.5.1.1). Upload clean → all members render green; upload
flawed → B3 turns red, and clicking it shows the clause path that explains why.

---

## Table of contents
1. [What it is / what it is not](#1-what-it-is--what-it-is-not)
2. [Architecture](#2-architecture)
3. [The ontology](#3-the-ontology)
4. [Project layout](#4-project-layout)
5. [Quickstart](#5-quickstart)
6. [Build status — what's real vs. fallback](#6-build-status--whats-real-vs-fallback)
7. [The standards registry (multi-standard support)](#7-the-standards-registry-multi-standard-support)
8. [Design decision: why compliance needs no LLM](#8-design-decision-why-compliance-needs-no-llm)
9. [Can we trust an LLM to generate the graph?](#9-can-we-trust-an-llm-to-generate-the-graph)
10. [Experiment: LLM-draft extraction from the real IS 456 PDF](#10-experiment-llm-draft-extraction-from-the-real-is-456-pdf)
11. [The Cognee memory layer (LLM Q&A)](#11-the-cognee-memory-layer-llm-qa)
12. [Demo script](#12-demo-script)
13. [Roadmap / next steps](#13-roadmap--next-steps)

---

## 1. What it is / what it is not

**It is:** bounded design assistance + compliance review for known problem classes, where
every verdict is backed by a traversal path through a curated standards graph.

**It is not:**
- Autonomous design ("design me a building").
- A chatbot wrapper. The differentiator is structured multi-hop traversal + an auditable
  reasoning path, demonstrated against flat RAG.

---

## 2. Architecture

```
IS 456 (curated)  -> standards graph ─┐
                                      ├─> one joined graph -> compliance traversal -> verdict + clause path -> 3D view
IFC model         -> design graph ────┘
```

Data flow end to end:

1. **IFC ingest** ([src/structiq/ifc_ingest.py](src/structiq/ifc_ingest.py)) — `ifcopenshell`
   parses each `IfcBeam`/`IfcColumn` into a `Member`, reading geometry and section straight
   from an explicit `Pset_StructIQ` property set. **No IFC geometry tessellation.**
2. **The join** ([src/structiq/graph.py](src/structiq/graph.py)) — a deterministic in-memory
   `StructGraph` holds both the standards nodes (clauses/materials/factors) and the design
   nodes (members), with `GOVERNED_BY` and `REFERENCES` edges between them.
3. **Compliance** ([src/structiq/compliance.py](src/structiq/compliance.py)) — for each
   member, traverse to its governing clauses, evaluate each numerically, and assemble a
   `ComplianceResult` with a `clause_path` (Member → DesignCode → SafetyFactor → Verdict).
4. **API** ([src/structiq/api.py](src/structiq/api.py)) — FastAPI exposes the engine. `GET
   /model` is the single backend↔frontend contract.
5. **3D view** ([frontend/](frontend/)) — Vite + React + react-three-fiber renders the frame;
   members are boxes colored green (pass) / red (fail), click-to-inspect shows the clause path.
6. **Memory layer (optional)** ([src/structiq/memory.py](src/structiq/memory.py)) — Cognee
   stores the *verified* model as graph+vector memory; `POST /ask` answers natural-language
   questions grounded in it via an LLM. Sits outside the verdict path (see §11).

### The worked example (beam B3)

```
IFC ──▶ Member{B3, beam, 230×450 mm, rebar "2-T10"}
parse "2-T10"  → 2 × π/4 × 10²            = 157 mm²        (regex + arithmetic)
graph edge: Member B3 ──GOVERNED_BY──▶ Cl 26.5.1.1
check:      As_min = 0.85·b·d/fy = 0.85·230·415/415 = 196 mm²
verdict:    157 < 196  →  FAIL  (clean frame uses 4-T16 = 804 mm² → PASS)
```

Clean frame → 7/7 pass. Flawed frame → 6 pass, 1 fail (B3).

---

## 3. The ontology

Six Pydantic entities ([src/structiq/ontology.py](src/structiq/ontology.py)) are the spine:
`Material`, `Member`, `LoadCase`, `DesignCode`, `SafetyFactor`, `Connection`. A parsed
`IfcBeam`/`IfcColumn` becomes a `Member`; a clause becomes a `DesignCode`. `Member` carries
explicit `start_xyz` / `end_xyz` (metres) so the 3D view can draw it without geometry math.

---

## 4. Project layout

```
src/structiq/
  ontology.py        # the 6 entities
  ifc_ingest.py      # IFC -> Member nodes (reads Pset_StructIQ)
  graph.py           # the join + deterministic traversal (in-memory StructGraph)
  compliance.py      # pure traversal + verdict assembly (NO rules here)
  baseline.py        # ChromaDB / keyword flat-RAG baseline (the weak contrast)
  memory.py          # Cognee memory layer: ingest verified model + LLM Q&A (cloud + Ollama)
  api.py             # FastAPI: /upload /check /model /baseline /ask /memory/status /health
  standards/
    base.py          # Standard dataclass, registry, result shapes, check primitives
    is456.py         # IS 456:2000 as data + numeric checks (the rules live HERE)
    __init__.py      # registry facade; imports built-in codes so they self-register
scripts/
  make_demo_ifc.py   # one frame definition -> frame_clean.ifc + frame_flawed.ifc
  inspect_graph.py   # print the joined graph for hand inspection
  extract_clauses.py # dump the PDF text layer + show clause context (see §10)
frontend/            # Vite + React + react-three-fiber
  src/components/{Scene,MemberMesh,InspectPanel,UploadBar,BaselinePanel,AskPanel}.tsx
  src/api.ts         # typed client mirroring GET /model
data/
  ifc/{frame_clean,frame_flawed}.ifc   # generated demo models
  standards/                           # the IS 456 PDF lives here
tests/test_compliance.py
```

---

## 5. Quickstart

```bash
# 1. Python deps
pip install -r requirements.txt

# 2. Generate the two demo IFCs
python scripts/make_demo_ifc.py

# 3. Backend API on :8000
PYTHONPATH=src python -m uvicorn structiq.api:app --port 8000        # bash
#   (PowerShell)  $env:PYTHONPATH="src"; python -m uvicorn structiq.api:app --port 8000

# 4. Frontend dev server on :5173 (proxies /model etc. to :8000)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Upload a file from `data/ifc/`, click **Check against IS 456**,
then click any member to see its clause path. For a single-origin build, run `npm run build`
in `frontend/` and the FastAPI app serves `frontend/dist` at http://localhost:8000.

```bash
pytest          # clean B3 passes; flawed B3 fails Cl 26.5.1.1 with a clause path
```

> The optional **Cognee memory layer** (`/ask`) has its own heavier setup (a short-path venv
> + Ollama + an optional cloud key) — see §11.

---

## 6. Build status — what's real vs. fallback

The core spine (**IFC → graph → compliance → verdict → 3D**) is fully built, tested, and
rendering. Three heavier integrations deliberately run in fallback mode; none is on the
demo's critical path.

| Area | Status |
|---|---|
| Ontology, IFC ingest, graph join, compliance engine | ✅ done & tested |
| Two demo IFCs (clean / flawed) | ✅ generated, differ only in B3 rebar |
| FastAPI (`/upload`, `/check`, `/model`, `/baseline`) | ✅ done |
| Three.js (Vite + r3f) 3D viewer, click-to-inspect | ✅ done & verified in-browser |
| Standards graph | ⚠️ **curated seed** (hand-authored), not parsed from the PDF |
| ChromaDB flat-RAG baseline | ⚠️ **keyword fallback** — `chromadb`/`sentence-transformers` not installed |
| Cognee memory layer + `/ask` (LLM Q&A) | 🔄 **wired** — proven end-to-end locally; cloud (OpenAI/Anthropic) + Ollama-fallback routing done; live cloud run + AskPanel test pending (§11, §13) |
| Frontend AskPanel | 🔄 built; not yet tested against a live `/ask` |

Note the compliance *join* deliberately stays an in-memory `StructGraph` (deterministic, §2);
Cognee is a *separate* memory layer for Q&A, never the verdict path. The reasons the other
rows are fallbacks (and why that's the right call) are in §8–§11.

---

## 7. The standards registry (multi-standard support)

Standards are pluggable. Each engineering code is a `Standard`
([src/structiq/standards/base.py](src/structiq/standards/base.py)): a bundle of curated nodes
(materials, clauses, safety factors), an applicability map (`member type -> clause ids`), and
the numeric checks (`clause id -> callable`). Codes register themselves; `graph.py` and
`compliance.py` iterate the registry generically and never name a specific code.

**To add a code** (e.g. ACI 318, Eurocode 2):

1. Create `src/structiq/standards/<code>.py`.
2. Build a `Standard(code_name=…, materials=…, clauses=…, factors=…, governs=…, checks=…)`.
3. Call `register(std)`.
4. Import it from `standards/__init__.py`.

Nothing in `graph.py` or `compliance.py` changes. `STRUCTIQ_CODES` (comma-separated code
names, env var) narrows which codes are active for a given run. This cleanly separates the
**data** (`clauses=[...]`) from the **rules** (`checks={...}`) — which matters a lot for §9.

---

## 8. Design decision: why compliance needs no LLM

**The verdict is deterministic arithmetic, not model inference** — reproducible like a
spreadsheet or a hand calculation. Every number in the B3 trace (§2) comes from either the
IFC file or a formula written into Python in `standards/is456.py` (`As_min = 0.85 * b * d /
fy`). No model "decides" whether a beam is safe. Run it a thousand times → identical verdict.
That is a requirement, not a limitation: you cannot have a generative model hallucinating a
safety verdict.

**Where an LLM was ever relevant:** exactly one optional place — **Cognee auto-extraction**,
i.e. using an LLM to read the PDF and auto-build the standards graph. We deliberately do not
rely on it (CLAUDE.md: *"prefer hand-authoring ~30 demo-critical nodes … a small correct
graph wins"*).

**What the IS 456 PDF does and does not do:**

| | Drives the verdict? |
|---|---|
| Hand-authored clauses/formulas in `is456.py` | ✅ **Yes** — the source of truth |
| The IS 456 **PDF** | ❌ **No** — it is a source of *text*, not *rules* |

Wiring the PDF in affects the **flat-RAG baseline** (real clause text in the contrast panel)
and could add **clause provenance** to the inspect panel — both deterministic (`pdfplumber`,
no LLM). Neither changes whether B3 passes or fails.

---

## 9. Can we trust an LLM to generate the graph?

Partly — and the boundary is the whole point. **Trust an LLM to *draft* the graph; never to
be the unverified source of truth for a verdict.** "Graph generation" bundles two very
different artifacts:

| Artifact | What it is | LLM-trustworthy? |
|---|---|---|
| **Structure + text** | clause ids, titles, prose, edges to materials/factors | ✅ yes, *with review* — this is extraction/linking |
| **The executable rule** | the running, unit-correct, exception-aware check that emits PASS/FAIL | ❌ no — stays hand-coded + unit-tested |

Cognee extraction gives you the first column (nodes with a `formula` *string*), not a vetted
check function. IS 456 is full of traps that auto-extraction silently gets wrong: `d` vs `D`
(effective vs overall depth), ratio vs percentage, table lookups with interpolation (Table 19
shear depends on both % steel and concrete grade), and "except when…" provisos.

**Professional pattern:** LLM drafts candidate nodes (schema-constrained by the 6 Pydantic
models) → a human reviews/corrects (`inspect_graph.py` is exactly this Day-1 step) → the
checks are written and unit-tested separately. The formula string in a node is for
display/provenance, never the execution path. Our registry refactor (§7) already supports
"LLM drafts the data, human owns the arithmetic."

---

## 10. Experiment: LLM-draft extraction from the real IS 456 PDF

We ran a draft pass on the actual PDF (`data/standards/is.456.2000.pdf`, 114 pages, text
layer present). `python scripts/extract_clauses.py` dumps the text layer and shows the
context around the demo-critical clauses — i.e. the raw input any extractor receives.

**Finding: the weak link is *upstream* of the LLM.** The PDF is a two-column scan whose OCR
text layer is badly garbled, so any model would reason over corrupted input and confidently
emit plausible-but-wrong nodes.

The formula our B3 check depends on (Cl 26.5.1.1) extracts like this — shattered across lines
and interleaved with a *different* clause's text:

```
26.5.1.3 Side face reinforcement          ← wrong clause heading, sitting on top
Wherethedepthofthewebinabeamexceeds750mm,
~ = 0.85                                   ← As/bd = 0.85 ...
bd f                                       ← ... bd f ...
y faces. Thetotalareaofsuchreinforcement  ← ... y   (= 0.85/fy, split 3 ways)
```

Table 19 (design shear strength) extracts with OCR-corrupted digits: `M2S`→M25, `M3S`→M35,
`0.11`→0.71, `0.$1`→0.57. The column min-steel rule (26.5.3.1) arrives as
`shallbenotlessthan0.8pIIIIftl` with the clause number not cleanly attached.

**Candidate nodes vs. the trusted hand seed:**

| Node | Hand seed (trusted) | LLM draft from this PDF | Verdict |
|---|---|---|---|
| `26.5.1.1` min tension steel | `As_min = 0.85·b·d/fy` | 0.85/fy present, **adjacent to "26.5.1.3 side face"** | ⚠️ high mis-attribution risk |
| `26.5.3.1` min column steel | `0.008·Ag` (= 0.8%) | "0.8 percent" garbled, heading lost | ⚠️ value right, provenance gone |
| `40.1` / Table 19 shear | τc lookup | digits OCR-corrupted (0.71→0.11) | ❌ numbers unusable |

**Conclusion:** auto-extraction from *this* source is not "messy but usable" — it is
dangerous, because the errors are invisible and the output looks authoritative. The
hand-authored seed remains the source of truth. LLM extraction becomes viable only with (a) a
*clean digital* copy of the standard, not a scan, **and** (b) human review of every node plus
independently coded, unit-tested checks.

**The upside — this is a demo asset.** The same garbled text strengthens the contrast story:
flat RAG over the real PDF returns corrupted paragraphs; the verified graph returns
`157 < 196 → FAIL, Cl 26.5.1.1`. It also pre-empts the obvious "why not just auto-extract?"
question and justifies the architecture.

> Note: the dumped `is456_text.txt` is gitignored (regenerable). Run
> `scripts/extract_clauses.py` to regenerate the evidence locally.

---

## 11. The Cognee memory layer (LLM Q&A)

§§8–10 establish where the LLM must *not* go — verdicts and unverified extraction. This is where
it legitimately lives: a natural-language Q&A layer grounded in **Cognee** as the memory store.
(Cognee is the hackathon sponsor; this satisfies the "use Cognee as an LLM memory layer"
requirement without touching the deterministic core.)

**Trust boundary (unchanged):** the engine computes verdicts deterministically and *writes the
verified facts* (members, clauses, verdicts, clause paths) into Cognee. The LLM only
**retrieves and explains** what's already in memory — it never computes pass/fail.

```
DETERMINISTIC CORE (source of truth)
  IFC → Members → StructGraph → compliance → verdicts + clause paths
        │  write verified facts as memory
        ▼
COGNEE MEMORY LAYER              [src/structiq/memory.py]
  cognify() → graph + vector memory
        │  grounded retrieval
        ▼
LLM Q&A   [POST /ask, GET /memory/status; frontend AskPanel]
  "Why did B3 fail? What change makes it pass?" → answer grounded in memory
```

One question, three answers — the contrast that makes the point:

| Source | "Does B3 meet minimum tension steel?" |
|---|---|
| Deterministic engine | `FAIL, Cl 26.5.1.1, 157 < 196` (the truth) |
| Flat-RAG baseline | garbled clause text, no verdict |
| Cognee-memory LLM | *"B3 fails minimum tension steel (Cl 26.5.1.1) — 157 mm² vs 196 required; 4-T16 (804 mm²) would comply."* |

### Provider strategy

Embeddings and the LLM are split so failover is safe:

| | Provider | Why |
|---|---|---|
| **Embeddings** | **always local Ollama** (`nomic-embed-text`, 768-dim) | never the bottleneck; fixed so the persisted vector store stays valid no matter which LLM answers |
| **LLM** | **cloud primary → Ollama fallback** | the LLM is the bottleneck and is stateless per call, so it fails over to local `llama3.2:3b` on rate-limit / API error |

The cloud LLM is auto-detected from `.env` (see [.env.example](.env.example)):
- `OPENAI_API_KEY=sk-...` → OpenAI, default `gpt-4o-mini`
- `ANTHROPIC_API_KEY=sk-ant-...` → Anthropic, default `claude-3-5-haiku`
- no key → fully local Ollama (slower)

### Why a cloud LLM at all — the latency finding

A full local run (`llama3.2:3b`) proved the architecture end-to-end and returned the correct
grounded answer, but `cognify` took **~90 minutes** and the 3B repeatedly emitted invalid graph
JSON (auto-retried). The bottleneck is the LLM, not Cognee's storage. A fast cloud model drops
that to ~1–2 min with reliable structured output; the local model stays as the rate-limit
backdoor.

### Setup

Cognee is heavy and trips a Windows 260-char path limit under the Store-Python `site-packages`,
so it lives in a **short-path venv**:

```bash
python -m venv C:/sqenv
C:/sqenv/Scripts/python -m pip install -r requirements.txt transformers
ollama pull llama3.2:3b && ollama pull nomic-embed-text
# optional: add a cloud key to .env (see .env.example), then run the backend on the venv:
PYTHONPATH=src C:/sqenv/Scripts/python -m uvicorn structiq.api:app --port 8000
```

`GET /memory/status` reports readiness and whether a cloud key was detected. Embeddings use
Ollama's `/api/embed`; Cognee's Ollama embedder needs a HF tokenizer for token-counting only
(`HUGGINGFACE_TOKENIZER=bert-base-uncased`). If Cognee/Ollama are absent, `/ask` degrades
gracefully and the deterministic core is unaffected.

**Status:** the memory layer + `/ask` are wired and proven end-to-end locally; cloud + Ollama
fallback routing is implemented. The live cloud run and the frontend AskPanel test are pending
(§13).

---

## 12. Demo script

1. Open the 3D view. Upload `frame_clean.ifc` → **Check against IS 456** → frame is all green.
2. Upload `frame_flawed.ifc` → **Check** → B3 turns red (6 pass, 1 fail).
3. Click **B3** → the inspect panel shows the verdict (`As_prov=157 < As_min=196 mm²`) and the
   clause path: Member B3 → IS 456 Cl 26.5.1.1 → safety factors → Verdict.
4. Open the **Flat-RAG baseline** panel, ask the same question → it returns clause text with no
   verdict bound to B3.
5. Open the **Ask (Cognee-memory LLM)** panel, ask the same question → a grounded
   natural-language answer built from Cognee's memory of the verified model. Three answers on
   one screen — the gap (baseline) vs. the grounding (Cognee) is the pitch.

---

## 13. Roadmap / next steps

**Finish the memory layer (§11):**
- **Live cloud run** — add a key to `.env`, confirm `cognify` + `/ask` are fast (~1–2 min) and
  reliable, and verify the Ollama rate-limit fallback.
- **Wire the frontend AskPanel** against the live `/ask`, with a sane loading/timeout state.
- **Persist + pre-build memory** so `/ask` reuses an existing Cognee store instead of
  re-`cognify`-ing on each model change or backend restart.

**Other:**
- **Wire the PDF into the flat-RAG baseline** (no LLM/key needed) so the contrast panel shows
  real-PDF retrieval vs. the graph verdict.
- **Clause provenance** in the inspect panel (deterministic `pdfplumber` text next to a verdict).
- **A second code** (ACI 318 / Eurocode 2) via the registry (§7): same building, switch the
  code, contrasting verdicts.
- **Reviewed LLM extraction** — only with a clean digital standard + a human in the loop + the
  checks coded and unit-tested separately (§9).

See [CLAUDE.md](CLAUDE.md) for build-order and contributor conventions.
