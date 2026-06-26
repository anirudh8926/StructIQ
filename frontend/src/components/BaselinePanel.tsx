import { useState } from 'react'
import { baseline, type BaselineResponse } from '../api'

// The contrast panel: ask the same question of flat-RAG. It returns clause text but no
// verdict bound to the member — the whole point of the side-by-side.
export default function BaselinePanel() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('Does beam B3 meet minimum tension reinforcement?')
  const [res, setRes] = useState<BaselineResponse | null>(null)
  const [busy, setBusy] = useState(false)

  async function ask() {
    setBusy(true)
    try {
      setRes(await baseline(q))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={`baseline ${open ? 'open' : ''}`}>
      <button className="baseline-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? '▾' : '▸'} Flat-RAG baseline (contrast)
      </button>
      {open && (
        <div className="baseline-body">
          <div className="baseline-row">
            <input value={q} onChange={(e) => setQ(e.target.value)} />
            <button className="btn" disabled={busy} onClick={ask}>
              {busy ? '…' : 'Ask'}
            </button>
          </div>
          {res && (
            <div className="baseline-out">
              <div className="baseline-mode">mode: {res.mode}</div>
              <ul>
                {res.hits.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </ul>
              <p className="baseline-note">{res.note}</p>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
