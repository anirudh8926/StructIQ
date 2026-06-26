import { useRef } from 'react'
import type { ModelResponse } from '../api'

interface Props {
  source: string | null
  summary: ModelResponse['summary'] | null
  checked: boolean
  busy: boolean
  onUpload: (file: File) => void
  onCheck: () => void
}

export default function UploadBar({ source, summary, checked, busy, onUpload, onCheck }: Props) {
  const fileRef = useRef<HTMLInputElement>(null)

  return (
    <header className="topbar">
      <div className="brand">
        <span className="logo">▢</span>
        <div>
          <strong>StructIQ</strong>
          <small>IS 456 compliance, grounded in a graph</small>
        </div>
      </div>

      <div className="actions">
        <input
          ref={fileRef}
          type="file"
          accept=".ifc"
          style={{ display: 'none' }}
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) onUpload(f)
            e.target.value = ''
          }}
        />
        <button className="btn" disabled={busy} onClick={() => fileRef.current?.click()}>
          Upload IFC
        </button>
        <button className="btn btn-primary" disabled={busy} onClick={onCheck}>
          {busy ? 'Checking…' : 'Check against IS 456'}
        </button>
      </div>

      <div className="status">
        {source && <span className="source">{source}</span>}
        {checked && summary && (
          <span className="counts">
            <span className="pill pill-pass">{summary.pass} pass</span>
            <span className="pill pill-fail">{summary.fail} fail</span>
          </span>
        )}
      </div>
    </header>
  )
}
