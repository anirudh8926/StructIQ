// Typed client for the StructIQ backend. The shapes here mirror api.py exactly —
// GET /model is the single backend<->frontend contract.

export type Status = 'PASS' | 'FAIL' | 'NOT_CHECKED' | 'UNCHECKED'

export interface PathStep {
  node: string
  kind: 'Member' | 'DesignCode' | 'SafetyFactor' | 'Verdict'
  detail: string
}

export interface CheckResult {
  clause_id: string
  title: string
  passed: boolean
  detail: string
  computed: Record<string, unknown>
}

export interface MemberView {
  id: string
  type: 'beam' | 'column' | string
  start: [number, number, number] | null
  end: [number, number, number] | null
  width_mm: number | null
  depth_mm: number | null
  concrete: string | null
  rebar: string | null
  status: Status
  explanation: string | null
  clause_path: PathStep[]
  checks: CheckResult[]
}

export interface ModelResponse {
  source: string | null
  members: MemberView[]
  summary: { pass: number; fail: number; total: number }
}

export async function getModel(): Promise<ModelResponse> {
  const r = await fetch('/model')
  if (!r.ok) throw new Error(`GET /model ${r.status}`)
  return r.json()
}

export async function uploadIfc(file: File): Promise<ModelResponse> {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch('/upload', { method: 'POST', body: fd })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `upload ${r.status}`)
  return r.json()
}

export async function runCheck(): Promise<ModelResponse> {
  const r = await fetch('/check', { method: 'POST' })
  if (!r.ok) throw new Error(`POST /check ${r.status}`)
  return r.json()
}

export interface BaselineResponse {
  query: string
  mode: string
  hits: string[]
  note: string
}

export async function baseline(q: string): Promise<BaselineResponse> {
  const r = await fetch(`/baseline?q=${encodeURIComponent(q)}`)
  if (!r.ok) throw new Error(`GET /baseline ${r.status}`)
  return r.json()
}

// --- Cognee-memory LLM Q&A ---

export interface AskResponse {
  available: boolean
  status: string
  answer: string | null
  source?: string
  backend?: string
}

export interface MemoryStatus {
  available: boolean
  status: string
  ingested_source: string | null
  backend: string
}

export async function memoryStatus(): Promise<MemoryStatus> {
  const r = await fetch('/memory/status')
  if (!r.ok) throw new Error(`GET /memory/status ${r.status}`)
  return r.json()
}

export async function ask(q: string): Promise<AskResponse> {
  const r = await fetch(`/ask?q=${encodeURIComponent(q)}`, { method: 'POST' })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `ask ${r.status}`)
  return r.json()
}
