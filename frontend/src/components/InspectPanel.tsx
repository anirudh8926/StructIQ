import type { MemberView, PathStep } from '../api'

const KIND_ICON: Record<PathStep['kind'], string> = {
  Member: '🧱',
  DesignCode: '📐',
  SafetyFactor: '⚖️',
  Verdict: '⚑',
}

function Step({ step, last }: { step: PathStep; last: boolean }) {
  return (
    <li className={`step step-${step.kind.toLowerCase()}`}>
      <span className="step-icon">{KIND_ICON[step.kind]}</span>
      <div className="step-body">
        <div className="step-kind">{step.kind}</div>
        <div className="step-detail">{step.detail}</div>
      </div>
      {!last && <div className="step-connector" />}
    </li>
  )
}

export default function InspectPanel({ member }: { member: MemberView | null }) {
  if (!member) {
    return (
      <aside className="inspect empty">
        <p>Click a member in the 3D model to inspect its compliance and clause path.</p>
      </aside>
    )
  }

  return (
    <aside className="inspect">
      <div className="inspect-head">
        <h2>{member.id}</h2>
        <span className={`badge badge-${member.status.toLowerCase()}`}>{member.status}</span>
      </div>

      <dl className="props">
        <dt>Type</dt><dd>{member.type}</dd>
        <dt>Section</dt><dd>{member.width_mm}×{member.depth_mm} mm</dd>
        <dt>Concrete</dt><dd>{member.concrete ?? '—'}</dd>
        <dt>Rebar</dt><dd>{member.rebar ?? '—'}</dd>
      </dl>

      {member.explanation && <p className="explanation">{member.explanation}</p>}

      {member.clause_path.length > 0 && (
        <>
          <h3>Clause path</h3>
          <ol className="steps">
            {member.clause_path.map((s, i) => (
              <Step key={i} step={s} last={i === member.clause_path.length - 1} />
            ))}
          </ol>
        </>
      )}
    </aside>
  )
}
