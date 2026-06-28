import { useEffect, useState } from 'react'
import { ask, memoryStatus, type AskResponse, type MemoryStatus } from '../api'

// The Cognee-memory LLM panel. Same question class as the flat-RAG baseline, but answered
// by an LLM grounded in Cognee's graph memory of the VERIFIED model — the smart contrast.
export default function AskPanel() {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<MemoryStatus | null>(null)
  const [q, setQ] = useState('Why did B3 fail, and what change would make it pass?')
  const [res, setRes] = useState<AskResponse | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (open && !status) memoryStatus().then(setStatus).catch(() => setStatus(null))
  }, [open, status])

  async function run() {
    setBusy(true)
    setRes(null)
    try {
      setRes(await ask(q))
    } catch (e) {
      setRes({ available: false, status: String(e), answer: null })
    } finally {
      setBusy(false)
    }
  }

  const offline = status && !status.available

  return (
    <section className={`ask ${open ? 'open' : ''}`}>
      <button className="ask-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? '▾' : '▸'} Ask (Cognee-memory LLM)
        {status && (
          <span className={`ask-dot ${status.available ? 'on' : 'off'}`} title={status.status} />
        )}
      </button>
      {open && (
        <div className="ask-body">
          {offline && (
            <div className="ask-offline">
              Memory layer offline: {status?.status}. The deterministic verdict still works;
              this panel needs Cognee + Ollama.
            </div>
          )}
          <div className="ask-row">
            <input value={q} onChange={(e) => setQ(e.target.value)}
                   placeholder="Ask about the model…" />
            <button className="btn btn-primary" disabled={busy} onClick={run}>
              {busy ? 'Thinking…' : 'Ask'}
            </button>
          </div>
          {res && (
            <div className="ask-out">
              {res.answer ? (
                <>
                  <p className="ask-answer">{res.answer}</p>
                  <div className="ask-meta">
                    grounded in Cognee memory · {res.backend} · {res.source}
                  </div>
                </>
              ) : (
                <div className="ask-offline">{res.status}</div>
              )}
            </div>
          )}
          <p className="ask-note">
            The LLM only retrieves and explains the engine's verdicts from Cognee — it never
            computes pass/fail.
          </p>
        </div>
      )}
    </section>
  )
}
