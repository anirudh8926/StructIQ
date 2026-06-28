import { useEffect, useState } from 'react'
import { getModel, runCheck, uploadIfc, type ModelResponse } from './api'
import Scene from './components/Scene'
import InspectPanel from './components/InspectPanel'
import UploadBar from './components/UploadBar'
import BaselinePanel from './components/BaselinePanel'
import AskPanel from './components/AskPanel'
import './App.css'

export default function App() {
  const [model, setModel] = useState<ModelResponse | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load whatever model the backend has on startup (defaults to frame_flawed.ifc).
  useEffect(() => {
    getModel().then(setModel).catch((e) => setError(String(e)))
  }, [])

  const checked = !!model && model.members.some((m) => m.status === 'PASS' || m.status === 'FAIL')

  async function onUpload(file: File) {
    setBusy(true)
    setError(null)
    setSelected(null)
    try {
      setModel(await uploadIfc(file))
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function onCheck() {
    setBusy(true)
    setError(null)
    try {
      setModel(await runCheck())
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const selectedMember = model?.members.find((m) => m.id === selected) ?? null

  return (
    <div className="app">
      <UploadBar
        source={model?.source ?? null}
        summary={model?.summary ?? null}
        checked={checked}
        busy={busy}
        onUpload={onUpload}
        onCheck={onCheck}
      />
      {error && <div className="error">{error}</div>}
      <main className="layout">
        <div className="viewport">
          {model && (
            <Scene members={model.members} selected={selected} onSelect={setSelected} />
          )}
          <div className="overlays">
            <AskPanel />
            <BaselinePanel />
          </div>
        </div>
        <InspectPanel member={selectedMember} />
      </main>
    </div>
  )
}
