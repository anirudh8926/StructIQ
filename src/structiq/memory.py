"""
Cognee memory layer — the LLM's memory for StructIQ.

Cognee is the project's MEMORY LAYER for an LLM. The compliance engine produces the
verified facts deterministically (members, clauses, verdicts, clause paths); we write
those into Cognee's graph + vector memory, and natural-language questions are answered by
an LLM grounded in that memory (Cognee GRAPH_COMPLETION search).

Trust boundary: the LLM NEVER computes a verdict. It retrieves and explains facts the
deterministic engine already decided and stored.

Provider strategy:
  • EMBEDDINGS  -> always local Ollama (nomic-embed-text, 768-dim). Never the bottleneck,
    free, and fixed so the persisted vector store stays valid regardless of the LLM.
  • LLM         -> cloud (your API key) as PRIMARY for speed/reliability, with an
    automatic fallback to local Ollama (llama3.2:3b) on rate-limit / API error.

Drop a key in .env (OPENAI_API_KEY=... or ANTHROPIC_API_KEY=...) and the cloud path turns
on automatically. With no key, it runs fully local (slower). If Cognee/Ollama are missing
entirely, this module degrades gracefully and /ask reports the memory layer is offline —
the deterministic core is unaffected.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Awaitable, Callable, Optional, TypeVar

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_LLM = os.environ.get("STRUCTIQ_OLLAMA_LLM", "llama3.2:3b")
EMBED_MODEL = os.environ.get("STRUCTIQ_EMBED_MODEL", "nomic-embed-text")

_DEFAULT_CLOUD_MODEL = {"openai": "gpt-4o-mini", "anthropic": "claude-3-5-haiku-20241022"}

_STATE: dict = {"ingested_source": None, "llm_mode": None}
_T = TypeVar("_T")


# --- configuration -------------------------------------------------------------------

def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        load_dotenv(os.path.join(root, ".env"))
    except Exception:
        pass


def _cloud_spec() -> Optional[dict]:
    """Resolve the cloud LLM (provider, model, key) from env, or None if no key."""
    _load_dotenv()
    provider = os.environ.get("LLM_PROVIDER", "").lower() or None
    key = os.environ.get("LLM_API_KEY") or ""
    if provider in (None, "ollama"):
        if os.environ.get("OPENAI_API_KEY"):
            provider, key = "openai", os.environ["OPENAI_API_KEY"]
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider, key = "anthropic", os.environ["ANTHROPIC_API_KEY"]
        else:
            return None
    if not key or key == "ollama":
        return None
    model = os.environ.get("LLM_MODEL") or _DEFAULT_CLOUD_MODEL.get(provider, "gpt-4o-mini")
    return {"provider": provider, "model": model, "key": key}


def _configure_common() -> None:
    """Embeddings (always local Ollama) + Cognee storage dirs. Idempotent."""
    os.environ["EMBEDDING_PROVIDER"] = "ollama"
    os.environ["EMBEDDING_MODEL"] = EMBED_MODEL
    os.environ["EMBEDDING_ENDPOINT"] = f"{OLLAMA_BASE}/api/embed"
    os.environ["EMBEDDING_DIMENSIONS"] = "768"
    os.environ["EMBEDDING_MAX_TOKENS"] = "512"
    # HF tokenizer is used only to COUNT tokens, not to embed (embeddings come from Ollama).
    os.environ.setdefault("HUGGINGFACE_TOKENIZER", "bert-base-uncased")
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    os.environ.setdefault("COGNEE_SYSTEM_DIRECTORY", os.path.join(root, ".cognee_system"))
    os.environ.setdefault("DATA_ROOT_DIRECTORY", os.path.join(root, "cognee_data"))


def _bust_llm_cache() -> None:
    """Force Cognee to re-read LLM config after we change provider env vars."""
    try:
        from cognee.infrastructure.llm.config import get_llm_config
        get_llm_config.cache_clear()
    except Exception:
        pass


def _apply_llm(mode: str) -> None:
    """Point Cognee's LLM at 'cloud' or 'ollama'. Embeddings are untouched (always Ollama)."""
    if mode == "cloud":
        spec = _cloud_spec()
        if not spec:
            return _apply_llm("ollama")
        os.environ["LLM_PROVIDER"] = spec["provider"]
        os.environ["LLM_MODEL"] = spec["model"]
        os.environ["LLM_API_KEY"] = spec["key"]
        os.environ.pop("LLM_ENDPOINT", None)  # let the provider use its default endpoint
    else:
        os.environ["LLM_PROVIDER"] = "ollama"
        os.environ["LLM_MODEL"] = OLLAMA_LLM
        os.environ["LLM_ENDPOINT"] = f"{OLLAMA_BASE}/v1"
        os.environ["LLM_API_KEY"] = "ollama"
    _STATE["llm_mode"] = mode
    _bust_llm_cache()


def _is_transient(exc: Exception) -> bool:
    """Rate-limit / quota / connectivity errors that warrant the Ollama fallback."""
    s = f"{type(exc).__name__} {exc}".lower()
    return any(k in s for k in (
        "rate", "429", "quota", "overloaded", "timeout", "timed out",
        "connection", "503", "502", "unavailable", "insufficient_quota",
    ))


# --- availability --------------------------------------------------------------------

def _ollama_models() -> Optional[list[str]]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=2) as r:
            return [m.get("name", "") for m in json.load(r).get("models", [])]
    except Exception:
        return None


def available() -> tuple[bool, str]:
    """Usable if cognee imports AND Ollama is up with the embedding model (always needed)."""
    try:
        import cognee  # noqa: F401
    except Exception as exc:
        return False, f"cognee not installed ({exc.__class__.__name__})"
    names = _ollama_models()
    if names is None:
        return False, f"ollama not reachable at {OLLAMA_BASE} (needed for embeddings)"
    if not any(EMBED_MODEL.split(":")[0] in n for n in names):
        return False, f"ollama missing embedding model '{EMBED_MODEL}'"
    cloud = _cloud_spec()
    has_local_llm = any(OLLAMA_LLM.split(":")[0] in n for n in names)
    if not cloud and not has_local_llm:
        return False, f"no cloud key and ollama missing '{OLLAMA_LLM}'"
    where = f"cloud:{cloud['provider']}/{cloud['model']}" if cloud else f"ollama/{OLLAMA_LLM}"
    return True, f"ready (LLM primary: {where}; embeddings: ollama/{EMBED_MODEL})"


# --- documents -----------------------------------------------------------------------

def _member_doc(m: dict) -> str:
    checks = "; ".join(
        f"{c['code_name']} {c['clause_id']} ({'pass' if c['passed'] else 'FAIL'}): {c['detail']}"
        for c in m.get("checks", [])
    )
    path = " -> ".join(s["detail"] for s in m.get("clause_path", []))
    return (
        f"{str(m['type']).capitalize()} {m['id']} is a structural member: section "
        f"{m.get('width_mm')}x{m.get('depth_mm')} mm, concrete {m.get('concrete')}, "
        f"reinforcement {m.get('rebar')}. Compliance status: {m.get('status')}. "
        f"{m.get('explanation') or ''} Checks: {checks or 'none'}. Clause path: {path}."
    )


def _build_documents(model_payload: dict) -> list[str]:
    from . import standards
    docs = [_member_doc(m) for m in model_payload.get("members", [])]
    for code, c in standards.all_clauses():
        docs.append(f"{code} clause {c.clause_id}: {c.title}. "
                    f"Applicability: {c.applicability}. Formula: {c.formula}.")
    s = model_payload.get("summary", {})
    docs.append(f"Model '{model_payload.get('source')}': {s.get('pass')} members pass, "
                f"{s.get('fail')} fail, of {s.get('total')} total.")
    return docs


# --- cloud-primary, ollama-fallback runner -------------------------------------------

async def _run_with_fallback(make_coro: Callable[[], Awaitable[_T]]) -> _T:
    """Run a Cognee op on the cloud LLM; on a transient/API error, retry on Ollama."""
    primary = "cloud" if _cloud_spec() else "ollama"
    _apply_llm(primary)
    try:
        return await make_coro()
    except Exception as exc:
        if primary == "cloud" and _is_transient(exc):
            _apply_llm("ollama")  # the backdoor
            return await make_coro()
        raise


# --- ingest + ask --------------------------------------------------------------------

async def ingest_async(model_payload: dict) -> None:
    _configure_common()
    import cognee

    async def _do():
        try:
            await cognee.prune.prune_data()
            await cognee.prune.prune_system(metadata=True)
        except Exception:
            pass
        await cognee.add("\n\n".join(_build_documents(model_payload)))
        await cognee.cognify()

    await _run_with_fallback(_do)
    _STATE["ingested_source"] = model_payload.get("source")


async def ask_async(question: str, model_payload: Optional[dict] = None) -> dict:
    ok, msg = available()
    if not ok:
        return {"available": False, "status": msg, "answer": None}

    _configure_common()
    import cognee
    from cognee import SearchType

    if model_payload is not None and _STATE["ingested_source"] != model_payload.get("source"):
        await ingest_async(model_payload)

    async def _do():
        try:
            return await cognee.search(query_type=SearchType.GRAPH_COMPLETION, query_text=question)
        except TypeError:  # older positional signature
            return await cognee.search(question, SearchType.GRAPH_COMPLETION)

    results = await _run_with_fallback(_do)
    answer = results[0] if isinstance(results, list) and results else results
    # cognee may wrap results in dicts; pull out the text best-effort
    if isinstance(answer, dict):
        answer = answer.get("search_result") or answer.get("answer") or answer
    return {"available": True, "status": "ok", "answer": str(answer),
            "source": _STATE["ingested_source"], "llm_mode": _STATE["llm_mode"]}


def status() -> dict:
    ok, msg = available()
    cloud = _cloud_spec()
    return {"available": ok, "status": msg, "ingested_source": _STATE["ingested_source"],
            "cloud_configured": bool(cloud), "llm_mode": _STATE["llm_mode"]}
