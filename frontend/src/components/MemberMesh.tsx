import { useMemo, useState } from 'react'
import * as THREE from 'three'
import type { MemberView, Status } from '../api'

// IFC is Z-up; three.js is Y-up. Map IFC (x, y, z) -> three (x, z, y).
export function toThree(p: [number, number, number]): THREE.Vector3 {
  return new THREE.Vector3(p[0], p[2], p[1])
}

const COLORS: Record<Status, string> = {
  PASS: '#22c55e',
  FAIL: '#ef4444',
  NOT_CHECKED: '#94a3b8',
  UNCHECKED: '#94a3b8',
}

interface Props {
  member: MemberView
  selected: boolean
  onSelect: (id: string) => void
}

export default function MemberMesh({ member, selected, onSelect }: Props) {
  const [hovered, setHovered] = useState(false)

  const geom = useMemo(() => {
    if (!member.start || !member.end) return null
    const start = toThree(member.start)
    const end = toThree(member.end)
    const dir = new THREE.Vector3().subVectors(end, start)
    const length = Math.max(dir.length(), 0.01)
    const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5)
    const quaternion = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(1, 0, 0),
      dir.clone().normalize(),
    )
    const depthM = (member.depth_mm ?? 300) / 1000
    const widthM = (member.width_mm ?? 300) / 1000
    return { mid, quaternion, args: [length, depthM, widthM] as [number, number, number] }
  }, [member])

  if (!geom) return null
  const base = COLORS[member.status] ?? '#94a3b8'

  return (
    <mesh
      position={geom.mid}
      quaternion={geom.quaternion}
      onClick={(e) => {
        e.stopPropagation()
        onSelect(member.id)
      }}
      onPointerOver={(e) => {
        e.stopPropagation()
        setHovered(true)
      }}
      onPointerOut={() => setHovered(false)}
    >
      <boxGeometry args={geom.args} />
      <meshStandardMaterial
        color={base}
        emissive={selected ? base : hovered ? '#334155' : '#000000'}
        emissiveIntensity={selected ? 0.6 : hovered ? 0.4 : 0}
        metalness={0.1}
        roughness={0.6}
      />
    </mesh>
  )
}
