import { useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import * as THREE from 'three'
import type { MemberView } from '../api'
import MemberMesh, { toThree } from './MemberMesh'

interface Props {
  members: MemberView[]
  selected: string | null
  onSelect: (id: string | null) => void
}

export default function Scene({ members, selected, onSelect }: Props) {
  // Centre the model so OrbitControls pivots around it.
  const center = useMemo(() => {
    const pts: THREE.Vector3[] = []
    members.forEach((m) => {
      if (m.start) pts.push(toThree(m.start))
      if (m.end) pts.push(toThree(m.end))
    })
    if (!pts.length) return new THREE.Vector3(0, 1.5, 0)
    const box = new THREE.Box3().setFromPoints(pts)
    return box.getCenter(new THREE.Vector3())
  }, [members])

  return (
    <Canvas
      shadows
      camera={{ position: [center.x + 9, center.y + 7, center.z + 11], fov: 45 }}
      onPointerMissed={() => onSelect(null)}
      style={{ width: '100%', height: '100%' }}
    >
      <color attach="background" args={['#0b1120']} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[10, 15, 8]} intensity={1.1} castShadow />
      <directionalLight position={[-8, 6, -6]} intensity={0.3} />

      <Grid
        position={[center.x, 0, center.z]}
        args={[40, 40]}
        cellSize={1}
        cellColor="#1e293b"
        sectionSize={5}
        sectionColor="#334155"
        fadeDistance={45}
        infiniteGrid
      />

      {members.map((m) => (
        <MemberMesh
          key={m.id}
          member={m}
          selected={selected === m.id}
          onSelect={onSelect}
        />
      ))}

      <OrbitControls target={center} makeDefault />
    </Canvas>
  )
}
