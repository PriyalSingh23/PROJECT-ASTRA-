import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Html, Line } from '@react-three/drei'
import * as THREE from 'three'
import { api } from '../../services/api'
import { Endpoint, Message, QueueStats, RelayNode } from '../../types'
import { TopologyModel, buildTopologyModel } from './model'
import { TopologyFallback } from './TopologyFallback'
import { ErrorBoundary } from '../ErrorBoundary'
import { MessageDrawer, DrawerStation } from '../MessageDrawer'
import { AnomalyStrip } from '../research/AnomalyStrip'
import { useAnomalyReport } from '../research/useAnomalyReport'

const ALPHA_POS: [number, number, number] = [-6, 0, 0]
const BRAVO_POS: [number, number, number] = [6, 0, 0]

interface LinkTopologyViewProps {
  endpoints: Endpoint[]
  messages: Message[]
  queueStats: QueueStats | null
  isBackendHealthy: boolean
}

// ---------------------------------------------------------------------------
// 3D primitives
// ---------------------------------------------------------------------------
const Station: React.FC<{
  position: [number, number, number]
  label: string
  sub: string
  color: string
  onSelect?: () => void
}> = ({ position, label, sub, color, onSelect }) => {
  const ref = useRef<THREE.Mesh>(null)
  useFrame(({ clock }) => {
    if (ref.current) {
      ref.current.scale.setScalar(1 + Math.sin(clock.elapsedTime * 2) * 0.045)
    }
  })
  return (
    <group position={position}>
      <mesh
        ref={ref}
        onClick={
          onSelect
            ? (e) => {
                e.stopPropagation()
                onSelect()
              }
            : undefined
        }
        onPointerOver={onSelect ? () => { document.body.style.cursor = 'pointer' } : undefined}
        onPointerOut={onSelect ? () => { document.body.style.cursor = 'auto' } : undefined}
      >
        <sphereGeometry args={[0.62, 32, 32]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.7} roughness={0.25} metalness={0.5} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.95, 1.12, 48]} />
        <meshBasicMaterial color={color} transparent opacity={0.55} side={THREE.DoubleSide} />
      </mesh>
      <Html center distanceFactor={14} position={[0, 1.5, 0]} pointerEvents="none">
        <div className="px-2 py-1 rounded border border-zinc-700 bg-zinc-950/85 text-center whitespace-nowrap">
          <div className="text-[11px] font-mono font-bold text-zinc-100 tracking-wide">{label}</div>
          <div className="text-[10px] font-mono text-zinc-400">{sub}</div>
        </div>
      </Html>
    </group>
  )
}

const RelayMarker: React.FC<{
  position: [number, number, number]
  label: string
  battery: number
  online: boolean
  failsafeCutoff?: boolean
}> = ({ position, label, battery, online, failsafeCutoff = false }) => {
  const ref = useRef<THREE.Mesh>(null)
  useFrame(({ clock }) => {
    if (ref.current) ref.current.rotation.y = clock.elapsedTime * 0.6
  })
  const color = failsafeCutoff ? '#f87171' : online ? '#34d399' : '#71717a'
  return (
    <group position={position}>
      <mesh ref={ref}>
        <octahedronGeometry args={[0.34, 0]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={failsafeCutoff ? 0.8 : 0.45}
          roughness={0.4}
        />
      </mesh>
      <Html center distanceFactor={16} position={[0, 0.78, 0]} pointerEvents="none">
        <div className="px-1.5 py-0.5 rounded bg-zinc-950/80 border border-zinc-700 text-center whitespace-nowrap">
          <div className="text-[9px] font-mono text-zinc-300">{label.slice(0, 16)}</div>
          {failsafeCutoff ? (
            <div className="text-[9px] font-mono text-rose-400 font-bold">[CUTOFF] {battery}%</div>
          ) : (
            <div className="text-[9px] font-mono text-zinc-500">{battery}%</div>
          )}
        </div>
      </Html>
    </group>
  )
}

const Packets: React.FC<{ count: number; color: string; points: [number, number, number][] }> = ({
  count,
  color,
  points,
}) => {
  const refs = useRef<(THREE.Mesh | null)[]>([])
  const curve = useMemo(
    () => new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p))),
    [points],
  )
  useFrame(({ clock }) => {
    const n = Math.max(count, 1)
    refs.current.forEach((m, i) => {
      if (!m) return
      const t = (clock.elapsedTime * 0.28 + i / n) % 1
      const p = curve.getPointAt(t)
      m.position.set(p.x, p.y, p.z)
      m.visible = i < count
    })
  })
  return (
    <>
      {Array.from({ length: Math.max(count, 1) }).map((_, i) => (
        <mesh
          key={i}
          ref={(el) => {
            refs.current[i] = el
          }}
        >
          <sphereGeometry args={[0.13, 12, 12]} />
          <meshBasicMaterial color={color} />
        </mesh>
      ))}
    </>
  )
}

const RadarSweep: React.FC<{ position: [number, number, number]; color: string }> = ({ position, color }) => {
  const ref = useRef<THREE.Mesh>(null)
  useFrame((_, dt) => {
    if (ref.current) ref.current.rotation.z += dt * 1.4
  })
  return (
    <group position={position} rotation={[-Math.PI / 2, 0, 0]}>
      <mesh>
        <ringGeometry args={[3.4, 3.5, 64]} />
        <meshBasicMaterial color={color} transparent opacity={0.35} side={THREE.DoubleSide} />
      </mesh>
      <mesh ref={ref}>
        <circleGeometry args={[3.4, 48, 0, Math.PI / 4]} />
        <meshBasicMaterial color={color} transparent opacity={0.12} side={THREE.DoubleSide} />
      </mesh>
    </group>
  )
}

const Scene: React.FC<{ model: TopologyModel; onSelectStation?: (station: DrawerStation) => void }> = ({
  model,
  onSelectStation,
}) => {
  const { alpha, bravo, relays, link } = model
  const color = link.color

  const linkPoints = useMemo<[number, number, number][]>(() => {
    const mid = relays.map((r) => r.position)
    return [ALPHA_POS, ...mid, BRAVO_POS]
  }, [relays])

  const packetCount = link.online ? Math.min(Math.max(link.pending, 1), 8) : 0

  return (
    <>
      <ambientLight intensity={0.45} />
      <directionalLight position={[6, 12, 8]} intensity={1.1} />
      <pointLight position={ALPHA_POS} intensity={18} distance={14} color={color} />
      <pointLight position={BRAVO_POS} intensity={18} distance={14} color={color} />

      <gridHelper args={[44, 44, '#1f2937', '#18181b']} position={[0, -2.4, 0]} />

      <RadarSweep position={[ALPHA_POS[0], -2.35, ALPHA_POS[2]]} color={color} />

      <Line
        points={linkPoints}
        color={color}
        lineWidth={link.queued > 0 ? 3.5 : 2}
        dashed={!link.online}
        dashSize={0.4}
        gapSize={0.3}
      />

      <Station
        position={ALPHA_POS}
        label={alpha.label}
        sub={`OUTBOX ${alpha.queued}`}
        color={color}
        onSelect={onSelectStation ? () => onSelectStation({ id: alpha.id, label: alpha.label }) : undefined}
      />
      <Station
        position={BRAVO_POS}
        label={bravo.label}
        sub={`DELIVERED ${bravo.queued}`}
        color={color}
        onSelect={onSelectStation ? () => onSelectStation({ id: bravo.id, label: bravo.label }) : undefined}
      />

      {relays.map((r) => (
        <RelayMarker
          key={r.id}
          position={r.position}
          label={r.label}
          battery={r.battery}
          online={r.online}
          failsafeCutoff={r.failsafeCutoff}
        />
      ))}

      {packetCount > 0 && <Packets count={packetCount} color={color} points={linkPoints} />}

      <OrbitControls
        enablePan={false}
        autoRotate
        autoRotateSpeed={0.4}
        minDistance={9}
        maxDistance={30}
        maxPolarAngle={Math.PI / 2.05}
      />
    </>
  )
}

// ---------------------------------------------------------------------------
// Panel chrome + data wiring
// ---------------------------------------------------------------------------
const LegendDot: React.FC<{ color: string; label: string }> = ({ color, label }) => (
  <span className="inline-flex items-center space-x-1.5">
    <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: color }} />
    <span className="text-zinc-400">{label}</span>
  </span>
)

export const LinkTopologyView: React.FC<LinkTopologyViewProps> = ({
  endpoints,
  messages,
  queueStats,
  isBackendHealthy,
}) => {
  const [relays, setRelays] = useState<RelayNode[]>([])
  const [activeTransport, setActiveTransport] = useState<{
    active_transport: string | null
    is_live: boolean
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [drawerStation, setDrawerStation] = useState<DrawerStation | null>(null)
  const { report: anomalyReport, loading: anomalyLoading, error: anomalyError, refresh: refreshAnomalies } = useAnomalyReport(30000)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [r, a] = await Promise.all([api.getRelays(), api.getActiveTransport()])
        if (cancelled) return
        setRelays(r)
        setActiveTransport({ active_transport: a.active_transport, is_live: a.is_live })
      } catch {
        /* backend offline — keep last known state */
      }
    }
    load()
    const interval = setInterval(load, 5000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  const model = useMemo(
    () => buildTopologyModel({ endpoints, queueStats, messages, relays, activeTransport }),
    [endpoints, queueStats, messages, relays, activeTransport],
  )

  const toggleLive = async () => {
    setBusy(true)
    setNotice(null)
    try {
      const next = activeTransport?.is_live ? null : 'motorola-mototrbo-01'
      const res = await api.setActiveTransport(next)
      setActiveTransport({ active_transport: res.active_transport, is_live: res.is_live })
      setNotice(
        next
          ? `Outbound path set to ${next}. Hardware transmits only when MOTOROLA_RADIO_APPROVED=true (dry-run otherwise).`
          : 'Outbound path returned to the simulated link.',
      )
    } catch (e) {
      setNotice(`Could not change outbound path: ${String(e)}`)
    } finally {
      setBusy(false)
    }
  }

  const linkColor = model.link.color

  return (
    <div className="space-y-3">
      {/* Header + live dispatch control */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-mono font-bold text-zinc-100 tracking-wide">3D LINK TOPOLOGY</h2>
            <p className="text-[11px] text-zinc-400 mt-0.5">
              Live operational picture — stations, relays, and the outbound path.
            </p>
          </div>
          <div className="flex items-center space-x-3 text-[11px] font-mono">
            <LegendDot color="#34d399" label="Online" />
            <LegendDot color="#fbbf24" label="Retrying" />
            <LegendDot color="#f87171" label="Down" />
            <span className="text-zinc-600">|</span>
            <span className={model.link.online ? 'text-emerald-400' : 'text-red-400'}>{model.link.label}</span>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800 pt-3">
          <div className="text-[11px] font-mono text-zinc-400">
            Outbound path:{' '}
            <span className={activeTransport?.is_live ? 'text-amber-400 font-bold' : 'text-emerald-400 font-bold'}>
              {activeTransport?.is_live ? activeTransport.active_transport : 'SIMULATION'}
            </span>
            <span className="mx-2 text-zinc-700">·</span>
            Queued <span className="text-zinc-200">{model.link.queued}</span>
            <span className="mx-2 text-zinc-700">·</span>
            Delivered <span className="text-zinc-200">{model.link.delivered}</span>
            <span className="mx-2 text-zinc-700">·</span>
            In flight <span className="text-zinc-200">{model.link.pending}</span>
          </div>
          <button
            onClick={toggleLive}
            disabled={busy || !isBackendHealthy}
            className={`px-3 py-1.5 rounded-md text-[11px] font-mono font-bold transition-colors disabled:opacity-40 ${
              activeTransport?.is_live
                ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/40'
                : 'bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 border border-emerald-500/40'
            }`}
          >
            {busy ? 'SWITCHING…' : activeTransport?.is_live ? 'RETURN TO SIMULATION' : 'GO LIVE (MOTOROLA)'}
          </button>
        </div>
        {notice && <div className="mt-2 text-[11px] font-mono text-amber-400">{notice}</div>}
      </div>

      {/* 3D canvas (lazy chunk) with 2D degradation */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden">
        <ErrorBoundary fallback={<div className="p-4"><TopologyFallback model={model} onSelectStation={setDrawerStation} /></div>}>
          <Canvas
            dpr={[1, 2]}
            camera={{ position: [0, 8, 18], fov: 45 }}
            style={{ height: '460px', background: 'radial-gradient(circle at 50% 40%, #0b1120 0%, #09090b 70%)' }}
          >
            <Scene model={model} onSelectStation={setDrawerStation} />
          </Canvas>
          <div className="flex items-center justify-between px-4 py-2 border-t border-zinc-800 text-[10px] font-mono text-zinc-500">
            <span>Drag to orbit · scroll to zoom · click a station to inspect its traffic</span>
            <span className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ backgroundColor: linkColor }} />
              <span>link {model.link.online ? 'nominal' : 'down'}</span>
            </span>
          </div>
        </ErrorBoundary>
      </div>

      {/* Live integrity battery — the same honest strip the Research Lab shows */}
      <AnomalyStrip
        report={anomalyReport}
        loading={anomalyLoading}
        error={anomalyError}
        onRefresh={refreshAnomalies}
        compact
      />

      <MessageDrawer
        station={drawerStation}
        endpoints={endpoints}
        onClose={() => setDrawerStation(null)}
      />
    </div>
  )
}

export default LinkTopologyView
